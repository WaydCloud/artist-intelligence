"""Verify a pre-registered genre-impulse rule against its answer sheet (D-064 dreamcore, D-065 alt z).

Purpose    Hit rate on positives, false-positive rate on negatives, and the share of the KR
           daily cohort the rule matches, all at the pre-registered thresholds.
Boundary   Read only. Never edits data/live. The rule and the pass criteria come from
           genre-impulse RULES §2.1.x and the answer-sheet doc; this script does not choose
           them. Run as a script it checks the dreamcore rule (RULES §2.1.4). Other sheets
           import the functions below (scripts/altz_sheet_verify.py).
Invariant  Percentiles use genre-impulse `_percentile` (share-or-below), and organic_ratio is
           derived with genre-impulse `_derive`. A second copy of either would let this check
           and the daily monitor measure different positions.
Failure    A record without every rule axis is reported as not evaluable, never as a non-match.

Usage:

    python scripts/dreamcore_sheet_verify.py data/research/genre-impulse/dreamcore \
        --sonic C:/Projects/artist-intelligence/data/live/sonic --end 2026-10-23

The directory holds answer_sheet.json and sheet_features.json, and verify.json is written
there. The older flags (--sheet, --answer-sheet, -o) still override each path.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "modules" / "genre-impulse" / "src"))
sys.path.insert(0, str(_root / "modules" / "sonic-profile" / "src"))
from genre_impulse.cli import (  # type: ignore[import-not-found]
    _derive,
    _percentile,
)

# Pre-registered (RULES §2.1.4). Both axes must sit at or below P_low.
RULE_LOW_ALL = ["percussive_ratio", "brightness_hz"]
# Exploration only (answer-sheet doc §3). Recorded, never part of the verdict.
EXPLORE = ["onset_rate", "spectral_flux", "tempo_bpm", "high_energy_ratio"]

# A rule is a list of (axis, direction). direction "low" means percentile <= low_pct,
# "high" means percentile >= high_pct. Every term must hold (AND).
Rule = Sequence[tuple[str, str]]
DREAMCORE_RULE: list[tuple[str, str]] = [(ax, "low") for ax in RULE_LOW_ALL]

GRADES_MID_OR_ABOVE = ("중간", "높음", "매우 높음")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def axis_values(features: dict[str, Any], axes: Sequence[str]) -> dict[str, float]:
    """Numeric value per axis. Axes absent from the stored features are derived, not guessed."""
    out = {ax: v for ax in axes if (v := _num(features.get(ax))) is not None}
    if len(out) < len(axes):
        # organic_ratio is not stored in snapshots (genre-impulse RULES §3). Deriving only
        # when an axis is missing keeps raw-axis checks free of the derived import.
        derived = _derive(features)
        out.update({ax: v for ax in axes if ax not in out and (v := _num(derived.get(ax))) is not None})
    return {ax: out[ax] for ax in axes if ax in out}


def _is_chart(r: dict[str, Any]) -> bool:
    return r.get("cohort") == "chart" or r.get("chart_rank") is not None


def _snapshots(sonic: Path, start: str, end: str | None) -> list[Path]:
    days = sorted(p for p in sonic.glob("????-??-??.json") if p.stem >= start)
    return [p for p in days if end is None or p.stem <= end]


def match(pcts: dict[str, float], rule: Rule, low_pct: float, high_pct: float) -> bool | None:
    if any(ax not in pcts for ax, _ in rule):
        return None
    return all(pcts[ax] <= low_pct if d == "low" else pcts[ax] >= high_pct for ax, d in rule)


def load_reference(sonic: Path, start: str, end: str | None) -> tuple[list[Path], dict[str, dict[str, Any]], list[tuple[str, list[dict[str, Any]]]]]:
    """Snapshots in the window, the unique KR chart recordings (latest observation wins),
    and each day's resolved records."""
    days = _snapshots(sonic, start, end)
    pool_rec: dict[str, dict[str, Any]] = {}
    per_day: list[tuple[str, list[dict[str, Any]]]] = []
    for p in days:
        doc = json.loads(p.read_text(encoding="utf-8"))
        recs = [r for r in doc.get("records") or [] if isinstance(r.get("features"), dict)]
        for r in recs:
            if _is_chart(r):
                pool_rec[f"{r.get('source')}:{r.get('track_id')}"] = r
        per_day.append((p.stem, recs))
    return days, pool_rec, per_day


def reference_pools(pool_rec: dict[str, dict[str, Any]], axes: Sequence[str]) -> dict[str, list[float]]:
    vals = [axis_values(r["features"], axes) for r in pool_rec.values()]
    return {ax: sorted(v[ax] for v in vals if ax in v) for ax in axes}


