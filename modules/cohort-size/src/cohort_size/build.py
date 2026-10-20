"""Build the facts-only fixture from the planning repo RAW captures.

Purpose    Read Kpop Wiki debut categories and the four success sources once, and write a small
           deterministic JSON with groups and per-group hits. `analyze` reads only that JSON.
Boundary   Stores facts only: year, program, rank, artist text as matched, lineup counts.
           No page text, no album art, no song lists. Raw captures stay in the planning repo.
Invariant  Same RAW in, byte-identical fixture out (no timestamps, sorted keys and lists).
           A missing page is recorded in `coverage.gaps`. It must never be written as a zero.
Failure    A source id that is absent or unreadable raises with its path, so the fixture is never half built.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cohort_size import match, sizes

# RAW ids in the planning repo (data/references). Year order matters: zip pairs years with ids.
KPOPWIKI_IDS: dict[int, int] = {**{2012 + i: 901 + i for i in range(10)}, 2022: 484, 2023: 485, 2024: 486}
WIN_IDS: list[int] = [*range(801, 856), *range(761, 791)]
MELON_IDS: list[int] = [*range(856, 866), *range(791, 795)]
CIRCLE_IDS: list[int] = [*range(866, 876), *range(795, 799)]
SPOTIFY_ID = 799

PROGRAMS = ("Music Bank", "Inkigayo", "M Countdown", "Show! Music Core", "Show Champion", "The Show")
WIN_YEARS = range(2012, 2027)
CHART_YEARS = range(2012, 2026)
_WIN_TITLE = re.compile(r"^List of (.+?) Chart winners \((\d{4})\)$")
_FIXTURE_VERSION = 1


def _dir(root: Path, slice_dir: str, rid: int) -> Path:
    prefix = slice_dir.split("-", 1)[0]
    return root / slice_dir / f"{prefix}-{rid:03d}"


def _read(p: Path) -> str:
    if not p.exists():
        raise FileNotFoundError(f"RAW file missing: {p}")
    return p.read_text(encoding="utf-8")


def _meta(d: Path) -> dict[str, Any]:
    return json.loads(_read(d / "meta.json"))


def load_groups(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for year, rid in KPOPWIKI_IDS.items():
        doc = json.loads(_read(_dir(root, "R04-cases", rid) / "source.json"))
        for batch in doc["batches"]:
            for page in batch["query"]["pages"]:
                cats = [c["title"] for c in page.get("categories", [])]
                revs = page.get("revisions") or []
                text = revs[0]["slots"]["main"]["content"] if revs else ""
                if not sizes.is_girl_group(cats, text):
                    continue
                s = sizes.debut_size(text)
                out.append({
                    "year": year,
                    "title": page["title"],
                    "name": match.match_name(page["title"]),
                    "hangul": sizes.hangul_name(text),
                    "n": s["n"],
                    "sizeSource": s["src"],
                    "current": s["current"],
                    "former": s["former"],
                    "unit": sizes.is_unit(cats),
                    "source": f"R04-{rid:03d}",
                })
    return out


def load_wins(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Win pages as (program, year, cells), plus the page index for the reliability line."""
    pages: list[dict[str, Any]] = []
    index: list[dict[str, Any]] = []
    for rid in WIN_IDS:
        d = _dir(root, "R08-fandom-market", rid)
        meta = _meta(d)
        m = _WIN_TITLE.match(str(meta.get("title", "")))
        if not m:
            raise ValueError(f"unexpected win page title in {d}: {meta.get('title')!r}")
        program, year = m.group(1), int(m.group(2))
        if program not in PROGRAMS:
            raise ValueError(f"unknown program {program!r} in {d}")
        redirect = "Redirect:" in str(meta.get("notes_factual", ""))
        body = match.wikitext_body(_read(d / "raw.md"))
        if redirect:
            body = match.year_section(body, year)
        cells, fmt = match.winner_cells(body)
        if not cells:
            raise ValueError(f"no winner rows read from {d} ({program} {year})")
        pages.append({"program": program, "year": year, "cells": cells})
        index.append({"id": f"R08-{rid}", "program": program, "year": year, "redirect": redirect,
                      "format": fmt, "lines": len(cells)})
    return pages, index


