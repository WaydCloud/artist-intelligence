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
# 저장할 라벨 수. **임계로 곡 수를 세는 축은 잘라 두면 그 수가 하한이 된다** —
# 악기는 임계(A&R 소유, RULES §3.1.6) 기준으로 집계하므로 40클래스 전부를 남긴다.
# 스타일(400)·장르(87)는 상위 k 표시용이라 5로 둔다(RULES §5: 1위를 확정하지 않는다).
TOP_K = 5
TOP_K_INSTRUMENT = 40

_SESSIONS: dict[str, Any] = {}
_LABELS: dict[str, list[str]] = {}


class TaggerUnavailable(RuntimeError):
    """모델·런타임이 없어 태깅을 못 하는 상태 — 지표 자체는 계속 낸다."""


def musicnn_mel(y16: np.ndarray) -> np.ndarray:
    """16kHz 모노 → (패치, 128, 96). Essentia 사양 그대로(RULES §3.3).

    `type=power`가 핵심이다 — Essentia MelBands의 기본값이며 소스에 명시되지 않는다.
    """
    import librosa

    S = np.abs(librosa.stft(y16, n_fft=N_FFT, hop_length=HOP, window="hann", center=False)) ** 2
    fb = librosa.filters.mel(sr=TAG_SR, n_fft=N_FFT, n_mels=N_MELS, fmin=0.0, fmax=TAG_SR / 2,
                             htk=False, norm="slaney")
    mel = np.log10(1.0 + 10000.0 * (fb @ S)).T          # (frames, 96)
    n = (len(mel) // PATCH) * PATCH
    if n == 0:
        raise TaggerUnavailable(f"too short for one patch ({len(mel)} < {PATCH} frames)")
    return mel[:n].reshape(-1, PATCH, N_MELS).astype(np.float32)


def _load(directory: Path) -> None:
    if _SESSIONS:
        return
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise TaggerUnavailable("onnxruntime not installed") from exc
    spec = {
        "effnet": "discogs-effnet-bsdynamic-1",
        "instrument": "mtg_jamendo_instrument-discogs-effnet-1",
        "genre": "mtg_jamendo_genre-discogs-effnet-1",
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
    import librosa

    _load(directory or DEFAULT_DIR)
    y16 = librosa.resample(np.asarray(y, dtype=np.float32), orig_sr=sr, target_sr=TAG_SR) \
        if sr != TAG_SR else np.asarray(y, dtype=np.float32)
    patches = musicnn_mel(y16)

    # 곡 단위 값 = 패치 평균 (30초 전체를 본다 — 10초 천장이 없는 것이 이 경로의 이점)
    styles, emb = _SESSIONS["effnet"].run(["activations", "embeddings"],
                                          {"melspectrogram": patches})
    inst = _SESSIONS["instrument"].run(["activations"], {"embeddings": emb})[0]
    genre = _SESSIONS["genre"].run(["activations"], {"embeddings": emb})[0]
    return {
        "styles": _top(_LABELS["effnet"], styles.mean(0)),
        "instruments": _top(_LABELS["instrument"], inst.mean(0), k=TOP_K_INSTRUMENT),
        "genres": _top(_LABELS["genre"], genre.mean(0)),
        "tag_patches": int(len(patches)),
        # RULES §3.1.7 — 정확도를 아직 사람 라벨로 재지 않았다. 표면에 그대로 전파된다.
        "tag_status": "unvalidated",
    }


def style_probability(y: np.ndarray, sr: int, label: str, *, directory: Path | None = None) -> tuple[int, float]:
    """특정 스타일의 (순위, 확률) — 전처리 회귀 검증용(TESTS §4)."""
    import librosa

    _load(directory or DEFAULT_DIR)
    y16 = librosa.resample(np.asarray(y, dtype=np.float32), orig_sr=sr, target_sr=TAG_SR) \
        if sr != TAG_SR else np.asarray(y, dtype=np.float32)
    styles = _SESSIONS["effnet"].run(["activations"], {"melspectrogram": musicnn_mel(y16)})[0].mean(0)
    idx = _LABELS["effnet"].index(label)
    return int(np.where(np.argsort(-styles) == idx)[0][0]) + 1, float(styles[idx])
