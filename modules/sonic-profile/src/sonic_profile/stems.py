"""스템 분리 축 (RULES §3.8 · 수용조건 TESTS §7.2) — D-034 ③.

§3.1.5가 남긴 정직한 공백을 여는 모듈이다. 중역 마디 프로파일 대비가 1.22로
평탄해 스네어가 보컬·베이스·신스에 묻히고, 그래서 저지클럽 **하프타임 스네어**·
드릴 **슬라이딩 808**·하이퍼팝 **보컬 처리**를 못 봤다. 분리하면 열린다(실측:
중역 대비 1.17~1.41 → 1.56~2.38).

**무보관 불변식(§1·§3.8.1)이 스템에도 적용된다 — 분리된 스템은 오디오다.**
이 모듈은 그것을 **구조로** 보증한다: demucs의 CLI(`demucs.separate`)를 쓰지
않고 `apply_model`에 텐서를 직접 넣는다. 파일 경로가 함수 서명에 아예 없으므로
"삭제를 잊는" 경로가 존재할 수 없다.

**순수 함수와 모델 의존부를 나눠 둔다** — 앞쪽(`halftime_snare_ratio`·
`bass_glide_ratio`·`grid_adherence`·`vibrato_strength`)은 네트워크 0·모델 0으로
`selftest_stems()`가 검증한다. rhythm.py가 쓰는 것과 같은 규율이다.

⚠ **2026-07-30 채택 게이트 1차 결과: 통과 축 0**(RULES §3.8.4.1). `grid_adherence`
기반 두 축은 f0 추정기의 격자를 재고 있어 **철회**됐고, `bass_glide_ratio`·
`pitch_shift_proxy`는 **판별력 없음**으로 판정됐다. 코드는 남기되 어떤 축도
검출 규칙으로 승격되지 않았다 — 구현했다고 채택되는 것이 아니다.
"""

from __future__ import annotations

import math
from typing import Any, TypedDict

import numpy as np

from sonic_profile.rhythm import (
    BINS,
    HOP,
    RhythmUnavailable,
    bar_profile,
    bar_profile_contrast,
)

# ── 엔진 · 대역 ──────────────────────────────────────────────────────────
# 캐시 키·provenance의 일부다(RULES §3.8.1). 이 값을 안 넣으면 캐시가 적중해
# **스템 축이 빈 옛 레코드가 되살아난다**(D-031 절단본 함정과 같은 구조).
STEM_MODEL = "htdemucs"
STEM_SET = "v1"

STEM_SR = 44100        # htdemucs 학습 샘플레이트 — 리샘플해 넣으면 분리 품질이 떨어진다
STEM_CHANNELS = 2

SNARE_BAND = (180.0, 1200.0)   # §3.1.5가 "중역"으로 부르던 대역 그대로
HIHAT_MIN_HZ = 6000.0

F0_HOP = 512           # f0 축은 16분음 해상도가 필요 없다. 23ms 프레임 → 나이퀴스트 21.7Hz
BASS_F0_RANGE = (30.0, 400.0)
VOCAL_F0_RANGE = (65.0, 1200.0)

# 옥타브 오류 거부 — 808은 배음이 강해 f0 추정이 옥타브를 튄다(RULES §3.8.3 한계 ①).
# 한 프레임에 반옥타브를 넘게 움직이면 글라이드가 아니라 추정 불연속이다.
OCTAVE_REJECT_ST = 6.0

VIBRATO_BAND_HZ = (4.0, 8.0)
VIBRATO_TOTAL_HZ = (0.5, 15.0)

# ── 하중받는 기준 (RULES §3.8.5) ─────────────────────────────────────────
# **전부 관습 기본값이며 도메인 소유자(A&R)가 재조정한다.** 코드에 은닉 금지 —
# CLI로 노출한다(AGENTS §2.1).
HALFTIME_MIN_RATIO_DEFAULT = 1.0
BASS_GLIDE_MIN_ST_PER_SEC_DEFAULT = 6.0
BASS_GLIDE_MIN_MS_DEFAULT = 80.0
SNARE_MIN_CONTRAST_DEFAULT = 1.71   # 저역 기준선. 미만이면 스네어 축을 결측 처리한다

_EPS = 1e-12
_MODEL: Any = None


