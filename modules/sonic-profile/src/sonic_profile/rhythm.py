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

from typing import Any

import numpy as np

HOP = 256          # 16분음 해상도용 (130BPM 16분 ≈ 115ms ≈ 10프레임)
BINS = 16          # 마디를 16분음 16칸으로
KICK_BAND = (20.0, 120.0)
MIN_DOWNBEATS = 3

# RULES §3.1.5 템플릿 원장 — 16분 격자 위 킥 위치. **값은 도메인 소유자 소유.**
TEMPLATES: dict[str, tuple[int, ...]] = {
    "four-on-floor": (0, 4, 8, 12),
    "backbeat(1·3)": (0, 8),
    "tresillo 3+3+2": (0, 3, 6),
    "tresillo(16th)": (0, 6, 12),
    "dembow": (0, 3, 6, 8, 11, 14),
    "trap-synco": (0, 3, 6, 10),
}

_A2B: Any = None


class RhythmUnavailable(RuntimeError):
    """비트/다운비트를 못 얻은 상태 — 나머지 지표는 계속 낸다."""


def tempo_from_beats(beats: np.ndarray) -> float:
    """비트 시각 → BPM. **최소자승 적합**으로 프레임 양자화를 씻는다(RULES §3.2).

    `median(diff)`를 쓰면 beat_this의 50fps 격자를 그대로 물려받아 128BPM이 130.43으로
    나온다. 적합하면 오차가 +0.02%로 떨어진다 — 산출 방식이 지표 정의의 일부다.
    """
    b = np.asarray(beats, dtype=np.float64)
    if b.size < 4:
        raise RhythmUnavailable(f"too few beats ({b.size})")
    slope = float(np.polyfit(np.arange(b.size), b, 1)[0])
    if not np.isfinite(slope) or slope <= 0:
        raise RhythmUnavailable("non-monotonic beat times")
    return 60.0 / slope


def kick_envelope(y: np.ndarray, sr: int) -> np.ndarray:
    """저역(20~120Hz) 온셋 포락 — 킥/808."""
    import librosa

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
    for a, b in zip(d[:-1], d[1:]):
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

    템플릿끼리 **직교하지 않는다** — four-on-floor와 backbeat는 상관이 높다.
    따라서 최고 정합은 **판정이 아니라 순위**다(RULES §3.1.5).
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


def _beat_tracker() -> Any:
    global _A2B
    if _A2B is None:
        try:
            from beat_this.inference import Audio2Beats
        except ImportError as exc:
            raise RhythmUnavailable("beat_this not installed") from exc
        try:
            _A2B = Audio2Beats(checkpoint_path="final0", device="cpu", dbn=False)
        except Exception as exc:  # noqa: BLE001 — 체크포인트 미다운로드 등
            raise RhythmUnavailable(f"beat_this load failed: {type(exc).__name__}") from exc
    return _A2B


def extract_rhythm(y: np.ndarray, sr: int) -> dict[str, Any]:
    """오디오 배열 → 리듬 지표. 실패는 RhythmUnavailable로 올린다(0으로 채우지 않는다)."""
    beats, downbeats = _beat_tracker()(np.asarray(y, dtype=np.float32), sr)
    beats = np.asarray(beats, dtype=np.float64)
    downbeats = np.asarray(downbeats, dtype=np.float64)

    tempo = tempo_from_beats(beats)
    profile = bar_profile(kick_envelope(y, sr), sr, downbeats)
    match = match_templates(profile)
    top = max(match, key=lambda k: match[k])
    return {
        "tempo_bpm_fit": round(tempo, 2),
        "beats_per_bar": round(float(len(beats)) / len(downbeats), 2) if len(downbeats) else None,
        "n_beats": int(len(beats)),
        "n_downbeats": int(len(downbeats)),
        "kick_bar_profile": [round(float(v), 4) for v in profile],
        "rhythm_match": match,
        # 순위이지 판정이 아니다 — 저정합도는 "해당 없음"이지 "다른 스타일"이 아니다
        "rhythm_top": top,
        "rhythm_top_score": match[top],
    }


def rhythm_provenance() -> dict[str, Any]:
    """값의 일부인 리듬 엔진 설정 — 캐시 키·시리즈 버전 분리에 쓰인다(RULES §2)."""
    return {
        "beat_engine": "beat_this",
        "beat_checkpoint": "final0",
        "beat_dbn": False,
        "rhythm_hop": HOP,
        "rhythm_bins": BINS,
        "rhythm_templates": sorted(TEMPLATES),
    }
