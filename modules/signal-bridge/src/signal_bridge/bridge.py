"""signal-bridge core — join two per-artist signal-series and surface temporal lead/lag.

Question: does #kpopdance **social buzz** (fandom-pulse `signals`) precede **chart
entry** (chart-history `signals`)? Both modules emit the shared *signal-series* data
contract (see SPEC.md); this bridge joins them on the identical entity-master canonical
key — no cross-module code import (D-007/D-010, data-only sharing).

책임소재 불변식(§0): lead(선행)는 **시간 순서일 뿐 인과가 아니다**. 출력은 증거·관측대상이며
"뜰 팀" 평결이 아니다. 임계값 θ_social·θ_rank는 **기준**(RULES §3, 값=A&R 소유, 파라미터로 노출).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median
from typing import Any

MODULE_ID = "signal-bridge"

# 진입 요약(R2)의 id. `questions`·`inferences`가 앵커하는 대상이라 한 곳에 둔다.
SUMMARY_ID = "class-mix"

# 막대 차트 한 장에 그리는 최대 행 수. 264줄짜리 막대는 읽는 것이 아니라 스크롤하는 것이다.
# 자른 사실은 **신뢰도 라인에 적는다** — 말없이 자르면 화면이 전부를 보여준 것처럼 읽힌다.
TOP_ROWS = 30


def _capped(total: int, what: str) -> str:
    """신뢰도 라인용 표본 문구 — 잘랐으면 잘랐다고 적는다."""
    return f"{what} {total}팀" + (f" · 상위 {TOP_ROWS}팀만 표시" if total > TOP_ROWS else "")

# ── 구획·문구 (D-043 · DESIGN §6.1·§7.1) ──────────────────────────────────────
#
# 이 탭은 **네 개의 다른 질문**에 답한다: 누가 먼저였나 · 한 팀에서 실제로 어떻게 겹치나
# · 차트 밖에서 도는 팀은 누구인가 · 기준을 움직이면 분류가 어떻게 달라지나. 요약이
# 답하는 "선행이 보편적인가"는 다섯째 질문이고, 이 탭에서 가장 오해받기 쉬운 지점이라
# 첫 화면의 도형 하나로 나간다 — 반례(차트가 먼저인 팀)를 같은 도형에 놓는다.
_SECTIONS: list[dict[str, str]] = [
    {
        "id": "leadlag",
        "label": "선행·지연",
        "question": "소셜과 차트 중 어느 쪽이 먼저인가?",
        "note": "일수는 시간 순서일 뿐 인과가 아니다. 두 창의 시작이 다르면 회고로 잰 선행 일수는 "
        "창의 산물일 수 있고, 수집 개시일과 온셋이 같은 팀은 '그날 진입'과 '이미 있었음'을 구분하지 못한다.",
    },
    {
        "id": "example",
        "label": "한 팀 보기",
        "question": "한 팀에서 두 신호는 어떻게 겹치나?",
        "note": "두 축은 단위가 달라 0~1로 각각 정규화한 값이다. 선의 높낮이를 서로 견주지 않고 "
        "**오르내리는 시점**만 본다.",
    },
    {
        "id": "pre",
        "label": "차트 밖",
        "question": "소셜에서 도는데 차트에 없는 팀은?",
        "note": "차트에 없다는 것은 이번 수집 창의 차트에서 보이지 않았다는 뜻이다. 조사 후보이며 "
        "진출 지시가 아니다.",
    },
    {
        "id": "tuner",
        "label": "기준",
        "question": "기준을 움직이면 분류가 달라지나?",
        "note": "온셋 기준은 담당자가 소유한다. 여기서 움직이는 것은 화면 안의 계산이다.",
    },
]

_CHART_META: dict[str, dict[str, str]] = {
    "lead-days": {
        "section": "leadlag",
        "title": "소셜이 먼저였던 팀 · 며칠 먼저",
        "question": "소셜 버즈가 차트보다 먼저 움직인 팀은 어디이고 얼마나 먼저인가?",
        "definition": "소셜 온셋 날짜와 차트 온셋 날짜의 차이(일). 온셋은 각 기준을 처음 넘은 날이며 "
        "수집 창 안에서만 정해진다. 시간 순서일 뿐 인과가 아니다.",
    },
    "lag-days": {
        "section": "leadlag",
        "title": "차트가 먼저였던 팀 · 며칠 먼저",
        "question": "소셜이 차트를 뒤따른 반례는 얼마나 되나?",
        "definition": "차트 온셋이 소셜 온셋보다 앞선 팀과 그 간격(일). **선행이 항상 성립하지 않는다는 "
        "반례**이며, 이 목록이 옆의 선행 목록과 같은 크기라면 선행은 규칙이 아니라 절반의 사례다.",
    },
    # 두 관문을 통과한 팀은 §3.1 교차 요약의 마지막 칸이고, 지금까지 **문장 안에만** 있었다.
    # 문장은 사람이 읽으라고 쓴 것이라 계약이 아니고, 읽는 표면(랜딩 서사)이 그 이름을 쓰려면
    # 문자열을 파싱해야 했다 — 파싱하는 순간 문구를 다듬을 때마다 그 표면이 조용히 틀린다.
    # 수(`판정 가능 선행`)는 지표가 이미 들고 있으므로 여기서 더하는 것은 **이름**뿐이다.
    "gate-passed": {
        "section": "leadlag",
        "title": "두 관문을 함께 통과한 팀 · 며칠 먼저",
        "question": "표본과 절단을 함께 통과한 팀은 누구인가?",
        # 정의는 **행이 하나일 때도 참이어야 한다.** "막대 길이는 선행 일수"라고 적었더니
        # 통과 1팀인 날에는 화면에 막대가 없어(대시보드가 비교 없는 길이를 그리지 않는다)
        # 정의가 없는 것을 가리켰다. 값이 무엇인지로 적으면 두 경우 다 선다.
        "definition": "소셜 선행 중 소셜 표본이 기준을 채우고 차트 온셋이 좌측 절단도 아닌 팀. 값은 "
        "선행 일수다. 통과는 선행이 사실이라는 판정이 아니라 **판단에 필요한 증거가 갖춰졌다는** "
        "뜻이며, 여기 없는 팀도 지운 것이 아니라 옆 목록에 근거와 함께 남아 있다.",
    },
    "lead-example": {
        "section": "example",
        "title": "한 팀에서 본 두 신호",
        "question": "두 신호가 겹치는 모양은 실제로 어떤가?",
        "definition": "소셜 버즈는 그 팀의 최고 일간 게시수를 1로 둔 값, 차트 강도는 순위가 높을수록 1에 "
        "가까워지는 값이다. 단위가 다른 두 축을 각각 정규화한 것이라 높낮이를 서로 견주지 않는다.",
    },
    "social-only": {
        "section": "pre",
        "title": "차트 밖에서 도는 팀 · 최고 일간 게시수",
        "question": "차트에 아직 없는데 소셜에서 도는 팀은 누구인가?",
        "definition": "이번 창의 차트 온셋이 없고 소셜 온셋만 있는 팀. 값은 그 팀의 하루 최고 게시수다. "
        "조사·모니터 후보이며 진출 지시가 아니다.",
    },
    "leadlag-tuner": {
        "section": "tuner",
        "title": "온셋 기준을 움직여 다시 분류하기",
        "question": "기준을 바꾸면 어느 팀이 선행으로 남나?",
        "definition": "두 슬라이더는 소셜·차트의 온셋 기준이다. 화면 안에서 분류를 다시 계산할 뿐 "
        "원자료와 원장의 기준값을 바꾸지 않는다.",
    },
}

_METRIC_META: dict[str, dict[str, str]] = {
    "추적 아티스트": {
        "section": "pre",
        "definition": "두 신호 중 하나라도 있는 팀의 수. 이 화면이 보는 전체 모집단이다.",
    },
    "조인(양측 신호)": {
        "section": "leadlag",
        "label": "두 신호가 다 있는 팀",
        "definition": "소셜과 차트 양쪽에서 온셋이 잡힌 팀의 수. 선행·지연을 잴 수 있는 대상이다.",
    },
    "소셜 선행": {
        "section": "leadlag",
        "definition": "소셜 온셋이 차트 온셋보다 앞선 팀의 수. 시간 순서이며 인과가 아니다.",
    },
    # 두 관문을 따로 센다. RULES §3.1이 "검열은 시간이 풀고 소표본은 기준값 문제라 두 축을
    # 섞어 보고하지 않는다"고 적어 두었는데, 지표가 최종 통과 수 하나뿐이면 읽는 사람은
    # 65에서 1로 줄어든 것만 보고 **무엇이 걸러 냈는지**를 알 수 없다.
    "표본 충족 선행": {
        "section": "leadlag",
        "label": "표본을 채운 선행",
        "definition": "소셜 선행 중 소셜 표본이 기준을 채운 팀의 수. 차트 온셋의 좌측 절단은 "
        "아직 거르지 않은 단계다. 이 관문은 기준값이 정하는 것이라 시간이 지나도 저절로 풀리지 않는다.",
    },
    "판정 가능 선행": {
        "section": "leadlag",
        "definition": "소셜 선행 중 표본이 기준 이상이고 차트 온셋이 좌측 절단되지 않은 팀의 수. "
        "나머지는 판단을 보류한다. 앞의 표본 관문과 달리 절단은 수집이 쌓이면 풀린다.",
    },
    "중앙값 선행": {
        "section": "leadlag",
        "definition": "소셜 선행 팀들의 선행 일수 중앙값. 표본이 극소라 값이 쉽게 흔들린다.",
    },
    "소셜-온리 관측대상": {
        "section": "pre",
        "label": "차트 밖에서 도는 팀",
        "definition": "이번 창에서 차트 온셋 없이 소셜 온셋만 있는 팀의 수.",
    },
    "차트-온리": {
        "section": "pre",
        "label": "소셜 신호가 없는 팀",
        "definition": "차트 온셋만 있고 이 해시태그 소셜 신호가 없는 팀의 수.",
    },
    "워치리스트 커버리지": {
        "section": "pre",
        "definition": "팔로우하는 팀 중 소셜 신호가 관측된 팀의 비율. 수집이 관심 대상을 실제로 "
        "비추고 있는지 보는 검증 지표다.",
    },
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_series(path: str) -> dict[str, Any]:
    """Load + minimally validate a signal-series doc (fail loudly on wrong shape — §4)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    # TRY004(TypeError를 쓰라)는 여기서 맞지 않는다 — 검사 대상은 호출자가 넘긴 인자가
    # 아니라 **디스크에서 읽은 파일의 내용**이다. 잘못된 규격의 데이터는 타입 오류가
    # 아니라 값 오류이고, 호출자에게 "파일이 틀렸다"로 읽혀야 한다.
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: signal-series must be an object")  # noqa: TRY004
    for key in ("signal", "dates", "series"):
        if key not in doc:
            raise ValueError(f"{path}: signal-series missing required key '{key}'")
    if not isinstance(doc["dates"], list) or not isinstance(doc["series"], dict):
        raise ValueError(f"{path}: 'dates' must be a list and 'series' an object")  # noqa: TRY004
    return doc


