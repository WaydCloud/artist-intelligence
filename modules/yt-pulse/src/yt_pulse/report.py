"""Build schema-valid report.json + yt-velocity signal-series from facts-only snapshots.

Official-channel firepower/velocity signals only — no hit prediction, no popularity
verdict (RULES §5, §0). Thresholds live in RULES §3 (기준 원장) as tunable params.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

MODULE_ID = "yt-pulse"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        metrics.append({"label": "추적 영상", "value": 0, "unit": "개"})
        insights.append("영상 없음. 채널 캐시와 수집 상태 확인 필요")
        return _wrap(source, fetched, generated_at, metrics, charts, insights)

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

    charts.append(
        {
            "type": "bar",
            "title": "팀별 최근작 조회 합 (공식 채널)",
            "data": [
                {"name": a, "value": views_by_act[a]}
                for a in sorted(acts, key=lambda a: (-views_by_act[a], a))
            ],
        }
    )
    charts.append(
        {
            "type": "bar",
            "title": "팀별 대표 평균 일 조회 (최대작 기준)",
            "data": [
                {"name": a, "value": best_velo[a][0]}
                for a in sorted(acts, key=lambda a: (-best_velo[a][0], a))
            ],
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
    return _wrap(source, fetched, generated_at, metrics, charts, insights)


def _wrap(
    source: str,
    fetched: str,
    generated_at: str,
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
) -> dict[str, object]:
    return {
        "moduleId": MODULE_ID,
        "title": "YT 펄스 · 워치리스트 공식 채널",
        "subtitle": f"{source} · {fetched}",
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
