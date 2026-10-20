"""Debut size against success, from the committed facts fixture only.

Purpose    Select the population, mark each group's success per measure inside the observation
           window, and compute rates, intervals and tests per size bucket, pooled and per debut era.
Boundary   Reads the fixture. Never reads the planning repo, so CI runs without it.
           Gives evidence about association in this sample. It does not explain why a group succeeds.
Invariant  A group counts as a success only from hits inside [debut year, debut year + window - 1].
           Cohorts whose window reaches past the last complete source year are kept out of tests unless
           asked. Mixing them in reads "not observed yet" as "did not succeed" and pulls rates down.
Failure    Untestable tables (no successes, one bucket) carry a reason string instead of numbers.
"""

from __future__ import annotations

import random
import statistics
import zlib
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from cohort_size import stats

MEASURES = ("any", "win", "melon", "circle")
TESTED = MEASURES  # spotify is a snapshot with no window: shown, never tested
VARIANTS = ("default", "range", "units")


@dataclass(frozen=True)
class Config:
    window: int = 3
    cuts: tuple[int, ...] = (3, 4, 5, 6)
    eras: tuple[tuple[int, int], ...] = ((2012, 2014), (2015, 2017), (2018, 2020), (2021, 2023))
    first_year: int = 2012
    last_year: int = 2024
    include_incomplete: bool = False
    exact_b: int = 20000
    boot_b: int = 2000
    seed: int = 20261020
    alpha: float = 0.05
    trend_scores: str = "ordinal"
    focus_size: int = 5


def bucket_labels(cuts: tuple[int, ...]) -> list[str]:
    labels = [f"{cuts[0]}명 이하"]
    for lo, hi in pairwise(cuts):
        labels.append(f"{hi}명" if hi == lo + 1 else f"{lo + 1}~{hi}명")
    labels.append(f"{cuts[-1] + 1}명 이상")
    return labels


def bucket_of(n: int, cuts: tuple[int, ...]) -> int:
    for i, c in enumerate(cuts):
        if n <= c:
            return i
    return len(cuts)


def last_complete_year(fixture: dict[str, Any]) -> int:
    """Last calendar year that every windowed source covers in full."""
    cov = fixture["coverage"]
    partial = set(cov.get("partialYears", {}).get("win", []))
    win_last = max(y for y in range(cov["winYears"][0], cov["winYears"][1] + 1) if y not in partial)
    return min(win_last, max(cov["melonYears"]), max(cov["circleYears"]))


def select(fixture: dict[str, Any], variant: str, cfg: Config) -> list[dict[str, Any]]:
    """default: determined size, units out. range: plus undetermined groups at current + former.
    units: plus sub-units and project groups with a determined size."""
    out = []
    for g in fixture["groups"]:
        if not (cfg.first_year <= g["year"] <= cfg.last_year):
            continue
        if g["unit"] and variant != "units":
            continue
        n = g["n"]
        if n is None and variant == "range" and not g["unit"]:
            n = g["current"] + g["former"]
        if not n:
            continue
        out.append({**g, "size": n})
    return out


def _in_window(year: int, g: dict[str, Any], w: int) -> bool:
    return g["year"] <= year <= g["year"] + w - 1


def mark(groups: list[dict[str, Any]], cfg: Config) -> None:
    for g in groups:
        h = g["hits"]
        for m in ("win", "melon", "circle"):
            yrs = sorted({x["year"] for x in h[m] if _in_window(x["year"], g, cfg.window)})
            g[m] = bool(yrs)
            g[m + "Years"] = yrs
        g["any"] = g["win"] or g["melon"] or g["circle"]
        g["spotify"] = h["spotify"] is not None


def _seed(cfg: Config, label: str) -> int:
    return (cfg.seed * 1_000_003 + zlib.crc32(label.encode("utf-8"))) & 0xFFFFFFFF