def load_watchlist(path: str | None) -> list[str]:
    """watchlist.json → 팔로우 acts의 캐노니컬 key 목록 (data-only, D-007/D-013)."""
    if not path or not Path(path).exists():
        return []
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    artists = doc.get("artists") if isinstance(doc, dict) else None
    if not isinstance(artists, list):
        return []
    return [a["key"] for a in artists if isinstance(a, dict) and isinstance(a.get("key"), str)]


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _social_onset(dates: list[str], values: list[Any], theta: int) -> str | None:
    for d, v in zip(dates, values):
        if isinstance(v, (int, float)) and v >= theta:
            return d
    return None


def _chart_onset(dates: list[str], values: list[Any], theta_rank: int) -> str | None:
    for d, v in zip(dates, values):
        if isinstance(v, (int, float)) and v <= theta_rank:
            return d
    return None


def _peak_social(values: list[Any]) -> int:
    nums = [int(v) for v in values if isinstance(v, (int, float))]
    return max(nums) if nums else 0


def _best_rank(values: list[Any]) -> int | None:
    nums = [int(v) for v in values if isinstance(v, (int, float))]
    return min(nums) if nums else None


def _align(dates: list[str], values: list[Any], union: list[str], fill: Any) -> list[Any]:
    idx = {d: i for i, d in enumerate(dates)}
    return [values[idx[d]] if d in idx else fill for d in union]


def _earliest_observable(chart: dict[str, Any]) -> dict[str, str]:
    """act → 그 act가 관측될 수 있었던 최초일 (RULES §3.1 `censored` 판정용).

    act가 잡힌 렌즈들의 수집 첫날 중 가장 이른 날. 차트 온셋이 이 날과 같으면
    "그날 진입"과 "이미 진입해 있었음"을 구분할 수 없다(좌측 절단).
    """
    first: dict[str, str] = (chart.get("provenance") or {}).get("platformFirstDates") or {}
    onsets: dict[str, dict[str, str]] = chart.get("platformOnsets") or {}
    out: dict[str, str] = {}
    for key, per_platform in onsets.items():
        dates = [first[p] for p in per_platform if p in first]
        if dates:
            out[key] = min(dates)
    return out


