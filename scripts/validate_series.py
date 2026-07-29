"""signal-series gate — validate an inter-module time-series document.

Counterpart of validate_snapshot.py for the signal-series contract
(packages/signal-series/signal-series.schema.json; prose canon in
modules/signal-bridge/SPEC.md). Two layers:

  1. SCHEMA      — envelope conforms to signal-series.schema.json.
  2. CONSISTENCY — what JSON Schema cannot express:
                   every series array has len(dates) entries (a silent
                   length skew silently mis-joins in the bridge),
                   dates strictly ascending, roster covers series keys.

    python scripts/validate_series.py <series.json> [...]

Exit: 0 = clean, 1 = invalid, 2 = unchecked (no schema/jsonschema).
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any, cast


def find_schema() -> Path | None:
    rel = Path("packages") / "signal-series" / "signal-series.schema.json"
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        node = base
        for _ in range(8):
            if (node / rel).exists():
                return node / rel
            if node.parent == node:
                break
            node = node.parent
    return None


def _schema_errors(doc: dict[str, object]) -> tuple[bool, list[str]]:
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
        for e in Draft202012Validator(schema).iter_errors(cast(Any, doc))
    ]
    return (True, errors)


def _consistency_errors(doc: dict[str, object]) -> list[str]:
    errors: list[str] = []
    dates = doc.get("dates")
    series = doc.get("series")
    roster = doc.get("roster")
    dates = dates if isinstance(dates, list) else []
    series = series if isinstance(series, dict) else {}
    roster = roster if isinstance(roster, dict) else {}

    for key, values in series.items():
        if isinstance(values, list) and len(values) != len(dates):
            errors.append(f"series[{key!r}]: {len(values)} value(s) != {len(dates)} date(s)")
    str_dates = [d for d in dates if isinstance(d, str)]
    if any(a >= b for a, b in pairwise(str_dates)):
        errors.append("dates: not strictly ascending")
    missing = sorted(set(series) - set(roster))
    if missing:
        errors.append(f"roster: missing {len(missing)} series key(s), e.g. {missing[:3]}")
    return errors


def validate_file(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print(f"{path}: REJECT — top-level is not an object", file=sys.stderr)
        return 1

    checked, errors = _schema_errors(doc)
    if not checked:
        print(f"{path}: SCHEMA UNCHECKED (jsonschema/schema not found)")
        return 2
    errors += _consistency_errors(doc)
    if errors:
        print(f"{path}: INVALID ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    prov = doc.get("provenance")
    prov = cast("dict[str, object]", prov if isinstance(prov, dict) else {})
    series = doc.get("series")
    n_keys = len(series) if isinstance(series, dict) else 0
    dates = doc.get("dates")
    n_dates = len(dates) if isinstance(dates, list) else 0
    print(
        f"{path}: OK — signal={doc.get('signal')} | {n_keys} key(s) x {n_dates} date(s)"
        f" | window={prov.get('window', '?')}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_series", description="signal-series contract gate"
    )
    parser.add_argument("series", nargs="+", help="path(s) to signal-series JSON")
    args = parser.parse_args(argv)
    results = [validate_file(Path(p)) for p in args.series]
    return max(results)


if __name__ == "__main__":
    raise SystemExit(main())
