"""Offline self-check. Each numbered check maps to TESTS.md.

Purpose    Prove the statistics against known values, the size rule against the planning rows, the name
           rules against known false and true hits, and the report against the schema and copy gates.
Boundary   Reads the committed fixture and test fixtures only. No network, no planning repo.
Failure    Any failed check makes the command exit 1. A missing dependency is a failure, not a skip.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import random
import re
from pathlib import Path
from typing import Any

from cohort_size import analyze as an
from cohort_size import build as bd
from cohort_size import match, sizes, stats
from cohort_size.report import build_report

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "data/research/cohort-size/facts.json"
SIZES_ROWS = ROOT / "modules/cohort-size/tests/fixtures/sizes_2022_2024.csv"

# Default-population groups of 2022 to 2024 with any of win, Melon, Circle in any captured year,
# as listed by the earlier planning count (no window there).
PLANNING_2022_2024 = {
    "CSR", "FIFTY FIFTY", "LE SSERAFIM", "NMIXX", "NewJeans", "VIVIZ", "KISS OF LIFE", "TripleS",
    "BABYMONSTER", "ILLIT", "Izna", "KATSEYE", "MEOVV", "RESCENE", "SAY MY NAME (group)",
}
# H1-KEY had no size in the planning count (four now, one former). Its size is now reviewed (4),
# so it joins the default population with its 2023 win.
SANITY_2022_2024 = PLANNING_2022_2024 | {"H1-KEY"}

# Planning rows 2022-2024 that the corrected rules change on purpose.
# Kandis: the lead says "Originally as a duo, they made their debut on August 27, 2023".
SIZES_CORRECTED = {("2023", "Kandis"): "2"}
# LA FLOR is listed in 2022 and 2023. One entry per title keeps 2022.
SIZES_REMOVED = {("2023", "LA FLOR")}


class _Run:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail and not ok else ""))


def _close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def _stats(r: _Run) -> None:
    known = [(3.841458820694124, 1, 0.05), (5.991464547107979, 2, 0.05), (7.814727903251178, 3, 0.05),
             (9.487729036781154, 4, 0.05), (20.0, 10, 0.029252688076961)]
    r.check("1 chi-square sf known values",
            all(_close(stats.chi2_sf(x, df), p, 1e-12) for x, df, p in known),
            str([stats.chi2_sf(x, df) for x, df, _ in known]))
    lo, hi = stats.wilson(5, 10)
    lo0, hi0 = stats.wilson(0, 10)
    r.check("2 Wilson 5/10 and 0/10", _close(lo, 0.2366, 1e-4) and _close(hi, 0.7634, 1e-4)
            and lo0 == 0.0 and _close(hi0, 0.2775, 1e-4), f"{lo, hi, lo0, hi0}")
    r.check("3 Cramer's V crafted tables",
            stats.cramers_v([(10, 10), (0, 10)]) == 1.0 and stats.cramers_v([(5, 10), (5, 10)]) == 0.0)
    vbc_full = stats.cramers_v_bc([(10, 10), (0, 10)])
    vbc_none = stats.cramers_v_bc([(5, 10), (5, 10)])
    t3 = [(1, 11), (5, 35), (3, 51), (7, 29), (10, 58)]
    vbc3, v3 = stats.cramers_v_bc(t3), stats.cramers_v(t3)
    r.check("3b bias-corrected V: 1 on full separation, 0 on equal rates, below plain V",
            vbc_full is not None and _close(vbc_full, 1.0, 1e-12) and vbc_none == 0.0
            and vbc3 is not None and v3 is not None and vbc3 < v3, f"{vbc_full} {vbc_none} {vbc3} {v3}")
    null_mc = stats.exact_mc([(5, 40), (5, 40), (5, 40)], random.Random(3), 2000)
    r.check("3c permutation null of corrected V is above an equal-rate table's V",
            null_mc is not None and 0.0 < null_mc[2] < 1.0 and stats.cramers_v_bc([(5, 40), (5, 40), (5, 40)]) == 0.0,
            str(null_mc))
    exact = stats.fisher_exact_2x2(8, 2, 1, 5)
    mc = stats.exact_mc([(8, 10), (1, 6)], random.Random(7), 20000)
    r.check("4 Monte Carlo exact p within 4 SE of Fisher by enumeration",
            mc is not None and abs(mc[0] - exact) <= 4 * mc[1], f"mc={mc} fisher={exact}")
    cs = stats.chi_square([(8, 10), (1, 6)])
    ca = stats.cochran_armitage([(8, 10), (1, 6)], [1, 2])
    r.check("5 Cochran-Armitage z^2 equals Pearson chi-square on 2 rows",
            cs is not None and ca is not None and _close(ca[0] ** 2, cs[0], 1e-9))
    r.check("6 Holm known example", [round(x, 6) for x in stats.holm([0.01, 0.04, 0.03])] == [0.03, 0.06, 0.06])
    r.check("7 untestable tables carry a reason",
            stats.testable([(0, 10), (0, 5)]) == "성공한 팀 0" and stats.testable([(3, 10)]) == "인원 구간이 둘 미만"
            and stats.exact_mc([(0, 10), (0, 5)], random.Random(1), 10) is None)
    a = stats.exact_mc([(3, 20), (9, 25), (2, 15)], random.Random(11), 500)
    b = stats.exact_mc([(3, 20), (9, 25), (2, 15)], random.Random(11), 500)
    r.check("8 same seed, same Monte Carlo p", a == b)


def _sizes(r: _Run) -> None:
    lead = "{{Infobox group\n| current = A<br>B\n| former = C\n}}\n'''X''' is a girl group. They debuted as a four-member group."
    s = sizes.debut_size(lead)
    r.check("9 lead sentence wins over member lists", s["n"] == 4 and s["src"] == "lead_debut", str(s))
    orig = "{{Infobox group\n| current = A\n}}\n'''X''' is a group. Originally as five, they now have one."
    r.check("10 'Originally as N'", sizes.debut_size(orig)["n"] == 5)
    cur = "{{Infobox group\n| current = A<br>B<br>C\n}}\n'''X''' is a group."
    s = sizes.debut_size(cur)
    r.check("11 no former members: current count", s["n"] == 3 and s["src"] == "current_no_former", str(s))
    amb = "{{Infobox group\n| current = A<br>B\n| former = C<br>D\n}}\n'''X''' is a group."
    s = sizes.debut_size(amb)
    r.check("12 current plus former: undetermined, range kept", s["n"] is None and s["current"] == 2
            and s["former"] == 2, str(s))
    r.check("13 unit flag and girl-group filter (lower-case infobox too)",
            sizes.is_unit(["Category:Female subunits", "Category:Sub-units"])
            and sizes.is_girl_group(["Category:Female groups"], "{{infobox musical artist\n}}")
            and not sizes.is_girl_group(["Category:Male groups"], "{{Infobox group}}"))
    # Rule shapes found by the review, each in a minimal page.
    cases = [
        ("37 'debuted as four' after an infobox holding '''KR:'''",
         ("{{infobox musical artist\n| website = '''KR:''' x\n| current =\n* A\n* B\n* C\n* D\n* E\n}}\n"
         "'''X''' is a five-member girl group. They debuted as four on August 1, 2014 with a single."), 2014, 4),
        ("38 'originally consisted of eight members'",
         ("{{Infobox group\n| current = A\n| former = B\n}}\n'''X''' is a girl group. They debuted on August 9, 2012."
         "\n\nThe group originally consisted of eight members; A, B."), 2012, 8),
        ("39 one-line infobox members (|former=|inactive=* ...}})",
         ("{{Infobox group\n| name = X\n|associated=[[Y]]|former=|inactive=* [[A]]\n* [[B|b]]\n* [[C]]}}\n"
         "'''X''' is a three-member group."), 2015, 3),
        ("40 disbanded group: 'was a 10-member' equals former count",
         "{{Infobox group\n| former =\n" + "".join(f"* M{i}\n" for i in range(10)) + "}}\n"
         "'''X''' was a 10-member girl group. They officially debuted on March 21, 2017.", 2017, 10),
        ("41 'was a N-member' that disagrees with the former count stays undetermined",
         "{{Infobox group\n| former =\n* A\n* B\n* C\n* D\n}}\n'''X''' was a three-member group.", 2013, None),
        ("42 re-debut sentence is not read",
         ("{{Infobox group\n| former =\n* A\n* B\n* C\n}}\n'''X''' was a girl group. In 2016 they re-debuted as a "
         "five-member group."), 2013, None),
        ("43 a debut sentence naming another year is not read",
         ("{{Infobox group\n| current =\n* A\n* B\n* C\n* D\n* E\n* F\n* G\n}}\n'''X''' is a seven-member group. "
         "They made their debut with complete members on April 1, 2024 with an album. Previously, they debuted as "
         "six members on November 27, 2023 with a single."), 2024, 7),
        ("44 'Originally as a duo'",
         ("{{Infobox group\n| current =\n* A\n* B\n* C\n}}\n'''X''' is a three-member group. Originally as a duo, "
         "they made their debut on August 27, 2023."), 2023, 2),
    ]
    for name, text, year, want in cases:
        got = sizes.debut_size(text, year)["n"]
        r.check(name, got == want, f"got {got}, want {want}")

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_title = {g["title"]: g for g in fixture["groups"]}
    expect = {"Red Velvet": 4, "AOA": 8, "GFRIEND": 6, "Crayon Pop": 5, "Weki Meki": 8, "PRISTIN": 10,
              "LOONA": 12, "H1-KEY": 4, "LIVE HIGH": 4, "BADKIZ": 5, "PRITTI-G": None, "BABYMONSTER": 7}
    wrong = {t: (by_title.get(t, {}).get("n"), n) for t, n in expect.items() if by_title.get(t, {}).get("n") != n}
    r.check("45 reviewed groups have the expected debut size in the fixture", not wrong, str(wrong))
    titles = [g["title"] for g in fixture["groups"]]
    r.check("46 one entry per Kpop Wiki title", len(titles) == len(set(titles)))
    r.check("47 duplicate titles keep the earliest year",
            by_title["BADKIZ"]["year"] == 2014 and by_title["PRITTI-G"]["year"] == 2015
            and by_title["LIVE HIGH"]["year"] == 2013)
    btriple = ("{{Infobox group\n| former =\n* A\n* B\n* C\n* D\n}}\n'''Btriple''' (비트리플) was a project "
               "four-member girl group under LSJ Company. They debuted on December 17, 2019.")
    r.check("48 'was a project four-member' (one modifier word) gives 4",
            sizes.debut_size(btriple, 2019)["n"] == 4 and by_title["Btriple"]["n"] == 4,
            f"{sizes.debut_size(btriple, 2019)} fixture {by_title['Btriple']['n']}")
    crayon = by_title["Crayon Pop"]
    r.check("49 hangul from the lead parenthesis when the infobox has none (Crayon Pop, Melon 2013)",
            crayon["hangul"] == "크레용팝" and any(x["year"] == 2013 for x in crayon["hits"]["melon"])
            and sizes.hangul_name("{{Infobox group\n}}\n'''X''' (엑스) is a group.") == "엑스",
            crayon["hangul"])

    # The planning rows are now a historical fixture. Rows that had a size must keep it, except the
    # documented corrections. Undetermined rows may gain a size. Only the duplicate LA FLOR 2023 row goes.
    with SIZES_ROWS.open(encoding="utf-8") as f:
        ref = list(csv.DictReader(f))
    mine = {(r_["year"], r_["group"]): r_ for r_ in bd.sizes_rows(fixture, (2022, 2023, 2024))}
    problems = []
    for old in ref:
        key = (old["year"], old["group"])
        if key not in mine:
            if key not in SIZES_REMOVED:
                problems.append(f"missing {key}")
            continue
        new = mine[key]
        if old["n"] and new["n"] != old["n"] and key not in SIZES_CORRECTED:
            problems.append(f"changed {key} {old['n']} -> {new['n']}")
    corrected_ok = all(mine.get(k, {}).get("n") == v for k, v in SIZES_CORRECTED.items())
    r.check("14 planning size rows 2022-2024 kept, except documented corrections", not problems and corrected_ok,
            "; ".join(problems[:5]))


def _lines(rows: tuple[str, ...]) -> str:
    return "\n".join(rows)


def _matching(r: _Run) -> None:
    false_lines = (
        'In 2023, 42 singles achieved number one. "Bubble" Rush Stars Curious appear in prose here.',
        "| <ref>{{Cite web|trans-title=Blackpink beats Crush CocaNButter Stars|url=x}}</ref>",
        "| <ref>{{Cite web|script-title=ko:x|trans-title=September 4th week Stars rankings",
        "| {{Dts|January 7}}",
        '| "5, 4, 3 (Pretty Woman)"',
        '| "Rush Hour"',
        '| "[[Curious (song)|Curious]]"',
        "| footer = Bubble NewJeans",
        "| [[Lee Seung-gi]]",
        "| April 5, 2015",
    )
    cells = match.win_cells(_lines(false_lines))
    for name in ("Bubble", "Pretty", "Rush", "Stars", "Curious", "CocaNButter", "January", "GI", "APRIL",
                 "NewJeans"):
        r.check(f"15 no false win: {name}", match.match_win(name, cells) is None, str(cells))
    true_lines = (
        "| [[NewJeans]]<!-- 1st -->",
        "| [[Illit]]",
        '| rowspan="2" | [[Meovv]]',
        '| rowspan="2 | [[Kiss of Life (group)|Kiss of Life]]',
        "| [[CSR (group)|CSR]]<!-- 1st -->",
        "| [[Katseye]]",
        "| [[April (girl group)|April]]",
    )
    true_cells = match.win_cells(_lines(true_lines))
    for title in ("NewJeans", "ILLIT", "MEOVV", "KISS OF LIFE", "CSR", "KATSEYE", "APRIL"):
        r.check(f"16 true win: {title}", match.match_win(title, true_cells) is not None, str(true_cells))
    article_lines = (
        "==List of winners==", "===2013===", "| [[Crayon Pop]]", "===2014===", "| [[Red Velvet]]",
        "===2015 to present===", "| [[Twice]]", "==Achievements by artists==", "| [[Twice]]", "| [[Crayon Pop]]",
    )
    article = _lines(article_lines)
    sec = match.year_section(article, 2014)
    r.check("17 redirect: only the year section is read",
            match.match_win("Red Velvet", match.win_cells(sec)) is not None
            and match.match_win("Crayon Pop", match.win_cells(sec)) is None
            and match.year_section(article, 2016) == "")
    cells_l, fmt = match.winner_cells("* 02.28 [[Miss A]]<!--<sup>1st</sup>--> \"'''Touch'''\"\n* see also")
    r.check("18 list-format year read when no table lines",
            fmt == "list" and match.match_win("Miss A", cells_l) is not None
            and match.match_win("Touch", cells_l) is None)
    melon = ("\n\n1\n\n[![a](x)](/album/detail.htm?albumId=1)\n\n[TWS\xa0(투어스)](/artist/detail.htm?artistId=1 \"t\")"
             "\n\n2\n\n[![b](x)](/album/detail.htm?albumId=2)\n\n[Wanna One (워너원)](/artist/detail.htm?artistId=2)")
    ent = match.melon_entries(melon)
    r.check("19 Melon rank and artist parsed, boundary match",
            ent == [(1, "TWS (투어스)"), (2, "Wanna One (워너원)")] and match.match_melon("TWS", "", ent) == (1, "TWS (투어스)")
            and match.match_melon("ONE (group)", "", ent) is None, str(ent))
    kr = [(82, "레이디스 코드"), (68, "러블리즈"), (5, "Red Velvet - IRENE & SEULGI")]
    r.check("19b Melon hangul-only names match through the infobox hangul (spaces ignored)",
            match.match_melon("LADIES' CODE", "레이디스코드", kr) == (82, "레이디스 코드")
            and match.match_melon("Lovelyz", "러블리즈", kr) == (68, "러블리즈")
            and match.match_melon("Red Velvet", "레드벨벳", kr) is None)
    circ = [(3, "트와이스 (TWICE)"), (9, "스테이씨(STAYC)"), (12, "아이브 (IVE)")]
    r.check("20 Circle exact name parts, hangul without spaces",
            match.match_circle("TWICE", "", circ) == (3, "트와이스 (TWICE)")
            and match.match_circle("Stacy", "스 테이씨", circ) == (9, "스테이씨(STAYC)")
            and match.match_circle("IV", "", circ) is None)
    sp = [(10, "NewJeans"), (20, "Heart"), (30, "ILLIT")]
    r.check("21 Spotify exact name, known collisions excluded",
            match.match_spotify("NewJeans", sp) == (10, "NewJeans") and match.match_spotify("Heart (group)", sp) is None
            and match.match_spotify("NewJean", sp) is None)


def _group(year: int, title: str, n: int | None, hits: dict[str, Any], unit: bool = False,
           current: int = 0, former: int = 0) -> dict[str, Any]:
    base = {"win": [], "melon": [], "circle": [], "spotify": None}
    base.update(hits)
    return {"year": year, "title": title, "name": title, "hangul": "", "n": n, "sizeSource": "lead_debut" if n else None,
            "current": current, "former": former, "unit": unit, "source": "x", "hits": base}


def _toy_fixture() -> dict[str, Any]:
    gs = [
        _group(2015, "A", 5, {"win": [{"year": 2018, "program": "Music Bank", "text": "a"}]}),  # Y+3: outside
        _group(2015, "B", 5, {"melon": [{"year": 2014, "rank": 1, "text": "b"}]}),  # before debut: outside
        _group(2015, "C", 7, {"circle": [{"year": 2017, "rank": 5, "text": "c"}]}),  # Y+2: inside
        _group(2015, "D", 4, {"spotify": {"rank": 1, "text": "d"}}),  # snapshot only
        _group(2016, "E", None, {}, current=6, former=2),
        _group(2016, "F", 3, {}, unit=True),
        _group(2024, "G", 5, {"win": [{"year": 2024, "program": "Inkigayo", "text": "g"}]}),
        *[_group(2016, f"Z{i}", 3 + i % 5, {}) for i in range(10)],
    ]
    return {"coverage": {"winYears": [2012, 2026], "partialYears": {"win": [2026]}, "melonYears": [2012, 2025],
                         "circleYears": [2012, 2025], "gaps": [{"program": "Inkigayo", "year": 2012}]},
            "sources": {"spotify": {"retrieved": "2026-10-19T00:00:00Z", "rows": 2500}}, "groups": gs}


def _analysis(r: _Run) -> None:
    fx = _toy_fixture()
    cfg = an.Config(first_year=2012, last_year=2024, eras=((2015, 2016),), exact_b=200)
    a = an.analyze(fx, cfg)
    succ = {g["title"] for g in a["successes"]}
    r.check("22 window: Y+3 and pre-debut hits do not count, Y+2 does",
            "A" not in {g["title"] for g in a["successes"] if g["winYears"]} and "C" in succ
            and not any(g["title"] == "B" and g["melonYears"] for g in a["successes"]))
    pooled = a["pooled"]["default"]["measures"]
    r.check("23 Spotify stays out of the composite",
            sum(x["k"] for x in pooled["any"]["rows"]) == 1 and "test" not in pooled["spotify"])
    r.check("24 incomplete cohort kept out of tests by default",
            a["incompleteYears"] == [2024] and a["counts"]["default"]["tested"] == a["counts"]["default"]["all"] - 1)
    a2 = an.analyze(fx, an.Config(first_year=2012, last_year=2024, eras=((2015, 2016),), exact_b=200,
                                  include_incomplete=True))
    r.check("25 --include-incomplete adds it", a2["counts"]["default"]["tested"] == a2["counts"]["default"]["all"])
    r.check("26 range variant uses current + former, units variant adds units",
            any(g["title"] == "E" for g in an.select(fx, "range", cfg))
            and next(g for g in an.select(fx, "range", cfg) if g["title"] == "E")["size"] == 8
            and any(g["title"] == "F" for g in an.select(fx, "units", cfg))
            and not any(g["title"] in ("E", "F") for g in an.select(fx, "default", cfg)))
    r.check("27 coverage gaps reach the cohorts whose window they fall in",
            a["cohorts"][0]["gaps"] == ["Inkigayo 2012"] and a["cohorts"][1]["gaps"] == [])
    r.check("28 buckets and labels", an.bucket_labels((3, 4, 5, 6)) == ["3명 이하", "4명", "5명", "6명", "7명 이상"]
            and [an.bucket_of(n, (3, 4, 5, 6)) for n in (1, 3, 4, 6, 7, 24)] == [0, 0, 1, 3, 4, 4])


def _gate_module() -> Any:
    p = ROOT / "scripts/validate_report_data.py"
    spec = importlib.util.spec_from_file_location("validate_report_data", p)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {p}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _report(r: _Run) -> None:
    import jsonschema

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cfg = an.Config(exact_b=2000)
    a = an.analyze(fixture, cfg)
    rep = build_report(a)
    schema = json.loads((ROOT / "packages/report-schema/report.schema.json").read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(rep))
    r.check("29 report is schema-valid", not errs, "; ".join(e.message[:80] for e in errs[:3]))
    gate = _gate_module()
    tmp = ROOT / "modules/cohort-size/output/.selftest-report.json"
    tmp.write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    try:
        views, _ = gate.known_tunable_views()
        problems = gate.check_report(str(tmp), views)
    finally:
        tmp.unlink()
    r.check("30 chart data and visualization contract gate is clean", not problems, "; ".join(problems[:3]))
    blob = json.dumps(rep, ensure_ascii=False)
    r.check("31 no em dash, no spaced hyphen dash", not re.search("[" + "".join(map(chr, (0x2014, 0x2015, 0x2E3A, 0x2E3B))) + "]", blob)
            and " - " not in blob)
    r.check("32 section questions fit one line (<= 21 chars)", all(len(s["question"]) <= 21 for s in rep["sections"]))
    r.check("33 verdict wording absent", not any(w in blob for w in ("상관없다", "무관하다", "중요하지 않다")))
    summary_names = [d["name"] for d in rep["summary"]["data"]]
    rows = [x for x in a["pooled"]["default"]["measures"]["any"]["rows"] if x["n"]]
    r.check("34 summary k/n text comes from the analysis",
            all(f"{x['k']}/{x['n']}팀" in nm for x, nm in zip(rows, summary_names, strict=True)))
    a_again = an.analyze(fixture, cfg)
    r.check("35 determinism: same fixture, same analysis", json.dumps(a, sort_keys=True) == json.dumps(a_again, sort_keys=True))
    titles = {g["title"] for g in fixture["groups"]
              if 2022 <= g["year"] <= 2024 and not g["unit"] and g["n"]
              and (g["hits"]["win"] or g["hits"]["melon"] or g["hits"]["circle"])}
    r.check("36 2022-2024 matches equal the planning count plus H1-KEY", titles == SANITY_2022_2024,
            f"extra {sorted(titles - SANITY_2022_2024)} missing {sorted(SANITY_2022_2024 - titles)}")
    by_title = {g["title"]: g for g in fixture["groups"]}
    r.check("36b Melon hangul matches reach the fixture (Ladies' Code 2013 #82, Lovelyz 2016 #68)",
            {(x["year"], x["rank"]) for x in by_title["LADIES' CODE"]["hits"]["melon"]} >= {(2013, 82)}
            and {(x["year"], x["rank"]) for x in by_title["Lovelyz"]["hits"]["melon"]} >= {(2016, 68)})
    d = a["determination"]
    r.check("36c determined and undetermined split adds up to the tested non-unit groups",
            d["determined"]["n"] == a["counts"]["default"]["tested"]
            and d["determined"]["n"] + d["undetermined"]["n"]
            == sum(1 for g in fixture["groups"] if g["year"] in set(a["completeYears"]) and not g["unit"]))
    r.check("33b the V upper-bound wording is gone", "이하 수준" not in blob)
    x = a["exact"]
    era = {e["label"]: e for e in x["eras"]}
    cell = {(e["label"], c["label"]): c for e in x["eras"] for c in e["cells"]}
    r.check("53 exact columns and eras: labels, cells add up to the era",
            x["labels"] == ["3명 이하", "4명", "5명", "6명", "7명", "8명", "9명 이상"]
            and list(era) == ["2012~17", "2018~23", "2024~26"]
            and all(sum(c["n"] for c in e["cells"]) == e["n"] and sum(c["k"] for c in e["cells"]) == e["k"]
                    for e in x["eras"]))
    six = {s["title"] for s in cell[("2018~23", "6명")]["successes"]}
    ph17 = era["2012~17"]["postHoc"]["8명 이상 vs 8명 미만"]
    r.check("54 known cells (checked against an independent count of the same fixture)",
            (cell[("2012~17", "8명")]["k"], cell[("2012~17", "8명")]["n"]) == (4, 6)
            and (cell[("2012~17", "9명 이상")]["k"], cell[("2012~17", "9명 이상")]["n"]) == (4, 5)
            and (ph17["k1"], ph17["n1"], ph17["k2"], ph17["n2"]) == (8, 11, 8, 173)
            and (cell[("2018~23", "6명")]["k"], cell[("2018~23", "6명")]["n"]) == (6, 23)
            and six == {"IVE", "LE SSERAFIM", "I-dle", "STAYC", "EVERGLOW (group)", "Billlie"}
            and (cell[("2018~23", "8명")]["k"], cell[("2018~23", "8명")]["n"]) == (0, 13), str(six))
    h2h = [s for s in cell[("2024~26", "8명")]["successes"] if s["title"] == "Hearts2Hearts"]
    r.check("55 2025-2026 debuts are in the in-progress row and never tested (Hearts2Hearts 8, wins counted)",
            not era["2024~26"]["closed"] and "postHoc" not in era["2024~26"] and bool(h2h) and h2h[0]["year"] == 2025
            and a["incompleteYears"] == [2024, 2025, 2026]
            and a["pooled"]["default"]["measures"]["any"]["test"]["n"]
            == sum(1 for g in fixture["groups"] if g["year"] <= 2023 and not g["unit"] and g["n"]))
    fam = era["2018~23"]["postHoc"]
    r.check("56 post-hoc family: every column plus the 8+ split, Holm at least the raw p",
            len(fam) == 8 and all(v["holmFamily"] == 8 and v["pHolm"] >= v["p"] - 1e-12 for v in fam.values())
            and all(_close(v["p"], stats.fisher_exact_2x2(v["k1"], v["n1"] - v["k1"], v["k2"], v["n2"] - v["k2"]))
                    for v in fam.values()))
    exact_chart = next(c for c in rep["charts"] if c["id"] == "exact-by-era")
    r.check("57 exact chart in the era section, names on screen, in-progress label",
            exact_chart["section"] == "era"
            and any(i.startswith("성공 팀 · 2018~23 · 6명 6/23:") and "LE SSERAFIM" in i for i in rep["insights"])
            and any("2024~26 진행 중" in d["name"] for d in exact_chart["data"])
            and any(i.get("chartId") == "exact-by-era" and "사후 비교" in i["limits"] for i in rep["inferences"]))
    era_tests = next(c for c in rep["charts"] if c["id"] == "era-tests")
    r.check("58 era-tests shows no test value for the in-progress row",
            not any("진행 중" in d["name"] for d in era_tests["data"]))
    obs = x["cut"]["observedYears"]
    r.check("59 partial 2026 cohort and mixed observation stated on screen",
            "10월 하순~12월" in rep["reliability"]["missing"] and "10월 하순~12월" in exact_chart["reliability"]["missing"]
            and obs["2024"] > 2.5 and obs["2026"] < 1.0, str(obs))
    r.check("60 post-hoc limits name the era boundaries and the 8 cut as chosen after seeing the data",
            any(i.get("chartId") == "exact-by-era" and "시기 경계" in i["limits"] and "8명이라는 기준" in i["limits"]
                for i in rep["inferences"]))
    im = a["imputation"]
    tested_nonunit = d["determined"]["n"] + d["undetermined"]["n"]
    r.check("50 imputation: five schemes, all groups back in, ranges ordered",
            set(im["schemes"]) == {"resampleDeterminedFailures", "resampleCheckedSample", "uniformInRange",
                                   "allAtFinal", "allAtUpper"}
            and all(s["n"] == tested_nonunit and s["pExactMin"] <= s["pExactMax"] for s in im["schemes"].values())
            and im["sampleN"] == min(36, d["undetermined"]["n"]))
    r.check("51 imputation is reproducible (same seeds, same ranges)", a_again["imputation"] == im)
    inf_limits = rep["inferences"][1]["limits"]
    lo = im["schemes"]["allAtUpper"]["pExactMin"]
    r.check("52 the imputation numbers on screen come from the analysis",
            ("<0.001" if lo < 0.001 else f"{lo:.3f}") in inf_limits and "멤버 변동 또는 인원 기록 없음" in inf_limits)


def run() -> int:
    r = _Run()
    for part in (_stats, _sizes, _matching, _analysis, _report):
        part(r)
    print(f"selftest: {r.passed} passed · {r.failed} failed")
    return 0 if r.failed == 0 else 1
