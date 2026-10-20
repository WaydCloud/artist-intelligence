"""Parse the four success sources and match group names against them.

Purpose    Turn raw captures (Wikipedia wikitext, Melon year-end page, Circle year-end JSON,
           kworb listener table) into facts, and decide which group a row belongs to.
Boundary   Pure functions over strings. No file or network access here, so tests can feed crafted lines.
Invariant  Win matching reads table lines only and strips refs, dts dates, cell attributes and quoted
           song titles before matching. Dropping any of these steps brings back known false hits
           (Bubble, Pretty, Rush, Stars, Curious, CocaNButter, January) and inflates the win counts.
Failure    An unparsable source yields an empty list. The caller reports it as a coverage gap, never as zero.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Template parameter lines ("| footer = ..."). Cell attribute lines ('| rowspan="2" | ...') are cells and stay.
_PARAM_LINE = re.compile(r'^\|\s*\w[\w ]*?\s*=\s*(?!")')
_REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?(</ref>|$)")
_DTS = re.compile(r"\{\{\s*dts\s*\|[^}]*\}\}", re.IGNORECASE)
_CELL_ATTR = re.compile(r'\w+="[^"|]*"?')  # also unclosed ones
_LINKED_TITLE = re.compile(r'"\[\[.*?\]\]"')
_PLAIN_TITLE = re.compile(r'"[^"]*"')
_TITLE_PAREN = re.compile(r"\s*\(.*?\)\s*$")
_HEADING = re.compile(r"^(=+)\s*(.*?)\s*=+\s*$")

# Names that are also dates, numbers or common words. They count only as a wikilink to a group page.
# Months and all-digit names are caught by rule. The rest were found by reading every hit of a
# 2012 to 2024 build: each matched dates, episode numbers, scores or other acts' names.
LINK_ONLY = frozenset({"january", "date", "episode", "destiny", "one"})
_MONTHS = frozenset(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
)
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
_QUALIFIER = re.compile(r"^(.*?)\s*\((.*?)\)\s*$")

# Spotify names that belong to unrelated acts with the same name (a Mexican band, a US band,
# a Danish band). Found by reading every Spotify hit. Excluded at build time and listed in the fixture.
SPOTIFY_COLLISIONS = frozenset({"camila", "heart", "aqua"})


def is_link_only(name: str) -> bool:
    n = norm(name)
    return n in LINK_ONLY or n in _MONTHS or n.isdigit()


def _link_hit(name: str, cell: str) -> str | None:
    """A wikilink whose target is the name with a group/band qualifier, e.g. [[april (girl group)|april]]."""
    for m in _LINK.finditer(cell):
        target = m.group(1).strip()
        q = _QUALIFIER.match(target)
        if q and q.group(1) == name and re.search(r"group|band", q.group(2)):
            return m.group(0)
    return None


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def match_name(title: str) -> str:
    """Kpop Wiki title without a trailing "(group)"-style qualifier."""
    return _TITLE_PAREN.sub("", title)


def name_pattern(title: str) -> re.Pattern[str]:
    """Case-insensitive name with boundaries. A hyphen counts as part of a word.

    Without the hyphen rule, the 2013 group "GI" matches "lee seung-gi" and "lee hong-gi"
    and gets five false wins. Names that contain a hyphen (H1-KEY, I-dle) are unaffected.
    """
    name = norm(match_name(title))
    return re.compile(r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])")


# ── music show wins ────────────────────────────────────────────────────────


def wikitext_body(raw_md: str) -> str:
    parts = raw_md.split("```wikitext", 1)
    if len(parts) < 2:
        return ""
    return parts[1].rsplit("```", 1)[0]


def year_section(body: str, year: int) -> str:
    """Lines under the first heading that is exactly the year, up to the next heading of the same or higher level.

    Redirect captures hold the whole program article. Only this section belongs to the year.
    Other sections (for example "Achievements by artists") list wins of every year and must not be read.
    """
    lines = body.splitlines()
    start, level = None, 0
    for i, ln in enumerate(lines):
        m = _HEADING.match(ln.strip())
        if m and m.group(2) == str(year):
            start, level = i + 1, len(m.group(1))
            break
    if start is None:
        return ""
    out: list[str] = []
    for ln in lines[start:]:
        m = _HEADING.match(ln.strip())
        if m and len(m.group(1)) <= level:
            break
        out.append(ln)
    return "\n".join(out)


def win_cells(body: str) -> list[str]:
    """Artist cells of a winner table, lowercased. Captions, citations, dates and song titles are dropped."""
    cells: list[str] = []
    for ln in body.splitlines():
        if not ln.startswith("|") or _PARAM_LINE.match(ln):
            continue
        cell = _REF.sub("", ln)
        cell = _DTS.sub("", cell)
        cell = _CELL_ATTR.sub("", cell)
        cell = _LINKED_TITLE.sub("", cell)
        cell = _PLAIN_TITLE.sub("", cell)
        cells.append(norm(cell))
    return cells


_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def list_cells(body: str) -> list[str]:
    """Bulleted winner lines (a date, a linked artist, a quoted song), cleaned like table cells.

    Two early years of one program are bulleted lists, not tables. The caller uses this only
    when a section has no table lines, so prose bullets elsewhere (see also, notes) are not read.
    """
    cells: list[str] = []
    for ln in body.splitlines():
        if not ln.startswith("*"):
            continue
        cell = _COMMENT.sub("", ln)
        cell = _REF.sub("", cell)
        cell = _LINKED_TITLE.sub("", cell)
        cell = _PLAIN_TITLE.sub("", cell)
        cells.append(norm(cell))
    return cells


def winner_cells(body: str) -> tuple[list[str], str]:
    """Table cells, or list cells when the section has no table lines. Returns the cells and the format."""
    cells = win_cells(body)
    if cells:
        return cells, "table"
    return list_cells(body), "list"


def match_win(title: str, cells: list[str]) -> str | None:
    """First matched text for this group in the cells, or None."""
    name = norm(match_name(title))
    if is_link_only(name):
        for c in cells:
            hit = _link_hit(name, c)
            if hit:
                return hit
        return None
    pat = name_pattern(title)
    for c in cells:
        m = pat.search(c)
        if m:
            return m.group(0)
    return None


# ── Melon year-end ─────────────────────────────────────────────────────────

_MELON_RANK = re.compile(r"(?m)^(\d{1,3})\s*\n\s*\n\[!\[")
_MELON_ARTIST = re.compile(r"\[([^\]]+)\]\(/artist/detail\.htm\?artistId=")


def melon_entries(raw_md: str) -> list[tuple[int, str]]:
    """(rank, artist) per song row. A song with two credited artists yields two entries with the same rank."""
    marks = list(_MELON_RANK.finditer(raw_md))
    out: list[tuple[int, str]] = []
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(raw_md)
        seen: list[str] = []
        for a in _MELON_ARTIST.findall(raw_md[m.end() : end]):
            a = re.sub(r"\s+", " ", a.replace("&nbsp;", " ")).strip()
            if a not in seen:
                seen.append(a)
        out.extend((int(m.group(1)), a) for a in seen)
    return out


def match_melon(title: str, entries: list[tuple[int, str]]) -> tuple[int, str] | None:
    """Best (lowest) rank whose artist text contains the group name with boundaries."""
    if is_link_only(match_name(title)):
        return None  # no wikilinks on Melon, so a common-word name cannot be told apart
    pat = name_pattern(title)
    hits = [(r, a) for r, a in entries if pat.search(norm(a))]
    return min(hits) if hits else None


# ── Circle year-end album ──────────────────────────────────────────────────


def circle_entries(raw_md: str) -> list[tuple[int, str]]:
    parts = raw_md.split("```json", 1)
    if len(parts) < 2:
        return []
    data = json.loads(parts[1].rsplit("```", 1)[0])
    out: list[tuple[int, str]] = []
    for row in data.get("List", {}).values():
        try:
            rank = int(str(row.get("SERVICE_RANKING")))
        except ValueError:
            continue
        out.append((rank, str(row.get("ARTIST_NAME") or "")))
    return sorted(out)


def _parts(name: str) -> set[str]:
    """'Stray Kids (스트레이 키즈)' gives {'straykids', '스트레이키즈'}: parts split on parentheses, spaces removed."""
    return {re.sub(r"\s+", "", p.lower()) for p in re.split(r"[()]", name) if p.strip()}


def circle_keys(title: str, hangul: str) -> set[str]:
    keys = {re.sub(r"\s+", "", match_name(title).lower())}
    if hangul:
        keys.add(re.sub(r"\s+", "", hangul.lower()))
    return keys


def match_circle(title: str, hangul: str, entries: list[tuple[int, str]]) -> tuple[int, str] | None:
    """Exact match of a name part against the English title or the hangul name, spaces removed."""
    keys = circle_keys(title, hangul)
    hits = [(r, a) for r, a in entries if _parts(a) & keys]
    return min(hits) if hits else None


# ── Spotify monthly listeners (kworb snapshot) ─────────────────────────────

_KWORB_ROW = re.compile(r'<tr><td>(\d+)</td><td class="text"><div><a href="artist/[^"]+">([^<]+)</a>')


def spotify_entries(raw_md: str) -> list[tuple[int, str]]:
    return [(int(r), n.replace("&amp;", "&")) for r, n in _KWORB_ROW.findall(raw_md)]


def match_spotify(title: str, entries: list[tuple[int, str]]) -> tuple[int, str] | None:
    """Exact (case-insensitive) artist name."""
    key = norm(match_name(title))
    if key in SPOTIFY_COLLISIONS:
        return None
    hits = [(r, a) for r, a in entries if norm(a) == key]
    return min(hits) if hits else None


def retrieved_at(raw_md: str) -> str:
    m = re.search(r"(?m)^retrieved:\s*(\S+)", raw_md)
    return m.group(1) if m else ""


def as_dict(rank: int | None, text: str, **extra: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"text": text}
    if rank is not None:
        d["rank"] = rank
    d.update(extra)
    return d
