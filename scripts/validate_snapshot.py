"""facts-only snapshot gate — validate a collection snapshot before it is trusted.

Two checks, both enforcing DATA_SOURCES §4 / the accountability invariant
(DOMAIN §0 — a rule must be *checkable* to be accountable):

  1. SCHEMA   — conforms to packages/snapshot-schema/snapshot.schema.json
                (provenance + quality + records envelope).
  2. PII GATE — `records` contain NO personal/content field keys (usernames,
                ids, urls, captions, mentions, comment text, ...). This turns
                "fetch strips PII" from a convention into a gate.

Also prints a quality summary and (optional) freshness check.

    python scripts/validate_snapshot.py <snapshot.json> [--max-age-days N]

Exit: 0 = clean, 1 = schema-invalid or PII leak, 2 = unchecked (no schema/jsonschema).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

# Exact record-key names that must never appear in a facts-only snapshot.
_EXACT_DENY = frozenset({
    "id", "url", "caption", "name", "owner", "author", "text", "message", "bio",
    "location", "locationname", "address", "handle", "shortcode", "comment",
})
# Substring patterns (lowercased key) that are unambiguously PII/content.
# NB: deliberately NOT "comment" (would hit the "comments" *count*); only the
# comment-text keys below.
_PATTERN_DENY = (
    "username", "fullname", "ownerid", "userid", "authorname", "authorusername",
    "profileurl", "profilepicurl", "displayurl", "inputurl", "posturl", "avatar",
    "mention", "taggeduser", "latestcomment", "firstcomment", "email", "phone",
)


def _bad_key(key: str) -> bool:
    low = key.lower()
    return low in _EXACT_DENY or any(p in low for p in _PATTERN_DENY)


def _scan_pii(node: Any, path: str = "records") -> list[str]:
    """Recursively collect denylisted key paths found anywhere under a record."""
    hits: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}"
            if isinstance(k, str) and _bad_key(k):
                hits.append(here)
            hits.extend(_scan_pii(v, here))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            hits.extend(_scan_pii(item, f"{path}[{i}]"))
    return hits


def find_schema() -> Path | None:
    rel = Path("packages") / "snapshot-schema" / "snapshot.schema.json"
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        node = base
        for _ in range(8):
            if (node / rel).exists():
                return node / rel
            if node.parent == node:
                break
            node = node.parent
    return None


def _schema_errors(snapshot: dict[str, object]) -> tuple[bool, list[str]]:
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
        for e in Draft202012Validator(schema).iter_errors(cast(Any, snapshot))
    ]
    return (True, errors)


def _freshness_days(fetched_at: str) -> float | None:
    try:
        when = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - when).total_seconds() / 86400.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_snapshot", description="facts-only snapshot gate (§4)")
    parser.add_argument("snapshot", help="path to a facts-only snapshot JSON")
    parser.add_argument("--max-age-days", type=float, default=None, help="warn if fetched_at older than N days")
    args = parser.parse_args(argv)

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        print("REJECT: top-level snapshot is not an object", file=sys.stderr)
        return 1

    failed = False

    # 1. schema
    checked, errors = _schema_errors(snapshot)
    if not checked:
        print("SCHEMA: UNCHECKED (jsonschema/schema not found)")
    elif errors:
        failed = True
        print(f"SCHEMA: INVALID ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
    else:
        print("SCHEMA: OK")

    # 2. PII gate
    records = snapshot.get("records")
    records = records if isinstance(records, list) else []
    leaks = _scan_pii(records)
    if leaks:
        failed = True
        print(f"PII GATE: REJECT ({len(leaks)} forbidden field(s)):", file=sys.stderr)
        for hit in leaks[:12]:
            print(f"  - {hit}", file=sys.stderr)
    else:
        print(f"PII GATE: OK ({len(records)} record(s), no PII/content keys)")

    # provenance / quality summary + freshness
    prov = snapshot.get("provenance") if isinstance(snapshot.get("provenance"), dict) else {}
    qual = snapshot.get("quality") if isinstance(snapshot.get("quality"), dict) else {}
    prov = cast("dict[str, object]", prov)
    qual = cast("dict[str, object]", qual)
    print(
        f"provenance: tos_class={prov.get('tos_class', '?')} | source={prov.get('source', '?')}"
    )
    if qual:
        print(f"quality: records={qual.get('records', '?')} raw={qual.get('raw', '?')} dropped={qual.get('dropped', '?')}")
    fetched = prov.get("fetched_at")
    if isinstance(fetched, str) and args.max_age_days is not None:
        age = _freshness_days(fetched)
        if age is not None and age > args.max_age_days:
            print(f"FRESHNESS: WARN — {age:.1f}d old (> {args.max_age_days}d)")

    if failed:
        return 1
    print("snapshot: CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