def table_rows(groups: list[dict[str, Any]], measure: str, cfg: Config) -> list[dict[str, Any]]:
    labels = bucket_labels(cfg.cuts)
    k = [0] * len(labels)
    n = [0] * len(labels)
    for g in groups:
        b = bucket_of(g["size"], cfg.cuts)
        n[b] += 1
        k[b] += bool(g[measure])
    rows = []
    for i, lab in enumerate(labels):
        lo, hi = stats.wilson(k[i], n[i])
        rows.append({"bucket": i, "label": lab, "k": k[i], "n": n[i],
                     "rate": (k[i] / n[i]) if n[i] else None, "lo": lo if n[i] else None, "hi": hi if n[i] else None})
    return rows


def _scores(rows: list[dict[str, Any]], groups: list[dict[str, Any]], cfg: Config) -> list[float]:
    if cfg.trend_scores == "median":
        out = []
        for r in rows:
            sizes = [g["size"] for g in groups if bucket_of(g["size"], cfg.cuts) == r["bucket"]]
            out.append(float(statistics.median(sizes)) if sizes else float(r["bucket"] + 1))
        return out
    return [float(r["bucket"] + 1) for r in rows]


def run_test(rows: list[dict[str, Any]], groups: list[dict[str, Any]], cfg: Config, label: str) -> dict[str, Any]:
    table = [(r["k"], r["n"]) for r in rows]
    big_n = sum(n for _, n in table)
    big_k = sum(k for k, _ in table)
    out: dict[str, Any] = {"n": big_n, "k": big_k}
    reason = stats.testable(table)
    if reason:
        out["reason"] = reason
        return out
    cs = stats.chi_square(table)
    assert cs is not None
    chi, df, expected = cs
    exact = stats.exact_mc(table, random.Random(_seed(cfg, "exact|" + label)), cfg.exact_b)
    boot = stats.bootstrap_v(table, random.Random(_seed(cfg, "boot|" + label)), cfg.boot_b)
    trend = stats.cochran_armitage(table, _scores(rows, groups, cfg))
    assert exact is not None and boot is not None
    out.update({
        "chi2": chi, "df": df, "pChi2": stats.chi2_sf(chi, df),
        "pExact": exact[0], "mcSe": exact[1], "exactB": cfg.exact_b,
        "v": stats.cramers_v(table), "vLo": boot[0], "vHi": boot[1], "bootB": cfg.boot_b,
        "trendZ": trend[0] if trend else None, "pTrend": trend[1] if trend else None,
        "lowExpected": sum(1 for e in expected if e < 5), "cells": len(expected),
    })
    return out