class StemOpts(TypedDict, total=False):
    """CLI가 내려보내는 하중받는 기준 묶음 — 이름을 타입으로 못박아 오타를 막는다."""

    min_ratio: float
    min_st_per_sec: float
    min_ms: float
    min_contrast: float


class StemsUnavailable(RuntimeError):
    """분리를 못 한 상태 — 나머지 지표는 계속 낸다(결측 ≠ 0, §0)."""


# ─────────────────────────────────────────── 순수 함수 (모델·네트워크 0)


def halftime_snare_ratio(profile: np.ndarray | list[float]) -> float | None:
    """`p[8] / (p[4] + p[12])`.

    16칸 격자에서 정박은 0·4·8·12다. 백비트 스네어는 **4·12**(2·4박)에 서고
    하프타임은 **8**(3박)에 선다. 분모가 0이면 **미해석**이다 — ∞를 큰 수로
    채우면 "하프타임 확실"로 읽히지만 실제로는 백비트가 아예 없는 것뿐이다.
    """
    p = np.asarray(profile, dtype=np.float64)
    if p.size < BINS:
        return None
    denom = float(p[4] + p[12])
    if denom <= _EPS:
        return None
    return float(p[8]) / denom


def snare_backbeat_ratio(profile: np.ndarray | list[float]) -> float | None:
    """`p[4] + p[12]` — 합=1 정규화 벡터이므로 곧 백비트 점유율.

    하프타임의 **대칭 축**이다. 이게 없으면 "하프타임이 아니다"와 "못 쟀다"가
    구별되지 않는다.
    """
    p = np.asarray(profile, dtype=np.float64)
    if p.size < BINS:
        return None
    return float(p[4] + p[12])


def _semitones(f0_hz: np.ndarray) -> np.ndarray:
    """Hz → A440 기준 세미톤. 무성·비유성은 NaN으로 남긴다(0으로 채우지 않는다)."""
    f = np.asarray(f0_hz, dtype=np.float64)
    out = np.full(f.shape, np.nan)
    ok = np.isfinite(f) & (f > 0)
    out[ok] = 12.0 * np.log2(f[ok] / 440.0)
    return out


def grid_adherence(f0_hz: np.ndarray) -> float | None:
    """반음 격자에 붙어 있는 정도 0~1 (1 = 완전히 격자 위).

    정의: 유성 프레임 f0의 **격자 이탈(cents) 중앙 절대값**을 0~1로 역정규화.
    최대 이탈은 50센트(반음의 절반)이므로 `1 − median|dev| / 50`이다.

    🔴 **이 함수가 내던 두 축(`bass_note_stability`·`vocal_tuning_hardness`)은
    철회됐다(RULES §3.8.4.1).** 함수 자체는 자기가 말하는 것을 정확히 계산하지만,
    f0 추정기(pyin)의 주파수 격자가 값을 지배한다 — 기본 `resolution=0.1`(=10센트)
    에서 122곡의 고유값이 6개뿐이었고, 해상도를 올리면 비용이 27배로 뛰면서도
    값이 **수렴하지 않았다**(0.616 → 0.684 → 0.656). 방출은 멈췄고 함수와
    selftest만 남긴다 — 안정적인 정의가 나오면 재사용한다.
    """
    st = _semitones(f0_hz)
    st = st[np.isfinite(st)]
    if st.size == 0:
        return None
    dev = np.abs(100.0 * (st - np.round(st)))
    return float(max(0.0, 1.0 - float(np.median(dev)) / 50.0))


def f0_range_st(f0_hz: np.ndarray) -> float | None:
    """유성 구간 f0의 5~95백분위 폭(세미톤). 양 끝을 자르는 이유는 추정 이상치다."""
    st = _semitones(f0_hz)
    st = st[np.isfinite(st)]
    if st.size < 2:
        return None
    lo, hi = np.percentile(st, [5, 95])
    return float(hi - lo)


