"""fandom-pulse CLI.

    python -m fandom_pulse analyze <snapshot.json ...> -o <outdir>
    python -m fandom_pulse fetch --hashtag <tag> -o <snapshot.json>
    python -m fandom_pulse validate <report.json>

`analyze` (offline, deterministic) is the smoke path; `fetch` is the live
collector (Apify, pay-per-result) that strips to facts-only before writing
(RULES §1/§2, DATA_SOURCES §4).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from fandom_pulse import apify, entities, normalize
from fandom_pulse.report import build_report, build_signal_series, now_iso


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


def _load_snapshot(path: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Accept a snapshot-schema {provenance, quality, records} doc or a bare records array."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return ([r for r in doc if isinstance(r, dict)], {})
    records = doc.get("records") if isinstance(doc, dict) else None
    prov = doc.get("provenance") if isinstance(doc, dict) else None
    return (
        [r for r in records if isinstance(r, dict)] if isinstance(records, list) else [],
        prov if isinstance(prov, dict) else {},
    )


def cmd_analyze(args: argparse.Namespace) -> int:
    records: list[dict[str, object]] = []
    provenance: dict[str, object] = {}
    for path in args.input:
        recs, prov = _load_snapshot(path)
        records.extend(recs)
        if not provenance:
            provenance = prov

    params_obj = provenance.get("params")
    params = params_obj if isinstance(params_obj, dict) else {}
    report = build_report(
        records,
        hashtag=args.hashtag or str(params.get("hashtag") or ""),
        provenance=provenance,
        generated_at=now_iso(),
        high_pct=args.high_pct,
        momentum_min_days=args.momentum_min_days,
        top_tags=args.top_tags,
        top_sounds=args.top_sounds,
        entity_index=entities.load_index(args.entities, args.watchlist),
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
    status = "valid" if checked else "UNCHECKED (jsonschema/schema not found)"
    print(f"wrote {out} | {len(records)} posts | schema {status}")
    return 0


def _snapshot_doc(
    records: list[dict[str, object]], fetched_at: str, raw_count: int, params: dict[str, object]
) -> dict[str, object]:
    """Wrap facts-only records in the shared snapshot contract (packages/snapshot-schema)."""
    return {
        "provenance": {
            "source": "Instagram / Apify apify~instagram-hashtag-scraper",
            "tool": "fandom-pulse.fetch",
            "tool_version": "0.1.0",
            "fetched_at": fetched_at,
            "license": "public-metrics",
            "tos_class": "managed-scraper",
            "params": params,
            "pii_policy": "facts-only: PII·원문 fetch 단계 폐기(§4)",
        },
        "quality": {
            "records": len(records),
            "raw": raw_count,
            "dropped": raw_count - len(records),
            "notes": [],
        },
        "records": records,
    }


def cmd_fetch(args: argparse.Namespace) -> int:
    raw = apify.fetch_hashtag(
        args.hashtag,
        results_type=args.results_type,
        results_limit=args.max_items,
        max_items=args.max_items,
        max_usd=args.max_usd,
        timeout=args.timeout,
    )
    records = [normalize.to_record(item) for item in raw]  # strip PII/content BEFORE writing (§4)
    params: dict[str, object] = {
        "hashtag": args.hashtag.lstrip("#"),
        "resultsType": args.results_type,
        "maxItems": args.max_items,
    }
    doc = _snapshot_doc(records, now_iso(), len(raw), params)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tag = args.hashtag.lstrip("#")
    print(f"wrote {out} | {len(records)} facts-only records (raw {len(raw)}) | #{tag}")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    """Emit a per-(date × artist) social-buzz signal-series for signal-bridge (data-only join)."""
    records: list[dict[str, object]] = []
    provenance: dict[str, object] = {}
    for path in args.input:
        recs, prov = _load_snapshot(path)
        records.extend(recs)
        if not provenance:
            provenance = prov
    params_obj = provenance.get("params")
    params = params_obj if isinstance(params_obj, dict) else {}
    series = build_signal_series(
        records,
        entity_index=entities.load_index(args.entities, args.watchlist),
        generated_at=now_iso(),
        hashtag=args.hashtag or str(params.get("hashtag") or ""),
        hashtag_index=entities.load_hashtag_index(args.watchlist),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(series, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artists = cast(dict[str, object], series["series"])
    dates = cast(list[str], series["dates"])
    print(f"wrote {out} | {len(artists)} artists × {len(dates)} days | social-buzz series")
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
    parser = argparse.ArgumentParser(
        prog="fandom_pulse", description="Public IG hashtag pulse — facts-only signal report"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="facts-only snapshot(s) → schema-valid report.json")
    p_analyze.add_argument("input", nargs="+", help="facts-only snapshot JSON(s)")
    p_analyze.add_argument("-o", "--output", required=True, help="output directory for report.json")
    p_analyze.add_argument("--hashtag", default=None, help="override hashtag label")
    p_analyze.add_argument("--high-pct", type=float, default=90.0, help="고참여 임계 분위 (기준 원장, 기본 90)")
    p_analyze.add_argument("--momentum-min-days", type=int, default=2, help="게시 가속 산출 최소 일수 (기본 2)")
    p_analyze.add_argument("--top-tags", type=int, default=10, help="공동 해시태그 상위 N (기본 10)")
    p_analyze.add_argument("--top-sounds", type=int, default=8, help="사운드 상위 N (기본 8)")
    p_analyze.add_argument(
        "--entities", default=None, help="공유 entity-master JSON — 사운드→아티스트 조인·로스터 대조(선행신호)"
    )
    p_analyze.add_argument(
        "--watchlist", default=None, help="사용자 워치리스트 JSON — 팔로우 acts 병합·오버라이드 (D-013)"
    )
    p_analyze.set_defaults(func=cmd_analyze)

    p_fetch = sub.add_parser("fetch", help="live Apify collect → facts-only snapshot (pay-per-result)")
    p_fetch.add_argument("--hashtag", required=True, help="hashtag (with/without #)")
    p_fetch.add_argument("-o", "--output", required=True, help="output snapshot .json path")
    p_fetch.add_argument("--results-type", default="posts", choices=["posts", "reels"], help="posts or reels")
    p_fetch.add_argument("--max-items", type=int, default=30, help="cap billable items (maxItems)")
    p_fetch.add_argument("--max-usd", type=float, default=0.10, help="cap total cost USD (maxTotalChargeUsd)")
    p_fetch.add_argument("--timeout", type=int, default=180, help="Actor run timeout seconds")
    p_fetch.set_defaults(func=cmd_fetch)

    p_signals = sub.add_parser(
        "signals", help="facts-only snapshot(s) → social-buzz signal-series (signal-bridge 조인용)"
    )
    p_signals.add_argument("input", nargs="+", help="facts-only snapshot JSON(s)")
    p_signals.add_argument("-o", "--output", required=True, help="output signal-series .json path")
    p_signals.add_argument("--hashtag", default=None, help="override hashtag label")
    p_signals.add_argument(
        "--entities", default=None, help="공유 entity-master JSON — 사운드→아티스트 캐노니컬 (조인 키)"
    )
    p_signals.add_argument(
        "--watchlist",
        default=None,
        help="사용자 워치리스트 JSON — acts 병합·오버라이드 + 해시태그 직접 귀속 (D-013)",
    )
    p_signals.set_defaults(func=cmd_signals)

    p_validate = sub.add_parser("validate", help="validate a report.json against report-schema")
    p_validate.add_argument("report", help="path to report.json")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))
