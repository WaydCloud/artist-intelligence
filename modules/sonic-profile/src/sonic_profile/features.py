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
# 지표 집합 버전. **지표를 늘리거나 정의를 바꾸면 올린다** — 캐시 키의 일부라(cli.py
# `engine_key`) 올리지 않으면 캐시 적중으로 새 지표가 빠진 레코드가 되살아난다.
#   v2 = D-031 (loudness_lufs · spectral_flatness · stereo_width 추가)
FEATURE_SET = "v2"
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


# ITU-R BS.1770-4 K-weighting 설계 파라미터 (pyloudnorm과 동일 — 임의 sr에서 재설계한다).
# 표준 표는 48kHz 계수만 주므로, 계수를 베끼면 우리 sr=22050에서 틀린 필터가 된다.
_KW_SHELF = (3.999843853973347, 0.7071752369554196, 1681.974450955533)  # (G dB, Q, fc)
_KW_HPF = (0.0, 0.5003270373238773, 38.13547087602444)
_LUFS_OFFSET = -0.691          # BS.1770 상수항
_LUFS_BLOCK_S = 0.400          # 게이팅 블록 400ms
_LUFS_OVERLAP = 0.75           # 75% 겹침
_LUFS_ABS_GATE = -70.0         # 절대 게이트 (LUFS)
_LUFS_REL_GATE = -10.0         # 상대 게이트 (LU, 비게이트 평균 대비)


def _biquad_shelf(g_db: float, q: float, fc: float, sr: int) -> tuple[np.ndarray, np.ndarray]:
    a_gain = 10.0 ** (g_db / 40.0)
    w0 = 2.0 * np.pi * fc / sr
    alpha = np.sin(w0) / (2.0 * q)
    cw, sq = np.cos(w0), np.sqrt(a_gain)
    b = np.array([
        a_gain * ((a_gain + 1) + (a_gain - 1) * cw + 2 * sq * alpha),
        -2 * a_gain * ((a_gain - 1) + (a_gain + 1) * cw),
        a_gain * ((a_gain + 1) + (a_gain - 1) * cw - 2 * sq * alpha),
    ])
    a = np.array([
        (a_gain + 1) - (a_gain - 1) * cw + 2 * sq * alpha,
        2 * ((a_gain - 1) - (a_gain + 1) * cw),
        (a_gain + 1) - (a_gain - 1) * cw - 2 * sq * alpha,
    ])
    return b / a[0], a / a[0]


def _biquad_hpf(q: float, fc: float, sr: int) -> tuple[np.ndarray, np.ndarray]:
    w0 = 2.0 * np.pi * fc / sr
    alpha = np.sin(w0) / (2.0 * q)
    cw = np.cos(w0)
    b = np.array([(1 + cw) / 2.0, -(1 + cw), (1 + cw) / 2.0])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def _loudness_lufs(y: np.ndarray, sr: int) -> float:
    """ITU-R BS.1770-4 게이팅 통합 라우드니스(LUFS). 모노 = 채널 가중 1.0.

    **주의(RULES §3)**: 우리 입력은 `sr=22050`의 30초 발췌라 마스터링 스위트의 전곡
    LUFS 판독과 같은 수가 아니다. 11kHz 위 대역이 애초에 없어 K-weighting이 셀 것이
    빠져 있다. **곡 간 상대 축으로만** 쓴다.
    """
    import scipy.signal as sps  # type: ignore  # librosa가 이미 끌고 오는 의존성

    x = np.asarray(y, dtype=np.float64)
    for b, a in (_biquad_shelf(*_KW_SHELF, sr), _biquad_hpf(_KW_HPF[1], _KW_HPF[2], sr)):
        # `zi` 없이 부르면 배열 하나만 돌아온다 — 타입체커가 (y, zf) 튜플로도 보므로 명시한다
        x = np.asarray(sps.lfilter(b, a, x), dtype=np.float64)

    block = round(_LUFS_BLOCK_S * sr)
    step = max(1, round(block * (1.0 - _LUFS_OVERLAP)))
    if x.size < block:
        raise Unresolved(f"too short for LUFS gating ({x.size} < {block})")
    starts = range(0, x.size - block + 1, step)
    power = np.array([float(np.mean(np.square(x[s : s + block]))) for s in starts])
    power = power[power > 0.0]
    if power.size == 0:
        raise Unresolved("silent after K-weighting")
    lj = _LUFS_OFFSET + 10.0 * np.log10(power)

    # 2단 게이트: 절대(-70 LUFS) → 상대(비게이트 평균 −10 LU)
    keep = lj > _LUFS_ABS_GATE
    if not keep.any():
        raise Unresolved("all blocks below absolute gate")
    rel = _LUFS_OFFSET + 10.0 * np.log10(float(np.mean(power[keep]))) + _LUFS_REL_GATE
    keep &= lj > rel
    if not keep.any():
        raise Unresolved("all blocks below relative gate")
    return _LUFS_OFFSET + 10.0 * np.log10(float(np.mean(power[keep])))