def _yearly(root: Path, ids: list[int], parse: Any) -> list[dict[str, Any]]:
    out = []
    for rid in ids:
        d = _dir(root, "R08-fandom-market", rid)
        meta = _meta(d)
        year = int(str(meta.get("date", ""))[:4])
        entries = parse(_read(d / "raw.md"))
        out.append({"id": f"R08-{rid}", "year": year, "entries": entries})
    return out


def build(root: Path) -> dict[str, Any]:
    groups = load_groups(root)
    win_pages, win_index = load_wins(root)
    melon = _yearly(root, MELON_IDS, match.melon_entries)
    circle = _yearly(root, CIRCLE_IDS, match.circle_entries)
    sp_raw = _read(_dir(root, "R08-fandom-market", SPOTIFY_ID) / "raw.md")
    spotify = match.spotify_entries(sp_raw)

    hits: dict[str, dict[str, Any]] = {}
    for g in groups:
        key = f"{g['year']}|{g['title']}"
        h: dict[str, Any] = {"win": [], "melon": [], "circle": [], "spotify": None}
        for p in win_pages:
            t = match.match_win(g["title"], p["cells"])
            if t:
                h["win"].append({"year": p["year"], "program": p["program"], "text": t})
        for page in melon:
            r = match.match_melon(g["title"], page["entries"])
            if r:
                h["melon"].append({"year": page["year"], "rank": r[0], "text": r[1]})
        for page in circle:
            r = match.match_circle(g["title"], g["hangul"], page["entries"])
            if r:
                h["circle"].append({"year": page["year"], "rank": r[0], "text": r[1]})
        sp = match.match_spotify(g["title"], spotify)
        if sp:
            h["spotify"] = {"rank": sp[0], "text": sp[1]}
        for k in ("win", "melon", "circle"):
            h[k].sort(key=lambda x: (x["year"], x.get("program", ""), x.get("rank", 0)))
        hits[key] = h

    present = {(p["program"], p["year"]) for p in win_pages}
    gaps = [{"program": pr, "year": y} for pr in PROGRAMS for y in WIN_YEARS if (pr, y) not in present]
    melon_years = sorted({p["year"] for p in melon})
    circle_years = sorted({p["year"] for p in circle})

    # Groups keep the API listing order of each year. It is stable for a given capture,
    # and it lets `sizes_rows` reproduce the planning CSV row order.
    for g in groups:
        g["hits"] = hits[f"{g['year']}|{g['title']}"]

    return {
        "fixtureVersion": _FIXTURE_VERSION,
        "note": "Facts only. Group lineup counts and matched success rows. Raw captures stay in the planning repo.",
        "sources": {
            "kpopwiki": {str(y): f"R04-{rid:03d}" for y, rid in KPOPWIKI_IDS.items()},
            "win": win_index,
            "melon": [{"id": p["id"], "year": p["year"], "rows": len(p["entries"])} for p in melon],
            "circle": [{"id": p["id"], "year": p["year"], "rows": len(p["entries"])} for p in circle],
            "spotify": {"id": f"R08-{SPOTIFY_ID}", "retrieved": match.retrieved_at(sp_raw), "rows": len(spotify)},
        },
        "coverage": {
            "programs": list(PROGRAMS),
            "winYears": [WIN_YEARS.start, WIN_YEARS.stop - 1],
            "gaps": gaps,
            "melonYears": melon_years,
            "circleYears": circle_years,
            "partialYears": {"win": [2026]},
        },
        "groups": groups,
    }


def write(fixture: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sizes_rows(fixture: dict[str, Any], years: tuple[int, ...]) -> list[dict[str, str]]:
    """Fixture groups in the column layout and row order of the planning sizes.csv."""
    gs = [g for g in fixture["groups"] if g["year"] in years]
    rows = [g for g in gs if not g["unit"] and g["n"]]
    amb = [g for g in gs if not g["unit"] and not g["n"]]
    units = [g for g in gs if g["unit"]]

    def fmt(g: dict[str, Any]) -> dict[str, str]:
        return {"year": str(g["year"]), "group": g["title"], "n": "" if g["n"] is None else str(g["n"]),
                "src": g["sizeSource"] or "", "current": str(g["current"]), "former": str(g["former"]),
                "unit": str(g["unit"])}

    return [fmt(g) for g in rows + amb + units]
