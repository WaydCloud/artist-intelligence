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
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

MODULE_ID = "signal-bridge"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_series(path: str) -> dict[str, Any]:
    """Load + minimally validate a signal-series doc (fail loudly on wrong shape — §4)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: signal-series must be an object")
    for key in ("signal", "dates", "series"):
        if key not in doc:
            raise ValueError(f"{path}: signal-series missing required key '{key}'")
    if not isinstance(doc["dates"], list) or not isinstance(doc["series"], dict):
        raise ValueError(f"{path}: 'dates' must be a list and 'series' an object")
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


def analyze(
    social: dict[str, Any],
    chart: dict[str, Any],
    *,
    theta_social: int,
    theta_rank: int,
) -> list[dict[str, Any]]:
    """Per-artist join → onset/lead/class. lead>0 ⇒ 소셜이 차트보다 먼저(선행)."""
    s_dates: list[str] = social["dates"]
    c_dates: list[str] = chart["dates"]
    s_series: dict[str, list[Any]] = social["series"]
    c_series: dict[str, list[Any]] = chart["series"]
    s_roster: dict[str, bool] = social.get("roster", {}) or {}
    c_roster: dict[str, bool] = chart.get("roster", {}) or {}

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
            }
        )
    return rows


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
    s_al = _align(social["dates"], social["series"].get(key, []), union, 0)
    c_al = _align(chart["dates"], chart["series"].get(key, []), union, None)
    s_max = max((v for v in s_al if isinstance(v, (int, float))), default=0) or 1
    social_norm = [round((v or 0) / s_max, 3) for v in s_al]
    chart_strength = [
        round(max(0.0, (theta_rank + 1 - v) / theta_rank), 3) if isinstance(v, (int, float)) else 0.0
        for v in c_al
    ]
    return {
        "type": "line",
        "title": f"선행신호 예시 · {key} — 소셜 버즈 vs 차트 강도 (정규화 0~1)",
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
) -> dict[str, Any]:
    """θ 튜너(view=leadlag, RULES §2) — 원자료 시계열+knobs를 실어 대시보드가
    클라이언트에서 온셋·분류를 재계산한다(§2.1: 값=A&R 소유, static-first)."""
    series: dict[str, Any] = {}
    for r in sorted(rows, key=lambda r: str(r["key"])):
        k = r["key"]
        entry: dict[str, Any] = {}
        if k in social["series"]:
            entry["social"] = social["series"][k]
        if k in chart["series"]:
            entry["chart"] = chart["series"][k]
        if entry:
            series[k] = entry
    return {
        "type": "tunable",
        "title": "θ 튜너 — 온셋 임계를 돌려 분류 변화를 본다 (값=A&R 소유, 기준 원장 §2.1)",
        "data": {
            "view": "leadlag",
            "socialDates": social["dates"],
            "chartDates": chart["dates"],
            "series": series,
            "knobs": [
                {
                    "key": "theta_social",
                    "label": "θ_social · 소셜 온셋(일 게시수 ≥)",
                    "default": theta_social,
                    "min": 1,
                    "max": max(10, theta_social),
                    "step": 1,
                },
                {
                    "key": "theta_rank",
                    "label": "θ_rank · 차트 온셋(순위 ≤)",
                    "default": theta_rank,
                    "min": 10,
                    "max": 200,
                    "step": 10,
                },
            ],
            "note": "임계값은 버전 매겨진 가설(진리 아님) — 슬라이더는 탐색 뷰이고 리포트 정본 수치는 CLI θ로 고정. lead=시간 순서(인과 아님·§0).",
        },
    }


# 활용방안 프레이밍 — 분류별 §0-안전 옵션(증거→검토 대상, 평결 아님)
_ACTION = {
    "social-only": "조사·모니터 우선순위 후보 — 차트 진입 여부 전향 관측 중",
    "social-led": "선행 후보 — 재현성·드라이버(사운드/챌린지) 확인 대상",
    "chart-led": "후행 팬 반응 — 콘텐츠 증폭 참고",
    "chart-only": "소셜 사운드/태그 확산 무관측 — 소셜 액티베이션 여지 검토 대상",
    "coincident": "동시 발생 — 캠페인 동기화 사례 참고",
    "no-signal": "이 창에서 소셜·차트 무신호 — 수집 창/태그 점검 or 휴지기(무신호도 정보)",
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
        lines.append(
            f"[프로필] {_seg(key)} — {r['class']}{lead_txt} · 소셜 {r['posts']}건·참여 {_fmt_eng(engagement.get(key, 0))} "
            f"· 드라이버: {why} · {chart_txt}{yt_txt} → {_ACTION.get(r['class'], '참고')}(§0)"
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
            f"렌즈 온셋 시차: 유효 표본 0 — 다렌즈 온셋 {censored}팀 전부 렌즈별 수집 첫날과 겹쳐 "
            "좌측 절단(수집 전부터 차트인했을 수 있음) 제외. 다일 축적 후 열립니다(§0 정직)."
        )
    summary = " · ".join(f"{k} 선행 {v}팀" for k, v in sorted(counts.items()))
    ex = f" — 예: {', '.join(examples)}" if examples else ""
    return (
        f"렌즈 온셋 순서(수집 개시 이후 온셋만·좌측 절단 {censored}팀 제외): {summary}{ex}. "
        "시차는 시간 순서일 뿐 인과 아님(§0)."
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
        f"⚡ 신규 차트 진입(창 최근 2일): {r['key']} — 온셋 {r['chart_onset']}, 최고 #{r['best_rank']}"
        f"{'·' + ','.join((c_markets.get(r['key']) or [])[:4]) if c_markets.get(r['key']) else ''} — 소셜 신호 보유 팀 (검증 대상, §0)"
        for r in hits[:6]
    ]


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
            "label": "중앙값 선행",
            "value": int(median(lead_vals)) if lead_vals else 0,
            "unit": "일",
            "hint": "소셜 선행 팀 한정 · 표본 극소 · 인과 아님(§0)",
        },
        {
            "label": "소셜-온리 관측대상",
            "value": len(social_only),
            "unit": "팀",
            "hint": "차트 밖 소셜 활성 (pre-mainstream, D-010)",
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
                "hint": f"차트 {w_c}/{len(watch)}{yt_txt} · 양측 {w_b} — 팔로우 acts 중 신호 관측 수",
            }
        )
    mkt_count = (chart.get("provenance") or {}).get("marketCount")

    charts: list[dict[str, Any]] = []
    exemplar = _exemplar(rows, social, chart)
    if exemplar:
        charts.append(_line_overlay(exemplar, social, chart, theta_rank))

    # lead/lag per joined artist (positive = social first). chart-led shown negative.
    join_sorted = sorted(joined, key=lambda r: (-(r["lead_days"] or 0), r["key"]))
    if join_sorted:
        charts.append(
            {
                "type": "bar",
                "title": "팀별 선행/지연 일수 (양수=소셜이 차트보다 먼저, 음수=차트가 먼저)",
                "data": [{"name": r["key"], "value": r["lead_days"]} for r in join_sorted],
            }
        )

    # social-only observation targets (pre-mainstream) by peak buzz
    only_rows = sorted(social_only, key=lambda r: (-r["peak_social"], r["key"]))
    if only_rows:
        charts.append(
            {
                "type": "bar",
                "title": "소셜-온리 · 차트 밖 관측대상 (pre-mainstream, 최고 일간 게시수)",
                "data": [{"name": r["key"], "value": r["peak_social"]} for r in only_rows],
            }
        )

    if rows:  # θ 튜너 — 임계 탐색 뷰(RULES §2 view=leadlag)
        charts.append(_tunable_leadlag(rows, social, chart, theta_social, theta_rank))

    insights = _insights(social, chart, led, chart_led, social_only, chart_only, theta_social, theta_rank)
    alerts = _new_entry_alerts(rows, chart)
    if alerts:  # '누구보다 빠르게' — 신규 진입은 최상단(정직 경고 다음)
        insights[1:1] = alerts
    lens_onset = _lens_onset_insight(chart)  # 렌즈 시차(D-016 ②) — 어느 플랫폼이 먼저 반응하나
    if lens_onset:
        insights.append(lens_onset)
    if watch:
        insights.extend(_profile_lines(rows, social, chart, watch, youtube))
    if chart_only_excluded:
        insights.append(
            f"차트 상위에 있으나 이 해시태그 소셜 버즈가 없는 {chart_only_excluded}곡은 제외(--focus-social) — "
            "선행 질문의 대상은 **버즈가 있는 아티스트**입니다."
        )
    recos = _recos()
    s_win = str((social.get("provenance") or {}).get("window") or "")
    c_win = str((chart.get("provenance") or {}).get("window") or "")
    mkt_txt = f" · 차트 {mkt_count}시장" if isinstance(mkt_count, int) and mkt_count > 1 else ""
    yt_src = " × YT(yt-pulse)" if youtube else ""
    subtitle = (
        f"소셜(fandom-pulse) × 차트(chart-history){yt_src} 선행/지연 · 조인 {len(joined)}팀 · "
        f"θ_social={theta_social}, θ_rank={theta_rank}{mkt_txt} · 소셜 {s_win} / 차트 {c_win}"
    )
    return {
        "moduleId": MODULE_ID,
        "title": "시그널 브리지 — 소셜 → 차트 선행신호",
        "subtitle": subtitle,
        "generatedAt": generated_at,
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": recos,
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
            "⚠ 메커니즘 시연 — 차트측 입력이 **합성 축적 fixture**입니다(실제 다일 collect 미확보). "
            "'소셜이 차트를 선행한다'는 **실증이 아니라** 브리지 배선·판정 로직 시연입니다. "
            "실증은 라이브 다일 collect(fandom-pulse fetch + chart-history collect, N일)가 본선(§0)."
        )
    elif reconstructed:
        eb = prov.get("entered_before_window")
        eb_txt = f" (창 이전 진입 {eb}팀)" if isinstance(eb, int) and eb else ""
        out.append(
            "실 데이터(회고) — 차트 진입일을 **라이브 Kworb 스냅샷의 Days(차트인 일수)로 역산**했습니다"
            f"{eb_txt}. 진입일(온셋)은 실제, 중간 순위는 현재값 근사. **소셜 버즈보다 차트 진입이 앞서면(음수 lead) "
            "= 이미 뜬 곡의 후행 반응**(예: 댄스 커버). 단정 아님(§0)."
        )
    out.append(
        "lead(선행)는 **시간 순서**일 뿐 인과가 아닙니다. 표본 극소 · 참고 신호(§0). "
        "조인 키 = 공유 entity-master 캐노니컬(소셜 사운드→아티스트 ↔ 차트 아티스트, D-007/D-010 데이터 공유)."
    )
    s_win = str((social.get("provenance") or {}).get("window") or "")
    c_win = str((chart.get("provenance") or {}).get("window") or "")
    if s_win[:10] and c_win[:10] and abs((_d(s_win[:10]) - _d(c_win[:10])).days) > 14:
        out.append(
            f"⚠ 창 비대칭 — 소셜 창({s_win})과 차트 창({c_win})의 시작이 크게 다릅니다. "
            "태그 수집이 과거 게시물을 소급하므로 회고 lead 절대값은 창 산물일 수 있음 — 방향 판단은 전향 축적으로(§0)."
        )
    if led:
        detail = ", ".join(f"{r['key']}(+{r['lead_days']}d)" for r in sorted(led, key=lambda r: (-r["lead_days"], r["key"]))[:5])
        out.append(f"소셜 선행 관측 {len(led)}팀: {detail} — 소셜 버즈가 차트 진입보다 앞선 사례. 검증 대상이지 예측 아님.")
    if chart_led:
        detail = ", ".join(f"{r['key']}({r['lead_days']}d)" for r in chart_led[:5])
        out.append(f"차트 선행(소셜 지연) {len(chart_led)}팀: {detail} — 소셜이 차트를 뒤따른 반례. 선행은 자동이 아님(정직).")
    if social_only:
        out.append(
            f"소셜-온리 {len(social_only)}팀({_names(sorted(social_only, key=lambda r: (-r['peak_social'], r['key'])))} 등) — "
            "차트 밖 소셜 활성. pre-mainstream 조사 우선순위 후보(D-010) · 진출 지시 아님(§0)."
        )
    if chart_only:
        out.append(f"차트-온리 {len(chart_only)}팀({_names(chart_only)} 등) — 이 해시태그 소셜 사운드 확산 없이 차트 존재.")
    out.append(
        f"온셋 기준(기준 원장 §3): 소셜 온셋 = 일간 게시수 ≥ θ_social({theta_social}), "
        f"차트 온셋 = 순위 ≤ θ_rank({theta_rank}). 임계값=A&R 소유(파라미터 노출)."
    )
    return out


def _recos() -> list[str]:
    return [
        "라이브 다일 collect를 축적(fandom-pulse fetch #tag 매일 + chart-history collect 매일)하면 "
        "합성 fixture를 실데이터로 대체해 선행 여부를 실증할 수 있습니다 — 이것이 본선입니다.",
        "θ_social(버즈 온셋)·θ_rank(차트 온셋)은 A&R 판단으로 조정하세요(--theta-social·--theta-rank) — "
        "기준은 버전 매겨진 가설입니다(기준 원장).",
        "소셜-온리 관측대상은 조사 우선순위 후보일 뿐 확정이 아닙니다 — 개별 검증 필요(§0).",
    ]