def analyze(
    social: dict[str, Any],
    chart: dict[str, Any],
    *,
    theta_social: int,
    theta_rank: int,
) -> list[dict[str, Any]]:
    """Per-artist join → onset/lead/class. lead>0 ⇒ 소셜이 차트보다 먼저(선행).

    각 행은 분류만이 아니라 **판정 근거**(누적 게시수·게시일수·좌측 절단 여부)를
    함께 싣는다 — 분류 단독으로는 그것을 믿을지 판단할 재료가 없다(RULES §3.1).
    """
    s_dates: list[str] = social["dates"]
    c_dates: list[str] = chart["dates"]
    s_series: dict[str, list[Any]] = social["series"]
    c_series: dict[str, list[Any]] = chart["series"]
    s_roster: dict[str, bool] = social.get("roster", {}) or {}
    c_roster: dict[str, bool] = chart.get("roster", {}) or {}
    earliest = _earliest_observable(chart)

    rows: list[dict[str, Any]] = []
    for key in sorted(set(s_series) | set(c_series)):
        s_vals = s_series.get(key, [])
        c_vals = c_series.get(key, [])
        s_onset = _social_onset(s_dates, s_vals, theta_social) if s_vals else None
        c_onset = _chart_onset(c_dates, c_vals, theta_rank) if c_vals else None
        lead: int | None = None
        if s_onset and c_onset:
            lead = (_d(c_onset) - _d(s_onset)).days
            klass = "social-led" if lead > 0 else ("coincident" if lead == 0 else "chart-led")
        elif s_onset:
            klass = "social-only"
        elif c_onset:
            klass = "chart-only"
        else:
            continue  # signal present but never crossed either onset threshold
        rows.append(
            {
                "key": key,
                "roster": bool(s_roster.get(key) or c_roster.get(key)),
                "social_onset": s_onset,
                "chart_onset": c_onset,
                "lead_days": lead,
                "class": klass,
                "peak_social": _peak_social(s_vals),
                "posts": sum(int(v) for v in s_vals if isinstance(v, (int, float))),
                "best_rank": _best_rank(c_vals),
                # 원인분석 레이어 (RULES §3.1) — 분류를 믿을지 판단할 재료
                "social_days": sum(1 for v in s_vals if isinstance(v, (int, float)) and v > 0),
                "censored": bool(c_onset and earliest.get(key) and c_onset == earliest[key]),
            }
        )
    return rows


def _evidence(r: dict[str, Any]) -> str:
    """행의 판정 근거를 한 조각 문자열로 (RULES §3.1 전파 규약)."""
    parts = [f"소셜 {r['posts']}건/{r['social_days']}일"]
    if r.get("censored"):
        parts.append("차트온셋 좌측절단(수집 개시일과 동일 — 이전 진입 배제 못함)")
    return " · ".join(parts)


def _exemplar(rows: list[dict[str, Any]], social: dict[str, Any], chart: dict[str, Any]) -> str | None:
    """Richest joined artist for the overlay visual — prefer social-led (the lead story),
    else chart-led (the honest lagging story: chart already high, social reacts later)."""
    pool = [r for r in rows if r["class"] == "social-led"] or [
        r for r in rows if r["class"] == "chart-led"
    ]
    if not pool:
        return None

    def richness(r: dict[str, Any]) -> tuple[int, int, str]:
        s_vals = social["series"].get(r["key"], [])
        c_vals = chart["series"].get(r["key"], [])
        pts = sum(1 for v in s_vals if isinstance(v, (int, float)) and v > 0)
        pts += sum(1 for v in c_vals if isinstance(v, (int, float)))
        return (pts, abs(r["lead_days"] or 0), r["key"])

    return max(pool, key=richness)["key"]


def _line_overlay(
    key: str, social: dict[str, Any], chart: dict[str, Any], theta_rank: int
) -> dict[str, Any]:
    """One artist: normalized social buzz vs chart strength over union dates (선행 시각화)."""
    union = sorted(set(social["dates"]) | set(chart["dates"]))
    # 🔴 **관측하지 않은 날을 0으로 그리지 않는다**(R6). 두 신호의 수집 창이 다르므로 합집합
    # 날짜에는 한쪽만 있는 구간이 있고, 거기에 0을 채우면 화면이 "그때는 차트에 없었다"고
    # 말한다 — 사실은 "그때는 아직 수집하지 않았다"다. 실제로 2026-07-30 육안 검사에서
    # 차트 강도 선이 넉 달 동안 바닥에 붙어 있다가 수집 개시일에 1로 치솟고 있었다.
    # 없는 값은 null로 두고 선을 끊는다(렌더러가 그렇게 그린다).
    s_al = _align(social["dates"], social["series"].get(key, []), union, None)
    c_al = _align(chart["dates"], chart["series"].get(key, []), union, None)
    s_max = max((v for v in s_al if isinstance(v, (int, float))), default=0) or 1
    social_norm = [round(v / s_max, 3) if isinstance(v, (int, float)) else None for v in s_al]
    chart_strength = [
        round(max(0.0, (theta_rank + 1 - v) / theta_rank), 3) if isinstance(v, (int, float)) else None
        for v in c_al
    ]
    seen_s = sum(1 for v in social_norm if v is not None)
    seen_c = sum(1 for v in chart_strength if v is not None)
    return {
        "type": "line",
        "id": "lead-example",
        "reliability": {
            "sample": f"{key} · 창 {len(union)}일 중 소셜 관측 {seen_s}일 · 차트 관측 {seen_c}일",
            "missing": "관측하지 않은 날은 선을 끊는다(0으로 잇지 않는다). 두 신호의 수집 창이 다르다",
        },
        "data": {
            "x": union,
            "series": [
                {"name": "소셜 버즈(정규화)", "values": social_norm},
                {"name": "차트 강도(정규화, 201−rank 개념)", "values": chart_strength},
            ],
        },
    }


def _tunable_leadlag(
    rows: list[dict[str, Any]],
    social: dict[str, Any],
    chart: dict[str, Any],
    theta_social: int,
    theta_rank: int,
    min_posts: int,
) -> dict[str, Any]:
    """θ 튜너(view=leadlag, RULES §2) — 원자료 시계열+knobs를 실어 대시보드가
    클라이언트에서 온셋·분류를 재계산한다(§2.1: 값=A&R 소유, static-first)."""
    series: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    for r in sorted(rows, key=lambda r: str(r["key"])):
        k = r["key"]
        entry: dict[str, Any] = {}
        if k in social["series"]:
            entry["social"] = social["series"][k]
        if k in chart["series"]:
            entry["chart"] = chart["series"][k]
        if entry:
            series[k] = entry
            # 판정 근거를 함께 실어야 클라이언트가 거를 수 있다 (RULES §3.1)
            evidence[k] = {
                "posts": r["posts"],
                "days": r["social_days"],
                "censored": bool(r.get("censored")),
            }
    return {
        "type": "tunable",
        "id": "leadlag-tuner",
        "reliability": {"sample": f"시계열이 있는 팀 {len(series)}팀"},
        "data": {
            "view": "leadlag",
            "socialDates": social["dates"],
            "chartDates": chart["dates"],
            "series": series,
            "knobs": [
                {
                    "key": "theta_social",
                    "label": "소셜 온셋 기준 (일 게시수 ≥)",
                    "default": theta_social,
                    "min": 1,
                    "max": max(10, theta_social),
                    "step": 1,
                },
                {
                    "key": "theta_rank",
                    "label": "차트 온셋 기준 (순위 ≤)",
                    "default": theta_rank,
                    "min": 10,
                    "max": 200,
                    "step": 10,
                },
                {
                    "key": "min_posts",
                    "label": "최소 누적 게시수 (표본 하한)",
                    "default": min_posts,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                },
                {
                    "key": "exclude_censored",
                    "label": "좌측 절단 온셋 제외",
                    "default": 0,
                    "min": 0,
                    "max": 1,
                    "step": 1,
                },
            ],
            "evidence": evidence,
            "note": "기준값은 조정 가능한 가설. 슬라이더는 탐색용이고 리포트 수치는 고정 기준으로 산출. "
            "'좌측 절단' = 차트 온셋이 수집 개시일과 같아 이전 진입을 배제 못하는 상태(축적되면 풀림). "
            "선행 = 시간 순서일 뿐 인과 아님",
        },
    }


