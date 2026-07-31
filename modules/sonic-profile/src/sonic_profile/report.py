"""스냅샷 → report.json / signal-series (오프라인·결정적).

RULES §4: 관측 0이어도 크래시하지 않고 유효 report를 낸다. 한계(§3.1 발췌 제약)는
insights에 **반드시** 병기한다 — 병기는 선택이 아니라 §5 준수 요건이다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from statistics import median
from typing import Any

import numpy as np

from sonic_profile.derived import derive_all
from sonic_profile.rhythm import (
    BINS,
    LEGACY_BINS,
    MIN_MATCH_DEFAULT,
    NO_MATCH,
    TEMPLATES,
    TIE_GAP_DEFAULT,
    RhythmUnavailable,
    bar_profile_contrast,
    classify_rhythm,
    fold_profile,
    render_template,
    syncopation_ratio,
    unrenderable_templates,
)
from sonic_profile.tagging import TOP_K_INSTRUMENT

MODULE_ID = "sonic-profile"

# 리포트가 받아들이는 마디 격자 — 옛 16칸과 새 32칸(D-038). 한 값으로 묶어 두면
# 격자를 바꾼 날 다른 쪽 레코드의 리듬 파생이 조용히 멈춘다.
_GRIDS = (LEGACY_BINS, BINS)

# 악기 검출 임계 — **A&R 소유**(RULES §3.1.6). 인자 기본값에 숨겨 두지 않는다.
MIN_PROB_DEFAULT = 0.3
# 노브가 내려갈 수 있는 최저 기준 = 리포트에 싣는 확률 하한. 둘이 같아야
# 전송 절감이 집계를 바꾸지 않는다(더 낮은 기준은 애초에 고를 수 없다).
SHIP_FLOOR = 0.05
# "신곡"의 경계 — **하중받는 기준**(RULES §3.5). 90일은 관습값이며 도메인 소유자 소유.
NEW_RELEASE_DAYS = 90
# 발매 분기 칸의 최소 표본. 얇은 칸은 중앙값이 튀어 트렌드로 읽히면 안 된다.
VINTAGE_MIN_N = 3

# 리포트 표면에 올리는 지표. crest_factor_db는 TESTS §3 검증 통과(2026-07-28)로 활성화
_SURFACED = [
    ("tempo_bpm", "템포", "BPM"),
    ("pulse_clarity", "펄스 명료도", ""),
    ("onset_rate", "온셋 밀도", "회/초"),
    ("low_end_ratio", "저역 비율", ""),
    ("brightness_hz", "음색 밝기", "Hz"),
    ("percussive_ratio", "타악 비율", ""),
    ("crest_factor_db", "다이내믹 여유(crest)", "dB"),
    # D-031 추가. `loudness_lufs`는 crest와 **같은 전제**(프리뷰 미정규화, TESTS §3)에
    # 기대므로 그 전제가 무너지면 둘이 함께 무효가 된다.
    ("loudness_lufs", "라우드니스", "LUFS"),
    ("spectral_flatness", "스펙트럼 평탄도", ""),
    ("stereo_width", "스테레오 폭", ""),
    ("syncopation_ratio", "싱코페이션", ""),
    ("bar_profile_contrast", "마디 프로파일 대비", "×"),
    ("grid_deviation_ms", "그리드 편차", "ms"),
    # C층 구성물 지표(RULES §3.1.6.2). **`_UNIT_AXES`에는 넣지 않는다** — valence는 0~1이
    # 아니고, danceability는 K-pop에서 천장에 붙어(중앙 0.995) 분포 축으로 쓸 수 없다.
    # danceability는 여기 남아 정의·저장을 유지하되 **표면에서는 `_NO_MEDIAN_OR_RANK`가 뺀다**.
    ("danceability", "danceability", ""),
    ("valence", "정서가(valence)", ""),
    ("arousal", "각성도(arousal)", ""),
    # ── D-032 T0 축. **전부 올리지 않는다.** 71개 스칼라를 계산·저장하지만 타일에는
    # 코호트에서 분산이 확인되고(§3.7 실측표) 서로 겹치지 않는 것만 올린다 — 축이 늘면
    # 리포트가 읽히지 않고, 판별력 없는 축이 섞이면 나머지 신뢰까지 깎인다.
    # 나머지는 스냅샷·시리즈에 그대로 있어 언제든 꺼내 볼 수 있다.
    ("organic_ratio", "유기음 비율", ""),
    ("loudness_range_lu", "라우드니스 레인지", "LU"),
    ("stereo_width_low", "저역 스테레오 폭", ""),
    ("phase_correlation", "위상 상관", ""),
    ("rhythm_self_similarity", "마디 자기유사도", ""),
    ("attack_sharpness", "어택 샤프니스", ""),
]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vals(records: list[dict[str, Any]], field: str) -> list[float]:
    out: list[float] = []
    for r in records:
        v = (r.get("features") or {}).get(field)
        if isinstance(v, (int, float)):
            out.append(float(v))
    return out


def _label(r: dict[str, Any]) -> str:
    """트랙 라벨 = `아티스트 - 곡명`.

    아티스트만 쓰면 같은 팀의 다른 곡이 구분되지 않는다(실측: 검정치마 2곡이 같은 이름으로
    나란히 표시됨). 해석된 레코드는 소스가 돌려준 정식 표기를 갖고 있으므로 그것을 쓴다.
    """
    artist = str(r.get("artist") or r.get("key") or "?").strip()
    title = str(r.get("title") or "").strip()
    return f"{artist} - {title}" if title else artist


def _labeled(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    """(라벨, 값) 쌍. 값이 있는 레코드에서 **직접** 만든다 — 별도로 필터링한 두 리스트를
    zip하면 지표가 없는 레코드에서 어긋나 엉뚱한 곡에 값이 붙는다."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in records:
        v = (r.get("features") or {}).get(field)
        if not isinstance(v, (int, float)):
            continue
        # 같은 녹음이 코호트·워치리스트 양쪽에 잡히면 한 번만
        tid = str(r.get("track_id") or "")
        dedup = tid or _label(r)
        if dedup in seen:
            continue
        seen.add(dedup)
        out.append({"name": _label(r), "value": float(v)})
    return out


def _hist(values: list[float], lo: float, hi: float, bins: int) -> list[dict[str, Any]]:
    if not values:
        return []
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        i = min(bins - 1, max(0, int((v - lo) / width)))
        counts[i] += 1
    return [
        {"name": f"{int(lo + i * width)}–{int(lo + (i + 1) * width)}", "value": c}
        for i, c in enumerate(counts)
    ]


# 분포 뷰에 쓰는 축 (0~1로 스케일이 같은 것끼리 묶어야 한 차트에 겹칠 수 있다).
# LUFS·ms·대비(×)·BPM·Hz는 여기 넣지 않는다 — RULES §4가 금지하는 스케일 혼합이다.
_UNIT_AXES = [
    ("pulse_clarity", "펄스 명료도"),
    ("low_end_ratio", "저역 비율"),
    ("percussive_ratio", "타악 비율"),
    ("spectral_flatness", "스펙트럼 평탄도"),
    ("stereo_width", "스테레오 폭"),
    # D-032 — 0~1 축이면서 코호트 분산이 확인된 것만. **선 6~7개가 한 그림의 한계**라
    # `syncopation_ratio`(분산 0.191)는 타일·히트맵에만 두고 이 목록에서는 뺀다.
    ("organic_ratio", "유기음 비율"),
]
# 🔴 **원장이 "쓰지 말라"고 적은 축은 표면에서 뺀다**(RULES §3.7 실측: `danceability`는
# 중앙 0.995 · p90부터 1.000에 붙어 **상위 절반이 구별되지 않는다** → "중앙값·순위 비교에
# 쓰지 말 것"). 그런데 지표 타일과 순위 격자에 올라가 있었고, 리포트는 그것을 그려 놓고
# **읽는 사람에게 쓰지 말라고 안내**하고 있었다 — 경고를 붙여 면피하는 형태다.
# 도구는 자기가 무효라고 적은 주장을 렌더하지 않는다(DOMAIN §0: 판단 이전에 증거가 선다).
#
# 값은 그대로 저장된다(D-032 "저장은 후하게, 표면은 인색하게") — 스냅샷·시리즈에 남아
# 있고 `_METRIC_DEFS`의 정의도 남긴다. 빠지는 것은 **중앙값 타일과 순위·비교 축**뿐이다.
# 낮은 쪽 꼬리(실측 p10 0.300)는 유의미하지만 그것은 새 지표이고 사전 등록 대상이다.
_NO_MEDIAN_OR_RANK: dict[str, str] = {
    "danceability": "코호트 상위 절반이 천장(1.000)에 붙어 중앙값·순위로 곡을 가르지 못함",
}

_ALL_AXES = [(f, la) for f, la, _ in _SURFACED if f not in _NO_MEDIAN_OR_RANK]