def bass_glide_ratio(
    f0_hz: np.ndarray,
    frame_s: float,
    *,
    min_st_per_sec: float = BASS_GLIDE_MIN_ST_PER_SEC_DEFAULT,
    min_ms: float = BASS_GLIDE_MIN_MS_DEFAULT,
    onset_frames: np.ndarray | None = None,
) -> float | None:
    """유성 프레임 중 **미끄러지는** 구간의 비율 0~1.

    **정의의 핵심은 "음이 바뀌는 것"과 "한 음이 미끄러지는 것"의 구분이다.**
    슬라이딩 808은 후자다. 그래서 ① 프레임 간 기울기가 임계를 넘고 ② 그 상태가
    `min_ms` 이상 **이어질** 때만 센다. 계단형 음 이동은 한 프레임짜리 스파이크라
    ②에서 떨어진다 — 이 조건이 없으면 평범한 베이스 라인이 전부 글라이드가 된다.

    옥타브 점프(|Δ| > `OCTAVE_REJECT_ST`)는 글라이드가 아니라 f0 추정 불연속으로
    보고 구간을 끊는다. 노트 온셋 프레임도 (주어지면) 제외한다.
    """
    st = _semitones(f0_hz)
    voiced = np.isfinite(st)
    n_voiced = int(voiced.sum())
    if n_voiced < 2 or frame_s <= 0:
        return None

    d = np.diff(st)                                   # 길이 n-1, 비유성은 NaN
    both_voiced = voiced[:-1] & voiced[1:]
    slope = np.abs(d) / frame_s
    gliding = both_voiced & np.isfinite(d) & (np.abs(d) <= OCTAVE_REJECT_ST) & (
        slope >= min_st_per_sec
    )
    if onset_frames is not None and len(onset_frames):
        block = np.zeros(gliding.shape, dtype=bool)
        idx = np.asarray(onset_frames, dtype=int)
        idx = idx[(idx >= 0) & (idx < block.size)]
        block[idx] = True
        gliding &= ~block

    min_frames = max(1, math.ceil((min_ms / 1000.0) / frame_s))
    counted = 0
    run = 0
    for flag in (*gliding.tolist(), False):           # 끝에서 열린 구간을 닫는다
        if flag:
            run += 1
            continue
        if run >= min_frames:
            counted += run
        run = 0
    return float(counted) / float(n_voiced)


def vibrato_strength(f0_hz: np.ndarray, frame_s: float) -> float | None:
    """f0 궤적의 4~8Hz 변조 세기 0~1 (0.5~15Hz 총 전력 대비).

    `grid_adherence`의 **독립 확인 축**이다 — 하드튠은 비브라토를 죽인다. 두 축이
    반대로 움직이지 않으면 f0 추정을 의심하라(RULES §3.8.4).
    """
    st = _semitones(f0_hz)
    ok = np.isfinite(st)
    if int(ok.sum()) < 16 or frame_s <= 0:
        return None
    # 결측을 보간해 등간격 시계열로 만든다(스펙트럼을 보려면 격자가 균일해야 한다).
    idx = np.arange(st.size)
    series = np.interp(idx, idx[ok], st[ok])
    series = series - series.mean()
    # 선형 추세(글리산도·전조)를 뺀다 — 저역에 새는 전력이 분모를 부풀린다.
    coef = np.polyfit(idx, series, 1)
    series = series - np.polyval(coef, idx)

    spec = np.abs(np.fft.rfft(series * np.hanning(series.size))) ** 2
    freqs = np.fft.rfftfreq(series.size, d=frame_s)
    total = spec[(freqs >= VIBRATO_TOTAL_HZ[0]) & (freqs <= VIBRATO_TOTAL_HZ[1])].sum()
    if total <= _EPS:
        return None
    band = spec[(freqs >= VIBRATO_BAND_HZ[0]) & (freqs <= VIBRATO_BAND_HZ[1])].sum()
    return float(band / total)


def pitch_shift_proxy(centroid_hz: float | None, f0_median_hz: float | None) -> float | None:
    """보컬 스펙트럼 중심 ÷ f0 중앙값.

    🔴 **게이트에서 판별력 없음으로 판정됐다(2026-07-30, RULES §3.8.4.1).**
    사전 등록한 가설은 "하이퍼팝 계보가 이 비에서 높게 나온다"였는데 정답지
    3곡이 전부 코호트 **중앙 이하**(P37.5·P24.0·P11.5)였다 — 예측과 반대다.
    측정은 건강하다(고유값 96/96). 값은 계속 내되 **해석을 붙이지 않는다**:
    검출 규칙으로 승격하지 않으며 리포트 표면에도 올리지 않는다.
    """
    if not centroid_hz or not f0_median_hz or f0_median_hz <= 0:
        return None
    return float(centroid_hz) / float(f0_median_hz)


