"""Debut lineup size of one Kpop Wiki group page.

Purpose    Decide the debut size of a girl group from its page wikitext (section 0).
Boundary   Reads one page at a time. Does not fetch anything and does not guess a size it cannot read.
Invariant  Must reproduce the earlier planning count row for row. If a regex drifts,
           the 2022 to 2024 regression rows in tests/fixtures stop matching and selftest fails.
Failure    A page without a readable size gets n=None and keeps current/former counts for the range variant.
"""

from __future__ import annotations

import re
from typing import Any

_WORDS = {
    w: i
    for i, w in enumerate(
        ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen"]
    )
}

# Lead sentence patterns, tried in this order. Order matters: the first hit with a number wins.
_LEAD_PATTERNS = (
    r"originally (?:as |with |consisting of |a |an )?(\w+)",
    r"debut(?:ed)? (?:as|with) (?:a |an )?(\w+)[- ]member",
    r"debut(?:ed)?[^.]{0,60} with (\w+) members",
    r"originally (?:a |an )?(\w+)[- ]member",
)
_REF = re.compile(r"<ref.*?</ref>|<ref[^>]*/>", re.DOTALL)
# Case-insensitive: 2012 to 2021 pages often write "infobox musical artist" in lower case.
# The earlier planning count was case-sensitive and saw no such page in 2022 to 2024,
# so its rows are unchanged. Without re.I, Red Velvet and Crayon Pop drop out of the population.
_INFOBOX = re.compile(r"Infobox[ _](group|musical[ _]artist)", re.IGNORECASE)
_HANGUL = re.compile(r"(?m)^\|\s*hangul\s*=\s*([^\n<{]+)")

FEMALE_CATEGORY = "Category:Female groups"


def _num(tok: str) -> int | None:
    tok = tok.lower()
    return int(tok) if tok.isdigit() else _WORDS.get(tok)


def _members(field: str, text: str) -> list[str]:
    m = re.search(r"\|\s*" + field + r"\s*=(.*?)(?=\n\s*\||\n\}\})", text, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    return [n for n in re.split(r"<br\s*/?>|\n|\*|,", body) if re.sub(r"[\[\]{}\s'|]", "", n)]


def is_unit(categories: list[str]) -> bool:
    """Sub-units and project groups are kept apart (sensitivity variant b)."""
    return any(("Sub-unit" in c) or ("Project group" in c) or ("project group" in c) for c in categories)


def is_girl_group(categories: list[str], text: str) -> bool:
    return FEMALE_CATEGORY in categories and bool(_INFOBOX.search(text))


def hangul_name(text: str) -> str:
    m = _HANGUL.search(text)
    return m.group(1).strip() if m else ""


def debut_size(text: str) -> dict[str, Any]:
    """Return n (or None), the source of n, and the current/former member counts.

    Rule: 1) lead sentence "Originally as N" or "debuted as a N-member" gives n (lead_debut).
    2) Else, no former members listed gives n = current + inactive (current_no_former).
    3) Else n is None. The range is current (low) to current + former (high).
    """
    i0 = text.find("'''")
    lead = _REF.sub("", text[i0 : i0 + 1500])
    n: int | None = None
    src: str | None = None
    hit = None
    for q in _LEAD_PATTERNS:
        hit = re.search(q, lead, re.IGNORECASE)
        if hit and _num(hit.group(1)):
            break
        hit = None
    if hit:
        n, src = _num(hit.group(1)), "lead_debut"
    cur = _members("current", text) + _members("inactive", text)
    past = _members("past", text) + _members("former", text)
    if n is None and cur and not past:
        n, src = len(cur), "current_no_former"
    return {"n": n, "src": src, "current": len(cur), "former": len(past)}
