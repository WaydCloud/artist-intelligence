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
from dataclasses import dataclass, replace
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
    last_year: int = 2026
    include_incomplete: bool = False
    exact_b: int = 20000
    seed: int = 20261020
    alpha: float = 0.05
    trend_scores: str = "ordinal"
    focus_size: int = 5
    impute_runs: int = 20
    impute_sample_seed: int = 20261021
    impute_sample_n: int = 36
    impute_b: int = 5000
    exact_cuts: tuple[int, ...] = (3, 4, 5, 6, 7, 8)
    exact_eras: tuple[tuple[int, int], ...] = ((2012, 2017), (2018, 2023))


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
    trend = stats.cochran_armitage(table, _scores(rows, groups, cfg))
    assert exact is not None
    out.update({
        "chi2": chi, "df": df, "pChi2": stats.chi2_sf(chi, df),
        "pExact": exact[0], "mcSe": exact[1], "exactB": cfg.exact_b,
        "v": stats.cramers_v(table), "vbc": stats.cramers_v_bc(table), "vbcNull95": exact[2],
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


def _determination(fixture: dict[str, Any], cfg: Config, years: set[int]) -> dict[str, Any]:
    """Composite success among tested-year non-unit groups, split by whether the debut size was read.

    If undetermined groups succeed at a different rate, the default population is a selected
    sample and its rates are not the rates of all debuting groups.
    """
    gs = [dict(g, size=1) for g in fixture["groups"] if g["year"] in years and not g["unit"]]
    mark(gs, cfg)
    det = [g for g in gs if g["n"]]
    und = [g for g in gs if not g["n"]]
    no_info = [g for g in und if g["current"] + g["former"] == 0]

    def kn(xs: list[dict[str, Any]]) -> dict[str, Any]:
        k = sum(1 for g in xs if g["any"])
        lo, hi = stats.wilson(k, len(xs))
        return {"k": k, "n": len(xs), "lo": lo, "hi": hi}

    return {"determined": kn(det), "undetermined": kn(und), "noMemberInfo": kn(no_info),
            "bySource": {src: kn([g for g in det if g["sizeSource"] == src])
                         for src in sorted({str(g["sizeSource"]) for g in det})}}


def _bracket(g: dict[str, Any]) -> tuple[int, int]:
    """Plausible debut-size range of an undetermined group: latest lineup size to current + former."""
    lo = g.get("finalSize") or g["current"] or min(3, g["former"] or 3)
    return lo, max(lo, g["current"] + g["former"])


def imputation(fixture: dict[str, Any], cfg: Config, years: set[int]) -> dict[str, Any]:
    """Composite tests with the undetermined groups given a size by five schemes.

    The default sample leaves these groups out. Each scheme puts them back with a different
    assumption, so a reader sees how far the composite p moves. Seeds are 1..runs per scheme and
    `impute_sample_seed` for the checked sample. Only the composite pooled table is tested.
    """
    base = [dict(g) for g in fixture["groups"] if g["year"] in years and not g["unit"]]
    mark(base, cfg)
    det = [g for g in base if g["n"]]
    und = [g for g in base if not g["n"]]
    for g in det:
        g["size"] = g["n"]
    fail_sizes = [g["n"] for g in det if not g["any"]]
    sample = random.Random(cfg.impute_sample_seed).sample(und, min(cfg.impute_sample_n, len(und)))
    sample_sizes = [g.get("finalSize") or (g["current"] + g["former"]) for g in sample]

    schemes: dict[str, Any] = {
        "resampleDeterminedFailures": lambda g, r: r.choice(fail_sizes),
        "resampleCheckedSample": lambda g, r: r.choice(sample_sizes),
        "uniformInRange": lambda g, r: r.randint(*_bracket(g)),
        "allAtFinal": lambda g, r: _bracket(g)[0],
        "allAtUpper": lambda g, r: _bracket(g)[1],
    }
    single = {"allAtFinal", "allAtUpper"}
    out: dict[str, Any] = {"undetermined": len(und), "sampleSeed": cfg.impute_sample_seed,
                           "sampleN": len(sample), "runs": cfg.impute_runs, "schemes": {}}
    for name, assign in schemes.items():
        seeds = [1] if name in single else list(range(1, cfg.impute_runs + 1))
        res = []
        for s in seeds:
            rng = random.Random(s)
            gs = det + [dict(g, size=assign(g, rng)) for g in und]
            t = run_test(table_rows(gs, "any", cfg), gs, cfg, f"impute|{name}|{s}")
            res.append(t)
        ok = [t for t in res if "pExact" in t]
        out["schemes"][name] = {
            "seeds": seeds,
            "n": res[0]["n"],
            "pExactMin": min(t["pExact"] for t in ok), "pExactMax": max(t["pExact"] for t in ok),
            "pTrendMin": min(t["pTrend"] for t in ok), "pTrendMax": max(t["pTrend"] for t in ok),
            "vbcMin": min(t["vbc"] for t in ok), "vbcMax": max(t["vbc"] for t in ok),
        }
    return out


def _span(lo: int, hi: int) -> str:
    return f"{lo}~{str(hi)[2:]}" if lo != hi else str(lo)


def _fisher_split(groups: list[dict[str, Any]], inside: Any) -> dict[str, Any]:
    """Fisher exact 2 x 2: groups where inside(size) holds against the rest, composite success."""
    a = sum(1 for g in groups if inside(g["size"]) and g["any"])
    n1 = sum(1 for g in groups if inside(g["size"]))
    c = sum(1 for g in groups if not inside(g["size"]) and g["any"])
    n2 = len(groups) - n1
    p = stats.fisher_exact_2x2(a, n1 - a, c, n2 - c) if n1 and n2 else None
    return {"k1": a, "n1": n1, "k2": c, "n2": n2, "p": p}


def exact_by_era(groups: list[dict[str, Any]], cfg: Config, complete: list[int], in_progress: list[int],
                 fixture: dict[str, Any]) -> dict[str, Any]:
    """Composite success by exact debut size (fine columns) and two wide eras, plus an in-progress row.

    Closed eras use the full window. The in-progress row counts success to date: wins up to the last
    captured page, Melon and Circle up to the last year-end chart. Post-hoc 2 x 2 tests are run for the
    closed eras only. They were chosen after seeing the data, so each era also gets every
    column-against-rest test and a Holm adjustment over that whole family.
    """
    labels = bucket_labels(cfg.exact_cuts)
    eras = [(lo, hi, True) for lo, hi in cfg.exact_eras]
    if in_progress:
        eras.append((min(in_progress), max(in_progress), False))
    rows_out = []
    for lo, hi, closed in eras:
        gs = [g for g in groups if lo <= g["year"] <= hi]
        cells = []
        for i, lab in enumerate(labels):
            members = [g for g in gs if bucket_of(g["size"], cfg.exact_cuts) == i]
            succ = sorted((g for g in members if g["any"]), key=lambda g: (g["year"], g["title"].lower()))
            k, n = len(succ), len(members)
            wl, wh = stats.wilson(k, n)
            cells.append({"label": lab, "k": k, "n": n, "rate": k / n if n else None,
                          "lo": wl if n else None, "hi": wh if n else None,
                          "successes": [{"title": g["title"], "year": g["year"], "size": g["size"]} for g in succ]})
        entry: dict[str, Any] = {"label": _span(lo, hi), "years": [lo, hi], "closed": closed and all(
            y in complete for y in range(lo, hi + 1)), "n": len(gs), "k": sum(1 for g in gs if g["any"]),
            "cells": cells}
        if entry["closed"]:
            family: dict[str, dict[str, Any]] = {}
            for i, lab in enumerate(labels):
                family[f"{lab} vs rest"] = _fisher_split(gs, lambda n, i=i: bucket_of(n, cfg.exact_cuts) == i)
            big = cfg.exact_cuts[-1]
            family[f"{big}명 이상 vs {big}명 미만"] = _fisher_split(gs, lambda n, big=big: n >= big)
            keys = [k_ for k_, v in family.items() if v["p"] is not None]
            for k_, adj in zip(keys, stats.holm([family[k_]["p"] for k_ in keys]), strict=True):
                family[k_]["pHolm"] = adj
                family[k_]["holmFamily"] = len(keys)
            entry["postHoc"] = family
        rows_out.append(entry)
    wins = fixture["sources"].get("win", [])
    last_win = max((w.get("retrieved", "") for w in wins), default="")
    return {
        "cuts": list(cfg.exact_cuts), "labels": labels, "eras": rows_out,
        "highlight": [f"{cfg.exact_cuts[-1]}명 이상 vs {cfg.exact_cuts[-1]}명 미만", "6명 vs rest"],
        "cut": {"winRetrieved": last_win, "melonLastYear": max(fixture["coverage"]["melonYears"]),
                "circleLastYear": max(fixture["coverage"]["circleYears"])},
    }


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
        eras.append({"label": _span(lo, hi), "years": [lo, hi],
                     "complete": all(y in complete_years for y in range(lo, hi + 1)), **block(gs, cfg, f"era|{lo}")})
    covered = {y for lo, hi in cfg.eras for y in range(lo, hi + 1)}
    rest = [y for y in incomplete_years if y not in covered]
    if rest:
        # Cohorts still inside their window form one "in progress" row: success to date only.
        lo, hi = min(rest), max(rest)
        gs = [g for g in default_all if g["year"] in rest]
        eras.append({"label": _span(lo, hi), "years": [lo, hi], "complete": False, **block(gs, cfg, f"era|{lo}")})

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
            "includeIncomplete": cfg.include_incomplete, "exactB": cfg.exact_b,
            "seed": cfg.seed, "alpha": cfg.alpha, "trendScores": cfg.trend_scores, "focusSize": cfg.focus_size,
            "exactCuts": list(cfg.exact_cuts),
            "exactEras": [list(e) for e in cfg.exact_eras], "imputeRuns": cfg.impute_runs, "imputeSampleSeed": cfg.impute_sample_seed, "imputeB": cfg.impute_b,
        },
        "lastCompleteYear": last_full,
        "completeYears": complete_years,
        "incompleteYears": incomplete_years,
        "cohorts": cohorts,
        "pooled": pooled,
        "eras": eras,
        "exact": exact_by_era(default_all, cfg, complete_years, rest, fixture),
        "successes": [brief(g) for g in default_all if g["any"] or g["spotify"]],
        "counts": {
            v: {"all": len(variants[v]["all"]), "tested": len(variants[v]["tested"])} for v in VARIANTS
        },
        "determination": _determination(fixture, cfg, tested_years),
        "imputation": imputation(fixture, replace(cfg, exact_b=cfg.impute_b), tested_years),
        "excludedDefault": {
            "undetermined": sum(1 for g in fixture["groups"]
                                if cfg.first_year <= g["year"] <= cfg.last_year and not g["unit"] and not g["n"]),
            "units": sum(1 for g in fixture["groups"] if cfg.first_year <= g["year"] <= cfg.last_year and g["unit"]),
        },
        "sources": fixture["sources"],
        "coverage": fixture["coverage"],
    }