def stereo_width(y_stereo: np.ndarray) -> float | None:
    """Mid/Side 에너지 비 (0~1). 0 = 완전 모노, 1 = 완전 역위상.

    **모노 소스는 `None`을 돌려준다** — 0.0("좁다")과 "정보 없음"은 다르다(결측 ≠ 0, §0).
    AAC 조인트 스테레오가 side를 깎을 수 있으므로 절대값을 믿지 않는다(RULES §3).
    """
    a = np.asarray(y_stereo, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != 2 or a.shape[1] == 0:
        return None
    mid, side = (a[0] + a[1]) / 2.0, (a[0] - a[1]) / 2.0
    em, es = float(np.sum(np.square(mid))), float(np.sum(np.square(side)))
    if em + es <= _EPS:
        return None
    return float(np.clip(es / (em + es), 0.0, 1.0))


def _key_mode(y: np.ndarray, sr: int) -> tuple[str, str, float]:
    """chroma → (key, mode, 상관계수). 정확도가 낮아 집계 전용(RULES §3)."""
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

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


def extract(
    y: np.ndarray,
    sr: int = SR,
    *,
    low_hz: float = LOW_HZ_DEFAULT,
    stereo: np.ndarray | None = None,
) -> dict[str, Any]:
    """오디오 배열 → RULES §3 지표 dict. 미해석 입력은 Unresolved를 던진다.

    `stereo`(2×N)를 주면 `stereo_width`를 함께 낸다. **모노 지표는 `y`에서만** 나오므로
    스테레오를 넘겨도 기존 값은 바뀌지 않는다 — 그 무회귀는 TESTS §6.2가 고정한다.
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

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

    flatness = float(np.median(librosa.feature.spectral_flatness(S=stft)))

    rms = float(np.sqrt(np.mean(np.square(y))))
    crest = float(20.0 * np.log10(peak / rms)) if rms > _EPS else 0.0

    w = None if stereo is None else stereo_width(stereo)
    width = None if w is None else round(w, 4)

    # 라우드니스는 게이팅에서 미해석이 날 수 있다 — 나머지 지표를 죽이지 않는다.
    try:
        lufs: float | None = round(_loudness_lufs(y, sr), 2)
    except Unresolved:
        lufs = None

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
        # D-031. LUFS는 crest와 **같은 전제**(프리뷰 미정규화, TESTS §3)에 기댄다 —
        # 전제가 무너지면 둘이 함께 무효가 된다.
        "loudness_lufs": lufs,
        "spectral_flatness": round(flatness, 4),
        "stereo_width": width,
        "key": key,
        "mode": mode,
        "key_corr": key_corr,
    }


def engine_provenance(low_hz: float = LOW_HZ_DEFAULT) -> dict[str, Any]:
    """값의 일부인 엔진 설정 — 바뀌면 시리즈를 버전 분리해야 한다(RULES §2)."""
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    return {
        "engine": "librosa",
        "engine_version": getattr(librosa, "__version__", "unknown"),
        "sample_rate": SR,
        "mono": False,  # 스테레오로 받아 width를 잰 뒤 다운믹스한다(D-031)
        "low_hz": low_hz,
        # **지표 집합의 버전**. 지표를 늘리면 반드시 올린다 — 안 올리면 캐시가 적중해
        # 새 지표가 빠진 옛 레코드를 그대로 다시 써 넣는다(RULES §3.1.6.1과 같은 함정).
        "feature_set": FEATURE_SET,
    }