def _position_heatmap(
    focus: list[dict[str, Any]], cohort: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """워치리스트 트랙이 차트 코호트 분포에서 **몇 위인가** (축별).

    heatmap 계약이 rank(1=최상) semantics라 그대로 맞는다. 이 뷰가 SPEC §2의
    "분포 안에서의 위치" — 값 자체보다 *어디쯤인지*가 판단 재료다.
    """
    if not focus or not cohort:
        return None
    rows, cells = [], []
    for r in sorted(focus, key=lambda x: _label(x)):
        feats = r.get("features") or {}
        row: list[int | None] = []
        for field, _ in _ALL_AXES:
            v = feats.get(field)
            pool = _vals(cohort, field)
            if not isinstance(v, (int, float)) or not pool:
                row.append(None)
                continue
            # 코호트 + 자기 자신을 합친 모집단에서 내림차순 순위 (1 = 가장 높음)
            row.append(sum(1 for p in pool if p > float(v)) + 1)
        if any(c is not None for c in row):
            rows.append(_label(r))
            cells.append(row)
    if not rows:
        return None
    return {
        "type": "heatmap",
        "id": "watchlist-rank",
        "title": f"분포 위치 · 워치리스트 트랙이 차트 {len(cohort)}곡 중 몇 위인가 (1 = 가장 높음)",
        "data": {"rows": rows, "cols": [la for _, la in _ALL_AXES], "cells": cells},
    }


def _cohort_compare(focus: list[dict[str, Any]], cohort: list[dict[str, Any]]) -> dict[str, Any] | None:
    """워치리스트 중앙값 vs 차트 중앙값 (0~1 축만 — 스케일이 같아야 나란히 읽힌다)."""
    if not focus or not cohort:
        return None
    data = []
    for field, label in _UNIT_AXES:
        f_v, c_v = _vals(focus, field), _vals(cohort, field)
        if not f_v or not c_v:
            continue
        data.append({"name": f"{label} · 워치리스트", "value": round(median(f_v), 4)})
        data.append({"name": f"{label} · 차트", "value": round(median(c_v), 4)})
    return (
        {"type": "bar", "id": "cohort-compare",
         "title": "코호트 비교 · 워치리스트 vs 차트 중앙값 (0~1 축)", "data": data}
        if data
        else None
    )


def _percentile_of(value: float, pool: list[float]) -> float:
    """`value`가 `pool` 분포에서 몇 백분위인가 (0~100).

    절대값은 판독 불가이고 **분포 안의 위치**가 판독 가능하다(REFERENCE §3 기제 ①).
    이 모듈은 이미 그 축 위에 있으므로 새 지표를 만드는 것이 아니라 화면에 노출하는 것이다.
    """
    if not pool:
        return 0.0
    return round(100.0 * sum(1 for p in pool if p <= value) / len(pool), 1)


def _summary_radar(
    focus: list[dict[str, Any]], cohort: list[dict[str, Any]], *, min_n: int = 3
) -> dict[str, Any]:
    """진입 요약 하나(R2) — 워치리스트가 차트 코호트 분포에서 **어디에 있는가**.

    한 도형이 두 기제를 동시에 만족한다: 기준 링(코호트 중앙값)과의 거리가 **비교 위치**이고,
    어떤 축은 링 밖 어떤 축은 링 안인 그림이 **불일치**다. 불일치가 진짜 산출물이라는 것이
    이식 대상 2번이다(REFERENCE §3 기제 ②).

    ⚠ 원값이 아니라 백분위를 그리는 이유: 이 축들은 전부 0~1이지만 실측 중앙값이
    스테레오 폭 0.11 · 평탄도 0.015 · 펄스 명료도 0.557로 자릿수가 다르다. 원값을 한
    폴리곤에 얹으면 도형이 값이 아니라 **스케일**을 보여준다.

    **표본이 얇은 축은 그리지 않는다** — 중앙값이 튀어 위치가 관측이 아니라 잡음이 된다.
    결측은 0이 아니라 null이고 사유를 함께 싣는다(R6).
    """
    axes: list[dict[str, Any]] = []
    for field, label in _UNIT_AXES:
        f_v, c_v = _vals(focus, field), _vals(cohort, field)
        if not f_v or not c_v:
            why = (
                "워치리스트 관측 없음" if not f_v else "비교할 차트 코호트 관측 없음"
            )
            axes.append({"name": label, "value": None, "missingReason": why, "sample": len(f_v)})
            continue
        if len(f_v) < min_n:
            axes.append({
                "name": label,
                "value": None,
                "missingReason": f"워치리스트 표본 {len(f_v)}곡 · 최소 {min_n}곡 미달로 위치를 내지 않음",
                "sample": len(f_v),
            })
            continue
        med = median(f_v)
        axes.append({
            "name": label,
            "value": _percentile_of(med, c_v),
            "sample": len(f_v),
            "raw": round(med, 4),
        })
    return {
        "type": "radar",
        "id": "summary-position",
        "title": "요약 · 워치리스트가 차트 코호트 안에서 어디에 있나",
        "question": "우리가 보는 팀의 소리는 지금 차트에 오른 곡들과 어느 축에서 다른가?",
        "definition": (
            "축마다 워치리스트 중앙값이 같은 날 차트 코호트 분포에서 몇 백분위인지 계산한 값. "
            "기준선 50은 차트 코호트의 중앙값이므로, 선 밖은 코호트보다 높은 쪽, 선 안은 낮은 쪽. "
            "원값이 아니라 위치를 그리는 이유는 축마다 값의 자릿수가 달라서."
        ),
        "data": {
            "axes": axes,
            "max": 100,
            "baseline": 50,
            "baselineLabel": "차트 코호트 중앙값",
            "scaleNote": "차트 코호트 내 백분위",
        },
    }


# ── 차트별 문구(R3 질문 · R5 정의). 한 표에 모으는 이유: 문구는 클라이언트 대면 카피라
# (DESIGN §6.1) 계산 코드 사이에 흩어 두면 검토가 불가능해진다. 키는 차트 id다.
#
# 🔴 R3의 규율은 "질문을 채운다"가 아니라 **"답할 질문이 없으면 그 차트를 뺀다"**다.
# 여기 새 항목을 적을 때 질문이 억지로 나온다면 그것은 문구 문제가 아니라 그 차트가
# 화면에 있을 이유가 없다는 신호다.
# ── 구획 (D-043 · DESIGN §7.1.1) ──────────────────────────────────────────────
#
# 이 탭은 파일럿이라 구획 없이 한 줄로 렌더되고 있었다. 차트 15개 · 타일 24개가
# 한 화면에 쏟아져 본문이 28,000자였다(구획을 쓰는 다른 탭은 구획당 2,400~9,900자).
#
# **구획 수는 질문의 수다.** 여섯인 이유는 이 탭이 실제로 여섯 가지를 묻기 때문이고,
# 상한(한 구획에 차트 3개)이 그것을 강제한다 — 답이 겹치는 차트를 한 칸에 몰아넣으면
# 검사기가 멈춰 세운다. 순서가 곧 읽는 차례다: 무엇인가(1·2) → 움직이나(3) →
# 그 움직임이 진짜인가(4·5) → 우리 팀은 어디 있나(6).
#
# 요약 도형이 답하는 "워치리스트가 어느 축에서 다른가"는 구획이 아니라 첫 화면의
# 도형 하나로 나간다(R2). 6번 구획은 그 위치를 곡별·원값으로 내려가 보는 자리다.
_SECTIONS: list[dict[str, str]] = [
    {
        "id": "sound",
        "label": "템포·박",
        "question": "이 곡들은 어떤 템포와 박인가?",
        "note": "30초 발췌에서 잰 값이고 곡 전체가 아니다. 미해석 곡은 0이 아니라 결측으로 빠진다.",
    },
    {
        "id": "rhythm",
        "label": "리듬·태그",
        "question": "리듬과 태그는 무엇으로 쏠려 있나?",
        "note": "리듬 유형은 가장 가까운 순위이지 판정이 아니다. 악기·스타일·정서 태그는 분류기가 낸 "
        "확률이며 정확도를 아직 재지 않았다.",
    },
    {
        "id": "drift",
        "label": "날짜별 추이",
        "question": "날짜가 쌓이면서 분포가 움직이나?",
        "note": "x축이 관측일이라 소리가 변한 것과 차트 구성이 바뀐 것이 섞여 있다. 그 둘을 가르는 것이 "
        "다음 두 구획이다.",
    },
    {
        "id": "control",
        "label": "같은 곡만",
        "question": "그 움직임이 소리의 변화가 맞나?",
        "note": "구성 변화를 걷어내는 두 가지 방법이다. 고정 코호트는 곡 집합을 묶고, 신곡만 뷰는 "
        "카탈로그 혼입을 뺀다.",
    },
    {
        "id": "vintage",
        "label": "발매 시기",
        "question": "발매 시기가 다르면 소리도 다른가?",
        "note": "x축이 발매 분기라 차트 재편성에 흔들리지 않는다. 대신 생존 편향이 있다: 옛 분기 칸의 "
        "곡은 그 분기의 대표 표본이 아니라 오늘까지 차트에 남은 곡이다.",
    },
    {
        "id": "watchlist",
        "label": "워치리스트",
        "question": "워치리스트는 이 코호트에서 어디인가?",
        # 이 구획의 타일은 워치리스트 값이 아니라 **차트 코호트 중앙값**이다. 아래 격자가
        # 그 축들을 전부 열로 그리므로 타일은 순위의 기준선 역할을 한다 — 그 사실을 적지
        # 않으면 워치리스트 질문 아래 놓인 코호트 숫자가 무엇인지 알 수 없다.
        "note": "위 타일은 순위의 기준이 되는 차트 코호트 중앙값이다. 표본이 다른 층이라 워치리스트 곡을 "
        "코호트에 합쳐 세웠고, 순위는 곡 사이의 간격을 표현하지 않는다.",
    },
]

_CHART_META: dict[str, dict[str, str]] = {
    "tempo-hist": {
        "section": "sound",
        "question": "이 코호트의 템포는 어느 구간에 모여 있나?",
        "definition": "비트 시각에 직선을 맞춰 구한 BPM을 20BPM 폭으로 세운 것. 막대 높이는 곡 수.",
    },
    "pulse-top": {
        "section": "sound",
        "question": "박이 가장 또렷하게 잡히는 곡은 무엇인가?",
        "definition": (
            "펄스 명료도는 온셋 포락 자기상관의 주 피크. 박이 규칙적으로 강하게 반복될수록 높음. "
            "춤 적합도·인기·품질과 무관하며 danceability도 아님."
        ),
    },
    "rhythm-mix": {
        "section": "rhythm",
        "question": "이 코호트의 킥 배치는 어떤 리듬 유형에 가까운가?",
        "definition": (
            "마디를 16분음 격자로 나눠 저역 킥 배치를 접은 뒤 이름 붙은 유형과 코사인 정합도를 낸 것. "
            "유형끼리 서로 겹치므로 가장 가까운 유형은 순위이지 판정이 아님. 정합도가 낮으면 '해당 없음'."
        ),
    },
    "instrument-mix": {
        "section": "rhythm",
        "question": "검출 임계를 어디에 두면 어떤 악기가 몇 곡에서 잡히나?",
        "definition": (
            "태거가 낸 악기별 확률이 임계를 넘는 곡 수. 확률은 서로 배타적이지 않아 한 곡이 여러 칸에 셈. "
            "정확도 미측정이라 곡 수는 하한으로 읽을 값."
        ),
    },
    "style-mix": {
        "section": "rhythm",
        "question": "1순위 스타일 라벨은 무엇으로 쏠려 있나?",
        "definition": (
            "Discogs 택소노미 기준 확률 1순위 라벨별 곡 수. 저지클럽·뭄바톤·아마피아노는 이 라벨 "
            "목록에 없어 여기 나타나지 않음."
        ),
    },
    "unit-trend": {
        "section": "drift",
        "question": "관측일이 쌓이면서 코호트의 소리 분포가 움직이나?",
        "definition": (
            "날짜별 0~1 축 중앙값. x축이 관측일이라 '소리가 변한 것'과 '차트 구성이 바뀐 것'이 섞여 있음. "
            "그 둘을 가르는 것이 아래 빈티지·고정 코호트·신곡만 뷰."
        ),
    },
    "tempo-trend": {
        "section": "drift",
        "question": "코호트 템포 중앙값이 날짜에 따라 움직이나?",
        "definition": "날짜별 템포 중앙값(BPM). 관측일 기준이라 차트 구성 변화가 섞여 있음.",
    },
    "vintage-unit": {
        "section": "vintage",
        "question": "발매 시기별로 소리 분포가 다른가?",
        "definition": (
            "x축이 관측일이 아니라 발매 분기이므로 차트 재편성에 흔들리지 않음. 대신 생존 편향이 있음: "
            "옛 분기 칸의 곡은 그 분기의 대표 표본이 아니라 오늘까지 차트에 남은 곡."
        ),
    },
    "vintage-tempo": {
        "section": "vintage",
        "question": "발매 시기별 템포 중앙값이 다른가?",
        "definition": "발매 분기별 템포 중앙값. 위 뷰와 같은 생존 편향이 적용됨.",
    },
    "age-hist": {
        "section": "vintage",
        "question": "지금 차트는 얼마나 신곡 중심인가?",
        "definition": (
            "관측일에서 발매일을 뺀 곡 나이를 구간별로 센 것. 발매일은 유통사 표기라 리마스터·재발매가 "
            "그 날짜로 잡힐 수 있음."
        ),
    },
    "age-trend": {
        "section": "drift",
        "question": "차트가 신곡 쪽으로 움직이나, 카탈로그 쪽으로 움직이나?",
        "definition": "날짜별 관측 코호트의 곡 나이 중앙값(일). 값이 내려가면 신곡 쪽.",
    },
    "fixed-cohort": {
        "section": "control",
        "question": "차트 구성 변화를 제거하면 같은 곡들의 소리 지표가 움직이나?",
        "definition": (
            "최초 관측일에 잡힌 곡 집합만 계속 따라간 중앙값. 집합이 날마다 바뀌지 않으므로 "
            "여기서 움직이는 값은 차트 재편성이 아니라 이 곡들의 이야기. 같은 곡의 값이 날마다 "
            "달라지는 것은 발췌 구간이 달라졌을 가능성을 포함함."
        ),
    },
    "fresh-trend": {
        "section": "control",
        "question": "카탈로그 혼입을 걷어낸 신곡만 보면 분포가 다른가?",
        "definition": "발매 90일 이내 곡만 남긴 날짜별 0~1 축 중앙값. 90일 경계는 관습값.",
    },
    "watchlist-rank": {
        "section": "watchlist",
        "question": "워치리스트의 각 곡은 축마다 차트 코호트에서 몇 위인가?",
        "definition": (
            "곡 하나의 축별 값을 차트 코호트에 합쳐 내림차순으로 세운 순위(1이 가장 높음). "
            "순위이므로 곡 사이의 간격은 표현하지 않음."
        ),
    },
    "cohort-compare": {
        "section": "watchlist",
        "question": "두 코호트의 축별 중앙값은 각각 얼마인가?",
        "definition": (
            "요약 도형은 위치(백분위)를 보여주고 이 막대는 원값을 보여줌. 위치가 같아도 원값 차이는 "
            "클 수 있어 둘이 따로 필요함."
        ),
    },
}

# 지표 타일의 정의(R5). `hint`(표본·주의)와 역할이 다르다 — 여기는 **무엇을 재는가**다.
_METRIC_DEFS: dict[str, str] = {
    "템포": "비트 시각에 직선을 맞춰 구한 분당 박 수. 고정 격자 방식이 아니라 130BPM 부근의 작은 차이도 남음.",
    "펄스 명료도": "온셋 포락 자기상관의 주 피크. 박이 규칙적으로 강하게 반복될수록 높음. danceability가 아님.",
    "온셋 밀도": "초당 감지된 소리 시작점 수. 음이 촘촘한 편곡일수록 높음.",
    "저역 비율": "전체 에너지 중 저역(경계 아래) 비중. 킥·베이스가 두꺼울수록 높음.",
    "음색 밝기": "스펙트럼 무게중심 주파수. 높을수록 밝고 날카롭게 들리는 쪽.",
    "타악 비율": "하모닉·퍼커시브 분리 후 퍼커시브 성분 비중.",
    "다이내믹 여유(crest)": "peak를 RMS로 나눈 값(dB). 낮을수록 압축이 강함. 프리뷰가 정규화되지 않았음을 전제로 함.",
    "라우드니스": "체감 음량(LUFS). crest와 같은 전제에 기대므로 그 전제가 무너지면 함께 무효.",
    "스펙트럼 평탄도": "스펙트럼이 잡음에 가까운 정도. 톤이 뚜렷하면 낮고 노이즈성이 강하면 높음.",
    "스테레오 폭": "좌우 채널 차이의 크기. 넓게 퍼진 믹스일수록 높음.",
    "싱코페이션": "센박이 아닌 자리에 놓인 킥의 비중.",
    "마디 프로파일 대비": "마디 안에서 킥이 몰린 칸과 빈 칸의 대비. 낮으면 배치가 평평함.",
    "그리드 편차": "비트가 균일 격자에서 벗어난 정도(ms). 상당 부분이 측정 잡음이며 단독 해석 대상이 아님.",
    "danceability": "분류기가 낸 확률. 춤 실력·안무 품질의 판정이 아니고, 차트 K-pop에서 천장에 붙어 곡을 가르지 못함.",
    "정서가(valence)": "주석자들이 매긴 긍·부정 정서 값. 곡의 물리적 성질이 아니며 학습 데이터가 K-pop이 아님.",
    "각성도(arousal)": "주석자들이 매긴 각성 정도. 위와 같은 한계가 적용됨.",
    "유기음 비율": "합성음 대비 생악기·목소리 계열 성분의 비중 추정치.",
    "라우드니스 레인지": "구간별 음량 분포의 폭(LU). 좁으면 시종 같은 크기로 들리는 쪽.",
    "저역 스테레오 폭": "저역대에서의 좌우 차이. 보통 좁게 유지되는 값.",
    "위상 상관": "좌우 채널의 위상 일치도. 1에 가까우면 모노에 가까움.",
    "마디 자기유사도": "마디끼리 얼마나 같은 패턴을 반복하는가.",
    "어택 샤프니스": "소리 시작점의 상승 급격함.",
}

# 타일도 구획에 나눠 넣는다(D-043) — 지표는 자기 질문 옆에 있을 때만 읽힌다.
#
# 배정 규칙은 하나다: **그 축을 실제로 그리는 차트가 있는 구획에 놓는다.** 24개를 주제별로
# 묶으면 그럴듯하지만 어느 그림도 그 축을 쓰지 않는 칸이 생기고, 그러면 타일이 다시
# "읽을 곳 없는 숫자"가 된다. 여기 남은 것들(밝기·음량·공간)은 전 축 비교 뷰에만
# 나오므로 워치리스트 구획으로 간다.
#
# 키는 `_SURFACED`의 라벨(타일 라벨의 ` 중앙값` 앞부분)과 표본 타일 2종이다.
# **어느 축을 표면에서 뺄지는 도메인 소유자 몫이다** — 여기서 정하는 것은 자리뿐이다.
_METRIC_SECTIONS: dict[str, str] = {
    "관측 트랙": "sound",
    "미해석": "sound",
    "템포": "sound",
    "펄스 명료도": "sound",
    "온셋 밀도": "sound",
    "어택 샤프니스": "sound",
    "싱코페이션": "rhythm",
    "마디 프로파일 대비": "rhythm",
    "마디 자기유사도": "rhythm",
    "그리드 편차": "rhythm",
    # danceability는 타일을 만들지 않는다(`_NO_MEDIAN_OR_RANK`) — 배정할 자리도 없다.
    "정서가(valence)": "rhythm",
    "각성도(arousal)": "rhythm",
    # unit-trend·vintage-unit·fixed-cohort·fresh-trend가 그리는 0~1 축
    "저역 비율": "drift",
    "타악 비율": "drift",
    "스펙트럼 평탄도": "drift",
    "스테레오 폭": "drift",
    "유기음 비율": "drift",
    # 전 축 비교 뷰(watchlist-rank·cohort-compare)에만 나오는 축
    "음색 밝기": "watchlist",
    "다이내믹 여유(crest)": "watchlist",
    "라우드니스": "watchlist",
    "라우드니스 레인지": "watchlist",
    "저역 스테레오 폭": "watchlist",
    "위상 상관": "watchlist",
}


def _as_date(value: Any) -> date | None:
    """`YYYY-MM-DD` → date. 파싱 실패는 **결측**이지 오늘이 아니다(§0)."""
    try:
        y, m, d = (int(x) for x in str(value)[:10].split("-"))
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _release_age_days(r: dict[str, Any]) -> int | None:
    """관측 시점의 곡 나이(일) = 관측일 − 발매일.

    **오늘 기준이 아니라 관측일 기준**이다. 오늘로 재면 과거 스냅샷의 나이가 리포트를
    돌릴 때마다 자라서 "그날 차트가 얼마나 신곡 중심이었나"를 못 잰다.
    """
    rel, obs = _as_date(r.get("release_date")), _as_date(r.get("observed_date"))
    if rel is None or obs is None:
        return None
    age = (obs - rel).days
    # 발매 예정일이 관측일보다 뒤인 경우(선공개·시차)는 0으로 눕히지 않고 버린다
    return age if age >= 0 else None


def _vintage_key(r: dict[str, Any]) -> str | None:
    """발매 분기 라벨. 분기는 관습 단위이며 표본이 얇으면 호출부가 걸러낸다."""
    rel = _as_date(r.get("release_date"))
    return f"{rel.year}-Q{(rel.month - 1) // 3 + 1}" if rel else None


def _observed_key(r: dict[str, Any]) -> str | None:
    v = r.get("observed_date")
    return str(v) if v else None


def _median_series(
    records: list[dict[str, Any]],
    axes: list[tuple[str, str]],
    title: str,
    *,
    chart_id: str,
    key_of: Callable[[dict[str, Any]], str | None] = _observed_key,
    min_n: int = 1,
    dedup: bool = False,
) -> dict[str, Any] | None:
    """축별 중앙값 시계열 — 트렌드는 **분포가 움직이는가**로만 보인다.

    단면 순위는 트렌드가 아니다. 점이 하나뿐이면 하나가 찍히고 축적되며 채워진다.

    `key_of`로 **무엇을 x축으로 삼을지**를 갈아 끼운다. 관측일이면 "차트가 어떻게
    움직였나", 발매 분기면 "제작 사조가 어떻게 움직였나"가 된다 — 후자는 차트 재편성에
    흔들리지 않는다(D-022·D-023 한계의 해소 경로). `dedup`은 녹음 단위 축(발매 빈티지)에
    쓴다: 같은 곡이 여러 날 잡혔다고 그 발매 분기의 표본이 늘어나는 것은 아니다.
    """
    by_date: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for r in records:
        k = key_of(r) if r.get("features") else None
        if not k:
            continue
        if dedup:
            tid = str(r.get("track_id") or "") or _label(r)
            if tid in seen:
                continue
            seen.add(tid)
        by_date.setdefault(k, []).append(r)
    # 표본이 얇은 칸은 중앙값이 튄다 — 빼되 몇 곡이 빠졌는지는 호출부가 병기한다
    by_date = {k: v for k, v in by_date.items() if len(v) >= min_n}
    dates = sorted(by_date)
    if not dates:
        return None
    series = []
    for field, label in axes:
        vals = [
            round(median(v), 4) if (v := _vals(by_date[d], field)) else None for d in dates
        ]
        if any(x is not None for x in vals):
            series.append({"name": label, "values": vals})
    return (
        {"type": "line", "id": chart_id, "title": title, "data": {"x": dates, "series": series}}
        if series
        else None
    )


def _counts_chart(pairs: list[tuple[str, int]], title: str, *, chart_id: str) -> dict[str, Any] | None:
    if not pairs:
        return None
    data = [{"name": k, "value": v} for k, v in sorted(pairs, key=lambda kv: (-kv[1], kv[0]))]
    return {"type": "bar", "id": chart_id, "title": title, "data": data}


def backfill_derived(
    records: list[dict[str, Any]], *, min_prob: float = MIN_PROB_DEFAULT
) -> list[dict[str, Any]]:
    """옛 스냅샷에 D-031 파생 지표를 채운다 — 저장된 `kick_bar_profile`에서 **재계산**.

    오디오를 저장하지 않으므로(RULES §1) 소급 적용의 경로는 이 프로파일뿐이다. 유형
    재계산(`_rhythm_rows`)과 같은 근거를 쓰며, **한 곳에서만** 채워 downstream(지표
    타일·분포 차트·시리즈)이 새 스냅샷과 옛 스냅샷을 구별하지 않게 한다.

    `grid_deviation_ms`는 **채울 수 없다** — 비트 시각은 저장돼 있지 않다. 0으로
    메우지 않고 결측으로 남긴다(결측 ≠ 0, §0). 다음 콜드 실행부터 채워진다.

    수집 시점에 이미 실린 값은 덮어쓰지 않는다. 두 경로가 같은 값을 내야 하며 그
    일치는 TESTS §6.1이 대조한다.
    """
    out: list[dict[str, Any]] = []
    for r in records:
        f = r.get("features")
        if not isinstance(f, dict):
            out.append(r)
            continue
        add: dict[str, Any] = {}
        # 리듬 파생은 마디 프로파일이 있을 때만. 없다고 **다른 파생까지 막지 않는다** —
        # 리듬을 못 얻은 곡도 악기·스타일 라벨은 갖고 있다.
        prof = f.get("kick_bar_profile")
        # 격자 두 종(옛 16칸·새 32칸)을 모두 받는다 — 두 지표는 칸 수에 무관한 정의다
        # (D-038). `== BINS`로 묶어 두면 격자를 바꾼 날 옛 레코드의 파생이 조용히 멈춘다.
        if (isinstance(prof, list) and len(prof) in _GRIDS
                and all(isinstance(v, (int, float)) for v in prof)):
            try:
                if not isinstance(f.get("syncopation_ratio"), (int, float)):
                    add["syncopation_ratio"] = round(syncopation_ratio(prof), 4)
                if not isinstance(f.get("bar_profile_contrast"), (int, float)):
                    add["bar_profile_contrast"] = round(bar_profile_contrast(prof), 3)
            except RhythmUnavailable:
                add = {}
        # 라벨·벡터 파생(§3.6) — 악기·스타일·무드·마디 프로파일에서 재계산된다.
        add.update(derive_all({**f, **add}, min_prob=min_prob))
        out.append({**r, "features": {**f, **add}} if add else r)
    return out


def _rhythm_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """리듬 관측 행 = (라벨, 마디 프로파일). **저장된 유형 이름은 쓰지 않는다.**

    유형은 `kick_bar_profile`에서 **매번 재계산**한다(RULES §3.1.5 재계산 가능성).
    스냅샷에 박제된 `rhythm_top`을 믿으면 템플릿 원장을 고쳐도 과거 산출물이 옛 이름을
    달고 남는다 — 2026-07-29에 두 tresillo의 이름이 서로 뒤바뀐 채 저장된 것이 그 사례다.
    오디오는 저장하지 않으므로(§1) 다시 잴 수단은 이 프로파일뿐이다.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in records:
        prof = (r.get("features") or {}).get("kick_bar_profile")
        if not isinstance(prof, list) or len(prof) not in _GRIDS:
            continue
        if not all(isinstance(v, (int, float)) for v in prof):
            continue
        dedup = str(r.get("track_id") or "") or _label(r)
        if dedup in seen:
            continue
        seen.add(dedup)
        vec = [round(float(v), 4) for v in prof]
        rows.append(
            {
                "name": _label(r),
                "profile": vec,
                "cohort": str(r.get("cohort") or ""),
                # 유형과 같은 근거(저장된 프로파일)에서 **재계산**한다 — 옛 스냅샷에도
                # 소급 적용된다(D-031). 오디오가 없어도 되는 것이 이 두 지표의 요점이다.
                "bins": len(vec),
                "syncopation": round(syncopation_ratio(vec), 4),
                "contrast": round(bar_profile_contrast(vec), 3),
            }
        )
    return rows


def _rhythm_tunable(
    rows: list[dict[str, Any]], *, min_match: float, tie_gap: float
) -> dict[str, Any] | None:
    """리듬 유형 구성(view=rhythm) — 원자료(마디 프로파일)+템플릿+노브를 실어 보낸다.

    클라이언트가 코사인 정합을 다시 계산하므로 A&R가 θ를 움직여 **직접 반박**할 수 있고,
    각 유형을 펼쳐 **어느 곡이 거기 들어갔는지**까지 확인할 수 있다. 곡 수만 보이면
    반박할 대상이 없다 — 틀린 배정은 곡 이름을 봐야 눈에 띈다(§2.1 노출의 실질).
    백엔드 없이(static-first) 성립한다.
    """
    if not rows:
        return None
    # **격자가 섞이면 내려 맞춘다**(RULES §3.1.5.2) — 32칸은 16칸으로 정확히 접히지만
    # 그 역은 없다. 올려 맞추면 없는 정보를 만드는 것이고, 안 맞추면 클라이언트가 길이가
    # 다른 벡터에 같은 템플릿을 곱한다.
    bins = min(int(r.get("bins") or len(r["profile"])) for r in rows)
    folded: list[dict[str, Any]] = []
    for r in rows:
        vec = [round(float(v), 4) for v in fold_profile(r["profile"], bins)]
        folded.append({**r, "profile": vec, "bins": bins,
                       "syncopation": round(syncopation_ratio(vec), 4),
                       "contrast": round(bar_profile_contrast(vec), 3)})
    # 템플릿은 원장의 **분수 위치**를 이 격자에 렌더한 것이다. 렌더 불가한 템플릿은
    # 빠지며(반올림 금지), 무엇이 빠졌는지는 insights가 병기한다.
    rendered: dict[str, list[int]] = {}
    for name, pos in TEMPLATES.items():
        vec_t = render_template(pos, bins)
        if vec_t is not None:
            rendered[name] = [int(i) for i in np.flatnonzero(vec_t)]
    return {
        "type": "tunable",
        "id": "rhythm-mix",
        "title": "리듬 패턴 구성 · 마디 안 킥 배치가 가장 가까운 유형 (판정 아닌 순위 · 펼치면 곡 목록)",
        "data": {
            "view": "rhythm",
            "bins": bins,
            "templates": rendered,
            "tracks": folded,
            "noMatchLabel": NO_MATCH,
            "knobs": [
                {
                    "key": "min_match",
                    "label": "유형 배정 최소 정합도 (미만 = 해당 없음)",
                    "default": min_match,
                    "min": 0.0,
                    "max": 0.8,
                    "step": 0.05,
                },
                {
                    "key": "tie_gap",
                    "label": "동점으로 볼 1위−2위 차",
                    "default": tie_gap,
                    "min": 0.0,
                    "max": 0.3,
                    "step": 0.01,
                },
            ],
            "note": "정합도 = 마디 킥 프로파일과 템플릿의 코사인(평균 제거). 템플릿끼리 직교하지 "
            "않아(최악 쌍 0.83) **1위는 순위이지 판정이 아니다**. 임계 미만은 '다른 유형'이 아니라 "
            "'해당 없음'이며, 동점 곡은 지우지 않고 표시만 한다. 기본값 0.30·0.05는 엔지니어가 정한 "
            "관습값이라 도메인 소유자가 결과를 보기 전에 정하는 편이 옳다",
        },
    }


def _tag_rows(
    records: list[dict[str, Any]], field: str, full_k: int, ship_floor: float = 0.0
) -> list[dict[str, Any]]:
    """트랙별 (라벨, 확률) + **저장 절단 지점**.

    태거는 라벨을 상위 k개만 남긴다. 임계로 곡 수를 세는 축에서 이 절단은 조용한
    과소집계가 된다 — 6번째 라벨이 임계를 넘어도 저장돼 있지 않으면 세지 못한다.
    그래서 트랙마다 `floor`(저장된 최소 확률)와 `truncated`를 같이 실어, 클라이언트가
    "이 임계에서 몇 곡이 불완전할 수 있는가"를 **셀 수 있게** 한다(결측 ≠ 0, §0).
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in records:
        labels = (r.get("features") or {}).get(field) or []
        pairs = [
            {"label": str(d["label"]), "p": round(float(d["p"]), 4)}
            for d in labels
            if isinstance(d, dict) and d.get("label") is not None and d.get("p") is not None
        ]
        if not pairs:
            continue
        dedup = str(r.get("track_id") or "") or _label(r)
        if dedup in seen:
            continue
        seen.add(dedup)
        rows.append(
            {
                "name": _label(r),
                # 전송 절감: 노브 하한 미만은 어떤 기준에서도 표시되지 않으므로 싣지 않는다.
                # **태거 절단과 혼동하면 안 된다** — `floor`·`truncated`는 잘라내기 전
                # 원본 목록으로 판정한다. 그래야 "몇 곡이 하한인가"가 계속 옳다.
                "labels": [x for x in pairs if x["p"] >= ship_floor],
                "floor": min(x["p"] for x in pairs),
                "truncated": len(pairs) < full_k,
            }
        )
    return rows


def _instrument_tunable(
    rows: list[dict[str, Any]], *, thresh: float, top: int = 14
) -> dict[str, Any] | None:
    """악기 구성(view=tags) — **임계를 코드에서 꺼내 노브로 만든다**(RULES §3.1.6).

    "확률 몇 이상을 검출로 볼 것인가"는 A&R 소유인데 `0.3`이 인자 기본값에 박혀 있었다.
    펼치면 곡 목록과 각 곡의 확률이 나와, 임계를 옮겼을 때 **무엇이 들고 나는지**가 보인다.
    """
    if not rows:
        return None
    return {
        "type": "tunable",
        "id": "instrument-mix",
        "title": "악기 구성 · 검출 확률 임계 이상인 곡 수 (참고 · 정확도 미측정 · 펼치면 곡 목록)",
        "data": {
            "view": "tags",
            "tracks": rows,
            "topBuckets": top,
            "knobs": [
                {
                    "key": "min_prob",
                    "label": "검출로 볼 최소 확률",
                    "default": thresh,
                    "min": SHIP_FLOOR,
                    "max": 0.9,
                    "step": 0.05,
                }
            ],
            "note": "확률은 **존재 가능성이지 비중이 아닙니다** — '기타 0.5'는 '기타가 절반'이 "
            "아니라 '있을 법함'입니다. 라벨끼리 배타적이지 않아 한 곡이 여러 칸에 들어갑니다. "
            "정확도는 아직 사람 라벨로 재지 않았으므로 단독 근거로 쓰지 마십시오. "
            "기본 임계 0.3은 엔지니어가 정한 관습값이라 담당자가 정할 사안입니다",
        },
    }


def _style_mix(records: list[dict[str, Any]], top: int = 12) -> dict[str, Any] | None:
    """1순위 스타일별 곡 수 (Discogs 택소노미)."""
    counts: dict[str, int] = {}
    for r in records:
        st = (r.get("features") or {}).get("styles") or []
        if st and isinstance(st[0], dict):
            counts[str(st[0]["label"])] = counts.get(str(st[0]["label"]), 0) + 1
    chart = _counts_chart(
        list(counts.items()),
        "스타일 구성 · 1순위 라벨별 곡 수 (참고 · 정확도 미측정)",
        chart_id="style-mix",
    )
    if chart:
        chart["data"] = chart["data"][:top]
    return chart


def _age_hist(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """최신 관측일 코호트의 곡 나이 분포 — "지금 차트가 얼마나 신곡 중심인가"."""
    latest = max((str(r.get("observed_date") or "") for r in records if r.get("features")), default="")
    if not latest:
        return None
    seen: set[str] = set()
    buckets = [("0–30일", 0, 30), ("31–90일", 31, 90), ("91–365일", 91, 365),
               ("1–3년", 366, 1095), ("3년 초과", 1096, 10**9)]
    counts = dict.fromkeys((b[0] for b in buckets), 0)
    for r in records:
        if str(r.get("observed_date") or "") != latest:
            continue
        age = _release_age_days(r)
        if age is None:
            continue
        tid = str(r.get("track_id") or "") or _label(r)
        if tid in seen:
            continue
        seen.add(tid)
        for name, lo, hi in buckets:
            if lo <= age <= hi:
                counts[name] += 1
                break
    if not any(counts.values()):
        return None
    return {
        "type": "bar",
        "id": "age-hist",
        "title": f"곡 나이 분포 · {latest} 관측 코호트 (관측일 − 발매일)",
        # 순서를 보존한다 — 나이 구간은 크기순이 아니라 시간순으로 읽어야 한다
        "data": [{"name": n, "value": counts[n]} for n, _, _ in buckets if counts[n]],
    }


def _age_series(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """날짜별 곡 나이 중앙값 — 차트가 신곡 쪽으로 움직이는지 카탈로그 쪽으로 움직이는지."""
    by_date: dict[str, list[int]] = {}
    for r in records:
        age = _release_age_days(r) if r.get("features") else None
        if age is not None:
            by_date.setdefault(str(r["observed_date"]), []).append(age)
    dates = sorted(by_date)
    if not dates:
        return None
    return {
        "type": "line",
        "id": "age-trend",
        "title": "곡 나이 추이 · 관측 코호트의 나이 중앙값 (일)",
        "data": {
            "x": dates,
            "series": [{"name": "나이 중앙값(일)", "values": [round(median(by_date[d]), 1) for d in dates]}],
        },
    }


def _inferences(
    *,
    summary: dict[str, Any],
    rhythm_rows: list[dict[str, Any]],
    resolved: list[dict[str, Any]],
    min_match: float,
    tie_gap: float,
    new_days: int,
) -> list[dict[str, Any]]:
    """태그된 자동 추론(R4 · D-039). **전부 관측에서 계산해 만든다.**

    불변식이 금지하는 것은 **평결**이고, 꼬리표 달린 추론은 평결이 아니다 — 출처가 명시된
    해석이며 사람이 채택·기각할 대상이다. 그래서 5필드(text + 동반 4종)가 전부 채워진
    것만 낸다: 근거 없는 추론이 화면에 오르는 경로를 방출 층에서 끊는다.

    ⚠ 어법(DESIGN §6.2): 명령형·예측 단정·인과 단정 금지, em dash 금지.
    허용은 "~와 정합한다"·"~신호가 있다"·"~로 읽힌다"뿐이며
    scripts/validate_report_data.py가 CI에서 검사한다.
    """
    out: list[dict[str, Any]] = []

    # ① 요약 도형에서 코호트와 가장 크게 어긋난 축. **불일치가 진짜 산출물**이다(기제 ②).
    placed = [a for a in summary["data"]["axes"] if isinstance(a.get("value"), (int, float))]
    # 기준선에서 이 폭 안은 "코호트 중앙값 근처"로 본다 — 백분위 몇 점 차이를 방향으로
    # 읽으면 표본 11곡에서 잡음이 결론이 된다.
    band = 15.0
    if placed:
        hi = [a for a in placed if float(a["value"]) - 50.0 >= band]
        lo = [a for a in placed if 50.0 - float(a["value"]) >= band]
        far = max(placed, key=lambda a: abs(float(a["value"]) - 50.0))
        # 한쪽으로만 쏠린 그림은 정보가 적다. **양쪽으로 갈린 그림이 불일치**이고 그게 산출물이다.
        if hi and lo:
            out.append({
                "text": (
                    f"워치리스트의 위치는 축에 따라 갈린다. {len(hi)}개 축은 차트 코호트보다 높은 쪽, "
                    f"{len(lo)}개 축은 낮은 쪽에 있는 신호가 있다."
                ),
                "basis": (
                    "높은 쪽 " + ", ".join(f"{a['name']} {a['value']}" for a in hi)
                    + " · 낮은 쪽 " + ", ".join(f"{a['name']} {a['value']}" for a in lo)
                    + f" (기준 50 = 차트 코호트 중앙값, 근처로 보는 폭 {band:g})"
                ),
                "sample": f"워치리스트 {far.get('sample', 0)}곡 대비 차트 코호트",
                # 워치리스트 표본이 두 자리 수를 넘지 않는 동안은 등급을 올리지 않는다.
                "confidence": "medium" if int(far.get("sample") or 0) >= 20 else "low",
                "limits": (
                    "발췌 구간이 곡마다 달라 같은 곡도 날마다 값이 흔들린다. 이 위치는 관측일 코호트 "
                    "안에서만 성립하며 차트 성적과의 관계를 말하지 않는다."
                ),
                "chartId": "summary-position",
            })
        elif abs(float(far["value"]) - 50.0) >= band:
            side = "높은" if float(far["value"]) > 50.0 else "낮은"
            same = hi if side == "높은" else lo
            out.append({
                "text": (
                    f"워치리스트는 {len(same)}개 축에서 차트 코호트보다 {side} 쪽에 몰려 있는 신호가 있다. "
                    f"가장 크게 벌어진 축은 {far['name']}으로 읽힌다."
                ),
                "basis": (
                    ", ".join(f"{a['name']} {a['value']}" for a in same)
                    + f" (기준 50 = 차트 코호트 중앙값, 근처로 보는 폭 {band:g})"
                    + f" · {far['name']} 워치리스트 중앙값 원값 {far.get('raw')}"
                ),
                "sample": f"워치리스트 {far.get('sample', 0)}곡 대비 차트 코호트",
                "confidence": "medium" if int(far.get("sample") or 0) >= 20 else "low",
                "limits": (
                    "한 방향으로만 쏠린 그림은 축이 서로 독립이 아닐 가능성을 포함한다. 발췌 구간이 "
                    "곡마다 달라 같은 곡도 날마다 값이 흔들리며, 차트 성적과의 관계를 말하지 않는다."
                ),
                "chartId": "summary-position",
            })

    # ② 리듬 유형 분포가 얼마나 단단한가. 동점·해당없음 비중을 그대로 근거로 쓴다.
    if rhythm_rows:
        cls = [classify_rhythm(x["profile"], min_match=min_match, tie_gap=tie_gap) for x in rhythm_rows]
        n_tie = sum(1 for c in cls if c["tie"])
        n_none = sum(1 for c in cls if c["assigned"] is None)
        soft = n_tie + n_none
        if cls and soft / len(cls) >= 0.2:
            out.append({
                "text": (
                    f"리듬 유형 막대는 곡 수를 그대로 읽기 어려운 상태와 정합한다. 관측 {len(cls)}곡 중 "
                    f"{soft}곡이 동점이거나 해당 없음으로 떨어진다."
                ),
                "basis": (
                    f"1위와 2위 차가 {tie_gap:g} 미만인 동점 {n_tie}곡, 정합도 {min_match:g} 미만인 "
                    f"해당 없음 {n_none}곡. 템플릿끼리 직교하지 않아 최악 쌍 상관이 0.83"
                ),
                "sample": f"리듬 관측 {len(cls)}곡",
                "confidence": "high",
                "limits": (
                    "프로파일이 저역 킥만 접으므로 킥과 스네어의 합주로 정의되는 유형은 무엇을 재는지 "
                    "불확실하다. 두 기준값은 관습값이며 튜너에서 움직여 확인할 수 있다."
                ),
                "chartId": "rhythm-mix",
            })

    # ③ 코호트가 신곡 중심인가 카탈로그 중심인가. 관측일 기준 추이의 해석 조건이 된다.
    ages = [a for r in resolved if (a := _release_age_days(r)) is not None]
    if ages:
        n_fresh = sum(1 for a in ages if a <= new_days)
        share = n_fresh / len(ages)
        med_age = int(median(ages))
        if share < 0.5:
            out.append({
                "text": (
                    "관측 코호트는 신곡보다 카탈로그 쪽으로 기운 구성으로 읽힌다. 관측일 기준 추이에서 "
                    "소리의 변화와 차트 구성의 변화가 섞여 보이는 상태와 정합한다."
                ),
                "basis": (
                    f"곡 나이 중앙값 {med_age}일, 발매 {new_days}일 이내 신곡 {n_fresh}/{len(ages)}곡"
                    f" ({share * 100:.0f}%)"
                ),
                "sample": f"발매일이 확인된 관측 {len(ages)}건",
                "confidence": "medium",
                "limits": (
                    "발매일은 유통사 표기라 리마스터·재발매가 그 날짜로 잡힌다. 신곡 경계 90일도 "
                    "관습값이다. 이 구성이 섞임을 걷어낸 뷰는 고정 코호트와 신곡만 추이다."
                ),
                "chartId": "age-hist",
            })

    return out


def build_report(
    records: list[dict[str, Any]],
    *,
    generated_at: str,
    provenance: dict[str, Any],
    watchlist: list[str] | None = None,
    min_match: float = MIN_MATCH_DEFAULT,
    tie_gap: float = TIE_GAP_DEFAULT,
    min_prob: float = MIN_PROB_DEFAULT,
    new_days: int = NEW_RELEASE_DAYS,
) -> dict[str, Any]:
    # 옛 스냅샷에도 D-031 파생 지표를 채운 뒤 시작한다 — 이 한 줄 덕분에 아래 전부가
    # 새 스냅샷과 옛 스냅샷을 구별하지 않는다(오디오 재취득 없음, RULES §1).
    records = backfill_derived(records, min_prob=min_prob)
    resolved = [r for r in records if r.get("features")]
    unresolved = [r for r in records if not r.get("features")]
    n, n_un = len(resolved), len(unresolved)

    metrics: list[dict[str, Any]] = [
        {"label": "관측 트랙", "value": n, "unit": "곡", "hint": "프리뷰 해석 성공",
         "section": _METRIC_SECTIONS["관측 트랙"]},
        {
            "label": "미해석",
            "value": n_un,
            "unit": "곡",
            "hint": "프리뷰 없음·디코드 실패·과단축. 0이 아니라 결측으로 집계 제외",
            "section": _METRIC_SECTIONS["미해석"],
        },
    ]
    for field, label, unit in _SURFACED:
        # 원장이 중앙값으로 쓰지 말라고 적은 축은 중앙값 타일을 만들지 않는다.
        if field in _NO_MEDIAN_OR_RANK:
            continue
        vs = _vals(resolved, field)
        if vs:
            m: dict[str, Any] = {
                "label": f"{label} 중앙값",
                "value": round(median(vs), 3),
                "unit": unit,
                "hint": f"관측 {len(vs)}곡의 중앙값 · 분포 지표(단일 곡 비교 아님)",
            }
            # R5 — 정의가 화면에 없으면 해석이 조용히 틀린다.
            if label in _METRIC_DEFS:
                m["definition"] = _METRIC_DEFS[label]
            # 구획을 선언한 리포트에서 `section` 없는 타일은 **어느 구획에서도 렌더되지
            # 않는다**(대시보드가 활성 구획으로 거른다). 표에서 빠뜨리면 조용히 사라지므로
            # 아래 배정 검증이 그것을 잡는다.
            if label in _METRIC_SECTIONS:
                m["section"] = _METRIC_SECTIONS[label]
            metrics.append(m)

    charts: list[dict[str, Any]] = []
    tempos = _vals(resolved, "tempo_bpm")
    if tempos:
        charts.append(
            {"type": "bar", "id": "tempo-hist", "title": "템포 분포 (BPM)",
             "data": _hist(tempos, 60, 180, 8)}
        )
    pulsed = _labeled(resolved, "pulse_clarity")
    if pulsed:
        charts.append(
            {
                "type": "bar",
                "id": "pulse-top",
                "title": "펄스 명료도 상위 · 아티스트 - 곡명 (박이 또렷한 순 · 춤 적합도 아님)",
                "data": sorted(pulsed, key=lambda d: (-d["value"], d["name"]))[:15],
            }
        )

    # ── 리듬 패턴 · 악기 · 스타일 (RULES §3.1.5·§3.1.6)
    rhythm_rows = _rhythm_rows(resolved)
    # 싣는 하한 = 노브 최솟값(_instrument_tunable). 그 아래는 어떤 기준에서도 안 보인다.
    inst_rows = _tag_rows(resolved, "instruments", TOP_K_INSTRUMENT, ship_floor=SHIP_FLOOR)
    for view in (
        _rhythm_tunable(rhythm_rows, min_match=min_match, tie_gap=tie_gap),
        _instrument_tunable(inst_rows, thresh=min_prob),
        _style_mix(resolved),
    ):
        if view:
            charts.append(view)

    # ── 트렌드·비교 뷰 (SPEC §2). 단면 순위만으로는 트렌드가 보이지 않는다.
    latest = max((str(r.get("observed_date") or "") for r in resolved), default="")
    today_rec = [r for r in resolved if str(r.get("observed_date") or "") == latest]
    # 차트 모집단은 `chart_rank` 보유로 선별한다(RULES §1 정체성) — 워치리스트와
    # 병합된 이중 소속 레코드(cohort="watchlist" + chart_rank)도 모집단에 한 번 든다.
    cohort = [r for r in today_rec if r.get("cohort") == "chart" or r.get("chart_rank") is not None]
    focus = [r for r in today_rec if r.get("cohort") == "watchlist"]
    # 고정 코호트 = **최초 관측일에 잡힌 트랙 집합**. 이 집합은 날마다 바뀌지 않으므로
    # 여기서 움직이는 값은 "차트 구성이 바뀐 것"이 아니라 "이 곡들"의 이야기다(D-022·D-023).
    first_date = min((str(r.get("observed_date") or "") for r in resolved), default="")
    fixed_ids = {
        str(r.get("track_id") or "") or _label(r)
        for r in resolved
        if str(r.get("observed_date") or "") == first_date
    }
    fixed = [r for r in resolved if (str(r.get("track_id") or "") or _label(r)) in fixed_ids]
    fresh = [r for r in resolved if (a := _release_age_days(r)) is not None and a <= new_days]

    for view in (
        _median_series(resolved, _UNIT_AXES, "분포 추이 · 0~1 축 중앙값 (날짜가 쌓이며 채워짐)",
                       chart_id="unit-trend"),
        _median_series(resolved, [("tempo_bpm", "템포 중앙값")], "분포 추이 · 템포 중앙값 (BPM)",
                       chart_id="tempo-trend"),
        # ① 발매 빈티지 — x축이 관측일이 아니라 발매 분기라 차트 재편성에 흔들리지 않는다
        _median_series(
            resolved, _UNIT_AXES,
            f"발매 빈티지별 분포 · 0~1 축 중앙값 (발매 분기 · 표본 {VINTAGE_MIN_N}곡 이상)",
            chart_id="vintage-unit",
            key_of=_vintage_key, min_n=VINTAGE_MIN_N, dedup=True,
        ),
        _median_series(
            resolved, [("tempo_bpm", "템포 중앙값")],
            f"발매 빈티지별 템포 · 중앙값 BPM (발매 분기 · 표본 {VINTAGE_MIN_N}곡 이상)",
            chart_id="vintage-tempo",
            key_of=_vintage_key, min_n=VINTAGE_MIN_N, dedup=True,
        ),
        # ② 곡 나이 — 지금 차트가 얼마나 신곡 중심인가, 그리고 그게 움직이는가
        _age_hist(resolved),
        _age_series(resolved),
        # ③ 고정 코호트 — 같은 곡들만 따라가면 구성 변화가 제거된다
        _median_series(fixed, _UNIT_AXES,
                       f"고정 코호트 추이 · {first_date} 관측 {len(fixed_ids)}곡만 계속 추적",
                       chart_id="fixed-cohort"),
        # ④ 신곡만 — 카탈로그 혼입을 걷어낸 분포
        _median_series(fresh, _UNIT_AXES, f"신곡만 분포 추이 · 발매 {new_days}일 이내 (0~1 축 중앙값)",
                       chart_id="fresh-trend"),
        _position_heatmap(focus, cohort),
        _cohort_compare(focus, cohort),
    ):
        if view:
            charts.append(view)

    insights: list[str] = []
    if not resolved:
        insights.append("관측 없음 — 이 입력에서 해석된 프리뷰가 없습니다(수집·매칭 점검 대상).")
    else:
        insights.append(
            f"프리뷰 {n}곡 해석 · 미해석 {n_un}곡 (커버리지 {n}/{n + n_un}). "
            "미해석은 0이 아니라 **결측**으로 집계에서 빠집니다"
        )
    # ── 한계 병기(RULES §4 필수) — 빠지면 §5 위반
    insights.append(
        "⚠ 30초 발췌 · **발췌 위치 비결정**(Apple이 어느 구간을 주는지 비공개). "
        "**곡 간 단일 비교 금지**. 허용되는 사용은 다수 곡의 **분포**와 같은 모집단의 **시계열**뿐입니다"
    )
    insights.append(
        "⚠ 곡 구조(인트로/벌스/훅)·전곡 다이내믹 아크·드롭 타이밍은 30초로 측정 불가. 범위 밖(SPEC §6)"
    )
    insights.append(
        "다이내믹 여유(crest factor) = peak/RMS(dB). 낮을수록 압축이 강합니다. "
        "TESTS §3 검증(2026-07-28). 10곡 표본에서 프리뷰 RMS 스프레드 19.46dB로 **정규화 없음** 확인 "
        "(US 스토어프론트·n=10·단일 시점. Apple이 정책을 바꾸면 재검증 필요)"
    )
    insights.append(
        "펄스 명료도 = 온셋 포락 자기상관의 주 피크. **danceability가 아니며** 춤 실력·인기·품질과 무관합니다(RULES §5)"
    )
    # 마디 격자가 섞였다는 사실을 숨기지 않는다 — 32칸 레코드가 16칸으로 접혀 표시되면
    # 32분·트리플렛 축은 이 화면에 없다(RULES §3.1.5.2). 각주로 미루면 안 읽힌다.
    grids = sorted({int(r.get("bins") or 0) for r in rhythm_rows} - {0})
    if grids:
        shown = min(grids)
        if len(grids) > 1:
            insights.append(
                f"⚠ 마디 격자가 섞여 있습니다({'·'.join(f'{g}칸' for g in grids)}). "
                f"비교 가능한 **{shown}칸으로 내려 맞춰** 표시했습니다(올려 맞추면 없는 정보를 "
                f"만드는 것입니다). 32분·트리플렛 축은 이 화면에 없습니다"
            )
        missing = unrenderable_templates(shown)
        if missing:
            insights.append(
                f"⚠ {shown}칸 격자에서 표현할 수 없는 템플릿은 순위에서 **빠졌습니다**: "
                f"{', '.join(missing)} (반올림해 넣으면 정합도가 음악이 아니라 반올림 오차를 "
                f"재게 됩니다)"
            )
    ages = [a for r in resolved if (a := _release_age_days(r)) is not None]
    if ages:
        n_fresh = sum(1 for a in ages if a <= new_days)
        insights.append(
            f"관측 코호트는 **카탈로그 혼합**입니다. 곡 나이 중앙값 {int(median(ages))}일, "
            f"발매 {new_days}일 이내 신곡은 관측 {len(ages)}건 중 {n_fresh}건입니다. "
            "그래서 관측일 기준 `분포 추이`는 '소리가 변한 것'과 '차트 구성이 바뀐 것'이 섞여 있습니다. "
            "**발매 빈티지·고정 코호트·신곡만 뷰가 그 둘을 분리하려는 것**입니다"
        )
        insights.append(
            "⚠ **발매 빈티지 뷰는 생존 편향이 있습니다**. 옛 분기 칸에 들어간 곡은 그 분기의 대표 "
            "표본이 아니라 **오늘까지 차트에 살아남은 곡**입니다. 따라서 '2021년 음악은 이랬다'가 "
            "아니라 '2021년 발매곡 중 지금도 들리는 것은 이렇다'로만 읽으십시오. 최근 분기로 갈수록 "
            "이 편향은 줄어듭니다"
        )
        insights.append(
            f"⚠ 발매일은 유통사 표기(Apple)이며 **원곡 발매일이 아닐 수 있습니다**. 리마스터·재발매·"
            "지역판이 그날짜로 잡힙니다. 오래된 곡의 빈티지 배치는 그만큼 흔들립니다. "
            f"'신곡' 경계 {new_days}일·빈티지 칸 최소 표본 {VINTAGE_MIN_N}곡도 관습값이라 "
            "담당자가 정할 사안입니다"
        )
    eng = provenance.get("engine_provenance") or {}
    if rhythm_rows:
        cls = [classify_rhythm(x["profile"], min_match=min_match, tie_gap=tie_gap) for x in rhythm_rows]
        n_none = sum(1 for c in cls if c["assigned"] is None)
        n_tie = sum(1 for c in cls if c["tie"])
        insights.append(
            "리듬 패턴 = 마디를 16분음 16칸으로 나눠 저역(20–120Hz) 킥 배치를 접은 뒤 "
            "이름 붙은 유형과 맞춰 본 것입니다. 유형끼리 서로 겹치므로 **가장 가까운 유형은 순위이지 판정이 아닙니다**. "
            "정합도가 낮으면 '다른 유형'이 아니라 '해당 없음'입니다"
        )
        # 막대 높이를 그대로 읽으면 안 되는 이유를 수치로 병기한다(RULES §4 리듬 뷰 규약)
        insights.append(
            f"⚠ 리듬 관측 {len(cls)}곡 중 **{n_tie}곡은 1위와 2위 차가 {tie_gap:g} 미만인 동점**이고 "
            f"**{n_none}곡은 정합도 {min_match:g} 미만이라 '해당 없음'**입니다. 템플릿이 서로 직교하지 않아 "
            "(최악 쌍 상관 0.83) 동점 곡의 유형은 표본이 조금만 흔들려도 뒤집힙니다. "
            "**막대 높이를 곡 수 그대로 읽지 마시고 튜너로 기준을 움직여 확인하십시오**"
        )
        insights.append(
            f"기준값 {min_match:g}(배정 임계)·{tie_gap:g}(동점 폭)는 **엔지니어가 정한 관습값이며 "
            "도메인 근거가 있는 값이 아닙니다**. 결과를 보기 전에 담당자가 정할 사안입니다. "
            "리듬 기준 튜너에서 조정한 값은 되돌려 보낼 수 있습니다"
        )
        insights.append(
            "⚠ 트랩·저지클럽의 특징인 하이햇 롤과 하프타임 스네어는 아직 측정하지 못합니다. "
            "믹스에서 스네어가 분리되지 않습니다(중역 대비 1.22 대 저역 1.71). 지금 내는 것은 "
            "정박·3+3+2·싱코페이션 여부까지입니다"
        )
        insights.append(
            "⚠ 유형 정의에 알려진 결함이 둘 있습니다: `dembow`는 킥+스네어 **합주** "
            "패턴인데 프로파일은 **킥만** 접으므로 무엇을 재고 있는지 불확실하고, "
            "`tresillo(16분·반마디)`는 반 마디에서 끊긴 조각이라 관용 패턴이 아닙니다"
            "(마디 끝까지 이으면 `dembow`와 같은 벡터). 이 두 유형의 곡 수는 특히 조심해서 읽으십시오"
        )
    if inst_rows:
        # 상위 k 절단이 임계 집계에서 조용한 과소집계가 된다 — 몇 곡이 영향권인지 센다
        n_cut = sum(1 for x in inst_rows if x["truncated"] and x["floor"] > min_prob)
        if n_cut:
            insights.append(
                f"⚠ 악기 곡 수는 **하한입니다** — 관측 {len(inst_rows)}곡 중 **{n_cut}곡**은 "
                f"태깅 당시 상위 라벨 일부만 저장돼(가장 낮은 저장 확률이 임계 {min_prob:g}보다 높음) "
                "임계를 넘는 악기가 더 있어도 세지 못합니다. 이후 수집분부터는 40개 악기를 모두 "
                "남기므로 이 하한은 점차 해소됩니다"
            )
    if any((r.get("features") or {}).get("styles") for r in resolved):
        insights.append(
            "⚠ 장르·악기는 **참고용이며 정확도를 아직 재지 않았습니다**(사람 라벨 대조 전). "
            "단독 근거로 쓰지 마시고, 1순위 라벨을 그 곡의 장르로 확정하지 마십시오. "
            "확률은 서로 배타적이지 않습니다"
        )
        insights.append(
            "저지클럽·뭄바톤·아마피아노는 이 태거의 라벨 목록에 없습니다. 그 축은 리듬 패턴이 담당합니다"
        )
        if eng.get("attribution"):
            insights.append(f"장르·악기 모델 출처 {eng['attribution']} · {eng.get('tagger_license')}")
    # C층 구성물 지표 — 병기가 채택 조건이다(RULES §3.1.6.2·§3.1.7 B, D-031).
    if any((r.get("features") or {}).get("valence") is not None for r in resolved):
        insights.append(
            "⚠ 정서가·각성도(valence·arousal)는 **주석자들이 정의한 값**이지 곡의 물리적 성질이 "
            f"아닙니다. {eng.get('valence_head', 'deam')} 기준이며 학습 데이터는 **K-pop이 아닙니다**. "
            "곡 간 단일 비교는 하지 마십시오(발췌 위치가 곡마다 다릅니다)"
        )
    if any((r.get("features") or {}).get("danceability") is not None for r in resolved):
        # 예전에는 타일과 순위 격자에 올려 둔 채 "쓰지 마십시오"라고 안내했다. 무효라고
        # 적은 주장을 그려 놓고 판단만 넘기는 형태여서, 렌더를 멈추고 그 사실을 적는다.
        insights.append(
            "danceability는 **지표 타일과 순위·비교 축에서 뺐습니다**. 차트 K-pop은 거의 전부 이 값이 "
            "천장에 붙어(실측 중앙 0.995 · 상위 10%는 1.000) **코호트 안에서 곡을 가르지 못하기** "
            "때문입니다. 값은 스냅샷에 그대로 남아 있습니다"
        )
        insights.append(
            "⚠ danceability는 분류기가 낸 확률이며 **춤 실력·안무 품질·'춤추기 좋은 정도'의 판정이 "
            "아닙니다**"
        )
    if any((r.get("features") or {}).get("moods") for r in resolved):
        insights.append(
            "무드 태그는 무드와 **용도**(광고·크리스마스·영화)가 한 목록에 섞여 있고 확률도 낮아 "
            "(실측 상위 0.10~0.23) **순위로만** 읽어야 합니다"
        )
    if any((r.get("features") or {}).get("grid_deviation_ms") is not None for r in resolved):
        insights.append(
            "⚠ 그리드 편차는 **상당 부분이 측정 잡음입니다**. 비트 추적이 0.02초 격자라 바닥이 "
            "약 5.8ms인데 실측 중앙값이 8.19ms였습니다. 반대로 아주 큰 값은 그루브가 아니라 "
            "**템포 변화로 직선 맞춤이 실패한 것**입니다. 단독 해석하지 마십시오"
        )
    insights.append(
        f"엔진 {eng.get('engine')} {eng.get('engine_version')} · {eng.get('sample_rate')}Hz "
        f"모노 분석(스테레오 폭만 2채널) · 저역 경계 {eng.get('low_hz')}Hz"
        + (f" · 비트 {eng.get('beat_engine')}({eng.get('beat_checkpoint')})" if eng.get("beat_engine") else "")
        + ". 엔진·설정이 바뀌면 과거 값과 비교할 수 없습니다(RULES §2)"
    )
    if any((r.get("features") or {}).get("tempo_source") == "beat_this-fit" for r in resolved):
        insights.append(
            "템포는 비트 시각에 직선을 맞춰 구합니다. 이전 방식은 값이 고정 격자에만 떨어져 "
            "130BPM 부근에서 6.5BPM보다 작은 변화를 볼 수 없었습니다(101곡이 18개 값만 산출). "
            "격자 값은 `tempo_bpm_grid`로 남겨 과거와 비교할 수 있게 했습니다"
        )
    if watchlist:
        hit = sorted({str(r.get("key")) for r in resolved if r.get("key") in set(watchlist)})
        insights.append(
            f"워치리스트 커버리지 {len(hit)}/{len(watchlist)}"
            + (f" · 잡힌 팀 {', '.join(hit[:8])}" if hit else " · 관측 없음(무신호도 정보)")
        )

    # ── R3·R5: 차트별 질문·정의를 한 표에서 붙인다. 표에 없는 id는 **조용히 넘기지 않는다** —
    # 검사기(scripts/validate_report_data.py)가 question 없는 차트를 잡으므로 여기서 빠뜨리면
    # CI가 멈춘다. 그게 의도다: 새 차트를 추가하면 "이 차트로 무엇을 답하나"를 답해야 한다.
    for c in charts:
        meta = _CHART_META.get(str(c.get("id") or ""))
        if meta:
            c.update(meta)

    # ── D-043: 구획을 선언한다. 놓을 차트가 없는 구획은 선언하지 않는다 — 이름만 있고
    # 눌러도 아무것도 없는 칸이 생기고, 검사기가 그것을 잡는다. 빈 입력에서도 계약이
    # 서야 하므로(라이브 수집이 하루 비는 것은 정상) 여기는 실측이 아니라 charts를 센다.
    sections = [dict(s) for s in _SECTIONS if any(c.get("section") == s["id"] for c in charts)]
    live_secs = {s["id"] for s in sections}
    # 배정된 구획이 살아남지 못한 타일은 **화면에서 사라진다**(대시보드가 활성 구획으로
    # 거른다). 지워지는 대신 첫 구획으로 내려 보낸다 — 축이 하나 빠진 날 지표까지 조용히
    # 없어지면 그것이 결측인지 0인지 화면에서 알 수 없다(§0).
    for m in metrics:
        sid = m.get("section")
        if not live_secs:
            m.pop("section", None)
        elif sid not in live_secs:
            m["section"] = sections[0]["id"]

    summary = _summary_radar(focus, cohort)

    # ── R8: 리포트 전체 기본 신뢰도. 차트별로 다른 것만 그 차트가 덮는다.
    reliability: dict[str, str] = {
        "sample": f"관측 {n}곡 · 미해석 {n_un}곡",
        "accuracy": (
            "템포·펄스 등 측정 지표는 엔진 검증 통과 · 장르·악기·정서 태그는 정확도 미측정"
            if any((r.get("features") or {}).get("styles") for r in resolved)
            else "측정 지표만 수록 · 분류 태그 없음"
        ),
        "engine": (
            f"{eng.get('engine')} {eng.get('engine_version')} · {eng.get('sample_rate')}Hz · "
            f"저역 경계 {eng.get('low_hz')}Hz"
        ),
    }
    if n_un:
        reliability["missing"] = f"프리뷰 없음·디코드 실패·과단축 {n_un}곡 · 0이 아니라 결측으로 집계 제외"
    # 워치리스트 뷰는 표본이 전혀 다른 층이라 최상위 표본을 물려받으면 오독된다.
    for c in charts + [summary]:
        if c.get("id") in {"watchlist-rank", "cohort-compare", "summary-position"}:
            c.setdefault("reliability", {})["sample"] = (
                f"워치리스트 {len(focus)}곡 · 비교 코호트 {len(cohort)}곡"
            )

    # ── R1: 이 탭에서 답할 수 있는 질문. 앵커가 실제로 존재하는 것만 남긴다 —
    # 끊긴 링크는 R1이 고치려는 실패("무엇을 볼지 알 수 없다")를 그대로 되돌려 놓는다.
    have = {str(c.get("id")) for c in charts + [summary] if c.get("id")}
    questions = [
        q
        for q in (
            {"q": "우리가 보는 팀의 소리는 지금 차트에 오른 곡들과 어느 축에서 다른가?", "chartId": "summary-position"},
            {"q": "차트에 오르는 소리가 실제로 바뀌고 있나, 아니면 차트 구성만 바뀐 것인가?", "chartId": "fixed-cohort"},
            {"q": "이 코호트의 킥 배치는 어떤 리듬 유형에 가까운가?", "chartId": "rhythm-mix"},
            {"q": "지금 차트는 신곡 중심인가, 카탈로그 중심인가?", "chartId": "age-hist"},
        )
        if q["chartId"] in have
    ]

    # ── R7: 못 답하는 질문. 커버리지 정직 규율의 UI 형태다. 한계 서술(insights)과 다르다 —
    # 여기 들어가는 것은 사용자가 물으러 왔을 수 있는 **질문**이다.
    not_answered = [
        "곡 구조(인트로·벌스·훅)와 드롭 타이밍. 30초 발췌로는 측정 범위 밖",
        "곡 하나에 대한 평가. 발췌 구간이 곡마다 달라 곡 간 단일 비교가 성립하지 않음",
        "하이햇 롤과 하프타임 스네어. 믹스에서 스네어가 분리되지 않아 아직 측정 못 함",
        "장르·악기 태그가 얼마나 맞는지. 사람 라벨 대조 전이라 정확도 미측정",
        "소리 지표와 차트 성적의 관계. 이 화면은 소리만 다루며 성적을 설명하지 않음",
    ]

    return {
        "moduleId": MODULE_ID,
        "title": "소닉 프로파일 · 30초 프리뷰 기반 소리 지표",
        "subtitle": "분포 안에서의 위치를 보는 증거 · 단일 곡 평결 아님",
        "generatedAt": generated_at,
        "summary": summary,
        "sections": sections,
        "questions": questions,
        "notAnswered": not_answered,
        "reliability": reliability,
        "inferences": _inferences(
            summary=summary, rhythm_rows=rhythm_rows, resolved=resolved,
            min_match=min_match, tie_gap=tie_gap, new_days=new_days,
        ),
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": [
            "차트 진입 직후 트랙만 좁혀 관측하면 비용·법적 노출을 최소화하면서 트렌드를 볼 수 있습니다",
            "지표 해석은 분포 대비 위치로. 임계값이 필요하면 도메인 소유자가 근거를 보기 전에 정하십시오",
        ],
    }


def build_signal_series(
    records: list[dict[str, Any]], *, field: str = "pulse_clarity", provenance: dict[str, Any] | None = None
) -> dict[str, Any]:
    """act × 날짜 → 지표 시리즈 (공유 signal-series 계약).

    계약(packages/signal-series)은 unit 비어있지 않음 + provenance에
    source/generatedAt/window를 요구한다. 스냅샷 provenance(module/version/
    engine_provenance…)는 부가 맥락으로 그대로 실어 보낸다.
    """
    dates = sorted({str(r.get("observed_date")) for r in records if r.get("observed_date")})
    idx = {d: i for i, d in enumerate(dates)}
    series: dict[str, list[Any]] = {}
    for r in records:
        key, d = r.get("key"), r.get("observed_date")
        v = (r.get("features") or {}).get(field)
        if not key or d not in idx or not isinstance(v, (int, float)):
            continue
        series.setdefault(str(key), [None] * len(dates))[idx[str(d)]] = v
    unit = next((u for f, _label, u in _SURFACED if f == field), "") or "unitless"
    return {
        "moduleId": MODULE_ID,
        "signal": field,
        "unit": unit,
        "higherIsStronger": True,
        "dates": dates,
        "series": series,
        "roster": {k: True for k in series},
        "provenance": {
            **(provenance or {}),
            "source": "30초 프리뷰 분석 (sonic-profile signals · 오디오 무보관)",
            "generatedAt": now_iso(),
            "window": f"{dates[0]}..{dates[-1]}" if dates else "",
        },
    }
