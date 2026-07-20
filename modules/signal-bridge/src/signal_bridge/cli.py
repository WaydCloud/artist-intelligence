"""signal-bridge CLI.

    python -m signal_bridge analyze --social <social.json> --chart <chart.json> -o <outdir>
    python -m signal_bridge validate <report.json>

`analyze` (offline, deterministic) joins two signal-series (fandom-pulse `signals` ×
chart-history `signals`) → schema-valid report.json. No network — the source modules
own collection; this bridge only joins their emitted *data* (D-007/D-010).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from signal_bridge.bridge import build_report, load_series, load_watchlist, now_iso


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


def cmd_analyze(args: argparse.Namespace) -> int:
    social = load_series(args.social)
    chart = load_series(args.chart)
    if social.get("signal") != "social-buzz":
        print(f"--social expects signal 'social-buzz', got {social.get('signal')!r}", file=sys.stderr)
        return 1
    if chart.get("signal") != "chart-rank":
        print(f"--chart expects signal 'chart-rank', got {chart.get('signal')!r}", file=sys.stderr)
        return 1
    youtube = None
    if args.youtube:
        youtube = load_series(args.youtube)
        if youtube.get("signal") != "yt-velocity":
            print(f"--youtube expects signal 'yt-velocity', got {youtube.get('signal')!r}", file=sys.stderr)
            return 1

    report = build_report(
        social,
        chart,
        generated_at=now_iso(),
        theta_social=args.theta_social,
        theta_rank=args.theta_rank,
        focus_social=args.focus_social,
        watchlist=load_watchlist(args.watchlist),
        youtube=youtube,
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
    n_charts = len(cast(list[object], report["charts"]))
    print(f"wrote {out} | {n_charts} charts | schema {status}")
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
        prog="signal_bridge", description="Join social-buzz × chart-rank signal-series → lead/lag"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="two signal-series → schema-valid report.json")
    p_analyze.add_argument("--social", required=True, help="social-buzz signal-series JSON (fandom-pulse signals)")
    p_analyze.add_argument("--chart", required=True, help="chart-rank signal-series JSON (chart-history signals)")
    p_analyze.add_argument("-o", "--output", required=True, help="output directory for report.json")
    p_analyze.add_argument(
        "--theta-social", type=int, default=1, help="소셜 온셋 임계 — 일간 게시수 이상 (기준 원장 §3, 기본 1)"
    )
    p_analyze.add_argument(
        "--theta-rank", type=int, default=50, help="차트 온셋 임계 — 이 순위 이하 진입 (기준 원장 §3, 기본 50)"
    )
    p_analyze.add_argument(
        "--focus-social",
        action="store_true",
        help="소셜 버즈 있는 아티스트만 (버즈 없는 차트-온리 곡 제외) — 선행 질문에 집중",
    )
    p_analyze.add_argument(
        "--watchlist",
        default=None,
        help="사용자 워치리스트 JSON — 커버리지 지표 + 팀별 프로필(누가·얼마나·왜·활용) 산출 (D-013)",
    )
    p_analyze.add_argument(
        "--youtube",
        default=None,
        help="yt-velocity signal-series (yt-pulse signals) — 프로필에 구독·velocity '얼마나' 레이어 (D-014)",
    )
    p_analyze.set_defaults(func=cmd_analyze)

    p_validate = sub.add_parser("validate", help="validate a report.json against report-schema")
    p_validate.add_argument("report", help="path to report.json")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))
