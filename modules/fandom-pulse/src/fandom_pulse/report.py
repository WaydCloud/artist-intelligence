"""Build a schema-valid report.json from facts-only IG snapshot record(s).

Public aggregate signals only — no virality/hit prediction, no popularity or
"quality" verdict (RULES.md §5, AGENTS.md §5/§0). Thresholds are *criteria* that
live in RULES.md §3 (기준 원장) and arrive as tunable params — never hidden here.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import median

from fandom_pulse.entities import match
from fandom_pulse.normalize import as_int

MODULE_ID = "fandom-pulse"


def _music_artists(music: object) -> list[str]:
    """사운드 라벨 'Artist - Song' → 아티스트(협업은 콤마 분리). UGC('Original audio')는 제외.

    한계(RULES §3): 공식 트랙 라벨만 귀속 · 곡명에 ' - ' 포함 시 오분리 · 표기차 누락.
    """
    if not isinstance(music, str) or " - " not in music:
        return []
    if "original audio" in music.lower():  # username - Original audio = UGC, 아티스트 귀속 아님
        return []
    artist_part = music.rsplit(" - ", 1)[0]
    return [a.strip() for a in artist_part.split(",") if a.strip()]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _engagement(rec: dict[str, object]) -> int:
    return as_int(rec.get("likes")) + as_int(rec.get("comments"))


def _percentile(values: list[int], pct: float) -> float:
    """Linear-interpolation percentile (deterministic; no numpy)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _date(ts: object) -> str:
    return ts[:10] if isinstance(ts, str) and len(ts) >= 10 else ""


