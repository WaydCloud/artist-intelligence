"""Merge accumulated daily IG social snapshots → one deduped snapshot for `signals`.

Forward experiment (D-012 후속): daily `fandom-pulse fetch` returns *recent* posts, so
consecutive days overlap. Facts-only records carry no post ID (PII stripped, §4), so we
dedup by a stable fingerprint (timestamp + sound + hashtags), keeping the highest-
engagement copy (engagement grows over time). Deterministic (sorted). No network.

    python scripts/merge_social.py <social_dir> <out.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _fingerprint(rec: dict[str, object]) -> tuple[str, str, tuple[str, ...]]:
    tags = rec.get("hashtags")
    tags_t = tuple(sorted(str(h) for h in tags)) if isinstance(tags, list) else ()
    return (str(rec.get("timestamp") or ""), str(rec.get("music") or ""), tags_t)


def _engagement(rec: dict[str, object]) -> int:
    def _i(v: object) -> int:
        return v if isinstance(v, int) and not isinstance(v, bool) else 0

    return _i(rec.get("likes")) + _i(rec.get("comments"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: merge_social.py <social_dir> <out.json>", file=sys.stderr)
        return 2
    src = Path(argv[0])
    files = sorted(src.glob("*.json")) if src.is_dir() else [src]
    best: dict[tuple[str, str, tuple[str, ...]], dict[str, object]] = {}
    prov: dict[str, object] = {}
    tags: set[str] = set()
    raw = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        records = doc.get("records") if isinstance(doc, dict) else (doc if isinstance(doc, list) else [])
        if isinstance(doc, dict):
            p = doc.get("provenance")
            if isinstance(p, dict):
                if not prov:
                    prov = p
                params = p.get("params")
                if isinstance(params, dict) and isinstance(params.get("hashtag"), str):
                    tags.add(params["hashtag"])
        for rec in records or []:
            if not isinstance(rec, dict):
                continue
            raw += 1
            fp = _fingerprint(rec)
            if fp not in best or _engagement(rec) > _engagement(best[fp]):
                best[fp] = rec
    merged = sorted(best.values(), key=lambda r: (str(r.get("timestamp") or ""), _fingerprint(r)))
    tag_list = sorted(tags)
    prov_out = {**prov, "note": f"merged+deduped from {len(files)} daily snapshot(s) (forward)"}
    if tag_list:  # 다중 태그 수집(D-013) — 시리즈 라벨·프로버넌스에 소스 태그 전파
        params = prov_out.get("params")
        prov_out["params"] = {
            **(params if isinstance(params, dict) else {}),
            "hashtag": ",".join(tag_list),
            "hashtags": tag_list,
        }
    out_doc = {
        "provenance": prov_out,
        "quality": {"records": len(merged), "raw": raw, "dropped": raw - len(merged), "notes": ["dedup by (timestamp,music,hashtags)"]},
        "records": merged,
    }
    Path(argv[1]).write_text(json.dumps(out_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {raw} → {len(merged)} unique records from {len(files)} file(s) → {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
