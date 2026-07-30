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

from fractions import Fraction
from itertools import pairwise
from typing import Any

import numpy as np

# 격자·프레임 예산은 함께 정해진다 — 칸을 두 배로 쪼개면 프레임도 두 배로 쪼개야 한다.
# 실측(RULES §3.1.5.2): HOP 256·32칸은 p95 BPM에서 칸당 4.3프레임으로 온셋 포락 평활
# 폭에 먹힌다. HOP 128·32칸이 옛 HOP 256·16칸과 **같은 8.6프레임**이다.
HOP = 128          # 32분음 해상도용 (5.8ms). ⚠ 256에서 내렸다 — 포락 파생 축 전부 값이 바뀐다
BINS = 32          # 마디를 32분음 32칸으로 (D-038)
TRIPLET_BINS = 24  # 트리플렛은 이진 격자에서 원리적으로 안 보인다(32/3 비정수) — 별개 격자
LEGACY_BINS = 16   # 2026-07-30 이전 저장 형식. 32 → 16 접기로만 비교한다(올리지 않는다)
KICK_BAND = (20.0, 120.0)
HIHAT_MIN_HZ = 6000.0   # 하이햇 축(RULES §3.1.5.3) — 믹스 고역. 스템이 필요 없다
MIN_DOWNBEATS = 3

