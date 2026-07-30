"""Build schema-valid report.json + yt-velocity signal-series from facts-only snapshots.

Official-channel firepower/velocity signals only — no hit prediction, no popularity
verdict (RULES §5, §0). Thresholds live in RULES §3 (기준 원장) as tunable params.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

MODULE_ID = "yt-pulse"

# 진입 요약(R2)의 id. `questions`·`inferences`가 앵커하는 대상이라 문자열을 한 곳에 둔다.
SUMMARY_ID = "velocity-by-act"

# ── 구획·문구 (D-043 · DESIGN §6.1·§7.1) ──────────────────────────────────────
#
# 이 탭은 **두 개의 다른 질문**에 답한다: 얼마나 쌓였나 · 지금 무엇이 올라오나. 요약이
# 답하는 "지금 무엇이 가장 빠른가"는 셋째 질문이고 첫 화면의 도형 하나로 나간다(R2).
#
# 쌓인 조회와 지금의 속도는 **다른 축**이다. 오래 쌓인 팀이 지금 빠른 팀과 같지 않다는
# 것이 이 탭이 실제로 보여주는 것이라, 둘을 같은 구획에 겹쳐 놓지 않는다.
_SECTIONS: list[dict[str, str]] = [
    {
        "id": "reach",
        "label": "쌓인 조회",
        "question": "공식 채널에 조회가 얼마나 쌓였나?",
        "note": "채널 캐시에 들어 있는 최근 업로드만 더한 값이다. 영상을 많이 올리는 팀이 커지는 값이라 "
        "팀의 크기나 인기가 아니다. 레이블 채널에 올라간 영상은 이 표본에 없다.",
    },
    {
        "id": "fresh",
        "label": "새 영상",
        "question": "지금 새 영상이 도는 팀은 어디인가?",
        "note": "업로드가 있다는 것은 캠페인이 돌고 있다는 신호로 읽을 수 있을 뿐, 성과가 아니다. "
        "판정 기간은 조정 가능한 기준이다.",
    },
]

_CHART_META: dict[str, dict[str, str]] = {
    "views-by-act": {
        "section": "reach",
        "title": "팀별 조회 합",
        "question": "수집한 영상의 조회는 어느 팀이 큰가?",
        "definition": "채널 캐시에 있는 영상의 조회수를 팀별로 더한 값. 영상 수가 많을수록 커지므로 "
        "팀 사이의 크기 비교가 아니라 이 표본 안에서의 합이다.",
    },
    "fresh-by-act": {
        "section": "fresh",
        "title": "최근 업로드 수",
        "question": "최근에 새 영상을 올린 팀은 어디인가?",
        "definition": "기준일로부터 판정 기간 안에 공개된 영상 수. 채널 캐시가 최근 업로드 위주라 "
        "이 수가 수집 영상 수와 가까울 수 있다.",
    },
}

# 지표의 구획·정의·라벨을 한 표에 모은다(DESIGN §6.1). `velocity`처럼 우리끼리 쓰던 말은
# 화면에서 걷어내고 가리키는 것을 그대로 쓴다.
_METRIC_META: dict[str, dict[str, str]] = {
    "추적 팀": {
        "section": "reach",
        "definition": "채널이 확인되고 영상이 하나라도 수집된 팀의 수. 워치리스트 전체가 아니다.",
    },
    "최근작 영상": {
        "section": "reach",
        "label": "수집한 영상",
        "definition": "이번 스냅샷에 들어 있는 영상 수. 같은 영상이 여러 날 잡히면 최신 것 하나로 센다.",
    },
    "최근작 조회 합": {
        "section": "reach",
        "label": "조회 합",
        "definition": "수집한 영상의 조회수를 모두 더한 값. 공개 집계 수치이며 인기의 총점이 아니다.",
    },
    "최고 평균 일 조회(velocity)": {
        "section": "fresh",
        "label": "가장 빠른 영상의 일 조회",
        "definition": "수집한 영상 중 평균 일 조회가 가장 높은 한 편의 값. 조회수를 공개 후 지난 날로 나눈 "
        "수명 평균이라, 갓 올라온 영상의 초반 화력은 낮게 잡힌다.",
    },
    "신작": {
        "section": "fresh",
        "label": "새 영상",
        "definition": "판정 기간 안에 공개된 영상 수. 기간은 캠페인 주기에 맞춰 조정 가능한 가설이다.",
    },
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _i(rec: dict[str, object], key: str) -> int:
    v = rec.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


def _s(rec: dict[str, object], key: str) -> str:
    v = rec.get(key)
    return v if isinstance(v, str) else ""


def _date(iso: str) -> date | None:
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def avg_daily(views: int, published_at: str, asof: str) -> int:
    """평균 일 조회(velocity 프록시, RULES §3): views ÷ max(1, 경과일). 수명 평균 근사."""
    pub, ref = _date(published_at), _date(asof)
    days = max(1, (ref - pub).days) if pub and ref else 1
    return round(views / days)


def _latest_per_video(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """다일 스냅샷 병합 시 같은 영상은 최신(최다 views) 레코드만."""
    best: dict[str, dict[str, object]] = {}
    for r in records:
        vid = _s(r, "video_id")
        if not vid:
            continue
        if vid not in best or _i(r, "views") > _i(best[vid], "views"):
            best[vid] = r
    return sorted(best.values(), key=lambda r: (_s(r, "artist"), _s(r, "video_id")))


# ── 시각화 계약 헬퍼 ──────────────────────────────────────────────────────────
#
# chart-history·fandom-pulse에도 같은 모양의 함수가 있다. **공유 모듈로 묶지 않는 것이
# 이 레포의 구조**다(D-007: 모듈은 코드를 공유하지 않고 데이터·계약만 공유한다). 공통 규격은
# `report.schema.json`과 `scripts/validate_report_data.py`가 들고 있고, 그것이 정본이다.


def _apply_meta(
    metrics: list[dict[str, object]], charts: list[dict[str, object]]
) -> list[dict[str, object]]:
    """차트·지표에 구획과 문구를 붙이고, 표에 없는 차트는 **떨어낸다**(R3).

    새 차트를 추가하면 `_CHART_META`에 한 줄을 적어야 하고, 그 한 줄이 "이 차트로 무엇을
    답하나"를 먼저 답하게 만든다.
    """
    for m in metrics:
        meta = _METRIC_META.get(str(m.get("label") or ""))
        if not meta:
            continue
        m["section"] = meta["section"]
        m["definition"] = meta["definition"]
        if meta.get("label"):  # 라벨 갈아 끼우기는 맨 마지막 — 위 조회가 원래 라벨을 키로 쓴다
            m["label"] = meta["label"]

    kept: list[dict[str, object]] = []
    for c in charts:
        meta = _CHART_META.get(str(c.get("id") or ""))
        if meta:
            c.update(meta)
            kept.append(c)
    return kept


def _place_sections(
    metrics: list[dict[str, object]], charts: list[dict[str, object]]
) -> list[dict[str, str]]:
    """차트가 실제로 놓인 구획만 남기고, 구획을 잃은 지표를 되찾아 준다.

    렌더러는 활성 구획의 지표만 그린다 — 사라진 구획을 가리키는 지표는 화면 어디에도
    놓이지 못한 채 조용히 빠진다.
    """
    sections = [dict(s) for s in _SECTIONS if any(c.get("section") == s["id"] for c in charts)]
    if len(sections) < 2:  # 구획이 하나뿐이면 내비게이션이 할 일이 없다 → 한 줄 렌더(하위 호환)
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


def _velocity_summary(pairs: list[tuple[str, int]], n_videos: int, n_acts: int) -> dict[str, object]:
    """진입 요약 하나(R2) — **지금 무엇이 가장 빠른가**.

    쌓인 조회(누적)와 지금의 속도는 다른 축이고, 이 탭에서 하중을 받는 쪽은 속도다.
    막대에 싣는 값은 일 조회(셀 수 있는 크기)이며 순위가 아니다.
    """
    return {
        "type": "bar",
        "id": SUMMARY_ID,
        "title": "팀별 대표 평균 일 조회",
        "question": "지금 가장 빠르게 조회를 모으는 팀은 어디인가?",
        "definition": "팀의 영상 중 평균 일 조회가 가장 높은 한 편의 값(조회수 ÷ 공개 후 지난 날, 상위 8팀). "
        "수명 전체 평균이라 갓 올라온 영상의 초반 화력은 낮게, 오래된 영상은 평탄하게 잡힌다. "
        "채널 규모가 크면 같은 반응에서도 값이 커진다.",
        "reliability": {"sample": f"팀 {n_acts}팀 · 영상 {n_videos}개"},
        "data": [{"name": a, "value": v} for a, v in pairs[:8]],
    }


def _questions(have: set[str]) -> list[dict[str, str]]:
    """R1 — 이 탭에서 답할 수 있는 질문(상한 4). 끊긴 앵커는 검사기가 잡는다."""
    kept = [
        q
        for q in (
            {"q": "지금 가장 빠르게 조회를 모으는 팀은 어디인가?", "chartId": SUMMARY_ID},
            {"q": "수집한 영상의 조회는 어느 팀이 큰가?", "chartId": "views-by-act"},
            {"q": "최근에 새 영상을 올린 팀은 어디인가?", "chartId": "fresh-by-act"},
        )
        if q["chartId"] in have
    ]
    for spare in (
        {"q": "가장 빠른 영상을 가진 팀은 어디인가?", "chartId": SUMMARY_ID},
        {"q": "이번 수집에 잡힌 팀은 몇 팀인가?", "chartId": SUMMARY_ID},
    ):
        if len(kept) >= 3:
            break
        kept.append(spare)
    return kept


def _not_answered() -> list[str]:
    """R7 — 이 화면이 **답하지 않는** 질문."""
    return [
        "이 영상이 차트로 이어질지. 이 화면은 채널 조회까지만 다룬다",
        "레이블 채널(HYBE LABELS 등)에 올라간 영상. 여기는 팀 공식 채널만 본다",
        "조회가 오르는 중인지 멈췄는지. 하루치 스냅샷은 증분을 알 수 없다",
        "누가 봤는지. 공개 집계 수치에는 지역도 연령도 없다",
        "광고가 붙은 조회인지. 유기적 조회와 구분하지 않는다",
    ]


def _reliability(source: str, asof: str, n_acts: int, n_videos: int) -> dict[str, str]:
    """R8 — 화면 전체의 기본 신뢰도. 차트별 값이 이것을 필드 단위로 덮는다."""
    return {
        "sample": f"팀 {n_acts}팀 · 영상 {n_videos}개 · 기준일 {asof[:10] or '?'}",
        "accuracy": "조회·구독은 API가 돌려준 공개 집계값. 평균 일 조회는 수명 평균 근사이며 정확도 미측정",
        "missing": "팀 공식 채널만 본다. 레이블 채널 업로드와 채널이 확인되지 않은 팀은 이 표본에 없다",
        "engine": f"{source} · 스냅샷 {asof}",
    }


def _yt_inferences(
    *,
    velo_pairs: list[tuple[str, int]],
    views_pairs: list[tuple[str, int]],
    fresh_pairs: list[tuple[str, int]],
    n_acts: int,
    n_videos: int,
    recent_days: int,
) -> list[dict[str, object]]:
    """태그된 자동 추론(R4 · D-039). 전부 관측에서 계산한다.

    허용 어법은 "~와 정합한다"·"~신호가 있다"·"~로 읽힌다"뿐이고, 명령·예측·인과 단정과
    em dash는 scripts/validate_report_data.py가 CI에서 잡는다.
    """
    out: list[dict[str, object]] = []

    # ① 쌓인 조회의 1위와 지금 빠른 1위가 다른가 — 이 탭이 두 축을 따로 두는 이유.
    if velo_pairs and views_pairs and velo_pairs[0][0] != views_pairs[0][0]:
        out.append({
            "text": f"쌓인 조회가 가장 큰 팀과 지금 가장 빠른 팀이 다른 것으로 읽힌다. "
            f"조회 합은 {views_pairs[0][0]}이고 일 조회는 {velo_pairs[0][0]}이다.",
            "basis": f"조회 합 1위 {views_pairs[0][0]} {views_pairs[0][1]:,} · "
            f"일 조회 1위 {velo_pairs[0][0]} {velo_pairs[0][1]:,}/일",
            "sample": f"팀 {n_acts}팀 · 영상 {n_videos}개",
            "confidence": "medium",
            "limits": "조회 합은 영상 수가 많을수록 커지고 일 조회는 수명 평균 근사라, 두 값은 같은 축이 아니다. "
            "채널 규모가 크면 양쪽 다 커진다.",
            "chartId": SUMMARY_ID,
        })

    # ② 속도의 쏠림. 1위가 중앙값의 몇 배인지 그대로 근거로 둔다.
    if len(velo_pairs) >= 3:
        vals = sorted((v for _a, v in velo_pairs), reverse=True)
        mid = vals[len(vals) // 2]
        if mid > 0 and vals[0] >= mid * 5:
            out.append({
                "text": f"일 조회가 한 팀 쪽으로 크게 쏠린 상태와 정합한다. 1위가 중앙값의 "
                f"{vals[0] / mid:.0f}배다.",
                "basis": f"1위 {velo_pairs[0][0]} {vals[0]:,}/일 · 중앙값 {mid:,}/일 · 팀 {len(vals)}팀",
                "sample": f"팀 {n_acts}팀 · 영상 {n_videos}개",
                "confidence": "medium",
                "limits": "구독자 규모가 큰 채널은 같은 반응에서도 값이 커진다. 이 값은 화력의 분포이지 "
                "완성도의 순위가 아니다.",
                "chartId": SUMMARY_ID,
            })

    # ③ 업로드가 한쪽으로 몰렸는가. **몰렸을 때만** 말한다 — 5·5·5를 놓고 "몰렸다"고 하면
    #    추론이 관측을 따라가지 않는 상태가 되고, 그 순간 이 배지는 신뢰가 아니라 장식이 된다.
    counts = sorted((c for _a, c in fresh_pairs), reverse=True)
    if len(counts) >= 3 and counts[len(counts) // 2] > 0 and counts[0] >= counts[len(counts) // 2] * 2:
        top = ", ".join(f"{a} {c}개" for a, c in fresh_pairs[:3])
        out.append({
            "text": f"최근 {recent_days}일 업로드가 한쪽으로 몰린 것으로 읽힌다. {top} 순이다.",
            "basis": f"업로드가 있는 {len(counts)}팀 · 합 {sum(counts)}개 · 중앙값 "
            f"{counts[len(counts) // 2]}개",
            "sample": f"팀 {n_acts}팀 · 영상 {n_videos}개",
            "confidence": "low",
            "limits": "채널 캐시가 최근 업로드 위주라 이 수는 수집 창의 산물이기도 하다. 업로드 수는 "
            "활동량이며 성과가 아니다.",
            "chartId": "fresh-by-act",
        })
    return out


def build_report(
    records: list[dict[str, object]],
    *,
    provenance: dict[str, object],
    generated_at: str,
    asof: str,
    recent_days: int = 14,
) -> dict[str, object]:
    recs = _latest_per_video(records)
    source = str(provenance.get("source") or "YouTube Data API v3")
    fetched = str(provenance.get("fetched_at") or "snapshot")

    metrics: list[dict[str, object]] = []
    charts: list[dict[str, object]] = []
    insights: list[str] = []

    if not recs:
        # 빈 스냅샷도 계약을 지킨다(R1·R2·R7·R8). 요약 도형은 빈 막대로 남아 "데이터 없음"을
        # 스스로 말하고, 놓을 차트가 없으므로 구획은 선언하지 않는다.
        metrics.append({"label": "추적 영상", "value": 0, "unit": "개"})
        insights.append("영상 없음. 채널 캐시와 수집 상태 확인 필요")
        return _wrap(
            source,
            fetched,
            generated_at,
            metrics,
            charts,
            insights,
            {
                "summary": _velocity_summary([], 0, 0),
                "questions": _questions({SUMMARY_ID}),
                "notAnswered": _not_answered(),
                "reliability": _reliability(source, asof, 0, 0),
            },
        )

    acts = sorted({_s(r, "artist") for r in recs if _s(r, "artist")})
    views_by_act: dict[str, int] = {}
    best_velo: dict[str, tuple[int, str]] = {}  # act → (avg_daily, title)
    subs_by_act: dict[str, int] = {}
    fresh: list[dict[str, object]] = []
    ref = _date(asof)
    for r in recs:
        act = _s(r, "artist")
        views_by_act[act] = views_by_act.get(act, 0) + _i(r, "views")
        velo = avg_daily(_i(r, "views"), _s(r, "published_at"), asof)
        if act not in best_velo or velo > best_velo[act][0]:
            best_velo[act] = (velo, _s(r, "title"))
        subs_by_act[act] = max(subs_by_act.get(act, 0), _i(r, "subscribers"))
        pub = _date(_s(r, "published_at"))
        if pub and ref and (ref - pub).days <= recent_days:
            fresh.append(r)

    top_velo_act = max(best_velo, key=lambda a: (best_velo[a][0], a))
    metrics.append({"label": "추적 팀", "value": len(acts), "unit": "팀", "hint": "채널 해석·영상 보유"})
    metrics.append({"label": "최근작 영상", "value": len(recs), "unit": "개", "hint": "채널당 최근 업로드 창"})
    metrics.append({"label": "최근작 조회 합", "value": sum(views_by_act.values()), "unit": "views"})
    metrics.append(
        {
            "label": "최고 평균 일 조회(velocity)",
            "value": best_velo[top_velo_act][0],
            "unit": "views/일",
            "hint": f"{top_velo_act} · 평균 일 조회(수명 평균 근사)",
        }
    )
    metrics.append(
        {"label": "신작", "value": len(fresh), "unit": "개", "hint": f"최근 {recent_days}일 내 업로드(캠페인 활성)"}
    )

    views_pairs = [(a, views_by_act[a]) for a in sorted(acts, key=lambda a: (-views_by_act[a], a))]
    velo_pairs = [(a, best_velo[a][0]) for a in sorted(acts, key=lambda a: (-best_velo[a][0], a))]
    fresh_by_act: dict[str, int] = dict.fromkeys(acts, 0)
    for r in fresh:
        act = _s(r, "artist")
        if act in fresh_by_act:
            fresh_by_act[act] += 1
    fresh_pairs = [(a, fresh_by_act[a]) for a in sorted(acts, key=lambda a: (-fresh_by_act[a], a))]

    charts.append(
        {
            "type": "bar",
            "id": "views-by-act",
            "data": [{"name": a, "value": v} for a, v in views_pairs],
        }
    )
    # 업로드가 도는 팀 — 요약(속도)과 `reach`(누적)가 답하지 않는 셋째 질문이다.
    charts.append(
        {
            "type": "bar",
            "id": "fresh-by-act",
            "reliability": {"sample": f"최근 {recent_days}일 · 영상 {len(fresh)}개 / {len(recs)}개"},
            "data": [{"name": a, "value": c} for a, c in fresh_pairs if c],
        }
    )

    for r in sorted(fresh, key=lambda r: (_s(r, "published_at"), _s(r, "video_id")), reverse=True)[:5]:
        act = _s(r, "artist")
        pub = _date(_s(r, "published_at"))
        days_ago = (ref - pub).days if (pub and ref) else 0
        insights.append(
            f"신작: {act} · '{_s(r, 'title')}' ({days_ago}일 전, 조회 {_i(r, 'views'):,}, "
            f"+{avg_daily(_i(r, 'views'), _s(r, 'published_at'), asof):,}/일) · 캠페인 활성 신호(참고)"
        )
    insights.append("공식 채널 업로드 한정. 레이블 채널(HYBE LABELS 등)에 올라간 MV는 미포착")
    insights.append("평균 일 조회는 수명 전체 평균 근사(초반 화력 과소평가 가능). 여러 날 쌓이면 실측 증분으로 대체 예정")
    insights.append("조회·구독은 공개 집계 지표. 인기나 실력의 단정이 아닌 참고 신호")

    charts = _apply_meta(metrics, charts)
    sections = _place_sections(metrics, charts)
    extra: dict[str, object] = {
        "summary": _velocity_summary(velo_pairs, len(recs), len(acts)),
        "questions": _questions({str(c["id"]) for c in charts} | {SUMMARY_ID}),
        "notAnswered": _not_answered(),
        "reliability": _reliability(source, asof, len(acts), len(recs)),
        "inferences": _yt_inferences(
            velo_pairs=velo_pairs,
            views_pairs=views_pairs,
            fresh_pairs=[(a, c) for a, c in fresh_pairs if c],
            n_acts=len(acts),
            n_videos=len(recs),
            recent_days=recent_days,
        ),
    }
    if sections:
        extra["sections"] = sections
    return _wrap(source, fetched, generated_at, metrics, charts, insights, extra)


def _wrap(
    source: str,
    fetched: str,
    generated_at: str,
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    # 부제에서 초 단위 타임스탬프를 걷어낸다(DESIGN §6.1). 정확한 값은 신뢰도 라인의 `engine`이 든다.
    when = fetched[:10] if len(fetched) >= 10 and fetched[4] == "-" else fetched
    return {
        "moduleId": MODULE_ID,
        "title": "YT 펄스 · 워치리스트 공식 채널",
        "subtitle": f"{source} · 수집 {when}",
        "generatedAt": generated_at,
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": [
            "다일 축적(daily_collect)이 쌓이면 조회 증분 라인·실측 velocity가 열립니다(v2).",
            "채널 오매칭은 채널 목록(yt_channels.json)에서 직접 정정 가능",
            "신작 판정 기간은 캠페인 주기에 맞춰 조정 가능. 기준은 조정 가능한 가설",
        ],
        **(extra or {}),
    }


def build_signal_series(
    snapshots: list[tuple[str, list[dict[str, object]], dict[str, object]]],
    *,
    generated_at: str,
) -> dict[str, object]:
    """(fetch일자, records, provenance)들 → yt-velocity signal-series (signal-bridge 계약).

    값 = act별 대표(최대) 평균 일 조회. 선택 필드 subscribers·videos(대표작)는 브리지
    프로필('얼마나' 레이어) 소비용. 데이터만 공유 — 코드 독립(D-007/D-013).
    """
    day_act: dict[str, dict[str, int]] = {}
    subs: dict[str, int] = {}
    top_video: dict[str, dict[str, object]] = {}
    for asof, records, _prov in snapshots:
        for r in _latest_per_video(records):
            act = _s(r, "artist")
            if not act:
                continue
            velo = avg_daily(_i(r, "views"), _s(r, "published_at"), asof)
            day = day_act.setdefault(asof, {})
            if velo > day.get(act, -1):
                day[act] = velo
            subs[act] = max(subs.get(act, 0), _i(r, "subscribers"))
            cur = top_video.get(act)
            cur_velo = cur.get("avg_daily") if cur else None
            if cur is None or velo > (cur_velo if isinstance(cur_velo, int) else 0):
                top_video[act] = {
                    "title": _s(r, "title"),
                    "views": _i(r, "views"),
                    "avg_daily": velo,
                    "published_at": _s(r, "published_at")[:10],
                }
    dates = sorted(day_act)
    keys = sorted({a for day in day_act.values() for a in day})
    series = {a: [day_act.get(d, {}).get(a) for d in dates] for a in keys}
    window = f"{dates[0]}..{dates[-1]}" if dates else ""
    return {
        "moduleId": MODULE_ID,
        "signal": "yt-velocity",
        "unit": "avg views/day",
        "higherIsStronger": True,
        "dates": dates,
        "series": series,
        "roster": {a: True for a in keys},  # 캐시=워치리스트 유래 → 전원 추적 유니버스
        "subscribers": {a: subs[a] for a in sorted(subs)},
        "videos": {a: top_video[a] for a in sorted(top_video)},
        "provenance": {
            "source": "YouTube Data API v3 · official channels (yt-pulse)",
            "generatedAt": generated_at,
            "window": window,
            "note": "팀별 대표 평균 일 조회(수명 평균 근사) · 공식 채널 한정 · 참고 신호",
        },
    }
