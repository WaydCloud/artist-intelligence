"""리듬 패턴 (RULES §3.1.5) — 마디 단위 킥 배치로 리듬 스타일을 잰다.

근거: Dixon·Gouyon·Widmer, *Towards Characterisation of Music via Rhythmic Patterns*
(ISMIR 2024가 아니라 ISMIR 2004) — "리듬 패턴은 장르에 무작위로 분포하지 않는다".
다운비트가 있어야 **마디 상대 위치**를 만들 수 있어 beat_this(MIT)를 쓴다.

**저역만 쓴다.** 실측에서 중역(스네어) 마디 프로파일의 대비가 1.22로 사실상 평탄해
(저역은 1.71) 보컬·베이스·신스에 스네어가 묻혔다. 그래서 하프타임 스네어·하이햇 롤은
내지 않는다 — 트랩·저지클럽 판별은 스템 분리가 생기기 전까지 열지 않는다(RULES §3.1.5).

순수 함수(`tempo_from_beats`·`bar_profile`·`match_templates`)와 모델 의존부
(`extract_rhythm`)를 분리해 둔다 — 앞쪽은 네트워크 0으로 selftest가 검증한다.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import numpy as np

HOP = 256          # 16분음 해상도용 (130BPM 16분 ≈ 115ms ≈ 10프레임)
BINS = 16          # 마디를 16분음 16칸으로
KICK_BAND = (20.0, 120.0)
MIN_DOWNBEATS = 3

# RULES §3.1.5 템플릿 원장 — 16분 격자 위 킥 위치. **값은 도메인 소유자 소유.**
# 이름은 격자와 맞아야 한다: 16분 16칸에서 8분음 n = 칸 2n이므로 8분 3+3+2 = 0·6·12다.
# (2026-07-29 이전에는 두 tresillo의 이름과 근거가 서로 뒤바뀌어 있었다 — D-027.)
TEMPLATES: dict[str, tuple[int, ...]] = {
    "four-on-floor": (0, 4, 8, 12),
    "backbeat(1·3)": (0, 8),
    "tresillo(8분 3+3+2)": (0, 6, 12),
    # 반마디 조각이라 관용 패턴이 아니다 — 마디 끝까지 이으면 dembow와 같은 벡터가 된다.
    # 제거를 권고하되 값은 도메인 소유자 소유라 이름·근거만 바로잡고 남긴다(RULES §3.1.5 결함 ①).
    "tresillo(16분·반마디)": (0, 3, 6),
    "dembow": (0, 3, 6, 8, 11, 14),
    "trap-synco": (0, 3, 6, 10),
}

# 하중받는 기준 — **관습 기본값이며 도메인 소유자(A&R)가 재조정한다**(RULES §3.1.5 원장).
# θ가 없으면 argmax가 언제나 이름을 뱉어 음의 상관도 "가장 가까운 유형"이 된다.
MIN_MATCH_DEFAULT = 0.30
TIE_GAP_DEFAULT = 0.05
NO_MATCH = "해당 없음"

# 리듬 산출 집합의 버전 — 늘리면 올린다(캐시 키의 일부, cli.py `engine_key`).
#   v2 = D-031 (grid_deviation_ms · syncopation_ratio · bar_profile_contrast)
RHYTHM_FEATURE_SET = "v2"

_A2B: Any = None


class RhythmUnavailable(RuntimeError):
    """비트/다운비트를 못 얻은 상태 — 나머지 지표는 계속 낸다."""


def beat_grid_fit(beats: np.ndarray) -> tuple[float, float]:
    """비트 시각 → (BPM, **격자 잔차 RMS ms**). 최소자승 적합으로 양자화를 씻는다(RULES §3.2).

    `median(diff)`를 쓰면 beat_this의 50fps 격자를 그대로 물려받아 128BPM이 130.43으로
    나온다. 적합하면 오차가 +0.02%로 떨어진다 — 산출 방식이 지표 정의의 일부다.

    **잔차는 버리지 않는다**(D-031): 적합 직선에서 비트가 얼마나 벗어나는가가 곧
    "완전 퀀타이즈된 그리드인가 연주인가"다. 여태 계산해 놓고 폐기하던 값이다.
    """
    b = np.asarray(beats, dtype=np.float64)
    if b.size < 4:
        raise RhythmUnavailable(f"too few beats ({b.size})")
    idx = np.arange(b.size, dtype=np.float64)
    slope, intercept = (float(v) for v in np.polyfit(idx, b, 1))
    if not np.isfinite(slope) or slope <= 0:
        raise RhythmUnavailable("non-monotonic beat times")
    resid = b - (slope * idx + intercept)
    return 60.0 / slope, float(np.sqrt(np.mean(resid**2)) * 1000.0)


def tempo_from_beats(beats: np.ndarray) -> float:
    """비트 시각 → BPM만. 잔차까지 필요하면 `beat_grid_fit`을 쓴다."""
    return beat_grid_fit(beats)[0]


def syncopation_ratio(profile: np.ndarray | list[float]) -> float:
    """마디 프로파일에서 **정박 칸을 뺀** 킥 에너지 비(0~1) — RULES §3.1.5.

    리듬 **유형**은 배정이라 임계·동점에 흔들리지만(비직교 최악 0.83·동점 27%),
    "얼마나 밀려 있는가"는 연속값이라 그 영향을 받지 않는다. 어느 스타일인지는
    말하지 않는다 — 그건 템플릿 정합의 몫이다.
    """
    p = np.asarray(profile, dtype=np.float64)
    total = float(p.sum())
    if p.size < 4 or total <= 0:
        raise RhythmUnavailable("empty bar profile")
    step = max(1, p.size // 4)  # 16칸이면 0·4·8·12
    on_beat = float(p[::step][: p.size // step].sum())
    return float(np.clip(1.0 - on_beat / total, 0.0, 1.0))


def bar_profile_contrast(profile: np.ndarray | list[float]) -> float:
    """`max/mean` — 완전 균일이면 정확히 1.0 (RULES §3.1.5).

    정의는 이 모듈이 이미 쓰던 것 그대로다(저역 1.71 vs 중역 1.22). **리듬 형태가
    있는가를 유형 배정과 분리해 잰다** — 지금은 "드럼이 약해 평탄한 곡"과 "θ 미달인
    곡"이 `해당 없음` 한 칸에 섞여 구별되지 않는다.
    """
    p = np.asarray(profile, dtype=np.float64)
    mean = float(p.mean()) if p.size else 0.0
    if p.size == 0 or mean <= 0:
        raise RhythmUnavailable("empty bar profile")
    return float(p.max() / mean)


def kick_envelope(y: np.ndarray, sr: int) -> np.ndarray:
    """저역(20~120Hz) 온셋 포락 — 킥/808."""
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    S = np.abs(librosa.stft(y, hop_length=HOP, n_fft=2048)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    rows = (freqs >= KICK_BAND[0]) & (freqs < KICK_BAND[1])
    return librosa.onset.onset_strength(S=librosa.power_to_db(S[rows] + 1e-10), sr=sr,
                                        hop_length=HOP)


def bar_profile(env: np.ndarray, sr: int, downbeats: np.ndarray, bins: int = BINS) -> np.ndarray:
    """온셋 포락을 **마디 상대 위치**로 접는다 → 합=1인 16칸 벡터.

    마디 경계가 틀리면 전부 틀린다 — 다운비트 정확도에 전적으로 의존한다.
    """
    d = np.asarray(downbeats, dtype=np.float64)
    if d.size < MIN_DOWNBEATS:
        raise RhythmUnavailable(f"too few downbeats ({d.size})")
    times = np.arange(len(env)) * HOP / sr
    prof = np.zeros(bins, dtype=np.float64)
    for a, b in pairwise(d):
        if not (b > a):
            continue
        m = (times >= a) & (times < b)
        if not m.any():
            continue
        idx = np.floor((times[m] - a) / (b - a) * bins).astype(int) % bins
        np.add.at(prof, idx, np.maximum(env[m], 0.0))
    total = prof.sum()
    if total <= 0:
        raise RhythmUnavailable("no kick energy in bars")
    return prof / total


def match_templates(profile: np.ndarray) -> dict[str, float]:
    """프로파일 × 명명 템플릿의 코사인 정합도(평균 제거 후).

    템플릿끼리 **직교하지 않는다** — 실측 최악 쌍이 0.83이다(RULES §3.1.5.1).
    따라서 최고 정합은 **판정이 아니라 순위**이고, 이 함수의 출력을 그대로
    `max()`에 넣으면 안 된다 — 임계·동점 처리는 `classify_rhythm`이 한다.
    """
    a = np.asarray(profile, dtype=np.float64)
    a = a - a.mean()
    na = float(np.linalg.norm(a))
    out: dict[str, float] = {}
    for name, positions in TEMPLATES.items():
        t = np.zeros(len(a))
        t[list(positions)] = 1.0
        t = t - t.mean()
        nt = float(np.linalg.norm(t))
        out[name] = round(float(a @ t / (na * nt)) if na > 0 and nt > 0 else 0.0, 4)
    return out


def classify_rhythm(
    profile: np.ndarray | list[float],
    *,
    min_match: float = MIN_MATCH_DEFAULT,
    tie_gap: float = TIE_GAP_DEFAULT,
) -> dict[str, Any]:
    """마디 프로파일 → **유형 배정 + 그 배정을 못 믿을 이유**(RULES §3.1.5).

    `match_templates`에 `max()`를 씌우는 것만으로는 두 가지가 조용히 깨진다:

    1. 코사인은 0을 중심으로 대칭이라 **음의 상관도 1위가 된다.** 실측 코호트에
       −0.027짜리 곡이 `backbeat`로 집계돼 있었다. → `min_match` 미만은 `None`.
    2. 프로파일이 완전 평탄하면 전 정합도가 0이 되고, `max()`는 **사전 첫 키인
       `four-on-floor`를 조용히 뽑는다.** "리듬 없음"이 "정박"으로 둔갑한다.
       (1)의 임계가 이 경로도 막는다 — θ를 0으로 내리면 되살아나므로 TESTS §5에 고정.

    `assigned=None`은 "다른 유형"이 아니라 **"해당 없음"**이다. `tie`는 1·2위가
    근소차라 표본이 조금만 흔들려도 뒤집힌다는 표시이며, **행을 지우지 않는다**.
    """
    match = match_templates(np.asarray(profile, dtype=np.float64))
    ranked = sorted(match.items(), key=lambda kv: (-kv[1], kv[0]))
    top, score = ranked[0]
    second, second_score = ranked[1] if len(ranked) > 1 else (None, None)
    gap = round(score - second_score, 4) if second_score is not None else None
    assigned = top if score >= min_match else None
    return {
        "match": match,
        "top": top,
        "top_score": score,
        "second": second,
        "second_score": second_score,
        "gap": gap,
        "assigned": assigned,
        # 동점은 배정된 곡에서만 의미가 있다 — 해당 없음은 애초에 순위를 주장하지 않는다
        "tie": bool(assigned is not None and gap is not None and gap < tie_gap),
    }


def _beat_tracker() -> Any:
    global _A2B
    if _A2B is None:
        try:
            # torch를 끌고 오는 선택적 의존성 — 미설치는 정상 경로이고(바로 아래에서 잡아
            # RhythmUnavailable로 올린다), CI 타입체크 환경에도 일부러 넣지 않는다.
            from beat_this.inference import Audio2Beats  # type: ignore
        except ImportError as exc:
            raise RhythmUnavailable("beat_this not installed") from exc
        try:
            _A2B = Audio2Beats(checkpoint_path="final0", device="cpu", dbn=False)
        except Exception as exc:  # 체크포인트 미다운로드 등
            raise RhythmUnavailable(f"beat_this load failed: {type(exc).__name__}") from exc
    return _A2B


def extract_rhythm(y: np.ndarray, sr: int) -> dict[str, Any]:
    """오디오 배열 → 리듬 지표. 실패는 RhythmUnavailable로 올린다(0으로 채우지 않는다)."""
    beats, downbeats = _beat_tracker()(np.asarray(y, dtype=np.float32), sr)
    beats = np.asarray(beats, dtype=np.float64)
    downbeats = np.asarray(downbeats, dtype=np.float64)

    tempo, grid_dev = beat_grid_fit(beats)
    profile = bar_profile(kick_envelope(y, sr), sr, downbeats)
    cls = classify_rhythm(profile)
    return {
        "tempo_bpm_fit": round(tempo, 2),
        # 적합 잔차 — 퀀타이즈된 그리드인가 연주인가(RULES §3.1.5). beat_this가 50fps
        # 격자라 ≈20ms 아래는 분해되지 않는다는 하한이 있다.
        "grid_deviation_ms": round(grid_dev, 2),
        # 아래 둘은 `kick_bar_profile`에서 재계산 가능하지만(리포트가 그렇게 한다)
        # 수집 시점에도 실어 둔다 — 값이 갈라지지 않는지 TESTS §6.1이 대조한다.
        "syncopation_ratio": round(syncopation_ratio(profile), 4),
        "bar_profile_contrast": round(bar_profile_contrast(profile), 3),
        "beats_per_bar": round(float(len(beats)) / len(downbeats), 2) if len(downbeats) else None,
        "n_beats": len(beats),
        "n_downbeats": len(downbeats),
        # 리포트는 이 프로파일에서 유형을 **재계산**한다 — 템플릿·θ를 고쳐도 오디오를
        # 다시 받지 않아도 되게 하는 것이 무보관 불변식(§1)과 기준 재조정(§2.1)의 접점이다.
        "kick_bar_profile": [round(float(v), 4) for v in profile],
        "rhythm_match": cls["match"],
        # 순위이지 판정이 아니다 — 저정합도는 "해당 없음"이지 "다른 스타일"이 아니다
        "rhythm_top": cls["top"],
        "rhythm_top_score": cls["top_score"],
        "rhythm_assigned": cls["assigned"],
        "rhythm_gap": cls["gap"],
        "rhythm_tie": cls["tie"],
    }


def rhythm_provenance() -> dict[str, Any]:
    """값의 일부인 리듬 엔진 설정 — 캐시 키·시리즈 버전 분리에 쓰인다(RULES §2)."""
    return {
        "beat_engine": "beat_this",
        "beat_checkpoint": "final0",
        "beat_dbn": False,
        "rhythm_hop": HOP,
        "rhythm_bins": BINS,
        # 템플릿·임계는 **캐시 키가 아니다**(cli.py `engine_key` 참조). 저장된
        # kick_bar_profile에서 재계산되므로 값을 바꿔도 프리뷰를 다시 받지 않는다.
        "rhythm_templates": sorted(TEMPLATES),
        "rhythm_min_match": MIN_MATCH_DEFAULT,
        "rhythm_tie_gap": TIE_GAP_DEFAULT,
        # 리듬 산출 집합의 버전 — 캐시 키의 일부(cli.py `engine_key`).
        #   v2 = D-031 (grid_deviation_ms · syncopation_ratio · bar_profile_contrast)
        "rhythm_feature_set": RHYTHM_FEATURE_SET,
    }
