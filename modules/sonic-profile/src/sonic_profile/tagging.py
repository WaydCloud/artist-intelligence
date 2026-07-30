"""장르 · 악기 태깅 (RULES §3.1.6) — Essentia 모델을 ONNX로 직접 구동.

사슬:
    오디오 → power-mel(128프레임 × 96밴드) → discogs-effnet
                                              ├─ styles[400]      Discogs 스타일
                                              └─ embeddings[1280] ─┬─ instruments[40]
                                                                   └─ genres[87]

**전처리가 전부다**(RULES §3.3). Essentia `TensorflowInputMusiCNN`과 한 파라미터라도
어긋나면 조용히 쓰레기가 나온다 — 실측에서 mel을 magnitude로 두자 전 곡이
`Electronic---Techno`로 뭉개졌고, power로 고치자 K-pop 중앙순위가 150위→1위가 됐다.
회귀 검증은 TESTS §4(K-pop 상위5 진입률)로 한다.

TensorFlow도 Essentia도 쓰지 않는다(둘 다 Windows/py3.14에서 설치 불가).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from sonic_profile.models import DEFAULT_DIR

# Essentia TensorflowInputMusiCNN 사양 — 바꾸면 과거 값과 비교 불가(RULES §3.3)
TAG_SR = 16000
N_FFT, HOP, N_MELS, PATCH = 512, 256, 96, 128
# msd-musicnn(valence·arousal 전용)은 **같은 mel에 패치만 187**이다. 이 하나가 다르고
# 나머지 사양은 전부 공유하므로 mel 계산을 복제하지 않는다(§3.3 지뢰를 두 벌 만들지 않기).
PATCH_MSD = 187
# valence·arousal 헤드. **값의 뜻이 여기 달려 있으므로 provenance·캐시 키에 들어간다.**
# `muse`는 실측에서 퇴화해 배제했다(`_valence_arousal` 도크스트링 · TESTS §6.4).
VA_HEAD = "deam-msd-musicnn-1"
# 저장할 라벨 수. **임계로 곡 수를 세는 축은 잘라 두면 그 수가 하한이 된다** —
# 악기는 임계(A&R 소유, RULES §3.1.6) 기준으로 집계하므로 40클래스 전부를 남긴다.
# 스타일(400)·장르(87)는 상위 k 표시용이라 5로 둔다(RULES §5: 1위를 확정하지 않는다).
TOP_K = 5
TOP_K_INSTRUMENT = 40

_SESSIONS: dict[str, Any] = {}
_LABELS: dict[str, list[str]] = {}


class TaggerUnavailable(RuntimeError):
    """모델·런타임이 없어 태깅을 못 하는 상태 — 지표 자체는 계속 낸다."""


def _musicnn_frames(y16: np.ndarray) -> np.ndarray:
    """16kHz 모노 → (frames, 96) mel. Essentia `TensorflowInputMusiCNN` 사양 그대로.

    `type=power`가 핵심이다 — Essentia MelBands의 기본값이며 소스에 명시되지 않는다.
    **프레임 계산은 여기 한 곳에만 둔다**: 패치로 자르는 길이만 모델마다 다르고(128 vs
    187) 나머지 사양이 같으므로, 복제하면 §3.3 지뢰가 두 벌이 된다.
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    S = np.abs(librosa.stft(y16, n_fft=N_FFT, hop_length=HOP, window="hann", center=False)) ** 2
    fb = librosa.filters.mel(sr=TAG_SR, n_fft=N_FFT, n_mels=N_MELS, fmin=0.0, fmax=TAG_SR / 2,
                             htk=False, norm="slaney")
    return np.log10(1.0 + 10000.0 * (fb @ S)).T          # (frames, 96)


def musicnn_mel(y16: np.ndarray, patch: int = PATCH) -> np.ndarray:
    """16kHz 모노 → (패치 수, `patch`, 96). 겹침 없음, 곡 단위는 호출부에서 패치 평균."""
    mel = _musicnn_frames(y16)
    n = (len(mel) // patch) * patch
    if n == 0:
        raise TaggerUnavailable(f"too short for one patch ({len(mel)} < {patch} frames)")
    return mel[:n].reshape(-1, patch, N_MELS).astype(np.float32)


def _load(directory: Path) -> None:
    if _SESSIONS:
        return
    try:
        import onnxruntime as ort  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)
    except ImportError as exc:
        raise TaggerUnavailable("onnxruntime not installed") from exc
    spec = {
        "effnet": "discogs-effnet-bsdynamic-1",
        "instrument": "mtg_jamendo_instrument-discogs-effnet-1",
        "genre": "mtg_jamendo_genre-discogs-effnet-1",
        # C층 (D-031). 앞 둘은 effnet 임베딩 편승, 뒤 둘은 msd-musicnn 체인.
        "moodtheme": "mtg_jamendo_moodtheme-discogs-effnet-1",
        "danceability": "danceability-discogs-effnet-1",
        "msd": "msd-musicnn-1",
        "va": "deam-msd-musicnn-1",
    }
    for key, stem in spec.items():
        onnx, meta = directory / f"{stem}.onnx", directory / f"{stem}.json"
        if not onnx.exists() or not meta.exists():
            _SESSIONS.clear()
            raise TaggerUnavailable(f"model file missing: {onnx.name}")
        _SESSIONS[key] = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
        _LABELS[key] = list(json.loads(meta.read_text(encoding="utf-8"))["classes"])


