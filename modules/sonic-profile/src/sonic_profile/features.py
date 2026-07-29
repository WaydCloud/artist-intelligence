"""소리 지표 엔진 — 순수·결정적. RULES §3 기준 원장의 코드측 구현.

이 모듈은 **오디오 배열만** 받는다(파일 경로도, 네트워크도 모른다). 무보관 불변식은
호출자(preview.py)가 지키고, 여기는 "같은 배열 → 같은 값"만 책임진다.

원칙(RULES §3): **정의가 곧 설명인 지표만** 낸다. 사전학습 분류기의 점수는 원장에
올릴 근거를 댈 수 없으므로 쓰지 않는다.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

SR = 22050  # 고정 — 바꾸면 과거 값과 비교 불가(RULES §2, provenance에 기록)
# 지표 집합 버전. **지표를 늘리거나 정의를 바꾸면 올린다** — 캐시 키의 일부라(cli.py
# `engine_key`) 올리지 않으면 캐시 적중으로 새 지표가 빠진 레코드가 되살아난다.
#   v2 = D-031 (loudness_lufs · spectral_flatness · stereo_width 추가)
#   v3 = D-032 (T0-b DSP 묶음 — 스테레오 상세 · LRA · 프로덕션 QC · 밴드별 crest ·
#               스펙트럼 상세 · 화성 상세)
FEATURE_SET = "v3"
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


def _k_weight(y: np.ndarray, sr: int) -> np.ndarray:
    """BS.1770 K-weighting 적용. LUFS와 LRA가 **같은 필터**를 써야 서로 비교된다."""
    import scipy.signal as sps  # type: ignore  # librosa가 이미 끌고 오는 의존성

    x = np.asarray(y, dtype=np.float64)
    for b, a in (_biquad_shelf(*_KW_SHELF, sr), _biquad_hpf(_KW_HPF[1], _KW_HPF[2], sr)):
        # `zi` 없이 부르면 배열 하나만 돌아온다 — 타입체커가 (y, zf) 튜플로도 보므로 명시한다
        x = np.asarray(sps.lfilter(b, a, x), dtype=np.float64)
    return x


def _block_loudness(x: np.ndarray, sr: int, window_s: float, hop_s: float) -> np.ndarray:
    """K-weighted 신호 → 블록별 LUFS 배열. 무음 블록은 제외한다(−inf를 만들지 않는다)."""
    block, step = round(window_s * sr), max(1, round(hop_s * sr))
    if x.size < block:
        raise Unresolved(f"too short for {window_s}s blocks ({x.size} < {block})")
    power = np.array([float(np.mean(np.square(x[s : s + block])))
                      for s in range(0, x.size - block + 1, step)])
    power = power[power > 0.0]
    if power.size == 0:
        raise Unresolved("silent after K-weighting")
    return _LUFS_OFFSET + 10.0 * np.log10(power)


def _loudness_range_lu(x: np.ndarray, sr: int) -> float:
    """EBU R128 라우드니스 레인지(LU) — 단기 라우드니스의 **P95 − P10**.

    `crest_factor_db`와 다른 것을 잰다: crest는 **순간** peak/RMS이고 LRA는 **곡 안의
    기복**이다. 압축이 강해도(crest 낮음) 조용한 벌스와 큰 훅이 있으면 LRA는 크다.
    """
    st = _block_loudness(x, sr, 3.0, 1.0)          # 단기 3초 · 1초 홉
    st = st[st > _LUFS_ABS_GATE]
    if st.size < 2:
        raise Unresolved("not enough short-term blocks")
    rel = float(np.mean(st)) - 20.0                 # 상대 게이트 −20 LU
    st = st[st > rel]
    if st.size < 2:
        raise Unresolved("all short-term blocks gated out")
    return float(np.percentile(st, 95) - np.percentile(st, 10))


def _loudness_lufs(y: np.ndarray, sr: int) -> float:
    """ITU-R BS.1770-4 게이팅 통합 라우드니스(LUFS). 모노 = 채널 가중 1.0.

    **주의(RULES §3)**: 우리 입력은 `sr=22050`의 30초 발췌라 마스터링 스위트의 전곡
    LUFS 판독과 같은 수가 아니다. 11kHz 위 대역이 애초에 없어 K-weighting이 셀 것이
    빠져 있다. **곡 간 상대 축으로만** 쓴다.
    """
    x = _k_weight(y, sr)
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


# 밴드 경계 (Hz) — 저역/중역/고역. 저역 상한은 킥·베이스 대역(RULES §3.1.5 KICK_BAND 상한과
# 같은 120Hz가 아니라 250Hz다: 여기는 온셋이 아니라 **에너지 분포**를 보므로 관용 대역을 쓴다).
BANDS: tuple[tuple[str, float, float], ...] = (("low", 20.0, 250.0),
                                               ("mid", 250.0, 2000.0),
                                               ("high", 2000.0, 11025.0))


def stereo_detail(y_stereo: np.ndarray, sr: int) -> dict[str, Any]:
    """스테레오 축 묶음 — 밴드별 폭 · 위상 상관 · 폭의 시간 변동(RULES §3.7).

    **저역 모노성이 이 묶음의 요점이다.** 클럽 재생·바이닐 커팅 규범상 저역은 모노로
    모으는 것이 관행이라, `stereo_width` 하나로는 안 보이던 프로덕션 규범이 밴드로 갈라야
    드러난다. 위상 상관이 음수면 모노 합산에서 **상쇄**가 일어난다(재생 환경 위험).
    """
    a = np.asarray(y_stereo, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != 2 or a.shape[1] < 64:
        return {}
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    left, right = a[0], a[1]
    out: dict[str, Any] = {}

    # 위상 상관 (−1 ~ 1). −1이면 완전 역위상 = 모노에서 사라진다
    ls, rs = float(np.std(left)), float(np.std(right))
    if ls > _EPS and rs > _EPS:
        out["phase_correlation"] = round(float(np.corrcoef(left, right)[0, 1]), 4)

    hop = 512
    ml = np.abs(librosa.stft((left + right) / 2.0, hop_length=hop))
    sd = np.abs(librosa.stft((left - right) / 2.0, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2 * (ml.shape[0] - 1))
    for name, lo, hi in BANDS:
        rows = (freqs >= lo) & (freqs < hi)
        if not rows.any():
            continue
        em = float(np.sum(ml[rows] ** 2))
        es = float(np.sum(sd[rows] ** 2))
        if em + es > _EPS:
            out[f"stereo_width_{name}"] = round(es / (em + es), 4)

    # 폭의 시간 변동 — 정적 이미징 vs 움직이는 이미징
    fm = np.sum(ml**2, axis=0)
    fs = np.sum(sd**2, axis=0)
    denom = fm + fs
    ok = denom > _EPS
    if int(np.count_nonzero(ok)) > 1:
        out["stereo_width_var"] = round(float(np.std(fs[ok] / denom[ok])), 4)
    return out


def production_qc(y: np.ndarray, sr: int, peak: float) -> dict[str, Any]:
    """프로덕션 결함 축 — 트루 피크 · 클리핑 · DC 오프셋 · 무음 비율(RULES §3.7).

    지표라기보다 **품질 플래그**다. 값이 이상하면 그 곡의 다른 지표도 의심해야 한다 —
    클리핑된 소스는 crest·flatness를 함께 왜곡한다.
    """
    out: dict[str, Any] = {}
    x = np.asarray(y, dtype=np.float64)
    if x.size == 0:
        return out
    out["dc_offset"] = round(float(np.mean(x)), 6)
    # **"클리핑"이 아니라 "0dBFS 초과"다.** 손실 압축을 디코드하면 원본이 멀쩡해도 표본이
    # 1.0을 넘는다(인터샘플 피크). 실측에서 코르티스가 peak +3.18dB · 초과 9%였고 말러·
    # 사티·재즈는 0%였다 — 즉 이 값은 결함 플래그가 아니라 **리미팅 강도의 지표**다.
    # 결함으로 읽으면 "현대 마스터는 전부 망가졌다"는 잘못된 결론이 나온다.
    out["over_unity_ratio"] = round(float(np.mean(np.abs(x) > 1.0)), 6)
    if peak > _EPS:
        out["peak_dbfs"] = round(float(20.0 * np.log10(peak)), 2)
    # 무음 비율 — 발췌 품질(앞뒤가 잘렸는지)
    frame = max(1, sr // 100)
    n = (x.size // frame) * frame
    if n:
        rms = np.sqrt(np.mean(np.square(x[:n].reshape(-1, frame)), axis=1))
        out["silence_ratio"] = round(float(np.mean(rms < 1e-4)), 4)
    return out


def band_dynamics(stft: np.ndarray, freqs: np.ndarray) -> dict[str, Any]:
    """밴드별 crest (dB) — **어느 대역이 압축됐나**(멀티밴드 컴프의 흔적, RULES §3.7).

    전체 crest 하나로는 "저역만 눌린" 현대 마스터와 "전대역 균일 압축"을 구별하지 못한다.
    """
    out: dict[str, Any] = {}
    for name, lo, hi in BANDS:
        rows = (freqs >= lo) & (freqs < hi)
        if not rows.any():
            continue
        env = np.sqrt(np.sum(stft[rows] ** 2, axis=0))
        m = float(np.sqrt(np.mean(np.square(env))))
        p = float(np.max(env)) if env.size else 0.0
        if m > _EPS and p > _EPS:
            out[f"crest_{name}_db"] = round(float(20.0 * np.log10(p / m)), 2)
    return out


def spectral_detail(y: np.ndarray, sr: int, stft: np.ndarray, freqs: np.ndarray) -> dict[str, Any]:
    """스펙트럼·음색 축 묶음(RULES §3.7).

    `brightness_hz`(중심)·`spectral_flatness`(톤성)가 못 보는 것들: 골짜기 구조(contrast),
    분포 폭(bandwidth)·형태(왜도·첨도), 변화 속도(flux), 음색 지문(MFCC).
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    out: dict[str, Any] = {}
    power = stft**2
    total = float(np.sum(power))

    # 밴드별 피크–밸리 대비. 벡터를 그대로 남긴다(재계산 가능성, §3.1.5와 같은 규율)
    contrast = librosa.feature.spectral_contrast(S=stft, sr=sr)
    out["spectral_contrast"] = [round(float(v), 3) for v in np.median(contrast, axis=1)]
    out["spectral_contrast_mean"] = round(float(np.mean(contrast)), 3)

    out["spectral_bandwidth_hz"] = round(
        float(np.median(librosa.feature.spectral_bandwidth(S=stft, sr=sr))), 1)
    out["zero_crossing_rate"] = round(
        float(np.median(librosa.feature.zero_crossing_rate(y))), 5)

    # 프레임 간 스펙트럼 변화량 — 온셋 '개수'가 아니라 '변화의 크기'
    if stft.shape[1] > 1:
        norm = stft / (np.sum(stft, axis=0, keepdims=True) + _EPS)
        out["spectral_flux"] = round(float(np.median(np.sum(np.diff(norm, axis=1) ** 2, axis=0))), 6)

    # 스펙트럼 분포의 형태 (주파수 축 모멘트)
    if total > _EPS:
        p = np.sum(power, axis=1)
        p = p / float(np.sum(p))
        mu = float(np.sum(freqs * p))
        var = float(np.sum(((freqs - mu) ** 2) * p))
        if var > _EPS:
            sd = math.sqrt(var)
            out["spectral_skewness"] = round(float(np.sum(((freqs - mu) / sd) ** 3 * p)), 4)
            out["spectral_kurtosis"] = round(float(np.sum(((freqs - mu) / sd) ** 4 * p)), 4)
        nz = p[p > 0]
        if nz.size > 1:
            out["spectral_entropy"] = round(
                float(-np.sum(nz * np.log(nz)) / math.log(nz.size)), 4)
        # 저역 안에서의 중심 — 808 튜닝 대역
        low = freqs < 150.0
        lp = np.sum(power[low], axis=1)
        if float(np.sum(lp)) > _EPS:
            out["low_centroid_hz"] = round(float(np.sum(freqs[low] * lp) / np.sum(lp)), 2)
        out["high_energy_ratio"] = round(float(np.sum(power[freqs >= 5000.0]) / total), 5)

    # 음색 지문 — 곡 간 유사도의 고전적 기반. 벡터로 남긴다
    mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    out["mfcc_mean"] = [round(float(v), 2) for v in np.mean(mf, axis=1)]
    out["mfcc_std"] = [round(float(v), 2) for v in np.std(mf, axis=1)]
    return out


