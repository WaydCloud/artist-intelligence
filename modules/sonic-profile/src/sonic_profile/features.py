"""소리 지표 엔진 — 순수·결정적. RULES §3 기준 원장의 코드측 구현.

이 모듈은 **오디오 배열만** 받는다(파일 경로도, 네트워크도 모른다). 무보관 불변식은
호출자(preview.py)가 지키고, 여기는 "같은 배열 → 같은 값"만 책임진다.

원칙(RULES §3): **정의가 곧 설명인 지표만** 낸다. 사전학습 분류기의 점수는 원장에
올릴 근거를 댈 수 없으므로 쓰지 않는다.
"""

from __future__ import annotations

from typing import Any

import numpy as np

SR = 22050  # 고정 — 바꾸면 과거 값과 비교 불가(RULES §2, provenance에 기록)
LOW_HZ_DEFAULT = 150.0  # 저역 경계 (튜닝 가능, RULES §3)
MIN_SECONDS = 2.0  # 이보다 짧으면 미해석 (결측 ≠ 0)
_EPS = 1e-10

# Krumhansl-Kessler 조성 프로파일 — key_mode 추정의 공개된 근거
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class Unresolved(Exception):
    """지표를 낼 수 없는 입력 — 0으로 채우지 않고 미해석으로 올린다."""


def _pulse_clarity(onset_env: np.ndarray, sr: int, hop: int) -> float:
    """온셋 포락의 자기상관 주 피크(0~1). '박이 얼마나 또렷하게 서 있는가'.

    danceability가 아니다(RULES §5) — 자기상관 피크값일 뿐이다.
    """
    env = onset_env - float(np.mean(onset_env))
    ac = np.correlate(env, env, mode="full")[len(env) - 1 :]
    if ac.size < 2 or ac[0] <= _EPS:
        return 0.0
    ac = ac / ac[0]
    # 30~300 BPM에 해당하는 lag만 본다(그 밖의 주기는 박이 아님)
    lo = max(1, round(60.0 / 300.0 * sr / hop))
    hi = min(ac.size - 1, round(60.0 / 30.0 * sr / hop))
    if hi <= lo:
        return 0.0
    return float(np.clip(np.max(ac[lo : hi + 1]), 0.0, 1.0))


def _key_mode(y: np.ndarray, sr: int) -> tuple[str, str, float]:
    """chroma → (key, mode, 상관계수). 정확도가 낮아 집계 전용(RULES §3)."""
    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = np.mean(chroma, axis=1)
    if float(np.sum(profile)) <= _EPS:
        raise Unresolved("chroma empty")
    best = (-2.0, 0, "major")
    for shift in range(12):
        rolled = np.roll(profile, -shift)
        for name, ref in (("major", _MAJOR), ("minor", _MINOR)):
            num = float(np.corrcoef(rolled, ref)[0, 1])
            if np.isfinite(num) and num > best[0]:
                best = (num, shift, name)
    return _PITCHES[best[1]], best[2], round(best[0], 3)


def extract(y: np.ndarray, sr: int = SR, *, low_hz: float = LOW_HZ_DEFAULT) -> dict[str, Any]:
    """오디오 배열 → RULES §3 지표 dict. 미해석 입력은 Unresolved를 던진다."""
    import librosa

    if y.ndim > 1:
        y = librosa.to_mono(y)
    y = np.asarray(y, dtype=np.float32)
    duration = float(len(y)) / sr
    if duration < MIN_SECONDS:
        raise Unresolved(f"too short: {duration:.2f}s < {MIN_SECONDS}s")
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak <= _EPS:
        raise Unresolved("silent")

    hop = 512
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo_arr = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, hop_length=hop)
    tempo = float(np.atleast_1d(tempo_arr)[0])
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop)

    stft = np.abs(librosa.stft(y, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2 * (stft.shape[0] - 1))
    power = stft**2
    total = float(np.sum(power))
    low_ratio = float(np.sum(power[freqs < low_hz, :]) / total) if total > _EPS else 0.0

    centroid = float(np.median(librosa.feature.spectral_centroid(S=stft, sr=sr)))
    harm, perc = librosa.decompose.hpss(stft)
    hp_total = float(np.sum(harm**2) + np.sum(perc**2))
    perc_ratio = float(np.sum(perc**2) / hp_total) if hp_total > _EPS else 0.0

    rms = float(np.sqrt(np.mean(np.square(y))))
    crest = float(20.0 * np.log10(peak / rms)) if rms > _EPS else 0.0

    try:
        key, mode, key_corr = _key_mode(y, sr)
    except Unresolved:
        key, mode, key_corr = None, None, None

    return {
        "duration_s": round(duration, 2),
        "tempo_bpm": round(tempo, 2),
        "pulse_clarity": round(_pulse_clarity(onset_env, sr, hop), 4),
        "onset_rate": round(len(onsets) / duration, 3),
        "low_end_ratio": round(low_ratio, 4),
        "brightness_hz": round(centroid, 1),
        "percussive_ratio": round(perc_ratio, 4),
        # TESTS §3 통과(2026-07-28): 10곡 표본에서 프리뷰 RMS 스프레드 19.46dB —
        # Apple 프리뷰는 라우드니스 정규화되지 않으며 마스터링 압축을 실제로 반영한다.
        "crest_factor_db": round(crest, 2),
        "crest_factor_status": "validated-2026-07-28",
        "key": key,
        "mode": mode,
        "key_corr": key_corr,
    }


def engine_provenance(low_hz: float = LOW_HZ_DEFAULT) -> dict[str, Any]:
    """값의 일부인 엔진 설정 — 바뀌면 시리즈를 버전 분리해야 한다(RULES §2)."""
    import librosa

    return {
        "engine": "librosa",
        "engine_version": getattr(librosa, "__version__", "unknown"),
        "sample_rate": SR,
        "mono": True,
        "low_hz": low_hz,
    }