def _dist(groups: list[dict[str, Any]], cfg: Config) -> dict[str, Any]:
    succ = [g for g in groups if g["any"]]
    labels = bucket_labels(cfg.cuts)

    def shares(gs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        c = [0] * len(labels)
        for g in gs:
            c[bucket_of(g["size"], cfg.cuts)] += 1
        return [{"label": lab, "k": c[i], "n": len(gs)} for i, lab in enumerate(labels)]

    return {
        "all": {"n": len(groups), "median": float(statistics.median([g["size"] for g in groups])) if groups else None,
                "focus": sum(1 for g in groups if g["size"] == cfg.focus_size), "shares": shares(groups)},
        "success": {"n": len(succ), "median": float(statistics.median([g["size"] for g in succ])) if succ else None,
                    "focus": sum(1 for g in succ if g["size"] == cfg.focus_size), "shares": shares(succ)},
    }


def block(groups: list[dict[str, Any]], cfg: Config, label: str) -> dict[str, Any]:
    measures: dict[str, Any] = {}
    for m in TESTED:
        rows = table_rows(groups, m, cfg)
        measures[m] = {"rows": rows, "test": run_test(rows, groups, cfg, f"{label}|{m}")}
    measures["spotify"] = {"rows": table_rows(groups, "spotify", cfg)}
    return {"n": len(groups), "measures": measures, "dist": _dist(groups, cfg)}


def analyze(fixture: dict[str, Any], cfg: Config) -> dict[str, Any]:
    last_full = last_complete_year(fixture)
    complete_years = [y for y in range(cfg.first_year, cfg.last_year + 1) if y + cfg.window - 1 <= last_full]
    incomplete_years = [y for y in range(cfg.first_year, cfg.last_year + 1) if y not in complete_years]
    tested_years = set(complete_years) | (set(incomplete_years) if cfg.include_incomplete else set())

    variants: dict[str, Any] = {}
    for v in VARIANTS:
        gs = select(fixture, v, cfg)
        mark(gs, cfg)
        variants[v] = {"all": gs, "tested": [g for g in gs if g["year"] in tested_years]}

    default_all = variants["default"]["all"]
    pooled = {v: block(variants[v]["tested"], cfg, f"pooled|{v}") for v in VARIANTS}

    eras = []
    for lo, hi in cfg.eras:
        gs = [g for g in default_all if lo <= g["year"] <= hi]
        eras.append({"label": f"{lo}~{str(hi)[2:]}" if lo != hi else str(lo), "years": [lo, hi],
                     "complete": all(y in complete_years for y in range(lo, hi + 1)), **block(gs, cfg, f"era|{lo}")})
    covered = {y for lo, hi in cfg.eras for y in range(lo, hi + 1)}
    for y in incomplete_years:
        if y in covered:
            continue
        gs = [g for g in default_all if g["year"] == y]
        eras.append({"label": str(y), "years": [y, y], "complete": False, **block(gs, cfg, f"era|{y}")})

    # Holm across the complete eras, per measure: four eras tested separately make a low p by chance likelier.
    for m in TESTED:
        fam = [e for e in eras if e["complete"] and "pExact" in e["measures"][m]["test"]]
        for e, adj in zip(fam, stats.holm([e["measures"][m]["test"]["pExact"] for e in fam]), strict=True):
            e["measures"][m]["test"]["pHolm"] = adj
            e["measures"][m]["test"]["holmFamily"] = len(fam)

    gaps = fixture["coverage"]["gaps"]
    cohorts = []
    for y in range(cfg.first_year, cfg.last_year + 1):
        win_years = range(y, y + cfg.window)
        cohorts.append({
            "year": y,
            "complete": y in complete_years,
            "tested": y in tested_years,
            "n": sum(1 for g in default_all if g["year"] == y),
            "gaps": [f"{x['program']} {x['year']}" for x in gaps if x["year"] in win_years],
        })

    def brief(g: dict[str, Any]) -> dict[str, Any]:
        return {"year": g["year"], "title": g["title"], "size": g["size"], "sizeSource": g["sizeSource"],
                "winYears": g["winYears"], "melonYears": g["melonYears"], "circleYears": g["circleYears"],
                "spotify": g["spotify"]}

    return {
        "config": {
            "window": cfg.window, "cuts": list(cfg.cuts), "buckets": bucket_labels(cfg.cuts),
            "eras": [list(e) for e in cfg.eras], "firstYear": cfg.first_year, "lastYear": cfg.last_year,
            "includeIncomplete": cfg.include_incomplete, "exactB": cfg.exact_b, "bootB": cfg.boot_b,
            "seed": cfg.seed, "alpha": cfg.alpha, "trendScores": cfg.trend_scores, "focusSize": cfg.focus_size,
        },
        "lastCompleteYear": last_full,
        "completeYears": complete_years,
        "incompleteYears": incomplete_years,
        "cohorts": cohorts,
        "pooled": pooled,
        "eras": eras,
        "successes": [brief(g) for g in default_all if g["any"] or g["spotify"]],
        "counts": {
            v: {"all": len(variants[v]["all"]), "tested": len(variants[v]["tested"])} for v in VARIANTS
        },
        "excludedDefault": {
            "undetermined": sum(1 for g in fixture["groups"]
                                if cfg.first_year <= g["year"] <= cfg.last_year and not g["unit"] and not g["n"]),
            "units": sum(1 for g in fixture["groups"] if cfg.first_year <= g["year"] <= cfg.last_year and g["unit"]),
        },
        "sources": fixture["sources"],
        "coverage": fixture["coverage"],
    }