def harmonic_detail(y: np.ndarray, sr: int) -> dict[str, Any]:
    """화성 축 묶음 — tonnetz · 화성 변화율 · chroma 엔트로피 · 조성 안정성(RULES §3.7).

    `key_mode`는 추정 정확도가 낮아 집계 전용인데(§3), 이 축들은 **절대 조성을 몰라도**
    성립한다 — 변화율·엔트로피·안정성은 상대량이라 조 추정 오류에 견고하다.
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    out: dict[str, Any] = {}
    harm = librosa.effects.harmonic(y)
    chroma = librosa.feature.chroma_cqt(y=harm, sr=sr)
    if chroma.size == 0:
        return out

    ton = librosa.feature.tonnetz(chroma=chroma)
    out["tonnetz"] = [round(float(v), 4) for v in np.mean(ton, axis=1)]
    if ton.shape[1] > 1:
        # HCDF — 조성 중심의 이동 속도 = 코드 전환 밀도의 프록시
        out["harmonic_change_rate"] = round(
            float(np.median(np.linalg.norm(np.diff(ton, axis=1), axis=0))), 5)

    prof = np.mean(chroma, axis=1)
    s = float(np.sum(prof))
    if s > _EPS:
        p = prof / s
        nz = p[p > 0]
        if nz.size > 1:
            out["chroma_entropy"] = round(float(-np.sum(nz * np.log(nz)) / math.log(nz.size)), 4)

    # 조성 안정성 — 구간별 chroma 최강음이 얼마나 유지되는가(조바꿈 빈도의 프록시)
    seg = max(1, chroma.shape[1] // 6)
    tops = [int(np.argmax(np.mean(chroma[:, i : i + seg], axis=1)))
            for i in range(0, chroma.shape[1] - seg + 1, seg)]
    if len(tops) > 1:
        out["key_stability"] = round(float(max(tops.count(t) for t in set(tops)) / len(tops)), 4)
    return out


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
        lra: float | None = round(_loudness_range_lu(_k_weight(y, sr), sr), 2)
    except Unresolved:
        lra = None

    # 축 묶음(RULES §3.7). **한 묶음이 실패해도 나머지는 낸다** — 결측은 사유와 함께 비운다.
    extra: dict[str, Any] = {}
    for name, fn in (
        ("spectral", lambda: spectral_detail(y, sr, stft, freqs)),
        ("harmonic", lambda: harmonic_detail(y, sr)),
        ("band", lambda: band_dynamics(stft, freqs)),
        ("qc", lambda: production_qc(y, sr, peak)),
        ("stereo", lambda: {} if stereo is None else stereo_detail(stereo, sr)),
    ):
        try:
            extra.update(fn())
        except Exception as exc:  # noqa: BLE001 — 한 축의 실패가 전체를 죽이지 않는다
            extra[f"{name}_unresolved"] = f"{type(exc).__name__}: {exc}"[:120]

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
        # LRA는 crest와 **다른 것**을 잰다: crest=순간 peak/RMS, LRA=곡 안의 기복
        "loudness_range_lu": lra,
        "spectral_flatness": round(flatness, 4),
        "stereo_width": width,
        **extra,
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
