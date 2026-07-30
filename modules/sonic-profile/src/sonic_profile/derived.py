"""저장된 라벨·벡터에서 재계산하는 파생 지표 (RULES §3.6) — **오디오가 필요 없다**.

오디오를 저장하지 않으므로(RULES §1) 소급 적용의 경로는 스냅샷에 남은 값뿐이다. 이 모듈은
`features.instruments`(악기 40종 확률)·`styles`·`moods`·`kick_bar_profile`처럼 **이미 저장된
것**만 먹고 새 축을 낸다. 그래서 옛 스냅샷에도 그대로 붙는다 — D-027이 리듬 유형 재계산을
위해 깔아 둔 경로의 연장이다.

전부 A층(§3): **정의가 곧 설명**이다. 모델을 부르지 않으므로 결정적이고 네트워크가 0이다.

**임계·매핑은 도메인 소유자 소유**(AGENTS §2.1). 이 파일의 라벨 집합은 코드에 숨긴 값이
아니라 원장(RULES §3.6)에 그대로 실려 있으며 반박·재조정 대상이다.
"""

from __future__ import annotations

import math
from typing import Any

# ── 유기음 ↔ 전자음 매핑 (RULES §3.6 원장 · **값은 도메인 소유자 소유**) ─────────────
#
# MTG-Jamendo 악기 40종을 셋으로 가른다. **모호한 것은 배정하지 않는다** — 추측 금지는
# 이 저장소의 규율이고(RULES §1 별칭 검증과 같은 논리), 억지 배정은 조용히 틀린 값을 만든다.
ORGANIC: frozenset[str] = frozenset({
    "accordion", "acousticbassguitar", "acousticguitar", "bongo", "brass", "cello",
    "clarinet", "classicalguitar", "doublebass", "flute", "harmonica", "harp", "horn",
    "oboe", "orchestra", "percussion", "piano", "pipeorgan", "saxophone", "strings",
    "trombone", "trumpet", "viola", "violin",
})
ELECTRONIC: frozenset[str] = frozenset({
    "beat", "computer", "drummachine", "electricpiano", "pad", "sampler", "synthesizer",
})
# 배정하지 않는 라벨과 그 이유 — 원장에 남겨야 재조정이 가능하다:
#   bass·guitar·drums·keyboard·organ·rhodes·bell : 어쿠스틱·전자 양쪽에 걸쳐 라벨이 구분하지 않음
#   electricguitar                               : '전기'지만 연주 악기 — '전자 프로덕션'과 다른 축
#   voice                                        : 어느 쪽도 아님
AMBIGUOUS: frozenset[str] = frozenset({
    "bass", "guitar", "drums", "keyboard", "organ", "rhodes", "bell", "electricguitar", "voice",
})

# 리듬 섹션 · 신스 팔레트 (§3.6 원장)
RHYTHM_SECTION: frozenset[str] = frozenset({"drums", "bass", "percussion", "beat", "drummachine"})
SYNTH_FAMILY: frozenset[str] = frozenset({"synthesizer", "pad", "sampler", "drummachine", "computer"})


def _probs(items: Any) -> dict[str, float]:
    """`[{label, p}, …]` → dict. 형식이 어긋나면 빈 dict(결측)."""
    if not isinstance(items, list):
        return {}
    out: dict[str, float] = {}
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("label"), str):
            p = it.get("p")
            if isinstance(p, (int, float)):
                out[it["label"]] = float(p)
    return out


def _entropy(values: list[float]) -> float | None:
    """정규화 섀넌 엔트로피(0~1). 전부 한 곳에 몰리면 0, 균등하면 1."""
    vs = [v for v in values if v > 0.0]
    total = sum(vs)
    if len(vs) < 2 or total <= 0.0:
        return None
    h = -sum((v / total) * math.log(v / total) for v in vs)
    return h / math.log(len(vs))


def organic_ratio(instruments: Any) -> dict[str, Any]:
    """유기음 / (유기음 + 전자음) — **어쿠스틱 ↔ 일렉트로닉 팔레트**(RULES §3.6).

    모호 라벨은 분자·분모 **양쪽에서 빠진다.** 그래서 비율과 함께 **배제된 질량**을 낸다 —
    배제율이 높으면 그 곡의 비율은 근거가 얇다는 뜻이고, 그 사실이 안 보이면 안 된다.

    **측정하는 것은 음색 팔레트이지 제작 방식이 아니다.** K-pop은 사실상 전부 DAW에서
    만들어진다 — 실연 스트링이 들어간 발라드도 전자적으로 제작된다(§3.6 1급 한계).
    """
    p = _probs(instruments)
    if not p:
        return {}
    org = sum(v for k, v in p.items() if k in ORGANIC)
    ele = sum(v for k, v in p.items() if k in ELECTRONIC)
    total = sum(p.values())
    if org + ele <= 0.0:
        return {"organic_unresolved": "no organic/electronic mass"}
    return {
        "organic_ratio": round(org / (org + ele), 4),
        # 이 값이 크면 비율의 근거가 얇다 — 반드시 함께 읽는다
        "organic_excluded_mass": round(1.0 - (org + ele) / total, 4) if total > 0 else None,
    }