def build_report(
    records: list[dict[str, object]],
    *,
    hashtag: str,
    provenance: dict[str, object],
    generated_at: str,
    high_pct: float = 90.0,
    momentum_min_days: int = 2,
    top_tags: int = 10,
    top_sounds: int = 8,
    entity_index: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    n = len(records)
    source = str(provenance.get("source") or "Instagram (Apify)")
    fetched = str(provenance.get("fetched_at") or "snapshot")
    params_obj = provenance.get("params")
    params = params_obj if isinstance(params_obj, dict) else {}
    tag = (hashtag or str(params.get("hashtag") or "")).lstrip("#")

    metrics: list[dict[str, object]] = [{"label": "게시물 수", "value": n, "unit": "건"}]
    charts: list[dict[str, object]] = []
    insights: list[str] = []

    if n == 0:
        insights.append("게시물이 없습니다 — 입력 스냅샷/해시태그를 확인하세요.")
        return _wrap(tag, source, fetched, n, generated_at, metrics, charts, insights, _recos())

    eng = [_engagement(r) for r in records]
    likes = [as_int(r.get("likes")) for r in records]
    comments = [as_int(r.get("comments")) for r in records]
    reels = sum(1 for r in records if r.get("type") == "reel")
    threshold = _percentile(eng, high_pct)
    high = sum(1 for e in eng if e >= threshold)

    metrics.append({"label": "총 참여", "value": sum(eng), "unit": "likes+comments"})
    metrics.append({"label": "중앙값 좋아요", "value": int(median(likes)), "unit": "likes"})
    metrics.append({"label": "중앙값 댓글", "value": int(median(comments)), "unit": "comments"})
    metrics.append(
        {
            "label": "고참여 게시물",
            "value": high,
            "unit": "건",
            "hint": f"상위 {int(high_pct)}분위(≥{int(threshold)}) 초과",
        }
    )
    metrics.append({"label": "릴스 비중", "value": round(100 * reels / n), "unit": "%"})

    # Chart 1 — top co-occurring hashtags (spread/reach signal)
    tag_counts: Counter[str] = Counter()
    for r in records:
        hs = r.get("hashtags")
        if isinstance(hs, list):
            for h in hs:
                if isinstance(h, str) and h and h != tag:
                    tag_counts[h] += 1
    top_co = tag_counts.most_common(top_tags)
    if top_co:
        charts.append(
            {
                "type": "bar",
                "title": "Top 공동 해시태그",
                "data": [{"name": f"#{h}", "value": c} for h, c in top_co],
            }
        )

    # Chart 2 — daily posting cadence (line); posting-acceleration if it spans enough days
    day_counts: Counter[str] = Counter(d for r in records if (d := _date(r.get("timestamp"))))
    days = sorted(day_counts)
    if len(days) >= max(2, momentum_min_days):
        charts.append(
            {
                "type": "line",
                "title": "일별 게시량",
                "data": {
                    "x": days,
                    "series": [{"name": f"#{tag} 게시물", "values": [day_counts[d] for d in days]}],
                },
            }
        )
        mid = len(days) // 2
        early, late = days[:mid], days[mid:]
        accel = round(
            sum(day_counts[d] for d in late) / len(late)
            - sum(day_counts[d] for d in early) / len(early),
            1,
        )
        metrics.append(
            {"label": "게시 가속", "value": accel, "unit": "건/일", "hint": f"{days[0]}~{days[-1]} 최근−이전"}
        )

    # Chart 3 — trending sounds (challenge/dance early signal), when present
    sound_counts: Counter[str] = Counter(
        s for r in records if isinstance(s := r.get("music"), str) and s
    )
    top_snd = sound_counts.most_common(top_sounds)
    if top_snd:
        charts.append(
            {"type": "bar", "title": "Top 사운드", "data": [{"name": s, "value": c} for s, c in top_snd]}
        )

    # Chart 4 — sound→artist join (pre-mainstream 선행신호, RULES §3):
    # 사운드 라벨의 공식 아티스트를 공유 entity-master로 귀속 → 차트로 안 잡히는 소셜 활성 표면화
    artist_posts: Counter[str] = Counter()
    for r in records:
        for a in _music_artists(r.get("music")):
            artist_posts[a] += 1
    if artist_posts:
        charts.append(
            {
                "type": "bar",
                "title": "Top 아티스트 · 사운드 확산",
                "data": [{"name": a, "value": c} for a, c in artist_posts.most_common(10)],
            }
        )
        metrics.append({"label": "사운드 확산 아티스트", "value": len(artist_posts), "unit": "팀"})
        if entity_index:
            outside = [a for a in artist_posts if match(entity_index, a) is None]
            metrics.append(
                {"label": "로스터 밖 확산", "value": len(outside), "unit": "팀", "hint": "차트 로스터 미포함 소셜 활성"}
            )
            if outside:
                names = ", ".join(sorted(outside, key=lambda a: -artist_posts[a])[:5])
                insights.append(
                    f"차트 로스터 밖 소셜 확산: {names} 등 {len(outside)}팀 — 차트(top-200)로 안 잡히는 "
                    "소셜 활성(신인·pre-mainstream 포함, 조사 대상). 선행 신호일 뿐 진출 지시 아님(§0)."
                )
        insights.append(
            "사운드→아티스트 귀속은 공식 트랙 라벨 기준('Original audio'·협업 표기·표기차로 일부 누락) — 참고 신호."
        )

    # Insights — signals with explicit limits (증폭 원칙: 신호 제시, 단정 금지 — §0/§5)
    insights.append(f"#{tag} 공개 게시물 {n}건 기준 · 총 참여 {sum(eng):,}(좋아요+댓글).")
    insights.append(
        f"중앙값 좋아요 {int(median(likes)):,} · 댓글 {int(median(comments)):,} "
        "— 평균 대신 중앙값(바이럴 1건 왜곡 견고)."
    )
    if top_co:
        names = ", ".join(f"#{h}" for h, _c in top_co[:3])
        insights.append(f"공동 해시태그 상위: {names} — 확산·맥락 도달 신호(참고).")
    if len(days) < max(2, momentum_min_days):
        insights.append("단일 창(하루) 스냅샷이라 게시 가속(모멘텀)은 다일 축적 시 산출됩니다.")
    insights.append(
        "공개 IG 스크랩 표본(첫 페이지 등)으로 편향 가능 — 공식 지표 아님, 인기·품질 단정 아님(참고 신호)."
    )

    return _wrap(tag, source, fetched, n, generated_at, metrics, charts, insights, _recos())


def build_signal_series(
    records: list[dict[str, object]],
    *,
    entity_index: dict[str, dict[str, object]] | None,
    generated_at: str,
    hashtag: str = "",
    hashtag_index: dict[str, str] | None = None,
) -> dict[str, object]:
    """Per-(date × artist) social-buzz series for the cross-module bridge (signal-bridge).

    Buckets IG posts by day and by the SAME shared entity-master canonical the
    single-day report uses — so chart-history's chart-rank series joins on the
    identical key. Attribution is TWO evidence paths (RULES §3, D-013):
    ① sound label 'Artist - Song' (D-010) · ② watchlist hashtag (#izna → izna) —
    covers pre-mainstream posts whose sound is UGC('Original audio'). One post
    counts once per act (set semantics). Also emits magnitude (engagement sum) and
    drivers (top sounds·tags per act) for the 얼마나/왜 layer. Un-rostered artists
    keep their raw label (roster=false). Counts only; no verdict (§0).
    Contract: modules/signal-bridge/SPEC.md.
    """
    idx = entity_index or {}
    tag_idx = hashtag_index or {}
    day_artist: dict[str, dict[str, int]] = {}  # date → {canonical: post count}
    roster: dict[str, bool] = {}
    engagement: dict[str, int] = {}
    drv_sounds: dict[str, Counter[str]] = {}
    drv_tags: dict[str, Counter[str]] = {}
    for r in records:
        d = _date(r.get("timestamp"))
        if not d:
            continue
        attributed: dict[str, bool] = {}  # key → rostered? (this post)
        for a in _music_artists(r.get("music")):
            hit = match(idx, a)
            key = str(hit["key"]) if hit else a
            attributed[key] = attributed.get(key, False) or hit is not None
        tags = r.get("hashtags")
        matched_tags: dict[str, str] = {}
        if isinstance(tags, list):
            for h in tags:
                if isinstance(h, str) and h.lower() in tag_idx:
                    key = tag_idx[h.lower()]
                    attributed[key] = True  # watchlist act = tracked universe
                    matched_tags[key] = h.lower()
        eng = _engagement(r)
        music = r.get("music")
        for key, rostered in attributed.items():
            day_artist.setdefault(d, {})[key] = day_artist.setdefault(d, {}).get(key, 0) + 1
            roster[key] = roster.get(key, False) or rostered
            engagement[key] = engagement.get(key, 0) + eng
            if isinstance(music, str) and music and "original audio" not in music.lower():
                drv_sounds.setdefault(key, Counter())[music] += 1
            if key in matched_tags:
                drv_tags.setdefault(key, Counter())[f"#{matched_tags[key]}"] += 1
    dates = sorted(day_artist)
    keys = sorted({k for day in day_artist.values() for k in day})
    series = {k: [day_artist.get(d, {}).get(k, 0) for d in dates] for k in keys}
    drivers = {
        k: {
            "sounds": [s for s, _c in drv_sounds.get(k, Counter()).most_common(3)],
            "tags": [t for t, _c in drv_tags.get(k, Counter()).most_common(3)],
        }
        for k in keys
    }
    window = f"{dates[0]}..{dates[-1]}" if dates else ""
    return {
        "moduleId": MODULE_ID,
        "signal": "social-buzz",
        "unit": "posts/day",
        "higherIsStronger": True,
        "dates": dates,
        "series": series,
        "roster": {k: roster[k] for k in sorted(roster)},
        "engagement": {k: engagement[k] for k in sorted(engagement)},
        "drivers": drivers,
        "provenance": {
            "source": "IG hashtag sound+tag→artist (fandom-pulse)",
            "hashtag": hashtag.lstrip("#"),
            "generatedAt": generated_at,
            "window": window,
            "attribution": "sound-label + watchlist-hashtag (D-013)" if tag_idx else "sound-label",
            "note": "일자별 게시수 · 사운드 라벨 + 워치리스트 해시태그 귀속 · 참고 신호(단정 아님, §0)",
        },
    }


def _recos() -> list[str]:
    return [
        "특정 그룹/컴백 해시태그로 fetch하면 그 캠페인의 화력·참여 신호를 집중 관측할 수 있습니다.",
        "다일 축적(collect)하면 게시 가속(모멘텀)을 실데이터 라인으로 볼 수 있습니다(v2).",
        "고참여 임계값(--high-pct)은 도메인 판단으로 조정하세요 — 기준은 가설입니다(기준 원장).",
    ]


def _wrap(
    tag: str,
    source: str,
    fetched: str,
    n: int,
    generated_at: str,
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    recommendations: list[str],
) -> dict[str, object]:
    return {
        "moduleId": MODULE_ID,
        "title": f"팬덤 펄스 — #{tag}",
        "subtitle": f"{source} · {fetched} · {n}건",
        "generatedAt": generated_at,
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": recommendations,
    }
