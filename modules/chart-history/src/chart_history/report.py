"""Build a schema-valid report.json from a parsed chart snapshot.

Facts and derived aggregates only. No hit/star prediction, no ranking of
artists by "quality" — see RULES.md §ethics and AGENTS.md §5.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from chart_history.entities import alias_index
from chart_history.normalize import (
    canonical_artist,
    canonical_key,
    canonical_title,
    primary_artist,
)

MODULE_ID = "chart-history"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _i(entry: dict[str, object], key: str) -> int:
    value = entry.get(key)
    return value if isinstance(value, int) else 0


def _s(entry: dict[str, object], key: str) -> str:
    value = entry.get(key)
    return value if isinstance(value, str) else ""


def _name(entry: dict[str, object]) -> str:
    artist, title = _s(entry, "artist"), _s(entry, "title")
    return f"{artist} - {title}" if title else artist


def _track_key(entry: dict[str, object]) -> str:
    return canonical_key(_s(entry, "artist"), _s(entry, "title"))


def _entries(parsed: dict[str, object]) -> list[dict[str, object]]:
    value = parsed.get("entries")
    return value if isinstance(value, list) else []


def _snapshot_date(parsed: dict[str, object]) -> str:
    meta = parsed.get("meta")
    if isinstance(meta, dict):
        d = meta.get("snapshot_date")
        if isinstance(d, str) and len(d) >= 10:
            return d[:10]
    return ""


def _snapshot_country(parsed: dict[str, object]) -> str:
    meta = parsed.get("meta")
    if isinstance(meta, dict):
        c = meta.get("country")
        if isinstance(c, str) and c.strip():
            return c.strip().upper()
    return "?"


def _snapshot_platform(parsed: dict[str, object]) -> str:
    """플랫폼 차원(D-016). 메타 없는 구 스냅샷 = spotify(기존 레일)."""
    meta = parsed.get("meta")
    if isinstance(meta, dict):
        p = meta.get("platform")
        if isinstance(p, str) and p.strip():
            return p.strip().lower()
    return "spotify"


def build_chart_signal_series(
    snapshots: list[dict[str, object]],
    *,
    entity_map: dict[str, object],
    generated_at: str,
) -> dict[str, object]:
    """Per-(date × artist) chart-rank series for the cross-module bridge (signal-bridge).

    Reuses this module's OWN parse + entity resolution: each dated snapshot → best
    (lowest) chart rank per artist that day, keyed by the SAME shared entity-master
    canonical (alias_index) fandom-pulse's social-buzz series uses — so the two join
    on the identical key (D-007/D-010, data-only). Absent day → null (not in chart).
    Facts only, no verdict (§0). Contract: modules/signal-bridge/SPEC.md.
    """
    aidx = alias_index(entity_map)
    day_artist: dict[str, dict[str, int]] = {}  # date → {canonical: best rank (any market/platform)}
    roster: dict[str, bool] = {}
    markets: dict[str, set[str]] = {}
    platforms: dict[str, set[str]] = {}
    plat_onsets: dict[str, dict[str, str]] = {}  # act → {platform: 첫 관측일} (D-016 ② 렌즈 시차)
    plat_first: dict[str, str] = {}  # platform → 수집 첫 일자 (좌측 절단 보정용)
    all_markets: set[str] = set()
    all_platforms: set[str] = set()
    tos_classes: set[str] = set()
    for parsed in snapshots:
        meta = parsed.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("tos_class"), str):
            tos_classes.add(meta["tos_class"])
        date = _snapshot_date(parsed)
        if not date:
            continue
        market = _snapshot_country(parsed)
        platform = _snapshot_platform(parsed)
        all_markets.add(market)
        all_platforms.add(platform)
        if platform not in plat_first or date < plat_first[platform]:
            plat_first[platform] = date
        for e in _entries(parsed):
            rank = e.get("rank")
            if not isinstance(rank, int):
                continue
            pa = primary_artist(_s(e, "artist"))
            if not pa:
                continue
            prim = aidx.get(pa.strip().lower())
            key = prim if prim else pa
            day = day_artist.setdefault(date, {})
            if key not in day or rank < day[key]:
                day[key] = rank
            markets.setdefault(key, set()).add(market)
            platforms.setdefault(key, set()).add(platform)
            po = plat_onsets.setdefault(key, {})
            if platform not in po or date < po[platform]:
                po[platform] = date
            if key not in roster:
                roster[key] = prim is not None
    dates = sorted(day_artist)
    keys = sorted({k for day in day_artist.values() for k in day})
    series: dict[str, list[int | None]] = {
        k: [day_artist.get(d, {}).get(k) for d in dates] for k in keys
    }
    window = f"{dates[0]}..{dates[-1]}" if dates else ""
    synthetic = "synthetic-fixture" in tos_classes
    note = "일자별 최고순위(전 시장·전 플랫폼 최저 rank) · 결측=차트 밖 · 참고 신호(단정 아님)"
    if len(all_platforms) > 1:
        note += " · ⚠ 플랫폼 혼합 최고순위. 진입 시점 파악용, 순위 절대값은 집계 범위가 달라 플랫폼 간 비교 금지"
    if synthetic:
        note = "⚠ 합성 샘플(실 데이터 아님). 메커니즘 시연용, 실증은 라이브 수집 축적 후. " + note
    return {
        "moduleId": MODULE_ID,
        "signal": "chart-rank",
        "unit": "rank (lower=stronger)",
        "higherIsStronger": False,
        "dates": dates,
        "series": series,
        "roster": {k: roster[k] for k in sorted(roster)},
        "markets": {k: sorted(markets[k]) for k in sorted(markets)},
        "platforms": {k: sorted(platforms[k]) for k in sorted(platforms)},
        "platformOnsets": {
            k: dict(sorted(plat_onsets[k].items())) for k in sorted(plat_onsets)
        },
        "provenance": {
            "source": "chart snapshots (chart-history: Kworb + Apple RSS)",
            "generatedAt": generated_at,
            "window": window,
            "marketCount": len(all_markets),
            "platformCount": len(all_platforms),
            "platformFirstDates": dict(sorted(plat_first.items())),
            "synthetic": synthetic,
            "note": note,
        },
    }


def build_chart_signal_series_from_days(
    snapshots: list[dict[str, object]],
    *,
    entity_map: dict[str, object],
    generated_at: str,
    window_days: int = 21,
) -> dict[str, object]:
    """Reconstruct a REAL chart-rank series from live snapshot(s) via the Kworb `Days`
    field (days-on-chart) — retrospective 실증 without waiting for multi-day accumulation.

    entry_date = snapshot_date − (Days − 1) is REAL (standard Kworb semantics). Multi-
    market (D-013): earliest entry / best rank across ALL given market snapshots, with
    a per-artist markets map. We mark an artist present (best rank) from their earliest
    entry within a bounded window; earlier days = null (or window start if entered
    before). **Real onset** drives the bridge's lead; intermediate ranks are held at
    current (approximation — flagged `reconstructed`). Limit: re-entries reset `Days`.
    Facts-derived, no verdict (§0).
    """
    aidx = alias_index(entity_map)
    snap_dates = [d for p in snapshots if (d := _snapshot_date(p))]
    if not snap_dates:
        raise ValueError("no snapshot_date in snapshots — cannot reconstruct entry dates")
    snap_d = date.fromisoformat(max(snap_dates))  # window anchored at the latest snapshot
    win_start = snap_d - timedelta(days=window_days - 1)
    dates = [(win_start + timedelta(days=i)).isoformat() for i in range(window_days)]

    # per artist: min rank + earliest entry across songs AND markets, + markets map
    best_rank: dict[str, int] = {}
    earliest_entry: dict[str, date] = {}
    roster: dict[str, bool] = {}
    markets: dict[str, set[str]] = {}
    platforms: dict[str, set[str]] = {}
    all_markets: set[str] = set()
    all_platforms: set[str] = set()
    for parsed in snapshots:
        this_snap = _snapshot_date(parsed)
        if not this_snap:
            continue
        this_d = date.fromisoformat(this_snap)
        market = _snapshot_country(parsed)
        platform = _snapshot_platform(parsed)
        all_markets.add(market)
        all_platforms.add(platform)
        for e in _entries(parsed):
            rank = e.get("rank")
            days = e.get("days")
            if not isinstance(rank, int):
                continue
            pa = primary_artist(_s(e, "artist"))
            if not pa:
                continue
            prim = aidx.get(pa.strip().lower())
            key = prim if prim else pa
            entry_d = this_d - timedelta(days=(days - 1)) if isinstance(days, int) and days >= 1 else this_d
            if key not in best_rank or rank < best_rank[key]:
                best_rank[key] = rank
            if key not in earliest_entry or entry_d < earliest_entry[key]:
                earliest_entry[key] = entry_d  # first time the artist charted (any market)
            markets.setdefault(key, set()).add(market)
            platforms.setdefault(key, set()).add(platform)
            if key not in roster:
                roster[key] = prim is not None
            else:
                roster[key] = roster[key] or prim is not None

    series: dict[str, list[int | None]] = {}
    entered_before = 0
    for key in sorted(best_rank):
        onset = max(earliest_entry[key], win_start)
        if earliest_entry[key] < win_start:
            entered_before += 1
        series[key] = [best_rank[key] if date.fromisoformat(d) >= onset else None for d in dates]

    note = (
        "⚠ 재구성(reconstructed) · 라이브 스냅샷의 Days(차트인 일수)로 진입일 역산. "
        "진입일(온셋)은 실제, 중간 순위는 현재값으로 근사. 재진입 시 Days 리셋(최근 진입 기준). 사실 파생이며 단정 아님"
    )
    return {
        "moduleId": MODULE_ID,
        "signal": "chart-rank",
        "unit": "rank (lower=stronger)",
        "higherIsStronger": False,
        "dates": dates,
        "series": series,
        "roster": {k: roster[k] for k in sorted(roster)},
        "markets": {k: sorted(markets[k]) for k in sorted(markets)},
        "platforms": {k: sorted(platforms[k]) for k in sorted(platforms)},
        "provenance": {
            "source": f"Kworb live snapshot(s) ≤{snap_d.isoformat()} · Days→entry reconstruction (chart-history)",
            "generatedAt": generated_at,
            "window": f"{dates[0]}..{dates[-1]}",
            "marketCount": len(all_markets),
            "platformCount": len(all_platforms),
            "synthetic": False,
            "reconstructed": True,
            "entered_before_window": entered_before,
            "note": note,
        },
    }


def build_report(
    parsed: dict[str, object],
    *,
    chart_name: str | None,
    generated_at: str,
    entity_map: dict[str, object] | None = None,
) -> dict[str, object]:
    meta = parsed.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    raw_entries = parsed.get("entries")
    entries: list[dict[str, object]] = raw_entries if isinstance(raw_entries, list) else []

    name = chart_name or str(meta.get("chart") or "Chart")
    snapshot_date = str(meta.get("snapshot_date") or "snapshot")
    source = str(meta.get("source") or "Kworb")
    n = len(entries)

    metrics: list[dict[str, object]] = [
        {"label": "차트 진입 곡", "value": n, "unit": "곡"},
    ]
    insights: list[str] = []
    charts: list[dict[str, object]] = []

    if n == 0:
        insights.append("차트 진입 곡 없음. 입력 스냅샷 형식 확인 필요")
        return _wrap(name, source, snapshot_date, n, generated_at, metrics, charts, insights, _recos())

    unique_artists = len({_s(e, "artist") for e in entries})
    top = entries[0]
    longest = max(entries, key=lambda e: _i(e, "days"))
    climbers = [e for e in entries if isinstance(e.get("pos_change"), int) and _i(e, "pos_change") > 0]
    biggest_climber = max(climbers, key=lambda e: _i(e, "pos_change")) if climbers else None

    metrics.append({"label": "고유 아티스트", "value": unique_artists, "unit": "팀"})
    metrics.append({"label": "1위", "value": _name(top), "hint": f"일간 {_i(top, 'streams'):,} 스트림"})
    top_metric: dict[str, object] = {"label": "1위 일간 스트림", "value": _i(top, "streams"), "unit": "streams"}
    if isinstance(top.get("streams_delta"), int):
        top_metric["delta"] = _i(top, "streams_delta")
    metrics.append(top_metric)
    metrics.append({"label": "최장 차트인", "value": _i(longest, "days"), "unit": "일", "hint": _name(longest)})
    if biggest_climber is not None:
        metrics.append(
            {
                "label": "최고 상승",
                "value": _i(biggest_climber, "pos_change"),
                "unit": "계단",
                "hint": _name(biggest_climber),
            }
        )

    # Chart 1 — top 10 tracks by daily streams
    by_streams = sorted(entries, key=lambda e: _i(e, "streams"), reverse=True)[:10]
    charts.append(
        {
            "type": "bar",
            "title": "Top 10 · 일간 스트림",
            "data": [{"name": _name(e), "value": _i(e, "streams")} for e in by_streams],
        }
    )

    # Chart 2 — top artists by summed daily streams within the chart
    artist_streams: dict[str, int] = defaultdict(int)
    artist_hits: dict[str, int] = defaultdict(int)
    for e in entries:
        artist_streams[_s(e, "artist")] += _i(e, "streams")
        artist_hits[_s(e, "artist")] += 1
    top_artists = sorted(artist_streams.items(), key=lambda kv: kv[1], reverse=True)[:10]
    charts.append(
        {
            "type": "bar",
            "title": "Top 아티스트 · 차트 내 일간 스트림 합",
            "data": [{"name": a, "value": s} for a, s in top_artists],
        }
    )

    # Insights — facts with explicit limits (증폭 원칙: 신호 제시, 단정 금지)
    insights.append(f"{snapshot_date} 스냅샷 기준 {n}곡 · 고유 아티스트 {unique_artists}팀.")
    insights.append(f"1위: {_name(top)} · 일간 {_i(top, 'streams'):,} 스트림, 누적 {_i(top, 'total'):,}.")
    if biggest_climber is not None:
        insights.append(
            f"최고 상승: {_name(biggest_climber)} (+{_i(biggest_climber, 'pos_change')}계단)."
        )
    multi = sorted(
        ((a, h) for a, h in artist_hits.items() if h >= 2), key=lambda kv: kv[1], reverse=True
    )
    if multi:
        top_a, top_h = multi[0]
        insights.append(f"복수 진입 최다: {top_a} · 차트에 {top_h}곡 동시 진입")
    insights.append("단일 일자 스냅샷 기준. 순위 변동 추이는 여러 날 쌓인 뒤 산출")
    insights.append("스트림 수치는 Kworb 집계값. Spotify 공식 지표와 다를 수 있어 참고용")

    if entity_map:
        _augment_entities(metrics, charts, insights, entries, entity_map)

    return _wrap(name, source, snapshot_date, n, generated_at, metrics, charts, insights, _recos())


def _recos() -> list[str]:
    return [
        "다일 스냅샷을 축적하면 순위 모멘텀·진입/이탈을 라인 차트로 볼 수 있습니다(v2).",
        "특정 컴백 주간을 지정해 해당 곡의 차트 궤적을 집중 관측하는 것을 권장합니다.",
        "국가별(글로벌/US/JP) 스냅샷과 교차하면 지역 팬덤 분포 신호를 얻을 수 있습니다.",
    ]


def _wrap(
    name: str,
    source: str,
    snapshot_date: str,
    n: int,
    generated_at: str,
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    recommendations: list[str],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """`extra`는 시각화 계약 필드(구획·요약·질문·신뢰도·추론 · D-041/D-043).

    선택으로 둔 이유: 이 함수는 단일 스냅샷·모멘텀·크로스소스 등 여러 경로가 공유한다.
    구획을 갖춘 경로만 채우고 나머지는 지금까지처럼 한 줄로 렌더된다.
    """
    return {
        "moduleId": MODULE_ID,
        "title": f"차트 히스토리 · {name}",
        "subtitle": f"{source} · {snapshot_date} · {n}곡",
        "generatedAt": generated_at,
        **(extra or {}),
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": recommendations,
    }


# ── v2: multi-snapshot (cross-country heatmap / date line time-series) ──────────
#
# `chart[].data` shapes (dashboard render contract):
#   heatmap : { rows: [track], cols: [market], cells: [[rank|null]] }
#   line    : { x: [label], series: [{ name: track, values: [rank|null] }] }


def build_multi(
    parsed_list: list[dict[str, object]],
    *,
    chart_name: str | None,
    generated_at: str,
    entity_map: dict[str, object] | None = None,
    geo_scope: str | None = None,
    market_min: int = 2,
    watch: list[str] | None = None,
) -> dict[str, object]:
    """Base = first snapshot (its full v1 report) + a cross-snapshot section.

    v4.1(D-016): 플랫폼 ≥2면 base 개념 없이 **플랫폼 수평 병렬 리포트**로 전환 —
    어떤 플랫폼도 '본편'이 아니다(사용자 판단: YouTube 영향력 ≥ Spotify, 수평 표시).
    """
    platforms = [_snapshot_platform(p) for p in parsed_list]
    if len(set(platforms)) >= 2:
        return _build_platform_parallel(
            parsed_list,
            platforms,
            generated_at=generated_at,
            entity_map=entity_map,
            geo_scope=geo_scope,
            market_min=market_min,
            watch=watch,
        )

    if geo_scope:  # 스코프 국가 스냅샷을 base로 (홈 차트 + 로스터 지리 = 일관, RULES §4.5)
        scope = geo_scope.upper()

        def _base_priority(p: dict[str, object]) -> tuple[int, int]:
            m = p.get("meta")
            cc = str(m.get("country") or "").upper() if isinstance(m, dict) else ""
            # spotify 우선(v4): base v1 섹션은 가장 깊은 레일(top-200) 홈 차트가 대표
            return (0 if cc == scope else 1, 0 if _snapshot_platform(p) == "spotify" else 1)

        parsed_list = sorted(parsed_list, key=_base_priority)
    base = parsed_list[0]
    report = build_report(base, chart_name=chart_name, generated_at=generated_at, entity_map=entity_map)

    metrics = report.get("metrics")
    charts = report.get("charts")
    insights = report.get("insights")
    if not (isinstance(metrics, list) and isinstance(charts, list) and isinstance(insights, list)):
        return report

    metas = [m if isinstance(m := p.get("meta"), dict) else {} for p in parsed_list]
    countries = [str(m.get("country") or "") for m in metas]
    dates = [str(m.get("snapshot_date") or "") for m in metas]
    charts_labels = [str(m.get("chart") or "") for m in metas]
    services = [_service(c) for c in charts_labels]

    if all(countries) and len(set(countries)) == len(parsed_list):
        _augment_cross_country(
            metrics, charts, insights, parsed_list, countries, entity_map, geo_scope, market_min
        )
    elif all(services) and len(set(services)) == len(parsed_list):
        _augment_cross_source(metrics, charts, insights, parsed_list, services, entity_map or {})
    elif len({d for d in dates if d}) >= 2:
        _augment_time_series(metrics, charts, insights, parsed_list, dates)
    elif len({c for c in charts_labels if c}) >= 2:
        _augment_cross_view(metrics, charts, insights, parsed_list, charts_labels)
    else:
        insights.append("교차 비교 축(플랫폼/국가/소스/날짜/뷰)을 찾지 못해 기준 스냅샷만 사용")
    return report


# ── v4: 플랫폼 교차 (D-016 멀티플랫폼 렌즈) ─────────────────────────────────
N_PLATFORM_ROWS = 15  # 히트맵 상위 행 수 (관습 — 표시 밀도)
N_UNIQUE_BARS = 12  # 단일-플랫폼 유니크 bar 상위 수 (관습)

# v4.1 수평 병렬: 위계가 아니라 **표시 순서**일 뿐. 순서 값 = 도메인 소유자 판단
# (사용자 2026-07-19: "YouTube는 범접할 수 없는 영향력 — 단, 수평으로 보여줄 것";
#  멜론 = 국내 정본이라 youtube 다음, D-017). §2.1.
# shazam(D-020)은 소비가 아니라 **발견** 신호라 성격이 달라 끝에 둔다 — 위치는 도메인 소유자가 조정.
PLATFORM_ORDER = ["youtube", "melon", "spotify", "apple", "shazam"]


def _plat_sort(names: set[str]) -> list[str]:
    order = {p: i for i, p in enumerate(PLATFORM_ORDER)}
    return sorted(names, key=lambda p: (order.get(p, len(order)), p))


def _lens_track_ranks(
    parsed: dict[str, object], aidx: dict[str, str]
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], str]]:
    """홈 스냅샷 → {(canon_artist, title) 소문자 키: rank} + 표시 라벨.

    아티스트는 entity 별칭으로 캐노니컬화(코르티스↔CORTIS) — 플랫폼 간 표기차를 접는다.
    제목 표기차가 남으면 행이 갈라질 수 있음(한계 — insight에 명시하지 않고 표시만 담당).
    """
    ranks: dict[tuple[str, str], int] = {}
    disp: dict[tuple[str, str], str] = {}
    for e in _entries(parsed):
        r = _i(e, "rank")
        if r <= 0:
            continue
        art = primary_artist(_s(e, "artist"))
        canon = aidx.get(art.strip().lower()) or art
        title = _s(e, "title")
        key = (canon.lower(), title.lower())
        if key not in ranks or r < ranks[key]:
            ranks[key] = r
            disp[key] = f"{canon} - {title}" if title else canon
    return ranks, disp


# ── 구획·문구 (D-043 · DESIGN §6.1·§7.1) ──────────────────────────────────────
#
# 이 모듈은 **네 개의 다른 질문**에 답한다. 지금까지는 넷이 한 페이지에 섞여 있어서
# 차트 10개와 지표 13개가 한 줄로 쏟아졌고, 무엇을 먼저 볼지 화면이 말해 주지 못했다.
# 구획은 그 넷을 갈라 한 번에 하나만 보이게 한다(구획당 차트 상한은 검사기가 센다).
#
# 문구를 한 표에 모으는 이유: 이것은 클라이언트 대면 카피이고(DESIGN §6.1), 계산 코드
# 사이에 흩어 두면 검토가 불가능해진다. 제목에서 대괄호 태그·`×`·괄호 경고문을 걷어내고
# 경고는 `definition`과 구획 `note`라는 제 자리로 보냈다.
_SECTIONS: list[dict[str, str]] = [
    {
        "id": "platforms",
        "label": "플랫폼",
        # 수를 적지 않는다 -- 이 표는 상수라 렌즈가 늘어도 따라오지 못한다(멜론 복귀 실측).
        "question": "플랫폼마다 같은 곡을 올리고 있나?",
        "note": "플랫폼마다 집계 대상과 순위 범위가 다르다. 순위 숫자를 플랫폼끼리 비교할 수 없다. "
        "이 구획이 답하는 것은 크기가 아니라 어디에 잡히는가다.",
    },
    {
        "id": "scale",
        "label": "규모",
        "question": "1위 곡은 실제로 얼마나 재생됐나?",
        "note": "두 차트의 단위가 다르다. 조회수와 스트림은 서로 환산되지 않으므로 나란히 두고 크기를 견주지 않는다.",
    },
    {
        "id": "geography",
        "label": "지리",
        "question": "우리 팀들은 어느 나라 차트에 올랐나?",
        "note": "원산지가 한국으로 확인된 팀만 본다. 숫자는 조사한 나라 집합 안에서의 값이며 세계 도달이 아니다.",
    },
    {
        "id": "rookies",
        "label": "신인",
        "question": "팬베이스 없는 신인은 어디에 닿았나?",
        "note": "데뷔 연도가 확인된 팀만 코호트에 든다. 확인되지 않은 팀은 빠지므로 이 표는 하한이다.",
    },
]

_CHART_META: dict[str, dict[str, str]] = {
    "kr-top10-lenses": {
        "section": "platforms",
        "title": "한국 차트 상위 10곡, 플랫폼별 순위",
        "question": "지금 한국에서 가장 많이 소비되는 곡이 플랫폼마다 다른가?",
        "definition": "각 플랫폼이 한국에서 집계한 순위. 숫자는 그 플랫폼 열 안에서만 의미가 있다. "
        "빈 칸은 그 플랫폼 차트에 없다는 뜻이며 순위가 낮다는 뜻이 아니다.",
    },
    "youtube-native": {
        "section": "scale",
        "title": "YouTube 일간 조회수 상위 10곡",
        "question": "YouTube에서 1위 곡은 아래 곡들과 얼마나 벌어져 있나?",
        "definition": "Kworb가 집계한 일간 조회수. YouTube 공식 지표와 다를 수 있다. "
        "Spotify 스트림과는 단위가 달라 두 차트의 값을 견주지 않는다.",
    },
    "spotify-native": {
        "section": "scale",
        "title": "Spotify 일간 스트림 상위 10곡",
        "question": "Spotify에서 1위 곡은 아래 곡들과 얼마나 벌어져 있나?",
        "definition": "Kworb가 집계한 일간 스트림. Spotify 공식 지표와 다를 수 있다. "
        "YouTube 조회수와는 단위가 달라 두 차트의 값을 견주지 않는다.",
    },
    "roster-by-lens": {
        "section": "platforms",
        "title": "팀별로 어느 플랫폼에 잡히나",
        "question": "한 플랫폼만 봤다면 누가 화면에서 사라지나?",
        "definition": "숫자는 그 팀의 곡이 해당 플랫폼에서 가장 높이 오른 순위이고, 답은 **빈칸** 쪽에 있다. "
        "빈칸만 있는 플랫폼을 빼고 수집했다면 그 팀은 통째로 화면에서 빠진다. "
        "잡힌 플랫폼이 적은 팀을 위에 두고, 워치리스트 팀을 그보다 앞에 둔다. "
        "플랫폼마다 순위 범위가 달라 열끼리 비교할 수 없다.",
    },
    "reach-ranking": {
        "section": "geography",
        "title": "곡별 진입 국가 수",
        "question": "가장 여러 나라 차트에 오른 곡은 무엇인가?",
        "definition": "한 곡이 조사 대상 나라 중 몇 곳의 차트에 올랐는지로 정렬. 열은 그 곡들이 실제로 진입한 나라만 "
        "권역 순서로 배열한다. 곡 매칭은 아티스트와 제목 문자열 기준이라 표기가 다르면 누락될 수 있다.",
    },
    "artist-markets": {
        "section": "geography",
        "title": "팀별 진입 국가와 순위",
        "question": "이 팀은 어느 나라에서 특히 높이 오르나?",
        "definition": "그 팀의 곡이 각 나라에서 오른 가장 높은 순위. 나라는 권역 순서로 배열한다. "
        "빈 칸은 그 나라 차트에 없다는 뜻이다.",
    },
    "market-gaps": {
        "section": "geography",
        "title": "아직 진입하지 않은 시장",
        "question": "어느 나라에 아직 어느 플랫폼으로도 오르지 못했나?",
        "definition": "빈 칸은 Spotify·Apple·YouTube 어디에도 오르지 않았다는 뜻이다. "
        "몇 팀이 오른 나라를 검증된 시장으로 볼지는 아래 슬라이더로 직접 조정한다. "
        "빈칸은 진입 후보 신호이며 진출 지시가 아니다.",
    },
    "rookie-markets": {
        "section": "rookies",
        "title": "데뷔 3년 이내 팀의 진입 국가",
        "question": "팬베이스가 아직 얇은 팀은 어느 나라에 닿았나?",
        "definition": "데뷔 3년 이내로 확인된 팀만. 데뷔 연도는 MusicBrainz가 검증한 Wikidata 링크에서만 가져오므로 "
        "연도가 확인되지 않은 팀은 이 표에 없다.",
    },
}

# 지표를 구획에 나눠 넣는다. 지표 13개를 첫 화면에 한꺼번에 쌓지 않기 위한 것이고,
# 각 지표는 자기 질문 옆에 있을 때만 읽힌다.
_METRIC_SECTION_EXACT: dict[str, str] = {
    "차트 플랫폼": "platforms",
    "Spotify 밖": "platforms",
    "조사 국가": "geography",
    "최광역 곡": "geography",
    "최광역 팀": "geography",
    "개척 시장": "geography",
    "신인 최광역": "rookies",
}
# 접미어 규칙 — 라벨에 아티스트 이름이 들어가는 지표(`BTS 최다 권역` 등).
_METRIC_SECTION_SUFFIX: list[tuple[str, str]] = [
    (" 1위", "platforms"),
    (" 최다 권역", "geography"),
    (" 미개척", "geography"),
]

# 플랫폼의 **정식 브랜드 표기**. 저장 키(`youtube`)를 그대로 화면에 찍으면 데이터 키가
# 새어 나온 것처럼 읽히고, 본문은 한글인데 축은 소문자 영문이라 표기가 갈린다.
_PLAT_DISPLAY: dict[str, str] = {
    "youtube": "YouTube",
    "spotify": "Spotify",
    "apple": "Apple",
    "shazam": "Shazam",
    "melon": "Melon",
}


def plat_label(p: str) -> str:
    return _PLAT_DISPLAY.get(p, p)


# 🔴 렌즈의 수는 **데이터가 정한다.** 문구가 "네 플랫폼"이라고 박아 두면 렌즈를 하나
# 늘리거나 하루 수집이 비는 순간 화면이 조용히 거짓말을 한다 -- 실제로 2026-08-01에
# 멜론이 4번째 렌즈로 돌아오자(D-017 복귀) 다섯인 화면이 "네 플랫폼"이라고 적고 있었다.
# 정적 게이트도 스모크도 이것을 못 잡는다(숫자가 문장 안에 있으므로).
#
# 관형사만 갈아 끼운다("네 플랫폼" -> "다섯 플랫폼"). 여섯을 넘으면 아라비아 숫자로
# 떨어뜨린다 -- 우리말 관형사가 그 위로는 자연스럽지 않고, 그때는 세는 것보다 읽는 것이
# 중요해진다.
_KO_COUNT: dict[int, str] = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯"}


def lens_count_word(n: int) -> str:
    return _KO_COUNT.get(n, str(n))


# 지표 라벨 갈아 끼우기(DESIGN §6.1). `최광역`·`개척 시장`·`미개척`은 뜻을 한 번 더
# 생각하게 만드는 별칭이라 가리키는 것을 그대로 쓴다. 접미어 규칙은 아티스트 이름이
# 앞에 붙는 라벨(`BTS 미개척`)을 위한 것이다.
_METRIC_RENAME_EXACT: dict[str, str] = {
    "차트 플랫폼": "수집한 플랫폼",
    "Spotify 밖": "Spotify에 없는 팀",
    "조사 국가": "조사한 나라",
    "최광역 곡": "가장 많은 나라에 오른 곡",
    "최광역 팀": "가장 많은 나라에 오른 팀",
    "개척 시장": "한국 팀이 이미 오른 나라",
    "신인 최광역": "신인 중 가장 넓게 오른 팀",
}
_METRIC_RENAME_SUFFIX: list[tuple[str, str]] = [
    (" 최다 권역", "가 가장 많이 오른 권역"),
    (" 미개척", "가 아직 안 오른 나라"),
]

_METRIC_DEFS: dict[str, str] = {
    "차트 플랫폼": "이번 실행에서 수집한 차트 플랫폼 수와 플랫폼별 시장 수.",
    "Spotify 밖": "Spotify 차트에는 없고 다른 플랫폼에는 오른 팀 수.",
    "조사 국가": "이번 실행에서 차트를 수집한 나라 수. 세계 전체가 아니라 이 집합이 분모다.",
    "최광역 곡": "가장 많은 나라 차트에 오른 곡과 그 나라 수.",
    "최광역 팀": "가장 많은 나라 차트에 오른 팀과 그 나라 수.",
    # ⚠ 스코프를 반드시 적는다. 이 두 지표는 **Spotify 차트 기준**인데 같은 구획의
    # `아직 진입하지 않은 시장`은 3플랫폼 통합 기준이라, 스코프를 밝히지 않으면 두 수가
    # 어긋나 보인다(둘 다 옳고 세는 대상이 다르다).
    "개척 시장": "Spotify 차트 기준으로 정해진 수 이상의 한국 팀이 이미 오른 나라. 검증된 시장으로 보는 기준선이며 값은 조정 가능하다.",
    "신인 최광역": "데뷔 3년 이내 팀 중 가장 많은 나라에 오른 팀.",
}


def _lens_roster_acts(
    parsed_list: list[dict[str, object]],
    platforms: list[str],
    aidx: dict[str, str],
    roster: set[str] | None,
) -> dict[str, set[str]]:
    """플랫폼 → 그 플랫폼에서 잡힌 로스터 팀 집합."""
    out: dict[str, set[str]] = {}
    for parsed, plat in zip(parsed_list, platforms):
        slot = out.setdefault(plat, set())
        for e in _entries(parsed):
            art = primary_artist(_s(e, "artist"))
            canon = aidx.get(art.strip().lower()) or art
            if roster is not None and canonical_artist(canon) not in roster:
                continue
            slot.add(canon)
    return out


def _summary_lens_shape(by_lens: dict[str, set[str]], plat_names: list[str]) -> dict[str, object]:
    """진입 요약 하나(R2) — **네 렌즈가 같은 것을 보고 있지 않다**를 한 도형으로.

    축 = 플랫폼, 값 = 전체 플랫폼에서 잡힌 팀을 100으로 뒀을 때 그 플랫폼이 잡은 비율.
    도형이 정다각형에 가까우면 렌즈들이 같은 팀을 보고 있다는 뜻이고, 한쪽으로 찌그러지면
    렌즈 하나만 보면 놓치는 팀이 있다는 뜻이다. 이 모듈의 주장이 그 찌그러짐이다.

    ⚠ 이 값은 **커버리지**이지 플랫폼의 우열이 아니다. 순위 범위와 수집 시장 수가 달라
    깊은 레일이 더 많이 잡는 것은 당연하다(RULES §1 위계 없음).
    """
    union = set().union(*by_lens.values()) if by_lens else set()
    axes: list[dict[str, object]] = []
    for p in plat_names:
        caught = by_lens.get(p)
        if caught is None:
            axes.append({"name": plat_label(p), "value": None,
                         "missingReason": "이번 실행에서 수집되지 않음", "sample": 0})
            continue
        axes.append({
            "name": plat_label(p),
            "value": round(100.0 * len(caught) / len(union), 1) if union else 0.0,
            "sample": len(caught),
            "raw": len(caught),
            "rawUnit": "팀",
        })
    placed = [float(v) for a in axes if isinstance(v := a.get("value"), (int, float))]
    # 문구가 세는 것은 **축의 수**(= 이 실행이 아는 렌즈)이지 상수가 아니다.
    lens = lens_count_word(len(axes))
    shape: dict[str, object] = {
        "type": "radar",
        "id": "lens-coverage",
        "title": "플랫폼별로 잡히는 팀의 비율",
        "question": "한 플랫폼만 보면 얼마나 놓치나?",
        "definition": f"{lens} 플랫폼 전체에서 한 번이라도 잡힌 한국 원산지 팀을 100으로 두고, "
        f"각 플랫폼이 그중 몇 퍼센트를 잡았는지 나타낸 값. 도형이 고를수록 {lens} 플랫폼이 "
        "같은 팀을 보고 있다는 뜻이다. 이 값은 커버리지이며 플랫폼의 우열이 아니다. "
        "순위 범위와 수집 시장 수가 다르면 깊은 쪽이 더 많이 잡는 것이 당연하다.",
        "data": {
            "axes": axes,
            "max": 100,
            "scaleNote": f"{lens} 플랫폼 전체에서 잡힌 팀 대비 비율",
            **(
                {"baseline": round(sum(placed) / len(placed), 1), "baselineLabel": "플랫폼 평균"}
                if placed
                else {}
            ),
        },
    }
    return shape


def _chart_history_inferences(
    *,
    by_lens: dict[str, set[str]],
    plat_names: list[str],
    non_sp_unique: int,
    act_mkt: dict[str, dict[str, int]],
    rookie_reach: list[tuple[str, int]],
) -> list[dict[str, object]]:
    """태그된 자동 추론(R4 · D-039). 전부 관측에서 계산한다.

    허용 어법은 "~와 정합한다"·"~신호가 있다"·"~로 읽힌다"뿐이고, 명령·예측·인과 단정과
    em dash는 scripts/validate_report_data.py가 CI에서 잡는다.
    """
    out: list[dict[str, object]] = []
    union = set().union(*by_lens.values()) if by_lens else set()

    # ① 렌즈가 서로 다른 것을 본다 — 이 모듈의 주장. 최다·최소 렌즈의 간격을 그대로 근거로.
    counts = [(p, len(by_lens.get(p) or set())) for p in plat_names if p in by_lens]
    if union and len(counts) >= 2:
        hi = max(counts, key=lambda kv: kv[1])
        lo = min(counts, key=lambda kv: kv[1])
        if hi[1] and lo[1] / hi[1] <= 0.7:
            out.append({
                "text": f"{plat_label(lo[0])}만 보면 {plat_label(hi[0])}에서 잡히는 팀의 상당수가 "
                "화면에 없는 상태와 정합한다.",
                "basis": " · ".join(f"{plat_label(p)} {n}팀" for p, n in counts)
                + f" · {lens_count_word(len(plat_names))} 플랫폼 합집합 {len(union)}팀",
                "sample": f"원산지가 확인된 로스터 팀 {len(union)}팀",
                "confidence": "high",
                "limits": "플랫폼마다 순위 범위와 수집 시장 수가 달라 이 비율은 커버리지 차이를 포함한다. "
                "우열이 아니며, 잡히지 않았다는 것이 그 나라에서 안 들린다는 뜻도 아니다.",
                "chartId": "lens-coverage",
            })

    # ② 단일 렌즈의 사각. **두 스코프를 함께 적는다** — 전체 차트 인구의 수(크지만 서구 팝을
    # 포함)와 원산지가 확인된 로스터의 수(작지만 이 제품의 판단 대상)는 다른 이야기이고,
    # 하나만 적으면 읽는 사람이 다른 쪽 크기로 오해한다.
    if non_sp_unique > 0:
        roster_blind = (union - (by_lens.get("spotify") or set())) if union else set()
        out.append({
            "text": "Spotify 한 곳만 수집했다면 다른 플랫폼에만 오른 팀이 화면에서 빠졌을 신호가 있다.",
            "basis": f"전체 차트 인구 기준 {non_sp_unique}팀. 원산지가 확인된 한국 로스터 {len(union)}팀 "
            f"중에서는 {len(roster_blind)}팀"
            + (f" ({', '.join(sorted(roster_blind)[:4])})" if roster_blind else ""),
            "sample": f"이번 실행에서 수집한 {len(plat_names)}개 플랫폼",
            "confidence": "high",
            "limits": "차트 진입 여부만 본 것이라 소비 규모를 말하지 않는다. 플랫폼별 순위 범위가 달라 "
            "어느 쪽이 더 큰지도 이 값으로는 알 수 없다. 전체 인구 쪽 수치에는 서구 팝이 대부분이다.",
            "chartId": "roster-by-lens",
        })

    # ③ 팬베이스가 얇은 팀도 일부 시장에 닿는가 — PRODUCT 1차 사용자가 신인이라 이 축이 핵심.
    if rookie_reach:
        top_name, top_n = rookie_reach[0]
        if top_n >= 2:
            spread = ", ".join(f"{a} {n}개국" for a, n in rookie_reach[:4])
            out.append({
                "text": f"데뷔 3년 이내 팀 중에도 여러 나라 차트에 닿은 사례가 있는 것으로 읽힌다. "
                f"가장 넓은 쪽은 {top_name}이다.",
                "basis": spread,
                "sample": f"데뷔 연도가 확인된 신인 {len(rookie_reach)}팀",
                "confidence": "medium",
                "limits": "데뷔 연도가 확인되지 않은 팀은 코호트에서 빠지므로 이 수는 하한이다. "
                "하루치 스냅샷이라 오름세인지 내림세인지 구분하지 않는다.",
                "chartId": "rookie-markets",
            })

    # ④ 진입 지도의 공백 규모 — 화이트스페이스가 실제로 얼마나 비어 있는가.
    if act_mkt:
        mkts = {cc for v in act_mkt.values() for cc in v}
        filled = sum(len(v) for v in act_mkt.values())
        total = len(act_mkt) * len(mkts)
        if total and filled / total <= 0.5:
            out.append({
                "text": f"진입 지도는 대부분이 빈 칸인 상태와 정합한다. {len(act_mkt)}팀 × {len(mkts)}개국 중 "
                f"{filled}칸에만 진입 기록이 있다.",
                "basis": f"채워진 칸 {filled}/{total} ({100.0 * filled / total:.0f}%)",
                "sample": f"로스터 {len(act_mkt)}팀 · 조사 {len(mkts)}개국",
                "confidence": "high",
                "limits": "빈 칸은 그 나라 차트 상위에 없다는 뜻이지 그 나라에서 안 들린다는 뜻이 아니다. "
                "차트 밖의 소비는 이 데이터로 보이지 않는다.",
                "chartId": "market-gaps",
            })
    return out


def _apply_section_meta(
    metrics: list[dict[str, object]], charts: list[dict[str, object]]
) -> list[dict[str, object]]:
    """차트·지표에 구획과 문구를 붙이고, 구획에 배정되지 않은 차트는 **떨어낸다**.

    떨어내는 쪽을 기본으로 둔 이유: 표에 없는 차트가 조용히 화면에 남으면 구획 상한이
    의미를 잃는다. 새 차트를 추가하면 여기 한 줄을 적어야 하고, 그 한 줄이 "이 차트로
    무엇을 답하나"를 답하게 만든다(R3).
    """
    for m in metrics:
        label = str(m.get("label") or "")
        sec = _METRIC_SECTION_EXACT.get(label)
        if sec is None:
            sec = next((s for suf, s in _METRIC_SECTION_SUFFIX if label.endswith(suf)), None)
        if sec:
            m["section"] = sec
        base = label
        for suf in (" 최다 권역", " 미개척"):
            if label.endswith(suf):
                base = suf.strip()
        if base in _METRIC_DEFS:
            m["definition"] = _METRIC_DEFS[base]
        elif label.endswith(" 1위"):
            m["definition"] = "그 플랫폼의 한국 차트 1위 곡. 플랫폼마다 집계 대상이 달라 서로 견주지 않는다."
        elif label.endswith(" 최다 권역"):
            m["definition"] = "그 팀이 가장 많이 오른 권역과 점유율. 권역 묶음은 조정 가능한 기준이다."
        elif label.endswith(" 미개척"):
            m["definition"] = (
                "그 팀이 아직 오르지 않은, 한국 팀이 이미 오른 나라의 수. Spotify 차트 기준이며 "
                "플랫폼 전체를 합친 공백은 같은 구획의 진입 지도가 따로 보여준다."
            )
        else:
            m["definition"] = _METRIC_DEFS.get(base, "")
        if not m.get("definition"):
            m.pop("definition", None)

        # 라벨 갈아 끼우기는 **구획·정의를 다 붙인 뒤** 한다. 위 매칭이 원래 라벨을 쓰기 때문이다.
        if label in _METRIC_RENAME_EXACT:
            m["label"] = _METRIC_RENAME_EXACT[label]
        else:
            for suf, rep in _METRIC_RENAME_SUFFIX:
                if label.endswith(suf):
                    m["label"] = label[: -len(suf)] + rep
                    break
            else:
                if label.endswith(" 1위"):
                    m["label"] = f"{plat_label(label[:-3])} 1위"
        # 힌트에서도 내부 어휘를 걷어낸다 — 타일에 늘 보이는 줄이라 제목만큼 눈에 띈다.
        hint = str(m.get("hint") or "")
        if hint:
            # `apple/youtube에서만 차트인` 치환은 **지웠다** — 힌트를 만드는 쪽이 이제
            # 실제 렌즈 목록에서 이름을 뽑는다. 여기서 다시 이름을 적으면 두 곳이 갈라진다.
            hint = hint.replace("개척 시장(≥", "이미 오른 나라(팀 수 ≥").replace(
                "기본 ≥", "기준 팀 수 ≥"
            ).replace("(조정가능)", ", 조정 가능")
            for raw, disp in _PLAT_DISPLAY.items():
                hint = hint.replace(f"{raw} ", f"{disp} ")
            m["hint"] = hint

    kept: list[dict[str, object]] = []
    for c in charts:
        meta = _CHART_META.get(str(c.get("id") or ""))
        if meta:
            c.update(meta)
            kept.append(c)
    return kept


def _build_platform_parallel(
    parsed_list: list[dict[str, object]],
    platforms: list[str],
    *,
    generated_at: str,
    entity_map: dict[str, object] | None,
    geo_scope: str | None,
    market_min: int,
    watch: list[str] | None,
) -> dict[str, object]:
    """v4.1 플랫폼 수평 병렬 리포트(D-016) — 어떤 플랫폼도 '본편'이 아니다.

    구성: 플랫폼별 1위 KPI(수평) → 홈 Top10 × 렌즈 히트맵 → 렌즈 네이티브 수치 bar
    (youtube 조회·spotify 스트림 — apple RSS는 무수치라 순위만) → 플랫폼 교차 증강
    → 지리 리프레임(spotify 서브그룹 = 최심 top-200 레일 기준, 위계 아님).
    """
    aidx = alias_index(entity_map or {})
    plat_names = _plat_sort(set(platforms))
    scope = (geo_scope or "").upper()

    home: dict[str, dict[str, object]] = {}
    markets_by_plat: dict[str, set[str]] = {}
    latest_date = ""
    for parsed, plat in zip(parsed_list, platforms):
        cc = _snapshot_country(parsed)
        markets_by_plat.setdefault(plat, set()).add(cc)
        d = _snapshot_date(parsed) or ""
        latest_date = max(latest_date, d)
        if cc == scope or not scope:
            prev = home.get(plat)
            if prev is None or (_snapshot_date(prev) or "") < d:
                home[plat] = parsed

    metrics: list[dict[str, object]] = []
    charts: list[dict[str, object]] = []
    insights: list[str] = []

    # 플랫폼별 1위 (홈 시장) — 수평 KPI 행
    for p in plat_names:
        top_label = "—"
        parsed = home.get(p)
        if parsed:
            for e in _entries(parsed):
                if _i(e, "rank") == 1:
                    art = primary_artist(_s(e, "artist"))
                    art = aidx.get(art.strip().lower()) or art  # 표기 캐노니컬화(코르티스→CORTIS)
                    title = _s(e, "title")
                    top_label = f"{art} - {title}" if title else art
                    break
        metrics.append(
            {
                "label": f"{p} 1위",
                "value": top_label,
                "unit": scope or "",
                "hint": f"{len(markets_by_plat.get(p, set()))}시장 수집",
            }
        )

    # 홈 Top10 × 렌즈 히트맵 — 3렌즈 합의/발산이 한눈에 (rank는 열 안에서만 의미)
    lens_ranks: dict[str, dict[tuple[str, str], int]] = {}
    lens_disp: dict[tuple[str, str], str] = {}
    for p in plat_names:
        parsed = home.get(p)
        if not parsed:
            continue
        ranks, disp = _lens_track_ranks(parsed, aidx)
        lens_ranks[p] = ranks
        for k, label in disp.items():
            lens_disp.setdefault(k, label)
    row_keys: set[tuple[str, str]] = set()
    for ranks in lens_ranks.values():
        row_keys.update(k for k, r in sorted(ranks.items(), key=lambda kv: kv[1])[:10])
    if row_keys and len(lens_ranks) >= 2:
        ordered_rows = sorted(
            row_keys,
            key=lambda k: (min(r.get(k, 10_000) for r in lens_ranks.values()), lens_disp[k]),
        )
        charts.append(
            {
                "type": "heatmap",
                "id": "kr-top10-lenses",
                "title": f"홈({scope or '전체'}) Top 10 × 플랫폼 · 세 플랫폼의 일치와 차이 (숫자=해당 플랫폼 순위, 열 간 비교 금지)",
                "data": {
                    "rows": [lens_disp[k] for k in ordered_rows],
                    "cols": [plat_label(p) for p in plat_names if p in lens_ranks],
                    "cells": [
                        [lens_ranks[p].get(k) for p in plat_names if p in lens_ranks]
                        for k in ordered_rows
                    ],
                },
            }
        )

    # 렌즈 네이티브 수치 — 각 플랫폼의 실측 단위 그대로 (혼합·환산 없음)
    native_units = {"youtube": "일간 조회", "spotify": "일간 스트림"}
    for p in plat_names:
        unit = native_units.get(p)
        parsed = home.get(p)
        if not unit or not parsed:
            continue
        top = sorted(
            (e for e in _entries(parsed) if isinstance(e.get("streams"), int)),
            key=lambda e: -_i(e, "streams"),
        )[:10]
        if top:
            charts.append(
                {
                    "type": "bar",
                    "id": f"{p}-native",
                    "title": f"{p} · 홈({scope}) {unit} Top 10 (네이티브 수치)",
                    "data": [
                        {
                            "name": f"{_s(e, 'artist')} - {_s(e, 'title')}",
                            "value": _i(e, "streams"),
                        }
                        for e in top
                    ],
                }
            )
    rank_only = [p for p in plat_names if p in ("apple", "melon")]
    if rank_only:
        insights.append(
            f"{'·'.join(rank_only)} 플랫폼은 소스가 수치 없이 **순위만** 제공. Top10 × 플랫폼 히트맵 참조. "
            "플랫폼 간 위계는 없으며 집계 범위가 달라 순위·수치의 **열 간 비교 금지**."
        )

    _augment_cross_platform(
        metrics, charts, insights, parsed_list, platforms, entity_map, watch, geo_scope
    )

    # ── 3렌즈 통합 진입 지도 (D-016 ①): 셀 = 어느 플랫폼이든 최고순위 ──
    # 화이트스페이스의 질문("어느 시장에 아직 없는가")은 플랫폼 불문 진입이 정답 —
    # 빈칸 = 3렌즈 전부 미진입(진짜 공백). 숫자는 혼합 최고순위(참고, 렌즈 간 비교 금지).
    roster = _roster_canon(entity_map, geo_scope)
    act_mkt: dict[str, dict[str, int]] = {}
    for parsed, plat in zip(parsed_list, platforms):
        cc = _snapshot_country(parsed)
        if _is_global(cc):
            continue
        for e in _entries(parsed):
            r = _i(e, "rank")
            if r <= 0:
                continue
            art = primary_artist(_s(e, "artist"))
            canon = aidx.get(art.strip().lower()) or art
            if roster is not None and canonical_artist(canon) not in roster:
                continue
            slot = act_mkt.setdefault(canon, {})
            if cc not in slot or r < slot[cc]:
                slot[cc] = r
    if act_mkt:
        mkts = sorted({cc for v in act_mkt.values() for cc in v})
        order = _order_countries([m.lower() for m in mkts])
        cols = [mkts[i] for i in order]
        rows_u = sorted(act_mkt, key=lambda k: (-len(act_mkt[k]), min(act_mkt[k].values()), k))
        charts.append(
            {
                "type": "tunable",
                "id": "market-gaps",
                "title": f"[{(geo_scope or '전체').upper()} 로스터] 3플랫폼 통합 진입 지도 · 미개척 시장 (빈칸=모든 플랫폼 미진입)",
                "data": {
                    "view": "whitespace",
                    "matrix": {
                        "rows": rows_u,
                        "cols": cols,
                        "cells": [[act_mkt[a].get(c) for c in cols] for a in rows_u],
                    },
                    "knobs": [
                        {
                            "key": "market_min",
                            "label": "개척 시장 임계(진입 팀 수)",
                            "default": market_min,
                            "min": 1,
                            "max": 8,
                            "step": 1,
                        }
                    ],
                    "topRows": 12,
                    "note": "3플랫폼 통합 진입. 빈칸은 spotify·apple·youtube 어디에도 미진입. 숫자=혼합 최고순위(플랫폼 간 비교 금지), 기준값은 조정 가능",
                },
            }
        )

    # 지리 리프레임 — spotify 서브그룹(최심 top-200·최다 시장 레일) 기준. 위계가 아니라 깊이 문제.
    sp_idx = [i for i, pl in enumerate(platforms) if pl == "spotify"]
    sp_group = [parsed_list[i] for i in sp_idx]
    sp_countries = [_snapshot_country(parsed_list[i]) for i in sp_idx]
    if sp_group and all(sp_countries) and len(set(sp_countries)) == len(sp_group):
        _augment_cross_country(
            metrics, charts, insights, sp_group, sp_countries, entity_map, geo_scope, market_min
        )
        insights.append(
            "지리 뷰(최광역·미개척)의 기준 데이터 = spotify. 위계가 아니라 **커버리지 차이**"
            "(top-200과 최다 시장으로 진입 지도가 가장 촘촘). 다른 플랫폼 시장이 넓어지면 확장 대상"
        )

    # ── 구획 배치 (D-043) ────────────────────────────────────────────────────
    #
    # ⚠ spotify 전용 미개척 지도(`spotify-gaps`)는 화면에서 **뺀다**. 바로 위 통합 진입
    # 지도(`market-gaps`)와 답하는 질문이 같은데("어느 시장에 아직 없는가"), 한 렌즈에서만
    # 비어 있는 칸은 진짜 공백이 아니라 그 렌즈의 커버리지 한계일 수 있어 통합 쪽이
    # 엄밀하게 우월하다. 데이터는 그대로 산출되며 표면에만 올리지 않는다(RULES §4.5 갱신).
    charts = _apply_section_meta(metrics, charts)

    by_lens = _lens_roster_acts(parsed_list, platforms, aidx, roster)
    summary = _summary_lens_shape(by_lens, plat_names)

    # 신인 코호트의 도달 폭 — 추론 ③의 근거. 지표에서 되읽지 않고 여기서 직접 센다.
    # "Spotify 밖" 팀 수는 _augment_cross_platform이 지표로 이미 냈다. 같은 계산을
    # 여기서 되풀이하면 두 수가 어긋날 수 있으므로 그 지표를 되읽는다.
    non_sp_count = next(
        (int(v) for m in metrics if m.get("label") == "Spotify 밖" and isinstance(v := m.get("value"), int)),
        0,
    )

    rookie_reach: list[tuple[str, int]] = []
    debut_map = _detail_by_canon(entity_map, "debut")
    cutoff_year = int(latest_date[:4]) if latest_date[:4].isdigit() else 0
    if cutoff_year:
        acts_by_debut: dict[str, int] = {}
        for canon, mkts_of in act_mkt.items():
            dy = _debut_year(debut_map.get(canonical_artist(canon)))
            if dy is not None and dy >= cutoff_year - ROOKIE_YEARS:
                acts_by_debut[canon] = len(mkts_of)
        rookie_reach = sorted(acts_by_debut.items(), key=lambda kv: (-kv[1], kv[0]))

    have = {str(c.get("id")) for c in charts if c.get("id")} | {"lens-coverage"}
    questions = [
        q
        for q in (
            {"q": "한 플랫폼만 봤다면 누가 화면에서 사라지나?", "chartId": "roster-by-lens"},
            {"q": "우리 팀들이 아직 오르지 못한 나라는 어디인가?", "chartId": "market-gaps"},
            {"q": "팬베이스가 얇은 신인은 어느 나라에 닿았나?", "chartId": "rookie-markets"},
            {"q": "한국 상위 10곡은 플랫폼마다 다른가?", "chartId": "kr-top10-lenses"},
        )
        if q["chartId"] in have
    ]

    all_markets = sorted({cc for v in markets_by_plat.values() for cc in v})
    extra: dict[str, object] = {
        "summary": summary,
        "sections": [dict(s) for s in _SECTIONS if any(c.get("section") == s["id"] for c in charts)],
        "questions": questions,
        "notAnswered": [
            # 🔴 이 줄은 **화면이 싣고 있는 것과 대조돼야** 한다. 멜론이 4번째 렌즈로 돌아온
            # 뒤에도 "멜론은 아직 연결되지 않아"라고 적혀 있었다 -- 바로 옆 타일이
            # `Melon 1위`를 싣고 있는데도. 게이트도 스모크도 이것을 못 잡는다(문장이 참인지는
            # 데이터를 봐야 안다). 그래서 상수로 두지 않고 **이번 실행이 아는 렌즈에서** 만든다.
            # 멜론은 세션-보조 수집이라 어떤 날은 정말로 없다(D-017) -- 그때는 옛 문장이 맞다.
            (
                "국내 코어 차트 중 써클차트. 멜론은 공식 MCP로 연결됐지만(KR 1시장 · 순위만) "
                "써클차트는 제휴 전이라 수집 경로가 없다. 멜론은 세션-보조 수집이라 "
                "수집일이 불연속일 수 있다"
                if "melon" in plat_names
                else "국내 코어 차트. 멜론과 써클차트는 아직 연결되지 않아 국내는 "
                "Spotify 한국 차트로 근사한다"
            ),
            "왜 그 나라에서 올랐는지. 이 화면은 어디에 올랐는지까지만 다룬다",
            "순위가 오르는 중인지 내리는 중인지. 하루치 스냅샷이라 방향을 알 수 없다",
            "플랫폼 사이의 크기 비교. 집계 대상과 순위 범위가 달라 순위 숫자를 서로 견줄 수 없다",
            "빌보드 순위. 데이터 원천이 유료 기업 거래용이라 수집 경로가 없다",
        ],
        "reliability": {
            "sample": f"{len(plat_names)}개 플랫폼 · {len(all_markets)}개 시장 · "
            f"{sum(len(_entries(p)) for p in parsed_list)}곡",
            "accuracy": "차트 순위와 수치는 사실. 아티스트 원산지와 데뷔 연도는 커뮤니티 데이터라 불완전할 수 있음",
            "missing": "원산지가 확인되지 않은 아티스트는 로스터 집계에서 제외",
            "engine": f"Kworb 집계값 · Apple 공식 RSS · 스냅샷 {latest_date or '?'}",
        },
        "inferences": _chart_history_inferences(
            by_lens=by_lens,
            plat_names=plat_names,
            non_sp_unique=non_sp_count,
            act_mkt=act_mkt,
            rookie_reach=rookie_reach,
        ),
    }

    # 제목·부제에서 내부 용어를 걷어낸다(DESIGN §6.1). "수평 뷰"·"병렬(위계 없음)"은
    # 우리끼리 쓰던 말이고, 위계가 없다는 사실은 이제 플랫폼 구획의 `note`가 말한다.
    return _wrap(
        f"{len(plat_names)}개 플랫폼",
        " · ".join(plat_label(p) for p in plat_names) + f" · {len(all_markets)}개 시장",
        latest_date or "?",
        sum(len(_entries(p)) for p in parsed_list),
        generated_at,
        metrics,
        charts,
        insights,
        _recos(),
        extra,
    )


def _augment_cross_platform(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    parsed_list: list[dict[str, object]],
    platforms: list[str],
    entity_map: dict[str, object] | None,
    watch: list[str] | None,
    geo_scope: str | None = None,
) -> None:
    """아티스트 × 플랫폼 교차 — 어느 렌즈에 잡히는가(단일 렌즈 사각 표면화, RULES §1).

    rank는 시장 간 최저(best)로 접되 **플랫폼 간 절대 비교는 금지**(top-N 천장·규모 상이) —
    이 뷰의 질문은 '얼마나 높이'가 아니라 '어느 플랫폼에 존재하는가'다(§0 사실 신호).
    """
    aidx = alias_index(entity_map or {})
    watch_set = set(watch or [])
    plat_names = _plat_sort(set(platforms))
    # act → platform → best rank (전 시장 최저)
    by_act: dict[str, dict[str, int]] = {}
    markets_by_plat: dict[str, set[str]] = {}
    for parsed, plat in zip(parsed_list, platforms):
        markets_by_plat.setdefault(plat, set()).add(_snapshot_country(parsed))
        for e in _entries(parsed):
            rank = _i(e, "rank")
            if rank <= 0:
                continue
            pa = primary_artist(_s(e, "artist"))
            if not pa:
                continue
            key = aidx.get(pa.strip().lower()) or pa
            slot = by_act.setdefault(key, {})
            if plat not in slot or rank < slot[plat]:
                slot[plat] = rank

    # 막대 스코프용 로스터. None이면 스코프 없음(전 인구)이라 워치리스트만 앞세운다.
    roster = _roster_canon(entity_map, geo_scope)
    non_sp_unique = {
        k: v for k, v in by_act.items() if len(v) == 1 and "spotify" not in v
    }
    sp_unique_n = sum(1 for v in by_act.values() if set(v) == {"spotify"})

    metrics.append(
        {
            "label": "차트 플랫폼",
            "value": len(plat_names),
            "unit": "플랫폼",
            "hint": " · ".join(
                f"{p} {len(markets_by_plat.get(p, set()))}시장" for p in plat_names
            ),
        }
    )
    # 🔴 힌트가 플랫폼 이름을 **손으로 나열하지 않는다.** 값은 "spotify가 아닌 렌즈 하나에만
    # 오른 팀"이라 렌즈가 늘면 세는 대상이 늘어나는데, 문구는 `apple/youtube`로 박혀 있었다
    # (표기 치환이 Shazam 을 끼워 넣어 셋처럼 보였을 뿐 Melon 은 어디에도 없었다).
    # 값과 문구가 같은 목록에서 나와야 갈라지지 않는다.
    non_sp_plats = [plat_label(p) for p in plat_names if p != "spotify"]
    metrics.append(
        {
            "label": "Spotify 밖",
            "value": len(non_sp_unique),
            "unit": "팀",
            "hint": f"{'·'.join(non_sp_plats)} 중 한 곳에만 차트인 · 단일 플랫폼만 보면 놓치는 팀",
        }
    )

    # 히트맵 rows: 워치리스트 우선 → **잡힌 플랫폼이 적은 순** → best rank (결정적).
    #
    # 적은 순으로 뒤집은 이유: 이 뷰의 쓸모는 "어디에 잡히나"보다 **"어디에 안 잡히나"**에
    # 있다. 많이 잡힌 팀을 위에 두면 빈칸이 아래로 밀려 사각지대가 화면 밖으로 나간다.
    # 로스터 스코프가 있으면 그 팀들만 남긴다 — 전 인구를 섞으면 서구 팝이 행을 차지한다.
    scope_acts = [
        k for k in by_act if k in watch_set or roster is None or canonical_artist(k) in roster
    ]

    def _row_key(k: str) -> tuple[int, int, int, str]:
        v = by_act[k]
        return (0 if k in watch_set else 1, len(v), min(v.values()), k)

    rows = sorted(scope_acts or list(by_act), key=_row_key)[:N_PLATFORM_ROWS]
    charts.append(
        {
            "type": "heatmap",
            "id": "roster-by-lens",
            "title": "아티스트 × 플랫폼 · 어디에 잡히는가 (숫자=최고순위, 플랫폼 간 비교 금지)",
            "data": {
                "rows": rows,
                "cols": [plat_label(p) for p in plat_names],
                "cells": [[by_act[r].get(p) for p in plat_names] for r in rows],
            },
        }
    )

    # ⚠ 여기 있던 "Spotify 밖에서만 보이는 팀" 막대는 **뺐다**(2026-07-30 육안 검사).
    # 세 가지가 한꺼번에 틀려 있었다: ① 스코프가 전체 차트 인구라 K-pop과 무관한
    # 아티스트가 표시됐고 ② 값이 **순위**인데 막대 길이로 그려 인코딩이 뒤집혔으며
    # (순위 170이 순위 1보다 긴 막대가 된다 — 순위는 크기가 아니라 순서다)
    # ③ 표시된 팀이 전부 1위라 막대 길이가 모두 같았다.
    #
    # 값을 "잡힌 플랫폼 수"로 고쳐 보니 이번엔 값이 1과 2 두 가지뿐이라 막대 길이가
    # 숫자 이상을 말하지 못했다. 그리고 그 답은 **바로 위 히트맵의 빈칸이 이미 보여준다**.
    # 답할 질문이 겹치면 차트를 뺀다(R3). 대신 히트맵을 잡힌 플랫폼이 **적은 순**으로
    # 정렬해 사각지대 팀이 맨 위에 오게 했다. 수치는 지표 타일과 해석이 들고 있다.

    watch_blind = sorted(k for k in watch_set if k in non_sp_unique)
    if watch_blind:
        ex = ", ".join(
            f"{k}(#{min(by_act[k].values())} {next(iter(by_act[k]))})" for k in watch_blind[:5]
        )
        insights.append(
            f"워치리스트 중 **Spotify 밖**에서만 차트인: {len(watch_blind)}팀 · {ex}. "
            "단일 플랫폼만 수집했다면 '미진입'으로 놓쳤을 팀"
        )
    insights.append(
        f"플랫폼 교차: {' · '.join(f'{p} {sum(1 for v in by_act.values() if p in v)}팀' for p in plat_names)} · "
        f"spotify-온리 {sp_unique_n}팀 · 비-spotify-온리 {len(non_sp_unique)}팀. "
        "순위는 플랫폼별 집계 범위가 달라 **절대값 비교 금지**. 이 뷰의 질문은 존재 여부"
    )


def _service(chart_label: str) -> str:
    label = chart_label.lower()
    if "spotify" in label:
        return "Spotify"
    if "apple" in label or "itunes" in label:
        return "Apple"
    if "melon" in label:
        return "Melon"
    return ""


def _rank_lookup(parsed_list: list[dict[str, object]]) -> list[dict[str, int]]:
    return [{_track_key(e): _i(e, "rank") for e in _entries(p)} for p in parsed_list]


# ── v3.5: 다국가 지리 리프레임 (RULES §4.5) ─────────────────────────────────
N_GEO = 6  # 조사 국가 수 ≥ N_GEO 이면 앵커-중립 지리 뷰로 전환 (RULES §4.5)
ROOKIE_YEARS = 3  # 데뷔 ≥ (스냅샷연도 − ROOKIE_YEARS) = 신인 코호트 (RULES §4.5, 값=A&R 튜닝가능)


def _detail_by_canon(entity_map: dict[str, object] | None, field: str) -> dict[str, object]:
    """entity-master의 field(debut/agency)를 canonical 아티스트명 → 값으로 (별칭 포함)."""
    out: dict[str, object] = {}
    if not entity_map:
        return out
    for primary, rec in entity_map.items():
        if isinstance(rec, dict) and rec.get(field):
            out[canonical_artist(primary)] = rec[field]
    for alias, ek in alias_index(entity_map).items():
        rec = entity_map.get(ek)
        if isinstance(rec, dict) and rec.get(field):
            out.setdefault(canonical_artist(alias), rec[field])
    return out


def _debut_year(value: object) -> int | None:
    text = str(value)[:4]
    return int(text) if text.isdigit() else None

# 권역 그룹: form=엔지니어 소유, 그룹핑=튜닝 가능(도메인 소유자). ISO alpha-2.
REGIONS: list[tuple[str, list[str]]] = [
    ("동아시아", ["kr", "jp", "tw", "hk"]),
    ("동남아", ["id", "my", "ph", "sg", "th", "vn"]),
    ("남아시아", ["in", "pk"]),
    ("유럽", ["gb", "uk", "de", "fr", "es", "it", "nl", "se", "pl", "pt", "ro", "be", "at", "ch",
             "ie", "dk", "fi", "no", "cz", "gr", "hu", "sk", "bg", "ee", "lt", "lv", "lu",
             "is", "cy", "mt", "ad", "by", "ru", "ua"]),
    ("북미", ["us", "ca"]),
    ("중남미", ["mx", "br", "ar", "cl", "co", "pe", "ec", "bo", "cr", "do", "gt", "hn",
               "ni", "pa", "py", "sv", "uy", "ve"]),
    ("MENA", ["ae", "sa", "tr", "eg", "il", "ma"]),
    ("아프리카", ["ng", "za"]),
    ("오세아니아", ["au", "nz"]),
    ("기타", ["kz"]),
]
_REGION_INDEX: dict[str, int] = {cc: i for i, (_, ccs) in enumerate(REGIONS) for cc in ccs}
_REGION_NAME: dict[str, str] = {cc: name for name, ccs in REGIONS for cc in ccs}


def _is_global(country: str) -> bool:
    return country.lower() == "global"


def _region_name(country: str) -> str:
    return _REGION_NAME.get(country.lower(), "기타")


def _order_countries(countries: list[str]) -> list[int]:
    """열 순서: GLOBAL 먼저 → 권역 그룹 순 → 국가코드. 입력 순서 무관(결정적)."""
    def key(i: int) -> tuple[int, int, str]:
        cc = countries[i].lower()
        if cc == "global":
            return (-1, -1, "")
        return (0, _REGION_INDEX.get(cc, len(REGIONS)), cc)

    return sorted(range(len(countries)), key=key)


def _roster_canon(entity_map: dict[str, object] | None, scope_country: str | None) -> set[str] | None:
    """entity-master에서 scope 원산지 아티스트의 canonical+별칭 집합 (RULES §4.5 로스터 스코프).

    None = 스코프 없음(전 시장 union). 원(raw) union은 서구 팝 헤게모니를 비추므로,
    K-pop 기획 관점에선 로스터(예: country=KR) 스코프가 신호를 살린다.
    """
    if not entity_map or not scope_country:
        return None
    scope = scope_country.upper()
    roster = {
        n for n, r in entity_map.items()
        if isinstance(r, dict) and str(r.get("country") or "").upper() == scope
    }
    canon = {canonical_artist(n) for n in roster}
    canon |= {alias for alias, primary in alias_index(entity_map).items() if primary in roster}
    return canon


_REGION_POS: dict[str, int] = {name: i for i, (name, _) in enumerate(REGIONS)}


def _dominant_region(
    cc_indices: set[int], best: dict[int, int], countries: list[str]
) -> tuple[str, int, int]:
    """한 아티스트의 최다 권역 (권역명, 국가수, 점유%). 결정적 tie-break (RULES §4.5):
    국가수 desc → 그 권역 최고(min)순위 asc → REGIONS 선언순. 동수면 더 높이 오른 권역."""
    reg: dict[str, tuple[int, int]] = {}  # name → (count, best_rank)
    for i in cc_indices:
        name = _region_name(countries[i])
        c, br = reg.get(name, (0, 10_000))
        reg[name] = (c + 1, min(br, best.get(i, 10_000)))
    name = min(reg, key=lambda n: (-reg[n][0], reg[n][1], _REGION_POS.get(n, len(REGIONS))))
    count = reg[name][0]
    return name, count, round(100 * count / len(cc_indices))


def _augment_cross_country(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    parsed_list: list[dict[str, object]],
    countries: list[str],
    entity_map: dict[str, object] | None = None,
    geo_scope: str | None = None,
    market_min: int = 2,
) -> None:
    non_global = [c for c in countries if not _is_global(c)]
    if len(non_global) >= N_GEO:  # 다국가 → 앵커-중립 지리 뷰 (RULES §4.5)
        _augment_geography(
            metrics, charts, insights, parsed_list, countries, entity_map, geo_scope, market_min
        )
        return

    ranks = _rank_lookup(parsed_list)
    top = sorted(_entries(parsed_list[0]), key=lambda e: _i(e, "rank"))[:12]

    def reach(entry: dict[str, object]) -> int:
        key = _track_key(entry)
        return sum(1 for r in ranks if r.get(key) is not None)

    rows = [_name(e) for e in top]
    cells: list[list[int | None]] = [[r.get(_track_key(e)) for r in ranks] for e in top]
    charts.append(
        {
            "type": "heatmap",
            "title": f"Top {len(top)} · 시장별 순위 ({countries[0]} 기준)",
            "data": {"rows": rows, "cols": countries, "cells": cells},
        }
    )

    everywhere = [e for e in top if reach(e) == len(parsed_list)]
    metrics.append({"label": "교차 시장", "value": len(parsed_list), "unit": "개국"})
    metrics.append(
        {"label": "전 시장 진입", "value": len(everywhere), "unit": "곡", "hint": f"{countries[0]} Top{len(top)} 중"}
    )
    if top:
        widest = max(top, key=reach)
        metrics.append({"label": "최광역 곡", "value": reach(widest), "unit": "개국", "hint": _name(widest)})

    if everywhere:
        names = ", ".join(_name(e) for e in everywhere[:3])
        tail = " 등" if len(everywhere) > 3 else ""
        insights.append(f"전 시장({', '.join(countries)}) 동시 진입: {names}{tail}.")
    insights.append("시장 간 매칭은 '아티스트-제목' 문자열 기준. 표기가 다르면 일부 누락 가능")


def _augment_geography(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    parsed_list: list[dict[str, object]],
    countries: list[str],
    entity_map: dict[str, object] | None = None,
    geo_scope: str | None = None,
    market_min: int = 2,
) -> None:
    """앵커-중립 다국가 지리 뷰 (RULES §4.5): 최광역 랭킹 + 지리 지문 + 화이트스페이스."""
    col_order = _order_countries(countries)  # 권역순 열 인덱스 (뷰별로 진입 시장만 필터)
    geo_idx = [i for i in col_order if not _is_global(countries[i])]  # reach 분모(GLOBAL 제외)

    # track_key → {country_idx: rank}, 표시명·아티스트(첫 등장)
    track_ranks: dict[str, dict[int, int]] = {}
    track_name: dict[str, str] = {}
    track_artist: dict[str, str] = {}
    for i, p in enumerate(parsed_list):
        for e in _entries(p):
            k = _track_key(e)
            track_ranks.setdefault(k, {})[i] = _i(e, "rank")
            track_name.setdefault(k, _name(e))
            track_artist.setdefault(k, _s(e, "artist"))

    # 로스터 스코프 (RULES §4.5): 지정 시 해당 원산지 로스터 트랙만 — 서구 팝 헤게모니 배제
    roster = _roster_canon(entity_map, geo_scope)
    scope_tag = f"[{geo_scope.upper()} 로스터] " if geo_scope and roster is not None else ""
    if roster is not None:
        track_ranks = {k: v for k, v in track_ranks.items() if canonical_artist(track_artist[k]) in roster}

    def track_reach(k: str) -> int:
        cmap = track_ranks[k]
        return sum(1 for i in geo_idx if i in cmap)

    # ── 뷰 1: 최광역 랭킹 (전 시장 union, reach≥2, 상위 K행) ──
    union = sorted(
        (k for k in track_ranks if track_reach(k) >= 2),
        key=lambda k: (-track_reach(k), k),
    )[:15]
    # 열은 조사 국가 전체가 아니라 '표시 곡이 실제 진입한 시장'만 (다국가 확장 시 가독성; GLOBAL 유지)
    union_cols = [i for i in col_order if _is_global(countries[i]) or any(i in track_ranks[k] for k in union)]
    charts.append(
        {
            "type": "heatmap",
            "id": "reach-ranking",
            "title": f"{scope_tag}최광역 랭킹 · {len(union)}곡 × {len(union_cols)}시장 (앵커 없음, 진입국가순)",
            "data": {
                "rows": [track_name[k] for k in union],
                "cols": [countries[i].upper() for i in union_cols],
                "cells": [[track_ranks[k].get(i) for i in union_cols] for k in union],
            },
        }
    )

    # ── 뷰 2: 지리 지문 (상위 reach 아티스트 × 시장, 곡 최고순위) ──
    art_best: dict[str, dict[int, int]] = {}
    art_cc: dict[str, set[int]] = {}
    for k, cmap in track_ranks.items():
        a = track_artist[k]
        best = art_best.setdefault(a, {})
        seen = art_cc.setdefault(a, set())
        for i, r in cmap.items():
            if i not in best or r < best[i]:
                best[i] = r
            if i in geo_idx:
                seen.add(i)
    artists = sorted(art_best, key=lambda a: (-len(art_cc[a]), a))[:10]
    fp_cols = [i for i in col_order if _is_global(countries[i]) or any(i in art_best[a] for a in artists)]
    charts.append(
        {
            "type": "heatmap",
            "id": "artist-markets",
            "title": f"{scope_tag}지리 지문 · Top {len(artists)} 아티스트 × {len(fp_cols)}시장 (곡 최고순위)",
            "data": {
                "rows": artists,
                "cols": [countries[i].upper() for i in fp_cols],
                "cells": [[art_best[a].get(i) for i in fp_cols] for a in artists],
            },
        }
    )

    # ── 지표 ──
    metrics.append({"label": "조사 국가", "value": len(geo_idx), "unit": "개국"})
    if union:
        wk = union[0]
        metrics.append({"label": "최광역 곡", "value": track_reach(wk), "unit": "개국", "hint": track_name[wk]})
    if artists:
        wa = artists[0]
        dom_reg, dom_cnt, dom_share = _dominant_region(art_cc[wa], art_best[wa], countries)
        metrics.append({"label": "최광역 팀", "value": len(art_cc[wa]), "unit": "개국", "hint": wa})
        metrics.append({"label": f"{wa} 최다 권역", "value": dom_reg, "hint": f"{dom_cnt}개국 · {dom_share}%"})

    # ── insights (지문 shape 사실 + 한계 필수, RULES §4.5) ──
    if roster is not None:
        insights.append(
            f"지리 뷰를 '{geo_scope.upper() if geo_scope else ''} 원산지 로스터'로 한정. "
            "원(raw) 전 시장 union은 서구 팝이 지배하므로 K-pop 기획엔 로스터 스코프가 유효"
            "(확인된 로스터에 한함, 미확인 아티스트 제외)."
        )
    else:
        insights.append("조사 범위 미지정(전 시장 합집합). 최광역 상위는 글로벌 팝 지형 참고용")
    if union:
        names = ", ".join(track_name[k] for k in union[:3])
        insights.append(f"최광역(앵커 무관): {names} 등이 조사 {len(geo_idx)}개국 중 최다 시장 진입.")
    fingerprints = []
    for a in artists[:4]:
        if art_cc[a]:
            dom, _, _ = _dominant_region(art_cc[a], art_best[a], countries)
            fingerprints.append(f"{a}={dom}({len(art_cc[a])}개국)")
    if fingerprints:
        insights.append("지리 지문 상위: " + " · ".join(fingerprints) + " · 팀별 최다 권역 비교용(지문 히트맵 참조)")
    insights.append("도달 국가 수는 조사한 국가 집합 기준. 세계 절대 도달 아님")
    # 이 뷰만 Spotify 단일 레일이다. Melon은 KR 1시장이라 **나라 사이 비교에 쓸 수 없고**,
    # 써클차트는 연결되지 않았다. 예전 문구("국내 차트 미반영")는 렌즈가 아예 없다는 뜻으로
    # 읽혀, 같은 리포트가 Melon 1위를 싣기 시작한 뒤로는 화면끼리 어긋났다.
    insights.append(
        "이 지리 뷰만 Spotify 단일 레일 기준. Melon은 KR 1시장이라 나라 사이 비교에 쓰지 않고, "
        "써클차트는 연결되지 않았다"
    )
    insights.append("지리 신호는 기획 참고용. 타겟 결정은 담당자의 몫")

    # ── 뷰 3·4: 화이트스페이스(기획) + 신인 코호트 (로스터 스코프 전용) ──
    if roster is not None:
        _whitespace_view(
            charts, metrics, insights, artists, art_best, art_cc,
            geo_idx, col_order, countries, market_min, scope_tag,
        )
        meta0 = parsed_list[0].get("meta")
        sdate = str(meta0.get("snapshot_date"))[:4] if isinstance(meta0, dict) else ""
        if sdate.isdigit():
            geo_cols = [i for i in col_order if i in set(geo_idx)]
            _cohort_view(
                charts, metrics, insights, art_best, art_cc,
                geo_cols, countries, entity_map, int(sdate), scope_tag,
            )


def _whitespace_view(
    charts: list[dict[str, object]],
    metrics: list[dict[str, object]],
    insights: list[str],
    artists: list[str],
    art_best: dict[str, dict[int, int]],
    art_cc: dict[str, set[int]],
    geo_idx: list[int],
    col_order: list[int],
    countries: list[str],
    market_min: int,
    scope_tag: str,
) -> None:
    """갭/화이트스페이스 (RULES §4.5, 기획): 로스터 강세 시장(≥market_min팀 진입)인데
    특정 팀이 미진입인 국가 = greenfield 타겟. **tunable 뷰**로 방출 — 대시보드에서
    A&R가 market_min을 슬라이더로 직접 조정하면 client-side 재계산(값=도메인 소유자, §2.1)."""
    geo_set = set(geo_idx)
    geo_cols = [i for i in col_order if i in geo_set]  # 권역순 non-global 시장
    roster_rows = sorted(art_best, key=lambda a: (-len(art_cc[a]), a))  # 전체 로스터, reach 순
    if not roster_rows or not geo_cols:
        insights.append("로스터 진입 데이터가 없어 미개척 시장 뷰 생략(조사 범위와 커버리지 확인 필요)")
        return

    # tunable 차트: 전체 행렬 + knob 탑재 → client가 임의 임계로 개척시장·갭 재계산 (RULES §4.5)
    charts.append(
        {
            "type": "tunable",
            "id": "spotify-gaps",
            "title": f"{scope_tag}미개척 지도 · 개척 시장 × 팀 (빈칸=미개척) · 기준 직접 조정",
            "data": {
                "view": "whitespace",
                "matrix": {
                    "rows": roster_rows,
                    "cols": [countries[i].upper() for i in geo_cols],
                    "cells": [[art_best[a].get(i) for i in geo_cols] for a in roster_rows],
                },
                "knobs": [
                    {
                        "key": "market_min",
                        "label": "개척 시장 기준 (진입 팀 수 ≥)",
                        "default": market_min,
                        "min": 1,
                        "max": 6,
                        "step": 1,
                    }
                ],
                "topRows": 10,
                "note": (
                    "개척 시장 = 로스터가 이 수 이상 진입한 검증된 시장. 빈칸 = 그 팀의 미개척(greenfield) "
                    "후보. 기준은 슬라이더로 직접 조정 가능. 후보 신호이지 진출 지시 아님"
                ),
            },
        }
    )

    # 기본 임계(market_min) 스냅샷 — KPI 지표·인사이트 (슬라이더와 별개의 참조값)
    market_acts: dict[int, int] = {}
    for ccset in art_cc.values():
        for i in ccset:
            market_acts[i] = market_acts.get(i, 0) + 1
    proven_order = [i for i in geo_cols if market_acts.get(i, 0) >= market_min]
    metrics.append(
        {"label": "개척 시장", "value": len(proven_order), "unit": "개국", "hint": f"기본 ≥{market_min}팀(조정가능)"}
    )
    if artists and proven_order:
        wa = artists[0]
        gaps0 = [i for i in proven_order if i not in art_cc[wa]]
        metrics.append(
            {"label": f"{wa} 미개척", "value": len(gaps0), "unit": "개국", "hint": f"개척 시장(≥{market_min}팀) 중 미진입"}
        )
    for a in artists[:3]:
        gaps = [i for i in proven_order if i not in art_cc[a]]
        if gaps:
            names = ", ".join(countries[i].upper() for i in gaps[:6])
            tail = " 등" if len(gaps) > 6 else ""
            insights.append(f"{a} 미개척(로스터 강세 시장, 기본 ≥{market_min}팀): {names}{tail} · 진입 후보 시장")
    insights.append(
        "미개척 기준은 대시보드 슬라이더로 직접 조정 가능. "
        "후보 신호이지 진출 지시 아님."
    )


def _cohort_view(
    charts: list[dict[str, object]],
    metrics: list[dict[str, object]],
    insights: list[str],
    art_best: dict[str, dict[int, int]],
    art_cc: dict[str, set[int]],
    geo_cols: list[int],
    countries: list[str],
    entity_map: dict[str, object] | None,
    snapshot_year: int,
    scope_tag: str,
) -> None:
    """신인 코호트 지리 (RULES §4.5): 데뷔 ≥ (snapshot_year − ROOKIE_YEARS) 팀만 →
    reach 정렬에 가려진 '신인도 특정 시장엔 닿는다'를 표면화(대기업 전용 아님)."""
    debut_map = _detail_by_canon(entity_map, "debut")
    agency_map = _detail_by_canon(entity_map, "agency")
    cutoff = snapshot_year - ROOKIE_YEARS

    def debut(a: str) -> int | None:
        return _debut_year(debut_map.get(canonical_artist(a)))

    rookies = [a for a in art_best if (y := debut(a)) is not None and y >= cutoff]
    rookies.sort(key=lambda a: (-len(art_cc[a]), a))
    if not rookies:
        insights.append(f"신인(데뷔 ≥{cutoff}) 데이터가 없어 신인 지리 뷰 생략")
        return
    rookies = rookies[:12]
    rookie_cols = [i for i in geo_cols if any(i in art_cc[a] for a in rookies)]
    if rookie_cols:
        charts.append(
            {
                "type": "heatmap",
                "id": "rookie-markets",
                "title": f"{scope_tag}신인 지리 지문 · 데뷔 ≥{cutoff} ({len(rookies)}팀) × 시장 · 팬베이스 없이 어디에 닿는지",
                "data": {
                    "rows": [f"{a} ({debut(a)})" for a in rookies],
                    "cols": [countries[i].upper() for i in rookie_cols],
                    "cells": [[art_best[a].get(i) for i in rookie_cols] for a in rookies],
                },
            }
        )
    top = rookies[0]
    metrics.append(
        {"label": "신인 최광역", "value": len(art_cc[top]), "unit": "개국", "hint": f"{top} ({debut(top)})"}
    )
    parts: list[str] = []
    for a in rookies[:5]:
        agency = agency_map.get(canonical_artist(a))
        tag = f"·{agency}" if isinstance(agency, str) else ""
        parts.append(f"{a}({debut(a)}{tag}) {len(art_cc[a])}개국")
    insights.append(
        f"신인 코호트(데뷔 ≥{cutoff}, {len(rookies)}팀): " + " · ".join(parts)
        + ". 팬베이스 없는 신인도 특정 시장에는 닿음"
    )
    insights.append(
        f"신인 판정 기준: 데뷔 {ROOKIE_YEARS}년 이내(데뷔연도 확인분 한정). 기준값 조정 가능"
    )


def _augment_time_series(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    parsed_list: list[dict[str, object]],
    dates: list[str],
) -> None:
    order = sorted(range(len(parsed_list)), key=lambda i: dates[i])
    snaps = [parsed_list[i] for i in order]
    xs = [dates[i] for i in order]
    ranks = _rank_lookup(snaps)
    top = sorted(_entries(snaps[-1]), key=lambda e: _i(e, "rank"))[:6]

    series = [
        {"name": _name(e), "values": [r.get(_track_key(e)) for r in ranks]} for e in top
    ]
    charts.append({"type": "line", "title": "순위 추이 (최근 Top 6)", "data": {"x": xs, "series": series}})

    def delta(entry: dict[str, object]) -> int | None:
        key = _track_key(entry)
        first, last = ranks[0].get(key), ranks[-1].get(key)
        return (first - last) if (first is not None and last is not None) else None

    moved = [(e, d) for e in top if (d := delta(e)) is not None]
    if moved:
        best = max(moved, key=lambda t: t[1])
        metrics.append({"label": "기간 최고 상승", "value": best[1], "unit": "계단", "hint": _name(best[0])})
    insights.append(f"{xs[0]}~{xs[-1]} {len(snaps)}개 스냅샷 순위 추이 (단일 소스, 참고용).")


# ── v3.2: cross-view momentum — same country+date, different chart view (일간×주간) ──
def _augment_cross_view(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    parsed_list: list[dict[str, object]],
    labels: list[str],
) -> None:
    ranks = _rank_lookup(parsed_list[:2])
    base_label = labels[0] or "일간"
    cmp_label = labels[1] or "주간"
    top = sorted(_entries(parsed_list[0]), key=lambda e: _i(e, "rank"))[:20]

    moved: list[tuple[dict[str, object], int]] = []
    for e in top:
        key = _track_key(e)
        base_rank, cmp_rank = ranks[0].get(key), ranks[1].get(key)
        if base_rank is not None and cmp_rank is not None:
            moved.append((e, cmp_rank - base_rank))  # + = base outranks compare = 상승세

    if not moved:
        insights.append(f"{base_label}·{cmp_label} 간 매칭 곡이 없어 모멘텀 비교를 건너뜀.")
        return

    risers = sorted(moved, key=lambda t: t[1], reverse=True)[:10]
    rising = [m for m in moved if m[1] > 0]
    charts.append(
        {
            "type": "bar",
            "title": f"모멘텀 · {base_label} vs {cmp_label} (순위차, + 상승)",
            "data": [{"name": _name(e), "value": mom} for e, mom in risers],
        }
    )
    metrics.append({"label": "상승세 곡", "value": len(rising), "unit": "곡", "hint": f"매칭 {len(moved)}곡 중"})
    best_entry, best_mom = risers[0]
    metrics.append({"label": "최고 모멘텀", "value": best_mom, "unit": "계단", "hint": _name(best_entry)})
    insights.append(
        f"{base_label}이 {cmp_label}보다 앞선(상승세) 곡 {len(rising)}/{len(moved)} · {base_label} 순위 가속 신호(참고)"
    )
    insights.append(f"최고 모멘텀: {_name(best_entry)} ({cmp_label} 대비 +{best_mom}계단).")


# ── v3.3: cross-source positioning — different platforms (Spotify × Apple) ──────
# Matched by canonical TITLE (language-neutral for many tracks); artist names may
# differ by language (CORTIS ↔ 코르티스), so title is the join key. See RULES §4.4.
def _augment_cross_source(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    parsed_list: list[dict[str, object]],
    services: list[str],
    entity_map: dict[str, object],
) -> None:
    base, comp = parsed_list[0], parsed_list[1]
    base_svc, comp_svc = services[0], services[1]
    aidx = alias_index(entity_map)  # v3.4: cross-language artist (코르티스 ↔ CORTIS)

    def entity_of(entry: dict[str, object]) -> str | None:  # entity key, or None if unresolved
        artist = _s(entry, "artist")
        return aidx.get(artist.strip().lower()) or aidx.get(canonical_artist(artist))

    # Match by title (language-neutral for many tracks); reject a title-match only when
    # BOTH artists resolve to DIFFERENT entities (collision). Entity aliases (코르티스↔CORTIS)
    # thus add precision without dropping unresolved-artist matches (HANRORO↔한로로).
    comp_by_title: dict[str, dict[str, object]] = {}
    for e in _entries(comp):
        comp_by_title[canonical_title(_s(e, "title"))] = e
    top = sorted(_entries(base), key=lambda e: _i(e, "rank"))[:20]

    matched: list[tuple[dict[str, object], int, int]] = []
    confirmed = 0
    for e in top:
        ce = comp_by_title.get(canonical_title(_s(e, "title")))
        if ce is None:
            continue
        be, ae = entity_of(e), entity_of(ce)
        if be is not None and ae is not None and be != ae:
            continue  # same title, different artist entity → collision
        matched.append((e, _i(e, "rank"), _i(ce, "rank")))
        if be is not None and be == ae:
            confirmed += 1

    if not matched:
        insights.append(f"{base_svc}·{comp_svc} 매칭 곡이 없어 크로스소스 비교를 건너뜀.")
        return

    rows = [_name(e) for e, _b, _c in matched[:12]]
    cells: list[list[int | None]] = [[b, c] for _e, b, c in matched[:12]]
    charts.append(
        {
            "type": "heatmap",
            "title": f"플랫폼별 순위 · {base_svc} vs {comp_svc}",
            "data": {"rows": rows, "cols": [base_svc, comp_svc], "cells": cells},
        }
    )
    metrics.append({"label": "양대 플랫폼 진입", "value": len(matched), "unit": "곡", "hint": f"{base_svc} Top{len(top)} 중"})
    # skew = comp_rank − base_rank; + = base(예: 스트리밍)에서 상대적으로 강함
    skew = max(matched, key=lambda t: t[2] - t[1])
    if skew[2] - skew[1] > 0:
        metrics.append(
            {"label": f"{base_svc} 편중", "value": skew[2] - skew[1], "unit": "계단", "hint": _name(skew[0])}
        )
    conf = f" · 엔티티 확인 {confirmed}곡(코르티스↔CORTIS 등 크로스언어)" if confirmed else ""
    insights.append(f"{base_svc} Top20 중 {len(matched)}곡이 {comp_svc}에도 진입 · 제목 매칭{conf}")
    insights.append(
        "아티스트는 엔티티 별칭으로 크로스언어 인식·콜리전 방지. 제목이 언어로 갈리는 곡(만찬가↔Bansanka)은 "
        "미매칭. 소스 커버리지 한계로 정밀 매칭은 유료 소스 확보 후 과제"
    )


# ── v3: entity master join (MusicBrainz) — artist origin distribution ───────────
def _augment_entities(
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    entries: list[dict[str, object]],
    entity_map: dict[str, object],
) -> None:
    counts: dict[str, int] = defaultdict(int)
    sources: dict[str, int] = defaultdict(int)
    resolved = 0
    total = 0
    unresolved: list[str] = []
    seen: set[str] = set()
    for e in sorted(entries, key=lambda x: _i(x, "rank")):
        artist = primary_artist(_s(e, "artist"))
        if not artist or artist in seen:
            continue
        rec = entity_map.get(artist)
        if rec is None:  # not in the enriched top-N
            continue
        seen.add(artist)
        total += 1
        country = rec.get("country") if isinstance(rec, dict) else None
        if isinstance(country, str) and country:
            resolved += 1
            counts[country] += 1
            source = rec.get("source") if isinstance(rec, dict) else None
            if isinstance(source, str):
                sources[source] += 1
        else:
            unresolved.append(artist)

    if total == 0:
        insights.append("엔티티 맵에 해당 차트 아티스트가 없어 원산지 조인을 건너뜀.")
        return

    dist = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    charts.append(
        {
            "type": "bar",
            "title": "아티스트 원산지 분포 (MusicBrainz)",
            "data": [{"name": c, "value": n} for c, n in dist],
        }
    )
    if resolved:
        kr = counts.get("KR", 0)
        metrics.append(
            {"label": "국내(KR) 아티스트", "value": round(100 * kr / resolved), "unit": "%", "hint": f"해석 {resolved}/{total}팀"}
        )
    top_origins = ", ".join(f"{c} {n}" for c, n in dist[:4])
    prov = " · ".join(f"{s} {n}" for s, n in sorted(sources.items(), key=lambda kv: (-kv[1], kv[0])))
    insights.append(f"상위 아티스트 원산지({resolved}/{total}팀 해석 · {prov}): {top_origins}.")
    if unresolved:
        insights.append(
            f"엔티티 미해석 {len(unresolved)}팀(표기 변형 등, 예: {unresolved[0]}) · 수기/추가 소스 보강 대상"
        )