def daily_share(
    per_day: list[tuple[str, list[dict[str, Any]]]],
    rule: Rule,
    low_pct: float,
    high_pct: float,
    min_day_n: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Share of each day's cohort that the rule matches, with within-day percentiles."""
    axes = list(dict.fromkeys(ax for ax, _ in rule))
    daily: list[dict[str, Any]] = []
    for date, recs in per_day:
        values = [axis_values(r["features"], axes) for r in recs]
        for frame in ("chart", "module"):
            members = [(r, v) for r, v in zip(recs, values) if frame == "module" or _is_chart(r)]
            vals = {ax: [v[ax] for _, v in members if ax in v] for ax in axes}
            n_chart = sum(1 for r in recs if _is_chart(r))
            row: dict[str, Any] = {"date": date, "frame": frame, "n": len(members), "n_chart": n_chart}
            if n_chart < min_day_n:
                row["skipped"] = f"resolved chart tracks {n_chart} < {min_day_n}"
                daily.append(row)
                continue
            hits, evaluable, matched = 0, 0, []
            for r, v in members:
                pcts = {ax: _percentile(vals[ax], v[ax]) for ax in axes if ax in v}
                m = match(pcts, rule, low_pct, high_pct)
                if m is None:
                    continue
                evaluable += 1
                if m:
                    hits += 1
                    matched.append(f"{r.get('source')}:{r.get('track_id')}|{r.get('artist')} - {r.get('title')}")
            row.update({"evaluable": evaluable, "matched": hits, "matched_tracks": matched})
            daily.append(row)

    by_date = dict(per_day)
    summary: dict[str, dict[str, Any]] = {}
    for frame in ("chart", "module"):
        used = [d for d in daily if d["frame"] == frame and "skipped" not in d]
        ev = sum(d["evaluable"] for d in used)
        hit = sum(d["matched"] for d in used)
        uniq_seen: set[str] = set()
        uniq_hit: set[str] = set()
        for d in used:
            uniq_hit.update(t.split("|")[0] for t in d["matched_tracks"])
            for r in by_date[d["date"]]:
                if frame == "module" or _is_chart(r):
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
    return daily, summary


def sheet_rows(
    sheet: dict[str, Any],
    answer: dict[str, Any],
    pools: dict[str, list[float]],
    axes: Sequence[str],
    rule: Rule | None,
    low_pct: float,
    high_pct: float,
) -> list[dict[str, Any]]:
    """One row per answer-sheet recording: source grade, percentiles on `axes`, rule match."""
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
        vals = axis_values(f, axes)
        row["pcts"] = {ax: _percentile(pools[ax], vals[ax]) for ax in axes if ax in vals}
        if rule is not None:
            row["match"] = match(row["pcts"], rule, low_pct, high_pct)
        rows.append(row)
    return rows


def rate(rows: list[dict[str, Any]], role: str, pred: Callable[[dict[str, Any]], bool] | None = None) -> dict[str, Any]:
    sel = [x for x in rows if x["role"] == role and x.get("match") is not None and (pred is None or pred(x))]
    k = sum(1 for x in sel if x["match"])
    return {"matched": k, "measured": len(sel), "rate": round(k / len(sel), 3) if sel else None}


def release_year(x: dict[str, Any]) -> int | None:
    d = str(x.get("release_date") or "")
    return int(d[:4]) if d[:4].isdigit() else None


def median_pct(rows: list[dict[str, Any]], axes: Sequence[str]) -> dict[str, dict[str, float | None]]:
    return {
        role: {ax: (statistics.median(ps) if (ps := [x["pcts"][ax] for x in rows if x["role"] == role and ax in (x.get("pcts") or {})]) else None)
               for ax in axes}
        for role in ("positive", "negative")
    }


def _paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    base = Path(args.dir) if args.dir else None
    def pick(given: str | None, name: str) -> Path:
        if given:
            return Path(given)
        if base is None:
            raise SystemExit(f"give the sheet directory or --{name.split('.')[0].replace('_', '-')}")
        return base / name
    return pick(args.sheet, "sheet_features.json"), pick(args.answer_sheet, "answer_sheet.json"), pick(args.output, "verify.json")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("dir", nargs="?", help="sheet directory (answer_sheet.json, sheet_features.json, verify.json)")
    ap.add_argument("--sheet", help="sheet_features.json (overrides the directory)")
    ap.add_argument("--answer-sheet", help="answer_sheet.json with source grades (overrides the directory)")
    ap.add_argument("--sonic", required=True, help="daily sonic snapshots (read only)")
    ap.add_argument("--start", default="2026-07-28")
    ap.add_argument("--end", default=None)
    ap.add_argument("--low-pct", type=float, default=20.0, help="P_low (shared genre-impulse knob)")
    ap.add_argument("--min-day-n", type=int, default=30, help="days with fewer resolved chart tracks are skipped")
    ap.add_argument("-o", "--output", help="verify.json (overrides the directory)")
    args = ap.parse_args(argv)
    sheet_path, answer_path, out = _paths(args)

    rule = DREAMCORE_RULE
    axes = list(dict.fromkeys([*RULE_LOW_ALL, *EXPLORE]))
    days, pool_rec, per_day = load_reference(Path(args.sonic), args.start, args.end)
    daily, shares = daily_share(per_day, rule, args.low_pct, 100.0, args.min_day_n)
    pool = reference_pools(pool_rec, axes)

    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    rows = sheet_rows(sheet, answer, pool, axes, rule, args.low_pct, 100.0)

    summary: dict[str, Any] = {
        "low_pct": args.low_pct,
        "positives": rate(rows, "positive"),
        "negatives": rate(rows, "negative"),
        "positives_grade_mid_or_above": rate(rows, "positive", lambda x: x.get("grade") in GRADES_MID_OR_ABOVE),
        "positives_release_lt_2015": rate(rows, "positive", lambda x: (release_year(x) or 9999) < 2015),
        "positives_release_ge_2015": rate(rows, "positive", lambda x: (release_year(x) or 0) >= 2015),
        "positives_release_unknown": rate(rows, "positive", lambda x: release_year(x) is None),
        "reference_pool": {"window": [days[0].stem if days else None, days[-1].stem if days else None],
                           "snapshots": len(days), "unique_chart_recordings": len(pool_rec),
                           "n_per_axis": {ax: len(v) for ax, v in pool.items()}},
        "explore_median_pct": median_pct(rows, axes),
        **shares,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "sheet": rows, "daily": daily}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
