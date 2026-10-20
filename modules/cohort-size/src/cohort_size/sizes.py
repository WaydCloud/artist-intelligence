"""Debut lineup size of one Kpop Wiki group page.

Purpose    Decide the debut size of a girl group from its page wikitext (section 0).
Boundary   Reads one page at a time. Does not fetch anything and does not guess a size it cannot read.
Invariant  The lead is the text after the infobox closes. Reading from the first ''' instead picks up
           '''KR:''' inside the infobox and misses the lead sentence (Red Velvet read 5, not 4).
           A debut sentence counts only if it does not mention a re-debut and names no year other
           than the category year. Otherwise its number describes another lineup (PRITTI-G 2021,
           BABYMONSTER's 2023 pre-debut single) and puts the group in the wrong bucket.
Failure    A page without a readable size gets n=None and keeps current/former counts for the range variant.
"""

from __future__ import annotations

import re
from typing import Any

_WORDS = {
    w: i
    for i, w in enumerate(
        ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen"]
    )
}
_WORDS.update({"duo": 2, "trio": 3, "quartet": 4, "quintet": 5, "sextet": 6, "septet": 7, "octet": 8})
_NUM = r"(\d+|" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")"

# Debut sentences, tried in this order. The first hit with a number wins.
_LEAD_PATTERNS = (
    # "Originally as five", "originally as a four-member", "originally consisted of eight members"
    r"originally (?:as |with |consisting of |consisted of |a |an )*" + _NUM + r"\b",
    # "debuted as four on August 1", "debuted as a 4-member group". A trailing word is required so
    # "debuted as one of" is not read as one member.
    r"(?<![\w-])debut(?:ed)? (?:as|with) (?:a |an )?" + _NUM + r"(?=[- ]member|\s+(?:on|in|with|under|and)\b|[,.])",
    r"(?<![\w-])debut(?:ed)?[^.]{0,60} with " + _NUM + r" members",
)
# "was a 10-member girl group": used only for groups with no current member, and only when the
# number equals the former-member count. Disbanded groups otherwise have no size at all.
# One modifier word may sit before the number ("was a project four-member girl group").
_WAS_N = re.compile(r"\b(?:is|was) (?:a|an) (?:[a-z]+ )?" + _NUM + r"[- ]member", re.IGNORECASE)
# Hangul in the lead parenthesis after the bold title: '''Crayon Pop''' (크레용팝) is ...
_LEAD_HANGUL = re.compile(r"^'''[^']+'''\s*\(([^);]*)")
_REDEBUT = re.compile(r"re-?debut", re.IGNORECASE)
_YEAR = re.compile(r"\b(?:19|20)\d\d\b")
# A sentence may end inside wiki markup: ''[[Album]].'' Previously, ...
_SENTENCE = re.compile(r"[.!?]['\"]*\s+")
_REF = re.compile(r"<ref.*?</ref>|<ref[^>]*/>", re.DOTALL)
# Case-insensitive: 2012 to 2021 pages often write "infobox musical artist" in lower case.
_INFOBOX = re.compile(r"Infobox[ _](group|musical[ _]artist)", re.IGNORECASE)
_INFOBOX_OPEN = re.compile(r"\{\{\s*Infobox[ _](?:group|musical[ _]artist)", re.IGNORECASE)

FEMALE_CATEGORY = "Category:Female groups"


def _num(tok: str) -> int | None:
    tok = tok.lower()
    return int(tok) if tok.isdigit() else _WORDS.get(tok)


