"""chart-history CLI.

    python -m chart_history analyze <snapshot.html> -o <outdir>
    python -m chart_history fetch --url <kworb-url> -o <fixture.html>
    python -m chart_history validate <report.json>

`analyze` (offline, deterministic) is the smoke path; `fetch` is the live
collector. Analysis is separated from collection so the smoke never touches
the network (D-003 static-first, DATA_SOURCES §4).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, cast

from chart_history import entities
from chart_history.normalize import primary_artist
from chart_history.parse import parse_chart
from chart_history.report import (
    build_chart_signal_series,
    build_chart_signal_series_from_days,
    build_multi,
    build_report,
    now_iso,
)

_UA = "Mozilla/5.0 (research; artist-intelligence chart-history collector)"


def find_schema() -> Path | None:
    rel = Path("packages") / "report-schema" / "report.schema.json"
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        node = base
        for _ in range(8):
            if (node / rel).exists():
                return node / rel
            if node.parent == node:
                break
            node = node.parent
    return None


def validate_report(report: dict[str, object]) -> tuple[bool, list[str]]:
    """Returns (checked, errors). checked=False means validation was skipped."""
    schema_path = find_schema()
    if schema_path is None:
        return (False, [])
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return (False, [])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = [
        f"{list(e.path)}: {e.message}"
        for e in Draft202012Validator(schema).iter_errors(cast(Any, report))
    ]
    return (True, errors)


def _watch_keys(watchlist_path: str | None) -> list[str]:
    if not watchlist_path or not Path(watchlist_path).exists():
        return []
    doc = json.loads(Path(watchlist_path).read_text(encoding="utf-8"))
    arts = doc.get("artists") if isinstance(doc, dict) else None
    return [
        str(a["key"]) for a in (arts if isinstance(arts, list) else []) if isinstance(a, dict) and a.get("key")
    ]


def cmd_analyze(args: argparse.Namespace) -> int:
    inputs: list[str] = []
    for p in args.input:
        path = Path(p)
        if path.is_dir():  # v3.2 flat store · v4 platform/market 중첩 스토어 (D-016)
            files = (
                sorted(path.glob("*.html"))
                + sorted(path.glob("*/*.html"))
                + sorted(path.glob("*/*/*.html"))
            )
            if args.latest:  # leaf 디렉토리별 최신 스냅샷만 (라이브 스토어 일간 분석)
                newest: dict[Path, Path] = {}
                for f in files:
                    if f.parent not in newest or f.name > newest[f.parent].name:
                        newest[f.parent] = f
                files = sorted(newest.values())
            inputs.extend(str(f) for f in files)
        else:
            inputs.append(p)
    if not inputs:
        print("no snapshot .html inputs found", file=sys.stderr)
        return 1
    parsed_list = [parse_chart(Path(p).read_text(encoding="utf-8")) for p in inputs]
    entity_map = entities.load_entities(args.entities, args.watchlist)
    if len(parsed_list) == 1:
        report = build_report(
            parsed_list[0], chart_name=args.chart_name, generated_at=now_iso(), entity_map=entity_map
        )
    else:
        report = build_multi(
            parsed_list,
            chart_name=args.chart_name,
            generated_at=now_iso(),
            entity_map=entity_map,
            geo_scope=args.geo_scope,
            market_min=args.market_min,
            watch=_watch_keys(args.watchlist),
        )

    checked, errors = validate_report(report)
    if errors:
        print(f"report is schema-INVALID ({len(errors)} error(s)) — not writing:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    base_entries = parsed_list[0].get("entries")
    count = len(base_entries) if isinstance(base_entries, list) else 0
    status = "valid" if checked else "UNCHECKED (jsonschema/schema not found)"
    scope = f"{len(parsed_list)} snapshots" if len(parsed_list) > 1 else "1 snapshot"
    ent = f" · entities {len(entity_map)}" if entity_map else ""
    print(f"wrote {out} · base {count} entries · {scope}{ent} · schema {status}")
    return 0


def _extract_first_table(html: str) -> str | None:
    m = re.search(r"(?s)<table.*?</table>", html)
    return m.group(0) if m else None


def _extract_date(html: str) -> str | None:
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", html)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _download_snapshot(url: str) -> tuple[str | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted static host)
        html = resp.read().decode("utf-8", "replace")
    return _extract_first_table(html), (_extract_date(html) or "unknown")


def _snapshot_doc(
    url: str,
    chart: str,
    country: str | None,
    date: str,
    table: str,
    *,
    platform: str = "spotify",
    tos_class: str = "open-aggregator",
    note: str = "facts-only chart snapshot (Kworb aggregator), site chrome stripped",
) -> str:
    country_part = f" | country: {country}" if country else ""
    meta = (
        f"<!-- source: {url} | chart: {chart}{country_part} | platform: {platform} "
        f"| snapshot_date: {date} | tos_class: {tos_class} | license: chart-facts "
        f"| note: {note} -->"
    )
    return meta + "\n" + table + "\n"


def cmd_fetch(args: argparse.Namespace) -> int:
    table, date = _download_snapshot(args.url)
    if table is None:
        print("no <table> found at URL", file=sys.stderr)
        return 1
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_snapshot_doc(args.url, args.chart_name or "Chart", args.country, date, table), encoding="utf-8")
    print(f"wrote {out} · snapshot_date={date}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    """Fetch a chart and append it to a dated snapshot store (v3.2 accumulation)."""
    table, date = _download_snapshot(args.url)
    if table is None:
        print("no <table> found at URL", file=sys.stderr)
        return 1
    store = Path(args.store)
    store.mkdir(parents=True, exist_ok=True)
    out = store / f"{date}.html"
    out.write_text(
        _snapshot_doc(
            args.url, args.chart_name or "Chart", args.country, date, table, platform=args.platform
        ),
        encoding="utf-8",
    )
    print(f"collected {date} → {out} ({len(list(store.glob('*.html')))} snapshots in store)")
    return 0


_APPLE_RSS = "https://rss.marketingtools.apple.com/api/v2/{sf}/music/most-played/{limit}/songs.json"


def _rss_date(updated: str) -> str:
    """RFC2822 'Sun, 19 Jul 2026 13:22:46 +0000' → '2026-07-19' (피드 갱신일 = 스냅샷 일자)."""
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(updated).date().isoformat()
    except (TypeError, ValueError):
        return "unknown"


def cmd_collect_apple(args: argparse.Namespace) -> int:
    """Apple 공식 RSS(most-played) → facts-only 차트 테이블 스냅샷 (v4 멀티플랫폼, D-016).

    JSON 피드를 기존 스토어 계약(헤더 있는 HTML 테이블 + 메타 주석)으로 변환해 저장 —
    parse/signals/analyze 전 파이프라인을 무변경 재사용한다. 순위=피드 순서(공식 제공).
    """
    sf = args.storefront.lower()
    url = _APPLE_RSS.format(sf=sf, limit=args.limit)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (official Apple feed)
        feed = json.loads(resp.read().decode("utf-8"))["feed"]
    results = feed.get("results") or []
    if not results:
        print(f"empty feed for storefront {sf}", file=sys.stderr)
        return 1
    date = _rss_date(str(feed.get("updated") or ""))
    rows = "".join(
        f"<tr><td>{i}</td><td>{r.get('artistName', '')} - {r.get('name', '')}</td></tr>"
        for i, r in enumerate(results, 1)
    )
    table = "<table><tr><th>Pos</th><th>Artist and Title</th></tr>" + rows + "</table>"
    store = Path(args.store)
    store.mkdir(parents=True, exist_ok=True)
    out = store / f"{date}.html"
    out.write_text(
        _snapshot_doc(
            url,
            f"Apple Music {sf.upper()} Most-Played",
            sf.upper(),
            date,
            table,
            platform="apple",
            tos_class="official-feed",
            note="facts-only chart snapshot (Apple Marketing Tools RSS, official public feed)",
        ),
        encoding="utf-8",
    )
    print(f"collected {date} → {out} ({len(results)} entries, official Apple RSS)")
    return 0


_MELON_PAREN_RE = re.compile(r"^(.*?)\s*[(（][^)）]*[)）]\s*$")
# 멜론 MCP 응답은 파이썬 repr 유사 문자열 — 곡/앨범명 내부 작은따옴표('선녀외전' 등)로
# literal_eval이 깨질 수 있어 **다음 고정 키를 앵커로 한 정규식**으로 사실 필드만 뽑는다.
_MELON_SONG_SPLIT = re.compile(r"\{'song_id':")
_MELON_TITLE_RE = re.compile(r"'song_name':'(.*?)','issue_date'", re.S)
_MELON_ARTIST_RE = re.compile(r"'artist_name':'(.*?)'\}", re.S)
_MELON_RANK_RE = re.compile(r"'current_rank':'(\d+)'")


def _melon_clean_artist(name: str) -> str:
    """'RESCENE (리센느)'·'아일릿(ILLIT)' 병기 표기에서 앞 표기만 — 별칭 인덱스가 양표기를 다 안다."""
    name = name.strip()
    m = _MELON_PAREN_RE.match(name)
    return m.group(1).strip() if m and m.group(1).strip() else name


def _melon_rows(text: str) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}
    for block in _MELON_SONG_SPLIT.split(text)[1:]:
        rank_m = _MELON_RANK_RE.search(block)
        title_m = _MELON_TITLE_RE.search(block)
        artist_m = _MELON_ARTIST_RE.search(block)
        if not (rank_m and title_m and artist_m):
            continue
        out[int(rank_m.group(1))] = (
            _melon_clean_artist(artist_m.group(1)),
            title_m.group(1).strip(),
        )
    return out


def cmd_convert_melon(args: argparse.Namespace) -> int:
    """멜론 공식 MCP 차트 응답(저장 파일들) → 스토어 스냅샷 (v4.2 4번째 렌즈, D-017).

    수집은 공식 Melon MCP(OAuth 세션)가 담당하고, 이 커맨드는 저장된 응답을 기존
    스토어 계약(facts-only 테이블+메타)으로 변환만 한다(오프라인·결정적).
    """
    rows_by_rank: dict[int, tuple[str, str]] = {}
    for path in args.pages:
        rows_by_rank.update(_melon_rows(Path(path).read_text(encoding="utf-8")))
    if not rows_by_rank:
        print("no songs parsed from melon pages", file=sys.stderr)
        return 1
    rows = "".join(
        f"<tr><td>{r}</td><td>{a} - {t}</td></tr>"
        for r, (a, t) in sorted(rows_by_rank.items())
    )
    table = "<table><tr><th>Pos</th><th>Artist and Title</th></tr>" + rows + "</table>"
    store = Path(args.store)
    store.mkdir(parents=True, exist_ok=True)
    out = store / f"{args.date}.html"
    out.write_text(
        _snapshot_doc(
            "https://mcp.melon.com/mcp get_music_chart(DAILY)",
            "Melon KR Daily",
            "KR",
            args.date,
            table,
            platform="melon",
            tos_class="official-mcp",
            note="facts-only chart snapshot (official Melon MCP, Kakao Ent · OAuth user consent)",
        ),
        encoding="utf-8",
    )
    print(f"converted {len(rows_by_rank)} entries → {out} (official Melon MCP)")
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    """Resolve a snapshot's top-N artists to MusicBrainz entities → committed cache."""
    parsed = parse_chart(Path(args.input).read_text(encoding="utf-8"))
    raw_entries = parsed.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []

    order: list[str] = []
    seen: set[str] = set()
    for e in sorted(entries, key=lambda x: x.get("rank") if isinstance(x.get("rank"), int) else 9999):
        artist = primary_artist(str(e.get("artist") or ""))
        if artist and artist not in seen:
            seen.add(artist)
            order.append(artist)
        if len(order) >= args.top:
            break

    resolved: dict[str, object] = {}
    by_source: dict[str, int] = {}
    hits = 0
    for i, artist in enumerate(order):
        try:
            rec = entities.resolve(artist, min_score=args.min_score, use_wiki=args.wiki)
        except Exception as exc:  # noqa: BLE001 (network best-effort; mark unresolved)
            print(f"  ! {artist}: {exc}", file=sys.stderr)
            rec = None
        if rec and rec.get("country"):
            resolved[artist] = rec
            hits += 1
            src = str(rec.get("source") or "?")
            by_source[src] = by_source.get(src, 0) + 1
        else:
            resolved[artist] = {"resolved": False}
        if i < len(order) - 1:
            time.sleep(args.delay)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sources": ["MusicBrainz", "Wikidata"], "license": "CC0", "artists": resolved}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    breakdown = ", ".join(f"{s} {n}" for s, n in sorted(by_source.items()))
    print(f"enriched {hits}/{len(order)} artists ({breakdown}) → {out}")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    """Emit a per-(date × artist) chart-rank signal-series for signal-bridge (data-only join)."""
    store = Path(args.store)
    if store.is_dir():
        # flat store · market subdirs (chart/<cc>/, D-013) · platform/market (chart/<platform>/<cc>/, D-016)
        files = (
            sorted(store.glob("*.html"))
            + sorted(store.glob("*/*.html"))
            + sorted(store.glob("*/*/*.html"))
        )
    else:
        files = [store]
    if not files:
        print(f"no snapshot .html in {store}", file=sys.stderr)
        return 1
    snapshots = [parse_chart(f.read_text(encoding="utf-8")) for f in files]
    entity_map = entities.load_entities(args.entities, args.watchlist)
    if args.reconstruct_days:  # retrospective: live snapshot(s) → entry via Days field
        series = build_chart_signal_series_from_days(
            snapshots,
            entity_map=entity_map,
            generated_at=now_iso(),
            window_days=args.reconstruct_days,
        )
    else:  # forward: multi-day store → real per-day series
        series = build_chart_signal_series(
            snapshots, entity_map=entity_map, generated_at=now_iso()
        )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(series, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artists = cast(dict[str, object], series["series"])
    dates = cast(list[str], series["dates"])
    print(f"wrote {out} | {len(artists)} artists × {len(dates)} days | chart-rank series")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    checked, errors = validate_report(report)
    if not checked:
        print("UNCHECKED — jsonschema not installed or schema not found", file=sys.stderr)
        return 2
    if errors:
        print(f"INVALID ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"{args.report} · schema valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chart_history", description="Kworb chart-history collector")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="snapshot HTML(s)/store dir → schema-valid report.json")
    p_analyze.add_argument(
        "input",
        nargs="+",
        help="one snapshot (v1), several to cross-compare (국가/날짜/뷰), or a store directory (v3.2)",
    )
    p_analyze.add_argument("-o", "--output", required=True, help="output directory for report.json")
    p_analyze.add_argument("--chart-name", default=None, help="override chart display name")
    p_analyze.add_argument(
        "--entities", default=None, help="entity map JSON (v3: artist origin join)"
    )
    p_analyze.add_argument(
        "--watchlist",
        default=None,
        help="사용자 워치리스트 JSON — 캐노니컬 병합 + 플랫폼 히트맵 우선 행 (v4, D-016)",
    )
    p_analyze.add_argument(
        "--latest",
        action="store_true",
        help="스토어 디렉토리에서 leaf(플랫폼/시장)별 최신 스냅샷만 분석 (라이브 일간 뷰, D-016)",
    )
    p_analyze.add_argument(
        "--geo-scope",
        default=None,
        help="다국가 지리 뷰를 이 원산지 로스터로 스코프 (예: KR). --entities 필요 (RULES §4.5)",
    )
    p_analyze.add_argument(
        "--market-min",
        type=int,
        default=2,
        help="화이트스페이스 '개척 시장' 임계 — 이 수 이상 로스터 팀이 진입한 국가 (기본 2, RULES §4.5)",
    )
    p_analyze.set_defaults(func=cmd_analyze)

    p_fetch = sub.add_parser("fetch", help="download a fresh snapshot (live collector)")
    p_fetch.add_argument("--url", required=True, help="Kworb chart URL")
    p_fetch.add_argument("-o", "--output", required=True, help="output .html path")
    p_fetch.add_argument("--chart-name", default=None, help="chart display name")
    p_fetch.add_argument("--country", default=None, help="market code for v2 cross-country (e.g. KR)")
    p_fetch.set_defaults(func=cmd_fetch)

    p_collect = sub.add_parser("collect", help="append a dated snapshot to a store (v3.2 축적)")
    p_collect.add_argument("--url", required=True, help="Kworb chart URL")
    p_collect.add_argument("--store", required=True, help="snapshot store directory (dated files)")
    p_collect.add_argument("--chart-name", default=None, help="chart display name")
    p_collect.add_argument("--country", default=None, help="market code (e.g. KR)")
    p_collect.add_argument(
        "--platform",
        default="spotify",
        help="차트 플랫폼 차원 (spotify|youtube|…, D-016 멀티플랫폼 온셋)",
    )
    p_collect.set_defaults(func=cmd_collect)

    p_apple = sub.add_parser(
        "collect-apple", help="Apple 공식 RSS(most-played) → 스토어 스냅샷 (v4, D-016)"
    )
    p_apple.add_argument("--storefront", required=True, help="Apple storefront 코드 (kr, jp, us…)")
    p_apple.add_argument("--store", required=True, help="snapshot store directory")
    p_apple.add_argument("--limit", type=int, default=100, help="상위 N곡 (최대 100)")
    p_apple.set_defaults(func=cmd_collect_apple)

    p_melon = sub.add_parser(
        "convert-melon", help="멜론 공식 MCP 차트 응답 파일들 → 스토어 스냅샷 (v4.2, D-017)"
    )
    p_melon.add_argument("pages", nargs="+", help="get_music_chart 응답 저장 파일(들) — 페이지네이션 병합")
    p_melon.add_argument("--store", required=True, help="snapshot store directory (chart/melon/kr)")
    p_melon.add_argument("--date", required=True, help="차트 일자 YYYY-MM-DD")
    p_melon.set_defaults(func=cmd_convert_melon)

    p_enrich = sub.add_parser("enrich", help="snapshot → MusicBrainz entity map (v3, live)")
    p_enrich.add_argument("input", help="path to a chart snapshot .html")
    p_enrich.add_argument("-o", "--output", required=True, help="output entity map .json")
    p_enrich.add_argument("--top", type=int, default=50, help="resolve top-N unique artists")
    p_enrich.add_argument("--min-score", type=int, default=90, help="min MusicBrainz match score")
    p_enrich.add_argument("--delay", type=float, default=1.1, help="seconds between requests (rate limit)")
    p_enrich.add_argument("--no-wiki", dest="wiki", action="store_false", help="disable Wikidata fallback")
    p_enrich.set_defaults(func=cmd_enrich, wiki=True)

    p_signals = sub.add_parser(
        "signals", help="dated snapshot store → chart-rank signal-series (signal-bridge 조인용)"
    )
    p_signals.add_argument("store", help="snapshot store directory (dated .html) or a single snapshot")
    p_signals.add_argument("-o", "--output", required=True, help="output signal-series .json path")
    p_signals.add_argument(
        "--entities", default=None, help="공유 entity-master JSON — 차트 아티스트 캐노니컬 (조인 키)"
    )
    p_signals.add_argument(
        "--watchlist",
        default=None,
        help="사용자 워치리스트 JSON — 팔로우 acts 별칭 병합·오버라이드 (진입 즉시 인식, D-013)",
    )
    p_signals.add_argument(
        "--reconstruct-days",
        type=int,
        default=0,
        help="회고 실증: 단일 라이브 스냅샷의 Days 필드로 진입일 역산, 이 길이(일)의 창으로 재구성 (0=끔, store 다일 모드)",
    )
    p_signals.set_defaults(func=cmd_signals)

    p_validate = sub.add_parser("validate", help="validate a report.json against report-schema")
    p_validate.add_argument("report", help="path to report.json")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))