# 활용방안 프레이밍 — 분류별 §0-안전 옵션(증거→검토 대상, 평결 아님)
_ACTION = {
    "social-only": "조사·모니터 우선순위 후보 · 차트 진입 여부 관측 중",
    "social-led": "선행 후보 · 재현성과 드라이버(사운드/챌린지) 확인 대상",
    "chart-led": "후행 팬 반응 · 콘텐츠 증폭 참고",
    "chart-only": "소셜 확산 무관측 · 소셜 활성화 여지 검토 대상",
    "coincident": "동시 발생 · 캠페인 동기화 사례 참고",
    "no-signal": "이 창에서 소셜·차트 무신호 · 수집 창/태그 점검 또는 휴지기(무신호도 정보)",
}


def _fmt_eng(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


# 프로필 라인 문법 구분자(RULES §4.1) — 자유텍스트(키·드라이버·영상 제목)에 이 시퀀스가
# 들어오면 무공백형으로 접어 라인 파싱을 보존한다(대시보드 카드 렌더 계약).
_PROFILE_DELIMS = ((" — ", "—"), (" · ", "·"), (" → ", "→"))


def _seg(text: str) -> str:
    for seq, folded in _PROFILE_DELIMS:
        text = text.replace(seq, folded)
    return text


def _profile_lines(
    rows: list[dict[str, Any]],
    social: dict[str, Any],
    chart: dict[str, Any],
    watch: list[str],
    youtube: dict[str, Any] | None = None,
    limit: int = 12,
) -> list[str]:
    """워치리스트 acts의 WHO·얼마나·왜·활용 프로필 (judgment-support, §0: 증거+옵션)."""
    engagement: dict[str, int] = social.get("engagement") or {}
    drivers: dict[str, Any] = social.get("drivers") or {}
    c_markets: dict[str, list[str]] = chart.get("markets") or {}
    c_platforms: dict[str, list[str]] = chart.get("platforms") or {}
    yt_subs: dict[str, int] = (youtube or {}).get("subscribers") or {}
    yt_videos: dict[str, Any] = (youtube or {}).get("videos") or {}
    by_key = {r["key"]: r for r in rows}
    # 워치리스트는 신호가 없어도 프로필에 남긴다(무신호도 정보) — 조인 행 없으면 스텁
    watched = [by_key.get(k) or {"key": k, "class": "no-signal", "posts": 0, "best_rank": None, "lead_days": None} for k in watch]
    watched.sort(key=lambda r: (-r["posts"], r["key"]))
    lines: list[str] = []
    for r in watched[:limit]:
        key = r["key"]
        drv = drivers.get(key) or {}
        why = _seg(", ".join((drv.get("sounds") or [])[:2] + (drv.get("tags") or [])[:2])) or "—"
        if r["best_rank"] is not None:
            mk = c_markets.get(key) or []
            mk_txt = f"{len(mk)}시장({','.join(mk[:5])}{'…' if len(mk) > 5 else ''})" if mk else "시장 미상"
            pf = c_platforms.get(key) or []
            # 플랫폼 병기(D-016) — 단일 spotify(기존 레일)면 생략, 그 외엔 어느 렌즈에 잡혔는지 명시
            pf_txt = f"·{'+'.join(pf)}" if pf and pf != ["spotify"] else ""
            chart_txt = f"차트 최고 #{r['best_rank']}·{mk_txt}{pf_txt}"
        else:
            chart_txt = "차트 미진입"
        lead_txt = f"({'+' if (r['lead_days'] or 0) > 0 else ''}{r['lead_days']}d)" if r["lead_days"] is not None else ""
        yt_txt = ""
        if key in yt_subs or key in yt_videos:
            vid = yt_videos.get(key) or {}
            v_part = f"·'{_seg(str(vid.get('title') or '')[:24])}' +{_fmt_eng(int(vid.get('avg_daily') or 0))}/일" if vid else ""
            yt_txt = f" · YT 구독 {_fmt_eng(yt_subs.get(key, 0))}{v_part}"
        # 좌측 절단이면 선행 일수를 그대로 읽으면 안 된다 — 카드에서 바로 보이게 (RULES §3.1)
        cens_txt = " · ⓘ 차트온셋 좌측절단(수집 개시일과 동일 — 선행 일수는 창 산물일 수 있음)" if r.get("censored") else ""
        lines.append(
            f"[프로필] {_seg(key)} — {r['class']}{lead_txt} · 소셜 {r['posts']}건·참여 {_fmt_eng(engagement.get(key, 0))} "
            f"· 드라이버: {why} · {chart_txt}{yt_txt}{cens_txt} → {_ACTION.get(r['class'], '참고')}"
        )
    return lines


def _lens_onset_insight(chart: dict[str, Any]) -> str | None:
    """렌즈 온셋 순서(D-016 ②) — 어느 플랫폼이 먼저 반응했는가(집계·검열 보정).

    렌즈별 수집 첫날과 같은 온셋 = 좌측 절단(수집 시작 전부터 있었을 수 있음) → 제외.
    유효 표본이 없으면 정직하게 '아직 없음'을 말한다(§0). 시차 = 시간 순서, 인과 아님.
    """
    onsets: dict[str, Any] = chart.get("platformOnsets") or {}
    first: dict[str, str] = (chart.get("provenance") or {}).get("platformFirstDates") or {}
    if not onsets or len(first) < 2:
        return None
    counts: dict[str, int] = {}
    examples: list[str] = []
    censored = 0
    for key in sorted(onsets):
        po = onsets[key]
        if not isinstance(po, dict) or len(po) < 2:
            continue
        valid = {p: d for p, d in po.items() if first.get(p) and d > first[p]}
        if len(valid) < 2:
            censored += 1
            continue
        earliest = min(valid.values())
        firsts = sorted(p for p, d in valid.items() if d == earliest)
        label = "동시" if len(firsts) == len(valid) else "+".join(firsts)
        counts[label] = counts.get(label, 0) + 1
        if label != "동시" and len(examples) < 3:
            seq = " → ".join(f"{p} {d}" for p, d in sorted(valid.items(), key=lambda x: (x[1], x[0])))
            examples.append(f"{key}({seq})")
    if not counts:
        return (
            f"플랫폼 온셋 시차: 유효 표본 0. 복수 플랫폼 온셋 {censored}팀 전부 수집 첫날과 겹쳐 "
            "제외(수집 전부터 차트인했을 수 있음). 여러 날 쌓이면 산출"
        )
    summary = " · ".join(f"{k} 선행 {v}팀" for k, v in sorted(counts.items()))
    ex = f" · 예: {', '.join(examples)}" if examples else ""
    return (
        f"플랫폼 온셋 순서(수집 개시 이후 온셋만·집계 제외 {censored}팀 제외): {summary}{ex}. "
        "시차는 시간 순서일 뿐 인과 아님."
    )


def _new_entry_alerts(rows: list[dict[str, Any]], chart: dict[str, Any]) -> list[str]:
    """차트 온셋이 창 마지막 2일 내 = 신규 진입 — '빠르게'의 핵심 알림 (사실 신호)."""
    c_dates: list[str] = chart.get("dates") or []
    if len(c_dates) < 2:
        return []
    recent = set(c_dates[-2:])
    c_markets: dict[str, list[str]] = chart.get("markets") or {}
    hits = [r for r in rows if r["chart_onset"] in recent and r["posts"] > 0]
    hits.sort(key=lambda r: (r["best_rank"] or 999, r["key"]))
    return [
        f"⚡ 신규 차트 진입(창 최근 2일): {r['key']} · 온셋 {r['chart_onset']}, 최고 #{r['best_rank']}"
        f"{'·' + ','.join((c_markets.get(r['key']) or [])[:4]) if c_markets.get(r['key']) else ''}"
        f" · {_evidence(r)} · 소셜 신호 보유 팀(검증 대상)"
        for r in hits[:6]
    ]


def _gate_passed(led: list[dict[str, Any]], min_posts: int) -> list[dict[str, Any]]:
    """두 관문(표본 하한 · 비검열)을 함께 통과한 `social-led` 행, 선행 일수 내림차순.

    **한 곳에서만 판정한다.** 교차 요약 문장(`_evidence_crosstab`)과 `gate-passed` 차트가
    각자 같은 조건을 적으면 한쪽만 고쳐질 때 화면의 두 자리가 다른 팀을 말하게 된다.
    지표 `판정 가능 선행`의 수도 같은 조건이라 셋이 어긋나면 안 된다.
    """
    passed = [r for r in led if r["posts"] >= min_posts and not r.get("censored")]
    passed.sort(key=lambda r: (-r["lead_days"], r["key"]))
    return passed


def _evidence_crosstab(joined: list[dict[str, Any]], min_posts: int) -> str | None:
    """표본 × 검열 교차표 (RULES §3.1) — 헤드라인 숫자 하나로 뭉개지 않는다."""
    led = [r for r in joined if r["class"] == "social-led"]
    if not led:
        return None
    cell = {(s, c): 0 for s in (False, True) for c in (False, True)}
    for r in led:
        cell[(r["posts"] >= min_posts, bool(r.get("censored")))] += 1
    clean = _gate_passed(led, min_posts)
    ex = (
        " · 양쪽 통과: "
        + ", ".join(f"{r['key']}(+{r['lead_days']}d·{r['posts']}건)" for r in clean[:5])
        if clean
        else " · 양쪽 통과 0팀"
    )
    return (
        f"판정 근거 교차(소셜 선행 {len(led)}팀): "
        f"소표본(<{min_posts}건)·검열 {cell[(False, True)]}팀 · 소표본·비검열 {cell[(False, False)]}팀 · "
        f"충분표본·검열 {cell[(True, True)]}팀 · 충분표본·비검열 {cell[(True, False)]}팀{ex}. "
        "검열 = 차트 온셋이 수집 개시일과 같아 '그날 진입'과 '이미 있었음'을 구분 못함(축적되면 풀림). "
        "소표본은 시간이 풀지 않는 기준값 문제다. 두 축은 성격이 다르다"
    )


# ── 시각화 계약 헬퍼 (D-041 · D-043) ──────────────────────────────────────────
#
# 다른 모듈에도 같은 모양의 함수가 있다. 공유 모듈로 묶지 않는 것이 이 레포의 구조다
# (D-007: 모듈은 코드가 아니라 데이터·계약을 공유한다).


def _apply_meta(
    metrics: list[dict[str, Any]], charts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """차트·지표에 구획과 문구를 붙이고, 표에 없는 차트는 **떨어낸다**(R3)."""
    for m in metrics:
        meta = _METRIC_META.get(str(m.get("label") or ""))
        if not meta:
            continue
        m["section"] = meta["section"]
        m["definition"] = meta["definition"]
        if meta.get("label"):  # 라벨 갈아 끼우기는 맨 마지막 — 위 조회가 원래 라벨을 키로 쓴다
            m["label"] = meta["label"]

    kept: list[dict[str, Any]] = []
    for c in charts:
        meta = _CHART_META.get(str(c.get("id") or ""))
        if meta:
            c.update(meta)
            kept.append(c)
    return kept


def _place_sections(
    metrics: list[dict[str, Any]], charts: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """차트가 실제로 놓인 구획만 남기고, 구획을 잃은 지표를 되찾아 준다."""
    sections = [dict(s) for s in _SECTIONS if any(c.get("section") == s["id"] for c in charts)]
    if len(sections) < 2:  # 구획이 하나뿐이면 내비게이션이 할 일이 없다 → 한 줄 렌더
        sections = []
    live = {s["id"] for s in sections}
    for m in metrics:
        sid = str(m.get("section") or "")
        if not sid or sid in live:
            continue
        if sections:
            m["section"] = str(sections[0]["id"])
        else:
            m.pop("section", None)
    return sections


def _class_mix_summary(
    led: list[dict[str, Any]],
    chart_led: list[dict[str, Any]],
    coincident: list[dict[str, Any]],
    social_only: list[dict[str, Any]],
) -> dict[str, Any]:
    """진입 요약 하나(R2) — **선행이 규칙인가 절반의 사례인가**.

    이 탭에서 가장 오해받기 쉬운 지점이 "소셜이 먼저다"라는 한 줄이라, 첫 화면의 도형에
    반례(차트가 먼저인 팀)를 같은 눈금 위에 놓는다. 선행만 세어 보여주면 그 수가 곧
    법칙처럼 읽힌다.
    """
    return {
        "type": "bar",
        "id": SUMMARY_ID,
        "title": "어느 쪽이 먼저였나",
        "question": "소셜이 먼저인 사례와 차트가 먼저인 사례 중 어느 쪽이 많나?",
        "definition": f"두 신호의 온셋 순서로 팀을 가른 수. 차트 온셋이 없어 순서를 잴 수 없는 팀 "
        f"{len(social_only)}팀은 여기 없고 '차트 밖' 구획에 있다(같은 눈금에 얹으면 그 수가 커서 "
        f"비교가 눌린다). 순서는 시간 순서일 뿐 인과가 아니며, 두 창의 시작이 다르면 이 구성도 "
        f"함께 흔들린다.",
        "data": [
            {"name": "소셜이 먼저", "value": len(led)},
            {"name": "차트가 먼저", "value": len(chart_led)},
            {"name": "같은 날", "value": len(coincident)},
        ],
    }


def _questions(have: set[str]) -> list[dict[str, str]]:
    """R1 — 이 탭에서 답할 수 있는 질문(상한 4). 끊긴 앵커는 검사기가 잡는다."""
    kept = [
        q
        for q in (
            {"q": "소셜이 먼저인 사례와 차트가 먼저인 사례 중 어느 쪽이 많나?", "chartId": SUMMARY_ID},
            {"q": "소셜이 먼저 움직인 팀은 얼마나 먼저였나?", "chartId": "lead-days"},
            {"q": "차트에 아직 없는데 소셜에서 도는 팀은 누구인가?", "chartId": "social-only"},
            {"q": "기준을 바꾸면 어느 팀이 선행으로 남나?", "chartId": "leadlag-tuner"},
        )
        if q["chartId"] in have
    ]
    for spare in (
        {"q": "두 신호가 다 있는 팀은 몇 팀인가?", "chartId": SUMMARY_ID},
        {"q": "순서를 잴 수 없는 팀은 몇 팀인가?", "chartId": SUMMARY_ID},
    ):
        if len(kept) >= 3:
            break
        kept.append(spare)
    return kept


def _not_answered() -> list[str]:
    """R7 — 이 화면이 **답하지 않는** 질문."""
    return [
        "이 버즈가 차트 진입을 만들었는지. 이 화면이 재는 것은 시간 순서까지다",
        "버즈 없이 차트에 오른 곡이 어떻게 올랐는지. 여기 대상은 버즈가 있는 팀이다",
        "해시태그를 붙이지 않은 확산. 소셜 쪽 표본은 태그와 사운드 라벨에 매여 있다",
        "수집을 시작하기 전의 순위 이력. 그 이전은 좌측 절단이라 알 수 없다",
        "같은 팀에서 선행이 다시 관측되는지. 창이 짧아 재현성은 아직 보지 못한다",
    ]


def _bridge_inferences(
    *,
    led: list[dict[str, Any]],
    chart_led: list[dict[str, Any]],
    joined: list[dict[str, Any]],
    social_only: list[dict[str, Any]],
    min_posts: int,
    s_win: str,
    c_win: str,
) -> list[dict[str, Any]]:
    """태그된 자동 추론(R4 · D-039). 전부 관측에서 계산한다.

    허용 어법은 "~와 정합한다"·"~신호가 있다"·"~로 읽힌다"뿐이고, 명령·예측·인과 단정과
    em dash는 scripts/validate_report_data.py가 CI에서 잡는다.
    """
    out: list[dict[str, Any]] = []

    # ① 선행이 규칙이 아니라는 것. 반례의 수를 같은 문장에 적는다.
    if led and chart_led:
        out.append({
            "text": f"소셜 선행이 항상 성립하지는 않는 상태와 정합한다. 소셜이 먼저인 팀이 {len(led)}팀, "
            f"차트가 먼저인 팀이 {len(chart_led)}팀이다.",
            "basis": f"두 신호가 다 있는 {len(joined)}팀 중 소셜 선행 {len(led)}팀 · 차트 선행 "
            f"{len(chart_led)}팀",
            "sample": f"두 신호가 다 있는 팀 {len(joined)}팀",
            "confidence": "high",
            "limits": "온셋은 수집 창 안에서만 정해진다. 두 창의 시작이 다르면 이 구성도 함께 흔들린다.",
            "chartId": SUMMARY_ID,
        })

    # ② 표본과 좌측 절단을 함께 통과한 팀이 몇인지 — 숫자를 크게 읽지 않도록.
    if led:
        solid = [r for r in led if r["posts"] >= min_posts and not r.get("censored")]
        out.append({
            "text": f"선행 {len(led)}팀 중 표본과 절단을 함께 통과한 팀은 {len(solid)}팀으로 읽힌다.",
            "basis": f"표본 {min_posts}건 이상 · 차트 온셋 비검열 = {len(solid)}팀 / 선행 {len(led)}팀",
            "sample": f"소셜 선행 {len(led)}팀",
            "confidence": "medium",
            "limits": "표본 부족은 기준값의 문제이고 절단은 시간이 푸는 문제라, 두 축은 성격이 다르다. "
            "남은 팀도 판정이 아니라 검토 대상이다.",
            "chartId": "lead-days",
        })

    # ③ 창 비대칭 — 회고로 잰 선행 일수가 창의 산물일 수 있다는 것.
    s0, c0 = s_win[:10], c_win[:10]
    if s0 and c0 and s0 < c0:
        out.append({
            "text": "회고로 잰 선행 일수가 창의 산물일 수 있는 상태와 정합한다. 소셜 창이 차트 창보다 "
            "먼저 시작한다.",
            "basis": f"소셜 {s_win} · 차트 {c_win}",
            "sample": f"두 신호가 다 있는 팀 {len(joined)}팀",
            "confidence": "high",
            "limits": "태그 수집은 과거 게시물을 함께 가져오므로 소셜 쪽 시작이 앞당겨진다. 방향 판단은 "
            "앞으로의 축적으로 본다.",
            "chartId": "lead-days",
        })
    return out


def build_report(
    social: dict[str, Any],
    chart: dict[str, Any],
    *,
    generated_at: str,
    theta_social: int = 1,
    theta_rank: int = 50,
    focus_social: bool = False,
    watchlist: list[str] | None = None,
    youtube: dict[str, Any] | None = None,
    min_posts: int = 20,
) -> dict[str, Any]:
    rows = analyze(social, chart, theta_social=theta_social, theta_rank=theta_rank)
    # focus: the leading-signal question is about artists WITH social buzz; drop pure
    # chart-only acts (songs charting without this hashtag's buzz) so they don't drown it.
    chart_only_excluded = 0
    if focus_social:
        chart_only_excluded = sum(1 for r in rows if r["class"] == "chart-only")
        rows = [r for r in rows if r["class"] != "chart-only"]
    by_class: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_class.setdefault(r["class"], []).append(r)

    led = by_class.get("social-led", [])
    chart_led = by_class.get("chart-led", [])
    coincident = by_class.get("coincident", [])
    social_only = by_class.get("social-only", [])
    chart_only = by_class.get("chart-only", [])
    joined = led + chart_led + coincident
    lead_vals = sorted(r["lead_days"] for r in led)

    metrics: list[dict[str, Any]] = [
        {"label": "추적 아티스트", "value": len(rows), "unit": "팀", "hint": "두 신호 합집합"},
        {"label": "조인(양측 신호)", "value": len(joined), "unit": "팀", "hint": "소셜·차트 온셋 모두 존재"},
        {"label": "소셜 선행", "value": len(led), "unit": "팀", "hint": "소셜 버즈가 차트 진입보다 먼저"},
        {
            "label": "표본 충족 선행",
            "value": sum(1 for r in led if r["posts"] >= min_posts),
            "unit": "팀",
            "hint": f"소셜 선행 중 누적 게시 ≥{min_posts}건 (좌측 절단은 아직 거르지 않음)",
        },
        {
            "label": "판정 가능 선행",
            "value": sum(1 for r in led if r["posts"] >= min_posts and not r.get("censored")),
            "unit": "팀",
            "hint": f"소셜 선행 중 표본 ≥{min_posts}건 · 차트 온셋 비검열 (RULES §3.1 · 나머지는 판단 보류)",
        },
        {
            "label": "중앙값 선행",
            "value": int(median(lead_vals)) if lead_vals else 0,
            "unit": "일",
            "hint": "소셜 선행 팀 한정 · 표본 극소 · 인과 아님",
        },
        {
            "label": "소셜-온리 관측대상",
            "value": len(social_only),
            "unit": "팀",
            "hint": "차트 진입 전 소셜 활성",
        },
        {"label": "차트-온리", "value": len(chart_only), "unit": "팀", "hint": "소셜 사운드 확산 없음"},
    ]
    watch = watchlist or []
    if watch:  # 커버리지 = 수집이 워치리스트를 실제로 비추는가 (검증 지표, D-013)
        keys_social = set(social["series"])
        keys_chart = set(chart["series"])
        w_s = sum(1 for k in watch if k in keys_social)
        w_c = sum(1 for k in watch if k in keys_chart)
        w_b = sum(1 for k in watch if k in keys_social and k in keys_chart)
        yt_keys = set((youtube or {}).get("series") or {})
        yt_txt = f" · YT {sum(1 for k in watch if k in yt_keys)}/{len(watch)}" if youtube else ""
        metrics.append(
            {
                "label": "워치리스트 커버리지",
                "value": f"{w_s}/{len(watch)}",
                "unit": "소셜",
                "hint": f"차트 {w_c}/{len(watch)}{yt_txt} · 양측 {w_b} · 팔로우 팀 중 신호 관측 수",
            }
        )
    mkt_count = (chart.get("provenance") or {}).get("marketCount")

    charts: list[dict[str, Any]] = []
    exemplar = _exemplar(rows, social, chart)
    if exemplar:
        charts.append(_line_overlay(exemplar, social, chart, theta_rank))

    # 선행과 지연을 **두 차트로 가른다**. 예전에는 부호 있는 값 하나를 막대에 실었는데,
    # 막대 길이는 음수를 그릴 수 없어(렌더러가 최소 폭으로 클램프한다) 차트 선행 팀들이
    # 전부 같은 길이의 짧은 막대가 됐다 — 44팀의 차이가 화면에서 사라진 상태였다.
    # 부호는 방향이지 크기가 아니므로, 방향은 차트를 가르는 데 쓰고 길이에는 크기만 싣는다.
    led_sorted = sorted(led, key=lambda r: (-(r["lead_days"] or 0), r["key"]))
    if led_sorted:
        charts.append(
            {
                "type": "bar",
                "id": "lead-days",
                "reliability": {
                    "sample": _capped(len(led_sorted), "소셜 선행")
                    + f" · 두 신호가 다 있는 팀 {len(joined)}팀"
                },
                "data": [{"name": r["key"], "value": r["lead_days"]} for r in led_sorted[:TOP_ROWS]],
            }
        )
    lag_sorted = sorted(chart_led, key=lambda r: (r["lead_days"] or 0, r["key"]))
    if lag_sorted:
        charts.append(
            {
                "type": "bar",
                "id": "lag-days",
                "reliability": {
                    "sample": _capped(len(lag_sorted), "차트 선행")
                    + f" · 두 신호가 다 있는 팀 {len(joined)}팀"
                },
                "data": [
                    {"name": r["key"], "value": abs(r["lead_days"] or 0)} for r in lag_sorted[:TOP_ROWS]
                ],
            }
        )

    # 두 관문을 통과한 팀 — 지표는 수를, 이 차트는 **이름**을 싣는다(RULES §3.1).
    # 통과 0팀이면 차트를 만들지 않는다. 빈 막대 카드는 "통과한 팀이 없다"가 아니라
    # "그릴 것이 없다"로 읽히고, 그 사실은 지표(`판정 가능 선행` 0)와 교차 요약이 이미 말한다.
    passed = _gate_passed(led, min_posts)
    if passed:
        charts.append(
            {
                "type": "bar",
                "id": "gate-passed",
                "reliability": {
                    "sample": _capped(len(passed), "두 관문 통과")
                    + f" · 소셜 선행 {len(led)}팀 중 · 표본 하한 {min_posts}건",
                    "missing": "표본이 하한에 못 미치거나 차트 온셋이 좌측 절단인 팀은 여기 없다. "
                    "지운 것이 아니라 선행 목록에 사유와 함께 남아 있다",
                },
                "data": [{"name": r["key"], "value": r["lead_days"]} for r in passed[:TOP_ROWS]],
            }
        )

    # social-only observation targets (pre-mainstream) by peak buzz
    only_rows = sorted(social_only, key=lambda r: (-r["peak_social"], r["key"]))
    if only_rows:
        charts.append(
            {
                "type": "bar",
                "id": "social-only",
                "reliability": {"sample": _capped(len(only_rows), "차트 온셋 없는 팀")},
                "data": [
                    {"name": r["key"], "value": r["peak_social"]} for r in only_rows[:TOP_ROWS]
                ],
            }
        )

    if rows:  # θ 튜너 — 임계 탐색 뷰(RULES §2 view=leadlag)
        charts.append(_tunable_leadlag(rows, social, chart, theta_social, theta_rank, min_posts))

    insights = _insights(social, chart, led, chart_led, social_only, chart_only, theta_social, theta_rank)
    alerts = _new_entry_alerts(rows, chart)
    if alerts:  # '누구보다 빠르게' — 신규 진입은 최상단(정직 경고 다음)
        insights[1:1] = alerts
    # 원인분석 교차표(RULES §3.1)는 선행 목록 바로 뒤 — 숫자를 보는 순간 근거도 같이 본다
    crosstab = _evidence_crosstab(joined, min_posts)
    if crosstab:
        insights.append(crosstab)
    lens_onset = _lens_onset_insight(chart)  # 렌즈 시차(D-016 ②) — 어느 플랫폼이 먼저 반응하나
    if lens_onset:
        insights.append(lens_onset)
    if watch:
        insights.extend(_profile_lines(rows, social, chart, watch, youtube))
    if chart_only_excluded:
        insights.append(
            f"차트 상위에 있으나 이 해시태그 소셜 버즈가 없는 {chart_only_excluded}곡은 제외. "
            "선행 분석의 대상은 **버즈가 있는 아티스트**"
        )
    recos = _recos()
    s_win = str((social.get("provenance") or {}).get("window") or "")
    c_win = str((chart.get("provenance") or {}).get("window") or "")
    mkt_txt = f" · 차트 {mkt_count}시장" if isinstance(mkt_count, int) and mkt_count > 1 else ""
    yt_src = " × YT(yt-pulse)" if youtube else ""
    # 부제에서 기준값 표기(θ)를 걷어낸다 — 신뢰도 라인의 `engine`이 말로 들고 있다(DESIGN §6.1).
    # 모듈 id는 남긴다: 대시보드가 이 문자열에서 출처 모듈을 찾아 탭 링크를 만든다.
    subtitle = (
        f"소셜(fandom-pulse) × 차트(chart-history){yt_src} 선행/지연 · "
        f"두 신호가 다 있는 팀 {len(joined)}팀{mkt_txt} · 소셜 {s_win} / 차트 {c_win}"
    )
    charts = _apply_meta(metrics, charts)
    # 예시 차트의 제목만 동적이다 — 어느 팀을 골랐는지가 제목에 없으면 카드가 무엇을
    # 보여주는지 알 수 없다. 표의 문구를 덮는 유일한 자리라 여기 한 줄로 둔다.
    for c in charts:
        if c.get("id") == "lead-example" and exemplar:
            c["title"] = f"{exemplar} · 두 신호의 겹침"
    sections = _place_sections(metrics, charts)
    extra: dict[str, Any] = {
        "summary": _class_mix_summary(led, chart_led, coincident, social_only),
        "questions": _questions({str(c["id"]) for c in charts} | {SUMMARY_ID}),
        "notAnswered": _not_answered(),
        "reliability": {
            "sample": f"추적 {len(rows)}팀 · 두 신호가 다 있는 팀 {len(joined)}팀 "
            f"· 소셜 {s_win or '?'} / 차트 {c_win or '?'}",
            "accuracy": "이름 매칭은 공용 아티스트 사전 기준. 온셋은 수집 창 안에서만 정해지며 정확도 미측정",
            "missing": "수집 개시일과 차트 온셋이 같은 팀은 좌측 절단이라 '그날 진입'과 '이미 있었음'을 "
            "구분하지 못한다",
            "engine": f"signal-bridge · 소셜 온셋 ≥{theta_social}건/일 · 차트 온셋 ≤{theta_rank}위",
        },
        "inferences": _bridge_inferences(
            led=led,
            chart_led=chart_led,
            joined=joined,
            social_only=social_only,
            min_posts=min_posts,
            s_win=s_win,
            c_win=c_win,
        ),
    }
    if sections:
        extra["sections"] = sections

    return {
        "moduleId": MODULE_ID,
        "title": "시그널 브리지 · 소셜 → 차트 선행신호",
        "subtitle": subtitle,
        "generatedAt": generated_at,
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": recos,
        **extra,
    }


def _names(rows: list[dict[str, Any]], n: int = 5) -> str:
    return ", ".join(r["key"] for r in rows[:n])


def _insights(
    social: dict[str, Any],
    chart: dict[str, Any],
    led: list[dict[str, Any]],
    chart_led: list[dict[str, Any]],
    social_only: list[dict[str, Any]],
    chart_only: list[dict[str, Any]],
    theta_social: int,
    theta_rank: int,
) -> list[str]:
    out: list[str] = []
    prov = chart.get("provenance") or {}
    chart_note = str(prov.get("note") or "")
    synthetic = bool(prov.get("synthetic")) or "합성" in chart_note or "synthetic" in chart_note.lower()
    reconstructed = bool(prov.get("reconstructed"))
    if synthetic:
        out.append(
            "⚠ 메커니즘 시연 · 차트측 입력이 **합성 샘플**(실제 다일 수집 미확보). "
            "'소셜이 차트를 선행한다'는 **실증이 아니라** 판정 로직 시연. "
            "실증은 여러 날의 라이브 수집이 기준"
        )
    elif reconstructed:
        eb = prov.get("entered_before_window")
        eb_txt = f" (창 이전 진입 {eb}팀)" if isinstance(eb, int) and eb else ""
        out.append(
            "실 데이터(회고) · 차트 진입일을 **라이브 Kworb 스냅샷의 Days(차트인 일수)로 역산**했습니다"
            f"{eb_txt}. 진입일(온셋)은 실제, 중간 순위는 현재값 근사. **소셜 버즈보다 차트 진입이 앞서면(음수 lead) "
            "= 이미 뜬 곡의 후행 반응**(예: 댄스 커버). 단정 아님."
        )
    out.append(
        "선행(lead)은 **시간 순서**일 뿐 인과 아님. 표본 극소 · 참고 신호. "
        "이름 매칭은 공용 아티스트 사전 기준(소셜 사운드와 차트 아티스트를 같은 이름으로 연결)."
    )
    s_win = str((social.get("provenance") or {}).get("window") or "")
    c_win = str((chart.get("provenance") or {}).get("window") or "")
    if s_win[:10] and c_win[:10] and abs((_d(s_win[:10]) - _d(c_win[:10])).days) > 14:
        out.append(
            f"⚠ 창 비대칭 · 소셜 창({s_win})과 차트 창({c_win})의 시작이 크게 다름. "
            "태그 수집이 과거 게시물을 소급해 회고 선행 일수는 창 산물일 수 있음. 방향 판단은 앞으로의 축적으로"
        )
    if led:
        detail = ", ".join(f"{r['key']}(+{r['lead_days']}d)" for r in sorted(led, key=lambda r: (-r["lead_days"], r["key"]))[:5])
        out.append(f"소셜 선행 관측 {len(led)}팀: {detail}. 소셜 버즈가 차트 진입보다 앞선 사례, 검증 대상이지 예측 아님")
    if chart_led:
        detail = ", ".join(f"{r['key']}({r['lead_days']}d)" for r in chart_led[:5])
        out.append(f"차트 선행(소셜 지연) {len(chart_led)}팀: {detail}. 소셜이 차트를 뒤따른 반례, 선행이 항상 성립하지는 않음")
    if social_only:
        out.append(
            f"소셜-온리 {len(social_only)}팀({_names(sorted(social_only, key=lambda r: (-r['peak_social'], r['key'])))} 등) · "
            "차트 진입 전 소셜 활성. 조사 우선순위 후보이며 진출 지시 아님"
        )
    if chart_only:
        out.append(f"차트-온리 {len(chart_only)}팀({_names(chart_only)} 등) · 이 해시태그의 소셜 확산 없이 차트에 존재")
    out.append(
        f"온셋(상승 시작) 기준: 소셜 = 일간 게시수 ≥ {theta_social}, "
        f"차트 = 순위 ≤ {theta_rank}. 기준값은 담당자가 조정 가능"
    )
    return out


def _recos() -> list[str]:
    return [
        # 컬렉션 안의 암묵 문자열 연결은 쉼표 누락과 구분되지 않는다 — 괄호로 묶는다(ISC004).
        (
            "라이브 다일 collect를 축적(fandom-pulse fetch #tag 매일 + chart-history collect 매일)하면 "
            "합성 샘플을 실데이터로 대체하면 선행 여부 실증 가능. 이것이 본선"
        ),
        "온셋 기준값은 담당자 판단으로 조정 가능. 기준은 조정 가능한 가설",
        "소셜-온리 관측대상은 조사 우선순위 후보일 뿐 확정 아님. 개별 검증 필요",
    ]
