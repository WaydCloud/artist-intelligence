"""cohort-size CLI: build the facts fixture, analyze it, check itself.

Purpose    `build` reads planning repo RAW once. `analyze` reads only the committed fixture and writes
           report.json (dashboard) plus analysis.json (every table and test, for tracing a number back).
Boundary   No network. `analyze` never touches the planning repo, so CI can run it.
Invariant  Thresholds that change what the screen says are flags here, with the ledger defaults.
Failure    A schema-invalid report is not written. The command exits 1 and lists the errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from cohort_size import analyze as an
from cohort_size import build as bd
from cohort_size.report import build_report

DEFAULT_FACTS = "data/research/cohort-size/facts.json"


def find_schema() -> Path | None:
    rel = Path("packages/report-schema/report.schema.json")
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
    errors = [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(cast(Any, report))]
    return (True, errors)


def _eras(text: str) -> tuple[tuple[int, int], ...]:
    out = []
    for part in text.split(","):
        lo, _, hi = part.strip().partition("-")
        out.append((int(lo), int(hi or lo)))
    return tuple(out)


def config_from(args: argparse.Namespace) -> an.Config:
    cuts = tuple(int(x) for x in args.bucket_cuts.split(","))
    if list(cuts) != sorted(set(cuts)):
        raise SystemExit("--bucket-cuts must be strictly increasing")
    return an.Config(
        window=args.window, cuts=cuts, eras=_eras(args.eras), first_year=args.first_year,
        last_year=args.last_year, include_incomplete=args.include_incomplete, exact_b=args.exact_b,
        seed=args.seed, alpha=args.alpha, trend_scores=args.trend_scores,
        focus_size=args.focus_size, impute_runs=args.impute_runs,
    )


def cmd_build(args: argparse.Namespace) -> int:
    fixture = bd.build(Path(args.raw))
    out = Path(args.output)
    bd.write(fixture, out)
    if args.check_sizes:
        import csv

        with open(args.check_sizes, encoding="utf-8") as f:
            ref = [r for r in csv.DictReader(f) if int(r["year"]) in (2022, 2023, 2024)]
        mine = bd.sizes_rows(fixture, (2022, 2023, 2024))
        same = mine == ref
        print(f"sizes 2022-2024 vs {args.check_sizes}: {'identical' if same else 'DIFFERENT'} ({len(mine)} rows)")
        if not same:
            return 1
    print(f"wrote {out} · groups {len(fixture['groups'])} · win gaps {len(fixture['coverage']['gaps'])}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    fixture = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    analysis = an.analyze(fixture, config_from(args))
    report = build_report(analysis)
    checked, errors = validate_report(report)
    if errors:
        print(f"report is schema-INVALID ({len(errors)} error(s)), not writing:", file=sys.stderr)
        for err in errors:
            print(f"  * {err}", file=sys.stderr)
        return 1
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (outdir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.print_matches:
        for g in analysis["successes"]:
            print(g["year"], g["title"], f"n={g['size']}", f"win={g['winYears']}", f"melon={g['melonYears']}",
                  f"circle={g['circleYears']}", f"spotify={g['spotify']}")
    t = analysis["pooled"]["default"]["measures"]["any"]["test"]
    status = "valid" if checked else "UNCHECKED (jsonschema/schema not found)"
    print(f"wrote {outdir / 'report.json'} | teams {t['n']} · success {t['k']} | schema {status}")
    return 0


def cmd_selftest(_args: argparse.Namespace) -> int:
    from cohort_size.selftest import run

    return run()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cohort_size", description="debut lineup size versus success (offline)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build", help="planning repo RAW -> facts fixture (run once, by hand)")
    p_b.add_argument("raw", help="path to the planning repo data/references directory")
    p_b.add_argument("-o", "--output", default=DEFAULT_FACTS)
    p_b.add_argument("--check-sizes", default=None,
                     help="planning sizes.csv: fail unless the 2022-2024 rows are reproduced exactly")
    p_b.set_defaults(func=cmd_build)

    p_a = sub.add_parser("analyze", help="facts fixture -> report.json + analysis.json")
    p_a.add_argument("--facts", default=DEFAULT_FACTS)
    p_a.add_argument("-o", "--output", required=True)
    # Load-bearing thresholds (RULES ledger). Values belong to the domain owner.
    p_a.add_argument("--window", type=int, default=3, help="observation window in calendar years from debut year")
    p_a.add_argument("--bucket-cuts", default="3,4,5,6",
                     help="upper bounds of all buckets but the last (default: <=3, 4, 5, 6, 7+)")
    p_a.add_argument("--eras", default="2012-2014,2015-2017,2018-2020,2021-2023")
    p_a.add_argument("--first-year", type=int, default=2012)
    p_a.add_argument("--last-year", type=int, default=2024)
    p_a.add_argument("--include-incomplete", action="store_true",
                     help="also test cohorts whose window is not closed yet")
    p_a.add_argument("--exact-b", type=int, default=20000, help="Monte Carlo permutations for the exact test")
    p_a.add_argument("--seed", type=int, default=20261020)
    p_a.add_argument("--alpha", type=float, default=0.05, help="level that switches the inference wording")
    p_a.add_argument("--trend-scores", choices=("ordinal", "median"), default="ordinal")
    p_a.add_argument("--focus-size", type=int, default=5, help="lineup size tracked in the era share chart")
    p_a.add_argument("--impute-runs", type=int, default=20, help="seeds per random scheme for undetermined sizes")
    p_a.add_argument("--print-matches", action="store_true")
    p_a.set_defaults(func=cmd_analyze)

    p_s = sub.add_parser("selftest", help="offline self-check (TESTS.md)")
    p_s.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