def apply_snare_gate(
    axes: dict[str, Any], contrast: float | None, *, min_contrast: float
) -> dict[str, Any]:
    """대비가 게이트 미만이면 하위 스네어 축을 **결측 처리**한다.

    게이트 없이 쓰면 평탄한 프로파일에서 뽑은 비율이 의미 있는 척한다 —
    `snare_bar_contrast`가 지표이면서 동시에 유효성 판정자인 이유다(RULES §3.8.2).
    """
    if contrast is not None and contrast >= min_contrast:
        return axes
    out = dict(axes)
    for k in ("halftime_snare_ratio", "snare_backbeat_ratio"):
        out[k] = None
    out["snare_axes_gated"] = True
    return out


# ─────────────────────────────────────────── 모델 의존부 (분리 · 특징 추출)


def _load_model() -> Any:
    global _MODEL
    if _MODEL is None:
        from demucs.pretrained import get_model  # type: ignore[import-not-found]

        _MODEL = get_model(STEM_MODEL)
        _MODEL.eval()
    return _MODEL


def separate(y_stereo: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """스테레오 44.1kHz(2×N) → {stem: 2×N}. **파일을 쓰지 않는다.**

    경로 인자가 없는 것이 설계다(§3.8.1 무보관). demucs CLI는 결과를 디스크에
    쓰므로 쓰지 않고 `apply_model`에 텐서를 직접 넣는다.
    """
    import torch  # type: ignore[import-not-found]
    from demucs.apply import apply_model  # type: ignore[import-not-found]

    if sr != STEM_SR:
        raise StemsUnavailable(f"stems need {STEM_SR}Hz, got {sr}")
    arr = np.asarray(y_stereo, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] < STEM_CHANNELS:
        raise StemsUnavailable("stems need 2-channel audio")
    arr = arr[:STEM_CHANNELS]
    if arr.shape[1] < sr:                       # 1초 미만은 분리 의미 없음
        raise StemsUnavailable(f"too short for separation ({arr.shape[1]} samples)")

    model = _load_model()
    ref = arr.mean(axis=0)
    scale = float(ref.std()) or 1.0
    x = torch.from_numpy((arr - ref.mean()) / scale)[None]
    with torch.no_grad():
        out = apply_model(model, x, device="cpu", progress=False)[0]
    out = out * scale + ref.mean()
    return {name: out[i].numpy() for i, name in enumerate(model.sources)}


def to_analysis(stem: np.ndarray, sr_in: int = STEM_SR, sr_out: int = 22050) -> np.ndarray:
    """스템(2×N @44.1k) → 모노 @22050.

    **모노 다운믹스 → 리샘플 순서**를 지킨다. `librosa.load(sr=…, mono=True)`가
    내부에서 하는 순서와 같게 맞춘 것이다 — 순서를 바꾸면 스템 축과 기존 축이
    부동소수 말단에서 갈리고, 그러면 둘을 같은 표에 올릴 수 없다(RULES §3.8.1).
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    y = np.asarray(stem, dtype=np.float32)
    mono = librosa.to_mono(y) if y.ndim == 2 else y
    if sr_in == sr_out:
        return np.asarray(mono, dtype=np.float32)
    return np.asarray(librosa.resample(mono, orig_sr=sr_in, target_sr=sr_out), dtype=np.float32)


def _band_onset_env(y: np.ndarray, sr: int, lo: float, hi: float | None) -> np.ndarray:
    """대역 제한 온셋 포락 — `rhythm.kick_envelope`와 **같은 방식**, 대역만 다르다."""
    import librosa  # type: ignore

    S = np.abs(librosa.stft(y, hop_length=HOP, n_fft=2048)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    rows = freqs >= lo
    if hi is not None:
        rows &= freqs < hi
    if not rows.any():
        raise StemsUnavailable(f"empty band {lo}~{hi}Hz at sr={sr}")
    return librosa.onset.onset_strength(
        S=librosa.power_to_db(S[rows] + 1e-10), sr=sr, hop_length=HOP
    )


def _f0(y: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
    import librosa  # type: ignore

    f0, _voiced, _prob = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr, hop_length=F0_HOP, frame_length=F0_HOP * 4
    )
    return np.asarray(f0, dtype=np.float64)


def extract_stem_features(
    y_stereo44: np.ndarray,
    downbeats: np.ndarray,
    *,
    min_ratio: float = HALFTIME_MIN_RATIO_DEFAULT,
    min_st_per_sec: float = BASS_GLIDE_MIN_ST_PER_SEC_DEFAULT,
    min_ms: float = BASS_GLIDE_MIN_MS_DEFAULT,
    min_contrast: float = SNARE_MIN_CONTRAST_DEFAULT,
    sr_out: int = 22050,
) -> dict[str, Any]:
    """스템 축 전부. 실패한 축은 **결측**으로 남기고 나머지를 계속 낸다(§0).

    `downbeats`는 rhythm 경로가 이미 구한 것을 받는다 — 스템에서 다시 비트를
    추적하면 마디 격자가 두 개가 되어 `kick_bar_profile`과 비교가 안 된다.
    """
    import librosa  # type: ignore

    stems = separate(y_stereo44, STEM_SR)
    axes: dict[str, Any] = {}

    # ── 드럼 스템: 하프타임 스네어 (RULES §3.8.2)
    try:
        drums = to_analysis(stems["drums"], sr_out=sr_out)
        env = _band_onset_env(drums, sr_out, *SNARE_BAND)
        prof = bar_profile(env, sr_out, downbeats)
        contrast = bar_profile_contrast(prof)
        axes["snare_bar_profile"] = [round(float(v), 6) for v in prof]
        axes["snare_bar_contrast"] = round(contrast, 4)
        axes["halftime_snare_ratio"] = halftime_snare_ratio(prof)
        axes["snare_backbeat_ratio"] = snare_backbeat_ratio(prof)
        axes["halftime_snare"] = (
            None if axes["halftime_snare_ratio"] is None
            else bool(axes["halftime_snare_ratio"] >= min_ratio)
        )
        axes = apply_snare_gate(axes, contrast, min_contrast=min_contrast)
        hi_env = _band_onset_env(drums, sr_out, HIHAT_MIN_HZ, None)
        peaks = librosa.util.peak_pick(
            hi_env, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.2, wait=2
        )
        dur = len(drums) / float(sr_out)
        axes["drum_onset_rate_high"] = round(len(peaks) / dur, 4) if dur > 0 else None
    except (RhythmUnavailable, StemsUnavailable, KeyError) as exc:
        axes["snare_unresolved"] = str(exc)

    # ── 베이스 스템: 슬라이딩 808 (RULES §3.8.3)
    try:
        bass = to_analysis(stems["bass"], sr_out=sr_out)
        f0 = _f0(bass, sr_out, *BASS_F0_RANGE)
        frame_s = F0_HOP / float(sr_out)
        axes["bass_glide_ratio"] = bass_glide_ratio(
            f0, frame_s, min_st_per_sec=min_st_per_sec, min_ms=min_ms
        )
        axes["bass_f0_range_st"] = f0_range_st(f0)
        # `bass_note_stability`는 철회됐다(RULES §3.8.4.1) — pyin의 주파수 격자가
        # 값을 지배해 123곡에서 고유값이 9개뿐이었고, 해상도를 올려도 값이 수렴하지
        # 않았다. 방출하지 않는다: 레코드에 남아 있으면 언젠가 인용된다.
    except (StemsUnavailable, KeyError) as exc:
        axes["bass_unresolved"] = str(exc)

    # ── 보컬 스템: 보컬 처리 (RULES §3.8.4)
    try:
        vocals = to_analysis(stems["vocals"], sr_out=sr_out)
        mix = to_analysis(np.asarray(y_stereo44, dtype=np.float32), sr_out=sr_out)
        v_rms = librosa.feature.rms(y=vocals, hop_length=F0_HOP)[0]
        m_rms = librosa.feature.rms(y=mix, hop_length=F0_HOP)[0]
        n = min(v_rms.size, m_rms.size)
        ref = float(np.median(m_rms[:n])) or _EPS
        axes["vocal_presence_ratio"] = round(
            float(np.mean(v_rms[:n] >= 0.1 * ref)), 4
        ) if n else None
        f0v = _f0(vocals, sr_out, *VOCAL_F0_RANGE)
        frame_s = F0_HOP / float(sr_out)
        # `vocal_tuning_hardness`도 같은 이유로 철회(RULES §3.8.4.1).
        axes["vocal_vibrato_strength"] = vibrato_strength(f0v, frame_s)
        voiced = f0v[np.isfinite(f0v) & (f0v > 0)]
        cent = librosa.feature.spectral_centroid(y=vocals, sr=sr_out, hop_length=F0_HOP)[0]
        axes["vocal_pitch_shift_proxy"] = pitch_shift_proxy(
            float(np.median(cent)) if cent.size else None,
            float(np.median(voiced)) if voiced.size else None,
        )
    except (StemsUnavailable, KeyError) as exc:
        axes["vocal_unresolved"] = str(exc)

    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in axes.items()}


def stem_provenance() -> dict[str, Any]:
    return {
        "stem_model": STEM_MODEL,
        "stem_set": STEM_SET,
        "stem_sr": STEM_SR,
        "stem_sources": ["drums", "bass", "other", "vocals"],
    }


# ─────────────────────────────────────────── selftest (TESTS §7.2.1)


def selftest_stems() -> tuple[int, list[str]]:
    """합성 픽스처 — 네트워크 0 · 모델 0. 정답을 아는 신호만 쓴다."""
    failures: list[str] = []
    ran = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal ran
        ran += 1
        print(f"  {'PASS' if ok else 'FAIL'} {name}{f'  ({detail})' if detail else ''}")
        if not ok:
            failures.append(name)

    def prof(*bins_on: int) -> np.ndarray:
        p = np.zeros(BINS)
        for b in bins_on:
            p[b] = 1.0
        return p / p.sum()

    # ── 하프타임 스네어
    r_back = halftime_snare_ratio(prof(4, 12))
    check("halftime 하한(백비트 4·12만)", r_back == 0.0, f"{r_back}")
    r_half = halftime_snare_ratio(prof(8))
    check("halftime 분모 0 → 미해석", r_half is None, f"{r_half}")
    r_even = halftime_snare_ratio(prof(4, 8, 12))
    check("halftime 기준점(4·8·12 균등)=0.5", r_even == 0.5, f"{r_even}")
    b_back, b_half = snare_backbeat_ratio(prof(4, 12)), snare_backbeat_ratio(prof(8))
    check("backbeat 대칭(백비트 1.0 ↔ 하프타임 0.0)",
          b_back == 1.0 and b_half == 0.0, f"{b_back} / {b_half}")

    # ── 유효성 게이트가 실제로 떨어뜨리는가
    axes = {"halftime_snare_ratio": 0.5, "snare_backbeat_ratio": 0.5}
    gated = apply_snare_gate(dict(axes), 1.0, min_contrast=SNARE_MIN_CONTRAST_DEFAULT)
    kept = apply_snare_gate(dict(axes), 2.0, min_contrast=SNARE_MIN_CONTRAST_DEFAULT)
    check("유효성 게이트: 균일 프로파일은 결측",
          gated["halftime_snare_ratio"] is None and gated["snare_backbeat_ratio"] is None
          and gated.get("snare_axes_gated") is True)
    check("유효성 게이트: 대비 충분하면 유지", kept["halftime_snare_ratio"] == 0.5)

    # ── 슬라이딩 808
    frame_s = F0_HOP / 22050.0                       # ≈23.2ms
    n = 200
    fixed = np.full(n, 55.0)
    check("glide 하한(고정 f0)", bass_glide_ratio(fixed, frame_s) == 0.0)
    # 기울기 ≫ 6 st/s여야 한다. 48세미톤 ÷ (n-1)프레임 × 43프레임/초 ≈ 21 st/s.
    # (처음 24세미톤/200프레임으로 잡았더니 5.2 st/s라 임계 아래였다 — 픽스처가
    #  "≫ G"라는 자기 선언을 안 지키고 있었다.)
    sweep = 55.0 * 2 ** (np.linspace(0, 4, n // 2))
    r_sweep = bass_glide_ratio(sweep, frame_s)
    check("glide 상한(선형 스윕 ≈21 st/s)", r_sweep is not None and r_sweep > 0.95, f"{r_sweep}")
    # 계단형: 40프레임마다 5세미톤 점프 — 미끄러지지 않으므로 세지 않는다
    steps = 55.0 * 2 ** (np.repeat(np.arange(5) * 5.0, n // 5) / 12.0)
    r_step = bass_glide_ratio(steps, frame_s)
    check("glide 온셋 배제(계단형 음 이동)", r_step == 0.0, f"{r_step}")
    # 옥타브 오류: 한 프레임만 2배로 튄다
    oct_err = np.full(n, 55.0)
    oct_err[100] = 110.0
    r_oct = bass_glide_ratio(oct_err, frame_s)
    check("glide 옥타브 오류 내성", r_oct == 0.0, f"{r_oct}")

    # ── 격자 밀착 (베이스 안정도 = 보컬 하드튠, 같은 계산)
    on_grid = 440.0 * 2 ** (np.arange(n) % 12 / 12.0)
    off_grid = on_grid * 2 ** (50.0 / 1200.0)        # 50센트 = 최대 이탈
    a_on, a_off = grid_adherence(on_grid), grid_adherence(off_grid)
    check("격자 밀착 상한(정확히 격자 위)", a_on is not None and a_on > 0.999, f"{a_on}")
    check("격자 밀착 하한(50센트 이탈)", a_off is not None and a_off < 0.001, f"{a_off}")
    s_sweep, s_fixed = grid_adherence(sweep), grid_adherence(fixed)
    check("note_stability 대칭(스윕 < 고정음)",
          s_sweep is not None and s_fixed is not None and s_sweep < s_fixed,
          f"{s_sweep} < {s_fixed}")

    # ── 비브라토: 대역(4~8Hz)을 실제로 고르는가. 같은 깊이의 1Hz 흔들림을 대조군으로
    # 둔다 — "변조 있음/없음"이 아니라 **대역 선택성**이 이 축의 주장이기 때문이다.
    t = np.arange(512) * frame_s
    vib = 220.0 * 2 ** (0.3 * np.sin(2 * np.pi * 6.0 * t) / 12.0)
    slow = 220.0 * 2 ** (0.3 * np.sin(2 * np.pi * 1.0 * t) / 12.0)
    v_on, v_off = vibrato_strength(vib, frame_s), vibrato_strength(slow, frame_s)
    check("비브라토 6Hz ≫ 같은 깊이 1Hz(대역 선택성)",
          v_on is not None and v_off is not None and v_on > 0.8 and v_on > 5 * v_off,
          f"{v_on} vs {v_off}")
    # 완전 직선 f0는 변조가 **없는** 것이지 0이 아니다 — 결측으로 남아야 한다(§0).
    straight = np.full(t.size, 220.0) * 2 ** (np.linspace(0, 0.02, t.size) / 12.0)
    check("무변조 f0 → 미해석(0으로 채우지 않는다)",
          vibrato_strength(straight, frame_s) is None)

    # ── 결측 규율
    check("f0 전건 무성 → 미해석",
          grid_adherence(np.full(10, np.nan)) is None
          and bass_glide_ratio(np.full(10, np.nan), frame_s) is None)
    check("프록시 분모 0 → 미해석",
          pitch_shift_proxy(1000.0, 0.0) is None and pitch_shift_proxy(None, 200.0) is None)

    return ran, failures


def selftest_no_persist(sr: int = STEM_SR) -> tuple[int, list[str]]:
    """무보관 불변식 — 분리가 임시 파일을 남기지 않는가 (모델 필요, opt-in)."""
    import tempfile
    from pathlib import Path

    failures: list[str] = []
    tmp = Path(tempfile.gettempdir())
    before = {p.name for p in tmp.glob("*") if p.is_file()}
    t = np.arange(sr * 2) / sr
    y = np.vstack([np.sin(2 * np.pi * 110 * t), np.sin(2 * np.pi * 220 * t)]).astype(np.float32)
    stems = separate(y * 0.3, sr)
    after = {p.name for p in tmp.glob("*") if p.is_file()}
    leaked = sorted(after - before)
    ok_sources = set(stems) == {"drums", "bass", "other", "vocals"}
    print(f"  {'PASS' if ok_sources else 'FAIL'} 4스템 반환  ({sorted(stems)})")
    if not ok_sources:
        failures.append("4스템 반환")
    print(f"  {'PASS' if not leaked else 'FAIL'} 무보관: 임시 파일 0개  ({leaked or 'none'})")
    if leaked:
        failures.append("무보관")
    return 2, failures