def _top(labels: list[str], probs: np.ndarray, k: int = TOP_K) -> list[dict[str, Any]]:
    """상위 k + 확률. **1위를 그 곡의 장르로 확정하지 않는다**(RULES §5)."""
    return [{"label": labels[int(i)], "p": round(float(probs[int(i)]), 4)}
            for i in np.argsort(-probs)[:k]]


def extract_tags(y: np.ndarray, sr: int, *, directory: Path | None = None) -> dict[str, Any]:
    """오디오 배열 → 스타일·악기·장르 상위 k. 실패는 TaggerUnavailable로 올린다."""
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    _load(directory or DEFAULT_DIR)
    y16 = librosa.resample(np.asarray(y, dtype=np.float32), orig_sr=sr, target_sr=TAG_SR) \
        if sr != TAG_SR else np.asarray(y, dtype=np.float32)
    patches = musicnn_mel(y16)

    # 곡 단위 값 = 패치 평균 (30초 전체를 본다 — 10초 천장이 없는 것이 이 경로의 이점)
    styles, emb = _SESSIONS["effnet"].run(["activations", "embeddings"],
                                          {"melspectrogram": patches})
    inst = _SESSIONS["instrument"].run(["activations"], {"embeddings": emb})[0]
    genre = _SESSIONS["genre"].run(["activations"], {"embeddings": emb})[0]

    # ── C층: 구성물 지표(RULES §3.1.6.2) ─────────────────────────────────────
    # **effnet을 다시 돌리지 않는다** — 위에서 이미 얻은 `emb`를 재사용한다.
    mood = _SESSIONS["moodtheme"].run(["activations"], {"embeddings": emb})[0]
    dance = _SESSIONS["danceability"].run(["activations"], {"embeddings": emb})[0].mean(0)
    dance_labels = _LABELS["danceability"]
    dance_p = float(dance[dance_labels.index("danceable")]) if "danceable" in dance_labels else None

    out: dict[str, Any] = {
        "styles": _top(_LABELS["effnet"], styles.mean(0)),
        "instruments": _top(_LABELS["instrument"], inst.mean(0), k=TOP_K_INSTRUMENT),
        "genres": _top(_LABELS["genre"], genre.mean(0)),
        "moods": _top(_LABELS["moodtheme"], mood.mean(0)),
        # `danceable` 클래스의 확률. **춤 실력·안무 품질의 판정이 아니다**(RULES §5) —
        # 그 클래스의 뜻은 학습 데이터가 정하며 K-pop으로 만들어지지 않았다.
        "danceability": None if dance_p is None else round(dance_p, 4),
        "tag_patches": len(patches),
        # RULES §3.1.7 — 정확도를 아직 사람 라벨로 재지 않았다. 표면에 그대로 전파된다.
        "tag_status": "unvalidated",
    }
    out.update(_valence_arousal(y16))
    return out


def _valence_arousal(y16: np.ndarray) -> dict[str, Any]:
    """msd-musicnn(200차원) → **deam** 회귀 2값. 척도는 데이터셋 정의라 정규화하지 않는다.

    effnet 편승이 안 되는 유일한 축이다 — 이 헤드는 다른 임베딩 위에 있다. 다만 mel
    사양이 같아 패치 길이만 187로 바꿔 자른다(§3.3 지뢰를 새로 밟지 않는 이유).
    실패는 나머지 태그를 죽이지 않는다.

    **왜 muse가 아닌가**(2026-07-29 실측, TESTS §6.4): 표본이 가장 큰 `muse`(약 9만
    트랙)를 먼저 골랐으나 **퇴화해 있었다** — 말러 "비극적" 5.249 · Happy 5.469 ·
    스크릴렉스 5.299로 순서도 폭(0.22)도 없었다. 같은 코드 경로에서 `deam`은
    4.385 / 5.418 / 6.190으로 순서가 맞는다. 헤드가 **선형 단층**이라(패치별 평균과
    임베딩 평균의 결과가 정확히 일치함을 확인) 배선 문제가 아님도 함께 확정됐다.
    """
    try:
        patches = musicnn_mel(y16, patch=PATCH_MSD)
        emb200 = _SESSIONS["msd"].run(["embeddings"], {"melspectrogram": patches})[0]
        # 입력은 (N, 1, 200) — 차원이 하나 더 있다. 그냥 먹이면 실패한다.
        va = _SESSIONS["va"].run(
            ["activations"], {"embeddings": emb200.reshape(-1, 1, 200)}
        )[0].mean(0)
    except Exception as exc:  # noqa: BLE001 — valence 실패가 다른 태그를 죽이지 않는다
        return {"valence_unresolved": f"{type(exc).__name__}: {exc}"[:120]}
    labels = _LABELS["va"]
    return {
        "valence": round(float(va[labels.index("valence")]), 4),
        "arousal": round(float(va[labels.index("arousal")]), 4),
        # 어느 주석 기준의 값인지가 **정의의 일부**다(RULES §3.1.7 B).
        "va_source": VA_HEAD,
    }


def style_probability(y: np.ndarray, sr: int, label: str, *, directory: Path | None = None) -> tuple[int, float]:
    """특정 스타일의 (순위, 확률) — 전처리 회귀 검증용(TESTS §4)."""
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    _load(directory or DEFAULT_DIR)
    y16 = librosa.resample(np.asarray(y, dtype=np.float32), orig_sr=sr, target_sr=TAG_SR) \
        if sr != TAG_SR else np.asarray(y, dtype=np.float32)
    styles = _SESSIONS["effnet"].run(["activations"], {"melspectrogram": musicnn_mel(y16)})[0].mean(0)
    idx = _LABELS["effnet"].index(label)
    return int(np.where(np.argsort(-styles) == idx)[0][0]) + 1, float(styles[idx])