def infobox(text: str) -> tuple[dict[str, str], int]:
    """Top-level infobox parameters and the index where the infobox closes.

    Parameters are split on '|' at brace and bracket depth zero, so one-line infoboxes
    ("|associated=[[VIVIZ]]|former=|inactive=* ...}}") parse the same as multi-line ones.
    """
    m = _INFOBOX_OPEN.search(text)
    if not m:
        return {}, 0
    i, depth_b, depth_k = m.start() + 2, 1, 0
    parts: list[str] = []
    buf: list[str] = []
    while i < len(text):
        two = text[i : i + 2]
        if two == "{{":
            depth_b += 1
            buf.append(two)
            i += 2
            continue
        if two == "}}":
            depth_b -= 1
            if depth_b == 0:
                parts.append("".join(buf))
                end = i + 2
                break
            buf.append(two)
            i += 2
            continue
        if two == "[[":
            depth_k += 1
        elif two == "]]":
            depth_k = max(0, depth_k - 1)
        if two in ("[[", "]]"):
            buf.append(two)
            i += 2
            continue
        ch = text[i]
        if ch == "|" and depth_b == 1 and depth_k == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    else:
        parts.append("".join(buf))
        end = len(text)
    params: dict[str, str] = {}
    for p in parts[1:]:
        key, eq, val = p.partition("=")
        if eq:
            params.setdefault(key.strip().lower(), val)
    return params, end


def _members(params: dict[str, str], field: str) -> list[str]:
    body = params.get(field, "")
    return [n for n in re.split(r"<br\s*/?>|\n|\*|,", body) if re.sub(r"[\[\]{}\s'|]", "", n)]


def lead_text(text: str) -> str:
    _, end = infobox(text)
    rest = text[end:]
    i0 = rest.find("'''")
    i0 = max(i0, 0)
    return _REF.sub("", rest[i0 : i0 + 1500])


def is_unit(categories: list[str]) -> bool:
    """Sub-units and project groups are kept apart (sensitivity variant b)."""
    return any(("Sub-unit" in c) or ("Project group" in c) or ("project group" in c) for c in categories)


def is_girl_group(categories: list[str], text: str) -> bool:
    return FEMALE_CATEGORY in categories and bool(_INFOBOX.search(text))


def hangul_name(text: str) -> str:
    """Infobox `hangul`, else the hangul in the lead parenthesis. Melon and Circle match on it."""
    params, _ = infobox(text)
    val = re.split(r"<br\s*/?>|\{\{|<", params.get("hangul", ""))[0].strip()
    if val:
        return val
    m = _LEAD_HANGUL.search(lead_text(text))
    if not m:
        return ""
    part = m.group(1).split(",")[0].replace("Hangul:", "").strip()
    return part if re.search("[가-힣]", part) else ""


def final_size(text: str) -> int | None:
    """Size the lead gives for the latest lineup ("is/was a N-member"), or None."""
    w = _WAS_N.search(lead_text(text))
    return _num(w.group(1)) if w else None


def debut_sentences(lead: str, year: int | None) -> str:
    """Lead sentences that may describe the debut of the category year."""
    keep = []
    for sent in _SENTENCE.split(lead):
        if _REDEBUT.search(sent):
            continue
        years = {int(y) for y in _YEAR.findall(sent)}
        if year is not None and years and year not in years:
            continue
        keep.append(sent)
    return " ".join(keep)


def debut_size(text: str, year: int | None = None) -> dict[str, Any]:
    """Return n (or None), the source of n, and the current/former member counts.

    Rule: 1) a debut sentence in the lead gives n (lead_debut). debut_sentences says which count.
    2) Else, no former members listed gives n = current + inactive (current_no_former).
    3) Else, no current member and "was a N-member" with N equal to the former count (lead_was_n).
    4) Else n is None. The range is current (low) to current + former (high).
    """
    params, _ = infobox(text)
    lead = lead_text(text)
    cur = _members(params, "current") + _members(params, "inactive")
    past = _members(params, "past") + _members(params, "former")
    redebut = bool(_REDEBUT.search(lead) or _REDEBUT.search(params.get("debut", "")))
    usable = debut_sentences(lead, year)
    n: int | None = None
    src: str | None = None
    for q in _LEAD_PATTERNS:
        hit = re.search(q, usable, re.IGNORECASE)
        if hit and _num(hit.group(1)):
            n, src = _num(hit.group(1)), "lead_debut"
            break
    if n is None and cur and not past:
        n, src = len(cur), "current_no_former"
    if n is None and not cur and past:
        w = _WAS_N.search(lead)
        if w and _num(w.group(1)) == len(past):
            n, src = len(past), "lead_was_n"
    return {"n": n, "src": src, "current": len(cur), "former": len(past), "redebut": redebut}
