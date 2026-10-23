"""Discovery and holdout checks for the alt z answer sheet (D-065).

Purpose    Pick rule axes on the discovery positives, then test the frozen rule on the holdout.
Boundary   Read only on data/live. Writes discover.json or verify.json in the sheet directory.
           The split, the axis list, the thresholds and the pass criteria come from
           docs/DRAFT-altz-answer-sheet.md section 3; this script does not choose them.
           Reference pool, daily share and percentiles are imported from
           scripts/dreamcore_sheet_verify.py, so both sheets are measured the same way.
Invariant  `holdout` reads the rule and the window from discover.json and never re-picks axes.
           Picking axes after holdout percentiles are seen would make the test circular.
Failure    Unresolved recordings and missing axes are not evaluable, never non-matches.

Usage:

    python scripts/altz_sheet_verify.py discover data/research/genre-impulse/altz \
        --sonic C:/Projects/artist-intelligence/data/live/sonic
    python scripts/altz_sheet_verify.py holdout data/research/genre-impulse/altz \
        --sonic C:/Projects/artist-intelligence/data/live/sonic
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dreamcore_sheet_verify import (  # type: ignore[import-not-found]
    GRADES_MID_OR_ABOVE,
    axis_values,
    daily_share,
    load_reference,
    rate,
    reference_pools,
    release_year,
    sheet_rows,
)

# Pre-registered candidate axes: genre-impulse AXIS_LABELS at commit beeb7a9, in that order.
# Frozen here so a later change to AXIS_LABELS cannot change what this sheet was tested on.
CANDIDATE_AXES = [
    "organic_ratio", "spectral_flatness", "over_unity_ratio", "onset_rate_high", "silence_ratio",
    "swing_ratio", "tempo_bpm", "brightness_hz", "spectral_contrast_mean",
]
LOW_PCT = 20.0
HIGH_PCT = 80.0
MIN_SAME_TAIL = 10  # absolute count of measured discovery positives in one tail
MAX_AXES = 3
# Holdout pass criteria (draft section 3.4), same four as D-064.
HIT_MIN, NEG_MAX, BASE_MAX, MIN_MEASURED = 0.60, 0.10, 0.15, 10
NO_AXIS = "판별 축 없음"


def _key(artist: Any, title: Any) -> tuple[str, str]:
    return (str(artist), str(title))


def _load(sheet_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    answer = json.loads((sheet_dir / "answer_sheet.json").read_text(encoding="utf-8"))
    sheet = json.loads((sheet_dir / "sheet_features.json").read_text(encoding="utf-8"))
    by_key = {_key(t["artist"], t["title"]): t for t in answer.get("tracks") or []}
    return answer, sheet, by_key


def _rows(sheet: dict[str, Any], answer: dict[str, Any], by_key: dict[tuple[str, str], dict[str, Any]],
          pools: dict[str, list[float]], rule: list[tuple[str, str]] | None) -> list[dict[str, Any]]:
    rows = sheet_rows(sheet, answer, pools, CANDIDATE_AXES, rule, LOW_PCT, HIGH_PCT)
    for row in rows:
        t = by_key[_key(row["sheet_artist"], row["sheet_title"])]
        row["split"] = t.get("split")
        row["hmap"] = t.get("hmap")
    return rows


def cmd_discover(args: argparse.Namespace) -> int:
    sheet_dir = Path(args.dir)
    answer, sheet, by_key = _load(sheet_dir)
    days, pool_rec, _ = load_reference(Path(args.sonic), args.start, args.end)
    pools = reference_pools(pool_rec, CANDIDATE_AXES)
    rows = [r for r in _rows(sheet, answer, by_key, pools, None) if r["role"] == "positive" and r["split"] == "discovery"]
    measured = [r for r in rows if "pcts" in r]

    axes: list[dict[str, Any]] = []
    for order, ax in enumerate(CANDIDATE_AXES):
        ps = [r["pcts"][ax] for r in measured if ax in r["pcts"]]
        low = sum(1 for p in ps if p <= LOW_PCT)
        high = sum(1 for p in ps if p >= HIGH_PCT)
        direction = "low" if low >= MIN_SAME_TAIL else "high" if high >= MIN_SAME_TAIL else None
        axes.append({"axis": ax, "order": order, "measured": len(ps), "low_tail": low, "high_tail": high,
                     "median_pct": statistics.median(ps) if ps else None,
                     "qualified": direction is not None, "direction": direction,
                     "count": low if direction == "low" else high if direction == "high" else None})
    qualified = sorted((a for a in axes if a["qualified"]), key=lambda a: (-a["count"], a["order"]))
    chosen = [{"axis": a["axis"], "direction": a["direction"], "count": a["count"]} for a in qualified[:MAX_AXES]]

    out = {
        "protocol": {"low_pct": LOW_PCT, "high_pct": HIGH_PCT, "min_same_tail": MIN_SAME_TAIL, "max_axes": MAX_AXES,
                     "candidate_axes": CANDIDATE_AXES, "source": "docs/DRAFT-altz-answer-sheet.md section 3.3"},
        "reference_pool": {"window": [days[0].stem if days else None, days[-1].stem if days else None],
                           "snapshots": len(days), "unique_chart_recordings": len(pool_rec),
                           "n_per_axis": {ax: len(v) for ax, v in pools.items()}},
        "discovery": {"positives": len(rows), "measured": len(measured),
                      "unresolved": [f"{r['sheet_artist']} - {r['sheet_title']}" for r in rows if "pcts" not in r]},
        "axes": axes,
        "qualified": [a["axis"] for a in qualified],
        "chosen": chosen,
        "verdict": "axes chosen" if chosen else NO_AXIS,
        "rows": rows,
    }
    path = sheet_dir / "discover.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("reference_pool", "discovery", "axes", "chosen", "verdict")}, ensure_ascii=False, indent=1))
    return 0


def _hmap(rows: list[dict[str, Any]], sheet: dict[str, Any]) -> dict[str, Any]:
    """Raw organic_ratio medians (draft section 3.5). Reported, never part of the verdict."""
    feats = {_key(r.get("sheet_artist"), r.get("sheet_title")): r.get("features") for r in sheet.get("records") or []}

    def vals(sel: list[dict[str, Any]]) -> list[float]:
        out = []
        for r in sel:
            f = feats.get(_key(r["sheet_artist"], r["sheet_title"]))
            if isinstance(f, dict) and (v := axis_values(f, ["organic_ratio"]).get("organic_ratio")) is not None:
                out.append(v)
        return out

    groups = {
        "positives": vals([r for r in rows if r["role"] == "positive"]),
        "below": vals([r for r in rows if r.get("hmap") == "below"]),
        "above": vals([r for r in rows if r.get("hmap") == "above"]),
    }
    med = {k: (round(statistics.median(v), 4) if v else None) for k, v in groups.items()}
    med_pct = {k: (statistics.median(ps) if (ps := [r["pcts"]["organic_ratio"] for r in rows if sel(r) and "organic_ratio" in (r.get("pcts") or {})]) else None)
               for k, sel in (("positives", lambda r: r["role"] == "positive"), ("below", lambda r: r.get("hmap") == "below"), ("above", lambda r: r.get("hmap") == "above"))}
    p1 = None if med["positives"] is None or med["below"] is None else med["positives"] > med["below"]
    p2 = None if med["positives"] is None or med["above"] is None else med["positives"] < med["above"]
    return {"axis": "organic_ratio", "n": {k: len(v) for k, v in groups.items()}, "median": med,
            "median_reference_pct": med_pct, "positives_above_below_group": p1, "positives_below_above_group": p2,
            "supported": None if p1 is None or p2 is None else (p1 and p2)}


def cmd_holdout(args: argparse.Namespace) -> int:
    sheet_dir = Path(args.dir)
    disc = json.loads((sheet_dir / "discover.json").read_text(encoding="utf-8"))
    start, end = disc["reference_pool"]["window"]
    rule = [(c["axis"], c["direction"]) for c in disc["chosen"]] or None
    answer, sheet, by_key = _load(sheet_dir)
    days, pool_rec, per_day = load_reference(Path(args.sonic), start, end)
    if len(days) != disc["reference_pool"]["snapshots"]:
        raise SystemExit(f"window {start}..{end} now has {len(days)} snapshots, discover saw {disc['reference_pool']['snapshots']}")
    pools = reference_pools(pool_rec, CANDIDATE_AXES)
    rows = _rows(sheet, answer, by_key, pools, rule)

    hold_pos = [r for r in rows if r["role"] == "positive" and r["split"] == "holdout"]
    negatives = [r for r in rows if r["role"] == "negative"]
    summary: dict[str, Any] = {
        "rule": [{"axis": a, "direction": d} for a, d in rule] if rule else NO_AXIS,
        "low_pct": LOW_PCT, "high_pct": HIGH_PCT,
        "reference_pool": {"window": [start, end], "snapshots": len(days), "unique_chart_recordings": len(pool_rec)},
        "resolved": {"holdout_positives": sum(1 for r in hold_pos if "pcts" in r), "holdout_positives_total": len(hold_pos),
                     "negatives": sum(1 for r in negatives if "pcts" in r), "negatives_total": len(negatives),
                     "unresolved": [f"{r['sheet_artist']} - {r['sheet_title']}" for r in rows if "pcts" not in r]},
        "hmap": _hmap(rows, sheet),
    }
    daily: list[dict[str, Any]] = []
    if rule:
        hold = [r for r in rows if r["split"] == "holdout"]
        c1 = rate(hold, "positive")
        c2 = rate(hold, "negative")
        c4 = rate(hold, "positive", lambda x: x.get("grade") in GRADES_MID_OR_ABOVE)
        daily, shares = daily_share(per_day, rule, LOW_PCT, HIGH_PCT, args.min_day_n)
        c3 = shares["cohort_share_chart"]
        crit = {
            "1_hit_rate": {**c1, "pass": c1["measured"] >= MIN_MEASURED and (c1["rate"] or 0) >= HIT_MIN},
            "2_false_positive": {**c2, "pass": c2["measured"] >= MIN_MEASURED and c2["rate"] is not None and c2["rate"] <= NEG_MAX},
            "3_cohort_baseline": {"share": c3["share"], "track_days_matched": c3["track_days_matched"],
                                  "track_days_evaluable": c3["track_days_evaluable"],
                                  "pass": c3["share"] is not None and c3["share"] <= BASE_MAX},
            "4_grade_mid_or_above_measured": {"measured": c4["measured"], "pass": c4["measured"] >= MIN_MEASURED},
        }
        summary["criteria"] = crit
        summary["verdict"] = "등재" if all(c["pass"] for c in crit.values()) else "기각"
        summary.update(shares)
        summary["discovery_in_sample"] = rate([r for r in rows if r["split"] == "discovery"], "positive")
        summary["boundary_negative_conan_gray"] = next((r.get("match") for r in negatives if r["sheet_artist"] == "Conan Gray"), None)
    else:
        summary["verdict"] = f"{NO_AXIS} · 홀드아웃 규칙 검정 없음"
    years = [release_year(r) for r in rows if r["role"] == "positive"]
    summary["positives_release_years"] = dict(sorted(Counter(str(y) if y else "unknown" for y in years).items()))
    summary["median_pct"] = {
        grp: {ax: (statistics.median(ps) if (ps := [r["pcts"][ax] for r in rows if sel(r) and ax in (r.get("pcts") or {})]) else None)
              for ax in CANDIDATE_AXES}
        for grp, sel in (("holdout_positive", lambda r: r["role"] == "positive" and r["split"] == "holdout"),
                         ("negative", lambda r: r["role"] == "negative"))
    }

    path = sheet_dir / "verify.json"
    path.write_text(json.dumps({"summary": summary, "sheet": rows, "daily": daily}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover", help="pick axes on the discovery positives (writes discover.json)")
    d.add_argument("dir")
    d.add_argument("--sonic", required=True, help="daily sonic snapshots (read only)")
    d.add_argument("--start", default="2026-07-28")
    d.add_argument("--end", default=None, help="defaults to the latest snapshot; holdout reuses this window")
    h = sub.add_parser("holdout", help="test the frozen rule on the holdout (writes verify.json)")
    h.add_argument("dir")
    h.add_argument("--sonic", required=True, help="daily sonic snapshots (read only)")
    h.add_argument("--min-day-n", type=int, default=30, help="days with fewer resolved chart tracks are skipped")
    args = ap.parse_args(argv)
    return cmd_discover(args) if args.cmd == "discover" else cmd_holdout(args)


if __name__ == "__main__":
    raise SystemExit(main())