# RULES §3.1.5 템플릿 원장 — **마디 상대 위치(분수)**. **값은 도메인 소유자 소유.**
#
# 칸 번호가 아니라 분수인 이유(2026-07-30 형식 수정): 칸으로 적으면 격자를 바꿀 때마다
# 원장을 손으로 다시 써야 하고 그 과정에서 이름과 근거가 어긋난다 — 실제로 2026-07-29
# 이전 산출은 두 tresillo의 이름·근거가 뒤바뀐 채 저장돼 있었다(D-027). 분수는 격자와
# 무관한 음악적 사실이고, 격자에 렌더하는 것은 `render_template`이 한다.
TEMPLATES: dict[str, tuple[Fraction, ...]] = {
    "four-on-floor": (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
    "backbeat(1·3)": (Fraction(0), Fraction(1, 2)),
    "tresillo(8분 3+3+2)": (Fraction(0), Fraction(3, 8), Fraction(3, 4)),
    # 🔴 `tresillo(16분·반마디)`(0, 3/16, 3/8)는 **제거됐다**(2026-07-30 승인, RULES §3.1.5
    # 결함 ①). 관용 패턴이 아닌 반마디 조각이고 — 마디 끝까지 이으면 dembow와 같은 벡터가
    # 된다 — `trap-synco`와의 상관이 16칸 0.832에서 **32칸 0.851로 더 나빠졌다**. 두 이름이
    # 같은 것을 재고 있었다. 제거 후 최악 쌍은 0.683(four-on-floor ↔ backbeat, 정박 공유라
    # 음악적으로 당연한 것)이다. 배정 5곡은 저장 프로파일에서 **재계산으로 자동 재배정**된다.
    "dembow": (Fraction(0), Fraction(3, 16), Fraction(3, 8), Fraction(1, 2),
               Fraction(11, 16), Fraction(7, 8)),
    "trap-synco": (Fraction(0), Fraction(3, 16), Fraction(3, 8), Fraction(5, 8)),
}

# 하중받는 기준 — **관습 기본값이며 도메인 소유자(A&R)가 재조정한다**(RULES §3.1.5 원장).
# θ가 없으면 argmax가 언제나 이름을 뱉어 음의 상관도 "가장 가까운 유형"이 된다.
MIN_MATCH_DEFAULT = 0.30
TIE_GAP_DEFAULT = 0.05
NO_MATCH = "해당 없음"

# 리듬 산출 집합의 버전 — 늘리면 올린다(캐시 키의 일부, cli.py `engine_key`).
#   v2 = D-031 (grid_deviation_ms · syncopation_ratio · bar_profile_contrast)
#   v3 = D-032 (스윙·IOI 엔트로피·어택·다운비트 강도·마디 자기유사도·템포그램비·밴드별 온셋)
#   v4 = D-038 (마디 격자 32칸 + 트리플렛 24칸 · HOP 128 · 하이햇 축 · 반쪽 재현성)
#        ⚠ HOP이 바뀌어 **포락 파생 축 전부**(onset_rate·swing·IOI·어택·자기유사도·
#        대역별 온셋률)의 값이 v3과 다르다. 캐시가 적중하면 옛 값이 새 축과 섞이므로
#        이 키를 올리는 것이 필수다(D-031 절단본 함정과 같은 구조).
RHYTHM_FEATURE_SET = "v4"

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


def band_onset_env(y: np.ndarray, sr: int, lo: float, hi: float | None) -> np.ndarray:
    """대역 제한 온셋 포락 — **이 모듈의 모든 대역 축이 이 함수를 쓴다.**

    킥(저역)·하이햇(고역)·스네어(중역, 스템)가 같은 방식으로 계산돼야 프로파일끼리
    비교할 수 있다. 두 벌이 되면 대역만 다른 축이 조용히 다른 것을 재게 된다(AGENTS §1
    — `stems.py`가 갖고 있던 사본을 이 함수로 합쳤다).
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    S = np.abs(librosa.stft(y, hop_length=HOP, n_fft=2048)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    rows = freqs >= lo
    if hi is not None:
        rows &= freqs < hi
    if not rows.any():
        raise RhythmUnavailable(f"empty band {lo}~{hi}Hz at sr={sr}")
    return librosa.onset.onset_strength(S=librosa.power_to_db(S[rows] + 1e-10), sr=sr,
                                        hop_length=HOP)


def kick_envelope(y: np.ndarray, sr: int) -> np.ndarray:
    """저역(20~120Hz) 온셋 포락 — 킥/808."""
    return band_onset_env(y, sr, *KICK_BAND)


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


def render_template(positions: tuple[Fraction, ...], bins: int) -> np.ndarray | None:
    """마디 상대 위치(분수) → `bins`칸 지시 벡터. **표현 불가면 None.**

    위치×칸수가 정수가 아니면 그 템플릿은 그 격자에서 표현될 수 없다(예: 트리플렛 ⅓은
    32칸에서 10.67칸). **반올림해 흘리지 않는다** — 앨리어싱된 템플릿과의 정합도는
    음악이 아니라 반올림 오차를 재는 것이고, 그걸 조용히 내면 그 사실이 소실된다
    (RULES §3.1.5.2).
    """
    t = np.zeros(bins, dtype=np.float64)
    for pos in positions:
        scaled = pos * bins
        if scaled.denominator != 1:
            return None
        t[int(scaled) % bins] = 1.0
    return t


def fold_profile(profile: np.ndarray | list[float], bins: int) -> np.ndarray:
    """세밀한 격자 → 거친 격자로 **정확히 접는다**(인접 칸 합, 무손실).

    32칸은 16칸으로 접히지만 그 역은 없다 — 없는 정보를 만드는 것이다(RULES §3.1.5.2).
    그래서 옛 레코드와 새 레코드를 함께 볼 때는 **내려 맞춘다.**
    """
    p = np.asarray(profile, dtype=np.float64)
    if p.size == bins:
        return p
    if p.size < bins or p.size % bins:
        raise RhythmUnavailable(f"cannot fold {p.size} bins into {bins}")
    return p.reshape(bins, p.size // bins).sum(axis=1)


def match_templates(profile: np.ndarray) -> dict[str, float]:
    """프로파일 × 명명 템플릿의 코사인 정합도(평균 제거 후).

    템플릿끼리 **직교하지 않는다** — 실측 최악 쌍이 0.83이다(RULES §3.1.5.1).
    따라서 최고 정합은 **판정이 아니라 순위**이고, 이 함수의 출력을 그대로
    `max()`에 넣으면 안 된다 — 임계·동점 처리는 `classify_rhythm`이 한다.

    격자에서 표현 불가한 템플릿은 **결과에서 빠진다**(0점으로 넣지 않는다 — 0점은
    "닮지 않았다"는 뜻이고 여기서 참인 것은 "재지 못했다"다, §0 결측 ≠ 0).
    """
    a = np.asarray(profile, dtype=np.float64)
    a = a - a.mean()
    na = float(np.linalg.norm(a))
    out: dict[str, float] = {}
    for name, positions in TEMPLATES.items():
        t = render_template(positions, len(a))
        if t is None:
            continue
        t = t - t.mean()
        nt = float(np.linalg.norm(t))
        out[name] = round(float(a @ t / (na * nt)) if na > 0 and nt > 0 else 0.0, 4)
    return out


def unrenderable_templates(bins: int) -> list[str]:
    """이 격자에서 표현할 수 없는 템플릿 이름 — 조용한 누락 금지(리포트가 병기한다)."""
    return [n for n, pos in TEMPLATES.items() if render_template(pos, bins) is None]


def hihat_roll_ratio(profile: np.ndarray | list[float]) -> float | None:
    """32칸에서 **16분 격자에 없는 칸**(홀수 칸)의 점유율 — RULES §3.1.5.3.

    16칸 격자에서는 이 값이 **정의상 0**이었다(32분 사건이 인접 16분 칸에 접혀
    들어갔다). 그게 하이햇 롤을 못 보던 이유다.
    """
    p = np.asarray(profile, dtype=np.float64)
    total = float(p.sum())
    if p.size < BINS or p.size % 2 or total <= 0:
        return None
    return float(p[1::2].sum() / total)


def hihat_active_ratio(profile: np.ndarray | list[float]) -> float | None:
    """활성 칸(균등 기대치 이상) 비율 — `hihat_roll_burst_ratio`의 **자기 진단 짝**.

    이 값이 높으면 하이햇이 상시로 깔린 곡이고, 그때 burst는 "롤"이 아니라
    "쉬지 않는 하이햇"을 재고 있다. 단독 해석 대상이 아니다(RULES §3.1.5.4).
    """
    p = np.asarray(profile, dtype=np.float64)
    total = float(p.sum())
    if p.size < BINS or total <= 0:
        return None
    return float((p >= total / p.size).sum() / p.size)


def hihat_roll_burst_ratio(profile: np.ndarray | list[float]) -> float | None:
    """활성 칸이 **3칸 이상 연속**인 구간에 든 에너지의 비중 — RULES §3.1.5.4.

    H1(`hihat_roll_ratio`)이 실패한 원인을 직접 겨눈다: 점유율은 **롤의 길이를
    재지 않아** 산발 32분과 연타 3칸을 구별하지 못한다. 롤은 점유율이 아니라
    **연속성**이다.

    · 활성 = `p[i] >= 1/bins`(균등 기대치). 격자에서 도출된 상수이며 다른 축에서
      빌려 온 임계가 아니다(D-037).
    · 런은 **마디를 순환**해서 센다 — 롤이 마디선을 넘어 이어질 수 있다.

    ⚠ 전 칸이 활성이면(상시 하이햇) 런이 마디 하나가 되어 1.0이 된다. 그건 롤이
    아니므로 `hihat_active_ratio`와 **함께** 읽어야 한다.
    """
    p = np.asarray(profile, dtype=np.float64)
    total = float(p.sum())
    if p.size < BINS or total <= 0:
        return None
    active = p >= total / p.size
    n = p.size
    if active.all():
        # 순환하면 런이 하나로 이어진다. 아래 일반 경로는 시작점을 찾지 못하므로 분기한다.
        return 1.0
    # 순환 런을 세려면 비활성 칸에서 시작해야 한다 — 그 지점부터 한 바퀴 돈다.
    start = int(np.flatnonzero(~active)[0])
    burst = 0.0
    run: list[int] = []
    for k in range(n + 1):
        i = (start + k) % n
        if k < n and active[i]:
            run.append(i)
            continue
        if len(run) >= 3:
            burst += float(p[run].sum())
        run = []
    return float(burst / total)


def backfill_hihat_axes(features: dict[str, Any]) -> dict[str, Any]:
    """**저장된 `hihat_bar_profile`에서** §3.1.5.4 축을 채운다 — 오디오 0.

    burst·active는 32칸 프로파일만의 함수이므로, 축이 정의되기 전에 취득한
    레코드도 **프리뷰를 다시 받지 않고** 소급할 수 있다 — D-031
    `syncopation_ratio` 소급 · `stems.regate_snare_axes`와 같은 경로다.

    · **프로파일이 없으면 되살리지 않는다**(결측 ≠ 0, §0).
    · **이미 있는 값은 덮지 않는다** — 저장 프로파일은 4자리로 반올림돼 있어
      재계산이 오디오 계산과 말단에서 갈린다(실측 101곡: 최대 2e-4 · 평균 2.2e-5).
      섞어 쓰면 같은 축이 두 정밀도를 갖게 되므로, 소급은 **빈 칸만** 채운다.
    · 멱등이다.
    """
    prof = features.get("hihat_bar_profile")
    if not isinstance(prof, list) or len(prof) < BINS:
        return dict(features)
    out = dict(features)
    for key, fn in (("hihat_roll_burst_ratio", hihat_roll_burst_ratio),
                    ("hihat_active_ratio", hihat_active_ratio)):
        if out.get(key) is None:
            v = fn(prof)
            if v is not None:
                out[key] = round(v, 4)
    return out


def hihat_triplet_bias(profile_triplet: np.ndarray | list[float]) -> float | None:
    """24칸 트리플렛 격자에서 `E(트리플렛 전용) / (E(트리플렛 전용) + E(8분 이진))`.

    24칸에서 8분음은 `i%3==0`(8칸), 8분 트리플렛은 `i%2==0`(12칸)이다. 둘의 교집합
    (`i%6==0`)은 이진에 귀속시키고, **트리플렛 전용**은 `i%2==0 and i%3!=0`(8칸)이다.
    0.5를 넘으면 3분할 우세 — 다만 0.5 근처는 "둘 다"가 아니라 **판별 불가**일 수 있다
    (이진 위치의 누출, RULES §3.1.5.3 한계).
    """
    p = np.asarray(profile_triplet, dtype=np.float64)
    if p.size != TRIPLET_BINS:
        return None
    idx = np.arange(p.size)
    trip = float(p[(idx % 2 == 0) & (idx % 3 != 0)].sum())
    binary = float(p[idx % 3 == 0].sum())
    denom = trip + binary
    if denom <= 1e-12:
        return None
    return float(trip / denom)


def bar_profile_split_half_2bar(env: np.ndarray, sr: int, downbeats: np.ndarray,
                                bins: int = BINS) -> float | None:
    """마디를 **2개씩 묶은 블록**의 홀↔짝 재현성 — RULES §3.1.5.4 ②.

    `bar_profile_split_half`는 홀짝 마디를 가르므로 **2마디 루프에서 실제 구조가
    있어도 낮게 나온다**(D-142에서 정답지 2곡이 그렇게 탈락했다). 2마디 루프는
    블록 안에서 완결되므로 두 반쪽이 같은 형태를 담는다.

    마디 수요가 두 배다 — 블록 2개(=4마디)를 못 채우면 결측이다(0이 아니다).
    """
    return _split_half(env, sr, downbeats, bins, block=2)


def bar_profile_split_half(env: np.ndarray, sr: int, downbeats: np.ndarray,
                           bins: int = BINS) -> float | None:
    """**홀수 마디 프로파일 ↔ 짝수 마디 프로파일**의 상관 — RULES §3.8.4.4.

    유효성 판정의 원리적 형식이다. 대비(max/mean)는 **한 번의 우연한 피크**로도
    높아지지만, 반쪽끼리의 재현성은 그럴 수 없다 — 반복되는 형태는 모든 마디에 있고
    표집 잡음은 반복되지 않는다.

    ⚠ **2마디 루프는 낮게 나온다**(홀짝이 루프의 서로 다른 절반을 담는다) — 이건 결함이
    아니라 이 축의 정의상 한계이며, `bar_half_asymmetry`와 함께 읽어야 한다.
    그 한계를 겨눈 것이 `bar_profile_split_half_2bar`다(RULES §3.1.5.4 ②).
    """
    return _split_half(env, sr, downbeats, bins, block=1)


def _split_half(env: np.ndarray, sr: int, downbeats: np.ndarray, bins: int,
                *, block: int) -> float | None:
    """반쪽 재현성의 공통 구현. `block`은 한 반쪽에 묶는 마디 수다.

    두 변형을 각각 구현하지 않는 이유: 분할 단위만 다르고 나머지(포락 접기·정규화·
    상관)가 같아서 따로 두면 한쪽만 고쳐지는 종류의 코드가 된다(AGENTS §1).
    """
    d = np.asarray(downbeats, dtype=np.float64)
    # 반쪽이 각 `block` 마디를 채우려면 마디가 2*block개 필요하고, 마디 n개에는
    # 다운비트가 n+1개 있어야 한다. block=1이면 예전 조건(MIN_DOWNBEATS+1)보다
    # 느슨해지지 않도록 둘 중 큰 쪽을 쓴다.
    need = max(MIN_DOWNBEATS + 1, 2 * block + 1)
    if d.size < need:
        return None
    times = np.arange(len(env)) * HOP / sr
    halves = [np.zeros(bins, dtype=np.float64), np.zeros(bins, dtype=np.float64)]
    for i, (a, b) in enumerate(pairwise(d)):
        if not (b > a):
            continue
        m = (times >= a) & (times < b)
        if not m.any():
            continue
        idx = np.floor((times[m] - a) / (b - a) * bins).astype(int) % bins
        np.add.at(halves[(i // block) % 2], idx, np.maximum(env[m], 0.0))
    if any(h.sum() <= 0 for h in halves):
        return None
    x, y = (h / h.sum() for h in halves)
    x, y = x - x.mean(), y - y.mean()
    nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
    if nx <= 0 or ny <= 0:
        return None
    return float(x @ y / (nx * ny))


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


def swing_ratio(beats: np.ndarray, onsets: np.ndarray) -> float | None:
    """비트 사이 온셋 위치의 중앙값 — 스윙/셔플 그루브의 **약한 프록시**(RULES §3.7).

    0.5 = 스트레이트, 0.66 근처 = 트리플렛 스윙. 템포에 무관한 상대값이다.

    ⚠ **온셋이 빽빽하면 0.5로 수렴한다**(2026-07-29 실측): 대조 표본에서 말러 0.676 ·
    70s록 0.670은 잡혔으나 **재즈 왈츠가 0.510으로 스트레이트하게 나왔다**. 비트 사이에
    온셋이 고르게 깔리면 중앙값이 중앙으로 끌려가기 때문이며, 이는 임계가 아니라 정의의
    한계다. **타악이 성긴 곡에서만 의미가 있고, 낮은 값을 "스트레이트"로 단정하면 안 된다.**
    """
    b = np.asarray(beats, dtype=np.float64)
    o = np.asarray(onsets, dtype=np.float64)
    if b.size < 4 or o.size < 4:
        return None
    pos: list[float] = []
    for a, c in pairwise(b):
        span = c - a
        if span <= 0:
            continue
        inner = o[(o > a + span * 0.2) & (o < c - span * 0.2)]
        pos.extend(float((t - a) / span) for t in inner)
    if len(pos) < 4:
        return None
    return float(np.median(pos))


def ioi_entropy(onsets: np.ndarray) -> float | None:
    """온셋 간격(IOI) 분포의 정규화 엔트로피 — 리듬 규칙성(0=기계적, 1=불규칙)."""
    o = np.asarray(onsets, dtype=np.float64)
    if o.size < 5:
        return None
    d = np.diff(o)
    d = d[d > 0]
    if d.size < 4:
        return None
    bins = min(12, d.size)
    hist, _ = np.histogram(d, bins=bins)
    p = hist[hist > 0] / float(hist.sum())
    # 한 칸에 다 몰리면 엔트로피는 **0이지 미해석이 아니다** — 완전히 규칙적인(기계적)
    # 리듬이 그 경우이며, 여기서 None을 돌려주면 가장 정확한 입력이 결측이 된다.
    if p.size < 2:
        return 0.0
    return float(-np.sum(p * np.log(p)) / np.log(bins))


def downbeat_strength(env: np.ndarray, sr: int, beats: np.ndarray,
                      downbeats: np.ndarray) -> float | None:
    """다운비트 온셋 세기 ÷ 전체 비트 온셋 세기 — **마디 감의 뚜렷함**.

    1보다 크면 마디 첫 박이 실제로 강조돼 있다는 뜻이다. `beats_per_bar`가 다운비트
    *개수*만 쓰는 데 반해 이건 **세기**를 본다.
    """
    b, d = np.asarray(beats, dtype=np.float64), np.asarray(downbeats, dtype=np.float64)
    if b.size < 4 or d.size < 2 or env.size == 0:
        return None
    times = np.arange(env.size) * HOP / sr

    def at(ts: np.ndarray) -> float:
        idx = np.clip(np.searchsorted(times, ts), 0, env.size - 1)
        return float(np.mean(env[idx])) if idx.size else 0.0

    allb = at(b)
    return round(at(d) / allb, 4) if allb > 1e-10 else None


def rhythm_self_similarity(env: np.ndarray, sr: int, downbeats: np.ndarray,
                           bins: int = BINS) -> float | None:
    """마디별 프로파일의 **마디 간 일관성**(0~1) — 루프 고정성 vs 변주.

    `bar_profile`이 모든 마디를 하나로 접어 버리는 정보를 되살린다. 1에 가까우면 같은
    패턴의 반복(루프), 낮으면 마디마다 다른 연주.
    """
    d = np.asarray(downbeats, dtype=np.float64)
    if d.size < MIN_DOWNBEATS + 1:
        return None
    times = np.arange(len(env)) * HOP / sr
    profs: list[np.ndarray] = []
    for a, b in pairwise(d):
        if not (b > a):
            continue
        m = (times >= a) & (times < b)
        if not m.any():
            continue
        p = np.zeros(bins, dtype=np.float64)
        idx = np.floor((times[m] - a) / (b - a) * bins).astype(int) % bins
        np.add.at(p, idx, np.maximum(env[m], 0.0))
        if p.sum() > 0:
            profs.append(p / p.sum())
    if len(profs) < 2:
        return None
    sims: list[float] = []
    for i in range(len(profs) - 1):
        x, y = profs[i] - profs[i].mean(), profs[i + 1] - profs[i + 1].mean()
        nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
        if nx > 0 and ny > 0:
            sims.append(float(x @ y / (nx * ny)))
    return round(float(np.median(sims)), 4) if sims else None


def attack_sharpness(env: np.ndarray, onsets_idx: np.ndarray) -> float | None:
    """온셋에서의 포락 상승 기울기 중앙값 — **타격감**(트랜지언트의 날카로움)."""
    if env.size < 3 or onsets_idx.size == 0:
        return None
    slopes: list[float] = []
    for i in np.asarray(onsets_idx, dtype=int):
        if 1 <= i < env.size:
            slopes.append(float(env[i] - env[i - 1]))
    return round(float(np.median(slopes)), 4) if slopes else None


def band_onset_density(y: np.ndarray, sr: int, duration: float) -> dict[str, Any]:
    """저·중·고역 각각의 초당 온셋 수 — **어느 대역이 리듬을 끄는가**.

    전체 `onset_rate` 하나로는 "하이햇이 빽빽한 곡"과 "킥이 빽빽한 곡"이 같은 값이 된다.
    """
    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    if duration <= 0:
        return {}
    S = np.abs(librosa.stft(y, hop_length=HOP, n_fft=2048)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    out: dict[str, Any] = {}
    for name, lo, hi in (("low", 20.0, 250.0), ("mid", 250.0, 2000.0), ("high", 2000.0, 11025.0)):
        rows = (freqs >= lo) & (freqs < hi)
        if not rows.any():
            continue
        env = librosa.onset.onset_strength(S=librosa.power_to_db(S[rows] + 1e-10), sr=sr,
                                           hop_length=HOP)
        idx = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=HOP)
        out[f"onset_rate_{name}"] = round(len(idx) / duration, 3)
    return out


def tempogram_ratio(env: np.ndarray, sr: int, bpm: float) -> dict[str, Any]:
    """비트의 2배·3배 lag에서의 온셋 포락 자기상관 — **원시 측정값만 낸다**.

    🔴 **박자 판정으로 쓰지 말 것**(2026-07-29 실측으로 철회, RULES §3.7). 여기서
    "2박 우세 / 3박 우세"를 도출하려 했으나 **3/4박자 곡 두 개(사티 짐노페디·에반스
    왈츠)를 모두 2박 우세로 판정했다** — 판정 기준을 결과 보기 전에 고정해 두었기에
    바로 걸렸다. 원인은 2배 lag의 자기상관이 백비트 때문에 박자와 무관하게 늘 강하다는
    것이고, 이건 임계 조정으로 고쳐지는 문제가 아니라 **정의의 문제**다.

    그래서 파생 비율(`meter_duple_bias`)은 **철회하고 원시 자기상관만 남긴다** —
    측정은 유효하고 해석이 틀렸으므로, 버릴 것은 해석이다. 박자는 `beats_per_bar`가
    담당하며 그쪽도 실음악 검증 전이라 집계 전용이다(§3.1.5).
    """
    if env.size < 8 or not (20.0 < bpm < 400.0):
        return {}
    e = env - float(np.mean(env))
    ac = np.correlate(e, e, mode="full")[e.size - 1 :]
    if ac.size < 4 or ac[0] <= 1e-10:
        return {}
    ac = ac / ac[0]
    beat_lag = 60.0 / bpm * sr / HOP
    out: dict[str, Any] = {}
    for mult, name in ((2.0, "duple"), (3.0, "triple")):
        lag = round(beat_lag * mult)
        if 1 <= lag < ac.size:
            out[f"tempogram_{name}"] = round(float(ac[lag]), 4)
    return out


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


def extract_rhythm(
    y: np.ndarray, sr: int, *, grid_out: dict[str, Any] | None = None
) -> dict[str, Any]:
    """오디오 배열 → 리듬 지표. 실패는 RhythmUnavailable로 올린다(0으로 채우지 않는다).

    `grid_out`을 주면 비트·다운비트 **시각 배열**을 거기 담아 돌려준다. 스템 축
    (RULES §3.8)이 같은 마디 격자를 써야 하기 때문이다 — 스템에서 비트를 다시
    추적하면 격자가 두 개가 되어 `snare_bar_profile`을 `kick_bar_profile`과
    비교할 수 없다. **레코드에는 담기지 않는다**(지표가 아니라 중간 산물).
    """
    beats, downbeats = _beat_tracker()(np.asarray(y, dtype=np.float32), sr)
    beats = np.asarray(beats, dtype=np.float64)
    downbeats = np.asarray(downbeats, dtype=np.float64)
    if grid_out is not None:
        grid_out["beats"] = beats
        grid_out["downbeats"] = downbeats

    import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

    tempo, grid_dev = beat_grid_fit(beats)
    env = kick_envelope(y, sr)
    profile = bar_profile(env, sr, downbeats)
    cls = classify_rhythm(profile)

    # 32칸 전용 축(RULES §3.1.5.2·§3.1.5.3) — 옛 16칸 레코드에는 **결측**이다(0이 아니다).
    grid: dict[str, Any] = {"bar_profile_bins": BINS}
    try:
        grid["kick_bar_profile_triplet"] = [
            round(float(v), 4) for v in bar_profile(env, sr, downbeats, TRIPLET_BINS)
        ]
    except RhythmUnavailable as exc:
        grid["triplet_unresolved"] = str(exc)
    try:
        # 하이햇은 **믹스 고역**에서 잰다 — 6kHz 위는 마스킹이 약해 스템이 필요 없다
        # (중역 스네어와 사정이 다르다, RULES §3.1.5.3).
        hi_env = band_onset_env(y, sr, HIHAT_MIN_HZ, None)
        hi_prof = bar_profile(hi_env, sr, downbeats, BINS)
        hi_trip = bar_profile(hi_env, sr, downbeats, TRIPLET_BINS)
        grid["hihat_bar_profile"] = [round(float(v), 4) for v in hi_prof]
        grid["hihat_bar_profile_triplet"] = [round(float(v), 4) for v in hi_trip]
        grid["hihat_bar_contrast"] = round(bar_profile_contrast(hi_prof), 4)
        # burst·active는 §3.1.5.4 사전 등록 축이다. 값은 저장하되 **리포트 표면 금지**
        # (정답지 검증 전) — D-032 "저장은 후하게, 표면은 인색하게".
        for k, v in (("hihat_roll_ratio", hihat_roll_ratio(hi_prof)),
                     ("hihat_triplet_bias", hihat_triplet_bias(hi_trip)),
                     ("hihat_roll_burst_ratio", hihat_roll_burst_ratio(hi_prof)),
                     ("hihat_active_ratio", hihat_active_ratio(hi_prof))):
            if v is not None:
                grid[k] = round(v, 4)
    except (RhythmUnavailable, ValueError) as exc:
        grid["hihat_unresolved"] = f"{type(exc).__name__}: {exc}"[:120]
    sh = bar_profile_split_half(env, sr, downbeats)
    if sh is not None:
        grid["bar_profile_split_half"] = round(sh, 4)
    # 2마디 블록 분할도 함께 낸다 — 두 값을 같은 실행에서 나란히 얻어야 H4의 조건
    # ②(정답지 보존)를 **같은 곡·같은 포락에서** 비교할 수 있다(§3.1.5.4 ②).
    sh2 = bar_profile_split_half_2bar(env, sr, downbeats)
    if sh2 is not None:
        grid["bar_profile_split_half_2bar"] = round(sh2, 4)

    # 리듬 축 묶음(RULES §3.7) — 이미 얻은 비트·다운비트·포락을 **재사용**한다.
    # 한 축이 실패해도 나머지는 낸다.
    extra: dict[str, Any] = {}
    duration = float(len(y)) / sr
    try:
        full_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
        onset_idx = librosa.onset.onset_detect(onset_envelope=full_env, sr=sr, hop_length=HOP)
        onset_times = np.asarray(onset_idx, dtype=np.float64) * HOP / sr
        for k, v in (
            ("swing_ratio", swing_ratio(beats, onset_times)),
            ("ioi_entropy", ioi_entropy(onset_times)),
            ("attack_sharpness", attack_sharpness(full_env, np.asarray(onset_idx))),
            ("downbeat_strength", downbeat_strength(env, sr, beats, downbeats)),
            ("rhythm_self_similarity", rhythm_self_similarity(env, sr, downbeats)),
        ):
            if v is not None:
                extra[k] = round(v, 4) if isinstance(v, float) else v
        extra.update(tempogram_ratio(full_env, sr, tempo))
        extra.update(band_onset_density(y, sr, duration))
    except Exception as exc:  # noqa: BLE001 — 부가 축 실패가 리듬 본체를 죽이지 않는다
        extra["rhythm_extra_unresolved"] = f"{type(exc).__name__}: {exc}"[:120]

    return {
        **extra,
        **grid,
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
        "rhythm_triplet_bins": TRIPLET_BINS,
        # 템플릿·임계는 **캐시 키가 아니다**(cli.py `engine_key` 참조). 저장된
        # kick_bar_profile에서 재계산되므로 값을 바꿔도 프리뷰를 다시 받지 않는다.
        "rhythm_templates": sorted(TEMPLATES),
        "rhythm_min_match": MIN_MATCH_DEFAULT,
        "rhythm_tie_gap": TIE_GAP_DEFAULT,
        # 리듬 산출 집합의 버전 — 캐시 키의 일부(cli.py `engine_key`).
        #   v2 = D-031 (grid_deviation_ms · syncopation_ratio · bar_profile_contrast)
        "rhythm_feature_set": RHYTHM_FEATURE_SET,
    }