def instrument_shape(instruments: Any, *, min_prob: float = 0.3) -> dict[str, Any]:
    """편곡 구성의 형태 — 몇 겹인가 · 리듬 주도인가 · 신스 비중은.

    `min_prob`은 **A&R 소유**(RULES §3.1.6)이며 리포트의 악기 임계와 같은 값을 쓴다.
    """
    p = _probs(instruments)
    if not p:
        return {}
    total = sum(p.values())
    out: dict[str, Any] = {
        "instrument_count": sum(1 for v in p.values() if v >= min_prob),
        "instrument_entropy": _entropy(list(p.values())),
    }
    if total > 0:
        out["rhythm_section_mass"] = round(
            sum(v for k, v in p.items() if k in RHYTHM_SECTION) / total, 4)
        out["synth_mass"] = round(sum(v for k, v in p.items() if k in SYNTH_FAMILY) / total, 4)
    e = out.get("instrument_entropy")
    if e is not None:
        out["instrument_entropy"] = round(e, 4)
    return out


def label_entropy(styles: Any, moods: Any) -> dict[str, Any]:
    """스타일·무드 분포의 엔트로피 — 장르 순수성 vs 혼종성.

    **주의**: 저장된 상위 k에 대한 엔트로피다(스타일은 400 중 5만 저장). 절대값이 아니라
    **곡 간 상대 비교**로만 읽는다 — 상위 k 절단이 값의 일부다(§3.1.6.1과 같은 성질).
    """
    out: dict[str, Any] = {}
    for name, items in (("style_entropy", styles), ("mood_entropy", moods)):
        p = _probs(items)
        if p:
            e = _entropy(list(p.values()))
            if e is not None:
                out[name] = round(e, 4)
    return out


def profile_shape(profile: Any) -> dict[str, Any]:
    """마디 프로파일(16칸)의 형태 — `bar_profile_contrast`가 못 보는 꼬리까지.

    `contrast`(max/mean)는 **최고점 하나**만 본다. 균등하게 4칸에 퍼진 것과 한 칸에 몰린
    것을 엔트로피가 가르고, 전·후반 비대칭이 2마디 루프를 드러낸다.
    """
    if not isinstance(profile, list) or len(profile) < 4:
        return {}
    vals = [float(v) for v in profile if isinstance(v, (int, float))]
    if len(vals) != len(profile):
        return {}
    total = sum(vals)
    if total <= 0:
        return {}
    out: dict[str, Any] = {}
    e = _entropy(vals)
    if e is not None:
        out["bar_profile_entropy"] = round(e, 4)
    # 평균 이상인 칸 수 = 킥이 실제로 서 있는 자리의 수
    mean = total / len(vals)
    out["kick_density"] = sum(1 for v in vals if v > mean)
    half = len(vals) // 2
    front, back = sum(vals[:half]), sum(vals[half:])
    if front + back > 0:
        # 0.5 = 대칭. 0 또는 1에 가까우면 반 마디에만 킥이 있다(2마디 루프 신호)
        out["bar_half_asymmetry"] = round(front / (front + back), 4)
    return out


def derive_all(features: dict[str, Any], *, min_prob: float = 0.3) -> dict[str, Any]:
    """저장된 feature dict → 파생 지표 전부. **이미 있는 키는 덮어쓰지 않는다.**

    한 곳에서만 파생시켜야 downstream(지표 타일·분포 차트·시리즈)이 새 스냅샷과 옛
    스냅샷을 구별하지 않는다.
    """
    out: dict[str, Any] = {}
    out.update(organic_ratio(features.get("instruments")))
    out.update(instrument_shape(features.get("instruments"), min_prob=min_prob))
    out.update(label_entropy(features.get("styles"), features.get("moods")))
    out.update(profile_shape(features.get("kick_bar_profile")))
    return {k: v for k, v in out.items() if k not in features and v is not None}
