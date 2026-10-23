"""Verify the pre-registered dreamcore rule against its answer sheet (D-064).

Purpose    Hit rate on positives, false-positive rate on negatives, and the share of the KR
           daily cohort the rule matches, all at the pre-registered thresholds.
Boundary   Read only. Never edits data/live. The rule and the pass criteria come from
           genre-impulse RULES §2.1.4 and docs/DRAFT-dreamcore-answer-sheet.md §3; this script
           does not choose them.
Invariant  Percentiles use genre-impulse `_percentile` (share-or-below). A second copy would let
           this check and the daily monitor measure different positions.
Failure    A record without both rule axes is reported as not evaluable, never as a non-match.

Usage:

    python scripts/dreamcore_sheet_verify.py \
        --sheet data/research/genre-impulse/dreamcore/sheet_features.json \
        --sonic C:/Projects/artist-intelligence/data/live/sonic \
        -o data/research/genre-impulse/dreamcore/verify.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "modules" / "genre-impulse" / "src"))
from genre_impulse.cli import (
    _percentile,  # type: ignore[import-not-found]
)

# Pre-registered (RULES §2.1.4). Both axes must sit at or below P_low.
RULE_LOW_ALL = ["percussive_ratio", "brightness_hz"]
# Exploration only (answer-sheet doc §3). Recorded, never part of the verdict.
EXPLORE = ["onset_rate", "spectral_flux", "tempo_bpm", "high_energy_ratio"]


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _is_chart(r: dict[str, Any]) -> bool:
    return r.get("cohort") == "chart" or r.get("chart_rank") is not None


def _snapshots(sonic: Path, start: str, end: str | None) -> list[Path]:
    days = sorted(p for p in sonic.glob("????-??-??.json") if p.stem >= start)
    return [p for p in days if end is None or p.stem <= end]


def _match(pcts: dict[str, float], low_pct: float) -> bool | None:
    if any(ax not in pcts for ax in RULE_LOW_ALL):
        return None
    return all(pcts[ax] <= low_pct for ax in RULE_LOW_ALL)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sheet", required=True, help="sheet_features.json")
    ap.add_argument("--answer-sheet", required=True, help="answer_sheet.json (source grades)")
    ap.add_argument("--sonic", required=True, help="daily sonic snapshots (read only)")
    ap.add_argument("--start", default="2026-07-28")
    ap.add_argument("--end", default=None)
    ap.add_argument("--low-pct", type=float, default=20.0, help="P_low (shared genre-impulse knob)")
    ap.add_argument("--min-day-n", type=int, default=30, help="days with fewer resolved chart tracks are skipped")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args(argv)

    days = _snapshots(Path(args.sonic), args.start, args.end)
    # Reference pool: unique KR chart recordings over the window, latest observation wins.
    pool_rec: dict[str, dict[str, Any]] = {}
    daily: list[dict[str, Any]] = []
    for p in days:
        doc = json.loads(p.read_text(encoding="utf-8"))
        recs = [r for r in doc.get("records") or [] if isinstance(r.get("features"), dict)]
        for r in recs:
            if _is_chart(r):
                pool_rec[f"{r.get('source')}:{r.get('track_id')}"] = r
        for frame, members in (("chart", [r for r in recs if _is_chart(r)]), ("module", recs)):
            vals = {ax: [v for r in members if (v := _num(r["features"].get(ax))) is not None] for ax in RULE_LOW_ALL}
            n_chart = sum(1 for r in recs if _is_chart(r))
            row: dict[str, Any] = {"date": p.stem, "frame": frame, "n": len(members), "n_chart": n_chart}
            if n_chart < args.min_day_n:
                row["skipped"] = f"resolved chart tracks {n_chart} < {args.min_day_n}"
                daily.append(row)
                continue
            hits, evaluable, matched = 0, 0, []
            for r in members:
                pcts = {ax: _percentile(vals[ax], v) for ax in RULE_LOW_ALL if (v := _num(r["features"].get(ax))) is not None}
                m = _match(pcts, args.low_pct)
                if m is None:
                    continue
                evaluable += 1
                if m:
                    hits += 1
                    matched.append(f"{r.get('source')}:{r.get('track_id')}|{r.get('artist')} - {r.get('title')}")
            row.update({"evaluable": evaluable, "matched": hits, "matched_tracks": matched})
            daily.append(row)

    pool = {ax: sorted(v for r in pool_rec.values() if (v := _num(r["features"].get(ax))) is not None)
            for ax in [*RULE_LOW_ALL, *EXPLORE]}

    sheet = json.loads(Path(args.sheet).read_text(encoding="utf-8"))
    answer = json.loads(Path(args.answer_sheet).read_text(encoding="utf-8"))
    grades = {k: str(v.get("grade")) for k, v in (answer.get("sources") or {}).items()}
    rows: list[dict[str, Any]] = []
    for r in sheet.get("records") or []:
        row: dict[str, Any] = {k: r.get(k) for k in ("role", "sheet_source", "sheet_artist", "sheet_title", "artist", "title", "release_date")}
        row["preview_source"] = r.get("source")
        row["grade"] = grades.get(str(r.get("sheet_source")))
        f = r.get("features")
        if not isinstance(f, dict):
            row["unresolved"] = r.get("unresolved")
            rows.append(row)
            continue
        pcts = {ax: _percentile(pool[ax], v) for ax in [*RULE_LOW_ALL, *EXPLORE] if (v := _num(f.get(ax))) is not None}
        row["pcts"] = pcts
        row["match"] = _match(pcts, args.low_pct)
        rows.append(row)

    def _rate(role: str, pred: Any = None) -> dict[str, Any]:
        sel = [x for x in rows if x["role"] == role and x.get("match") is not None and (pred is None or pred(x))]
        k = sum(1 for x in sel if x["match"])
        return {"matched": k, "measured": len(sel), "rate": round(k / len(sel), 3) if sel else None}

    def _year(x: dict[str, Any]) -> int | None:
        d = str(x.get("release_date") or "")
        return int(d[:4]) if d[:4].isdigit() else None

    summary: dict[str, Any] = {
        "low_pct": args.low_pct,
        "positives": _rate("positive"),
        "negatives": _rate("negative"),
        "positives_grade_mid_or_above": _rate("positive", lambda x: x.get("grade") in ("중간", "높음", "매우 높음")),
        "positives_release_lt_2015": _rate("positive", lambda x: (_year(x) or 9999) < 2015),
        "positives_release_ge_2015": _rate("positive", lambda x: (_year(x) or 0) >= 2015),
        "positives_release_unknown": _rate("positive", lambda x: _year(x) is None),
        "reference_pool": {"window": [days[0].stem if days else None, days[-1].stem if days else None],
                           "snapshots": len(days), "unique_chart_recordings": len(pool_rec),
                           "n_per_axis": {ax: len(v) for ax, v in pool.items()}},
        "explore_median_pct": {
            role: {ax: (statistics.median(ps) if (ps := [x["pcts"][ax] for x in rows if x["role"] == role and ax in (x.get("pcts") or {})]) else None)
                   for ax in [*RULE_LOW_ALL, *EXPLORE]}
            for role in ("positive", "negative")
        },
    }
    for frame in ("chart", "module"):
        used = [d for d in daily if d["frame"] == frame and "skipped" not in d]
        ev = sum(d["evaluable"] for d in used)
        hit = sum(d["matched"] for d in used)
        uniq_seen: set[str] = set()
        uniq_hit: set[str] = set()
        for d in used:
            uniq_hit.update(t.split("|")[0] for t in d["matched_tracks"])
        for p in days:
            if any(d["date"] == p.stem for d in used):
                doc = json.loads(p.read_text(encoding="utf-8"))
                for r in doc.get("records") or []:
                    if isinstance(r.get("features"), dict) and (frame == "module" or _is_chart(r)):
                        uniq_seen.add(f"{r.get('source')}:{r.get('track_id')}")
        rates = [d["matched"] / d["evaluable"] for d in used if d["evaluable"]]
        summary[f"cohort_share_{frame}"] = {
            "days_used": len(used), "days_skipped": sum(1 for d in daily if d["frame"] == frame and "skipped" in d),
            "track_days_matched": hit, "track_days_evaluable": ev,
            "share": round(hit / ev, 4) if ev else None,
            "daily_share_min": round(min(rates), 4) if rates else None,
            "daily_share_median": round(statistics.median(rates), 4) if rates else None,
            "daily_share_max": round(max(rates), 4) if rates else None,
            "unique_recordings_matched": len(uniq_hit), "unique_recordings_seen": len(uniq_seen),
        }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "sheet": rows, "daily": daily}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
