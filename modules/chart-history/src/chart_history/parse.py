"""Kworb chart snapshot → structured facts (stdlib only).

Header-driven column mapping (v3.2): columns are located by their header
label ("Pos", "Artist and Title", "Streams"…) rather than fixed indices, so
daily / weekly / other Kworb layouts all parse. The collector never stores site
chrome or creative works — only the factual chart table. See RULES.md.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _FirstTableParser(HTMLParser):
    """Collect the header row and data rows of the FIRST <table> only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.header: list[str] = []
        self.rows: list[list[str]] = []
        self._table_seen = False
        self._table_open = False
        self._in_row = False
        self._in_cell = False
        self._row_has_th = False
        self._row: list[str] = []
        self._cell: list[str] = []

    def _finalize_row(self) -> None:
        if not self._in_row:
            return
        self._in_row = False
        if self._row_has_th:
            if not self.header:
                self.header = self._row
        elif self._row:
            self.rows.append(self._row)
        self._row = []
        self._row_has_th = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if not self._table_seen:
                self._table_seen = True
                self._table_open = True
            return
        if not self._table_open:
            return
        if tag == "tr":
            self._finalize_row()  # implicit close if previous <tr> lacked </tr>
            self._in_row = True
            self._row = []
            self._row_has_th = False
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._cell = []
            if tag == "th":
                self._row_has_th = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
        elif tag in ("tr", "thead", "tbody"):  # some Kworb layouts omit </tr>
            self._finalize_row()
        elif tag == "table" and self._table_open:
            self._finalize_row()
            self._table_open = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell.append(data)


def parse_metadata(html: str) -> dict[str, str]:
    """Read the leading `<!-- key: value | key: value -->` fixture header."""
    meta: dict[str, str] = {}
    m = re.search(r"<!--(.*?)-->", html, re.S)
    if not m:
        return meta
    for part in m.group(1).split("|"):
        key, sep, value = part.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta


def _to_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    token = raw.replace(",", "").replace("+", "").strip()
    if not re.fullmatch(r"-?\d+", token):
        return None
    return int(token)


def _parse_change(raw: str | None) -> int | None:
    """Kworb 'P+' column: '=' → 0, '+N'/'-N' → signed int, 'NEW'/'RE' → None."""
    token = (raw or "").strip()
    if token in ("=", ""):
        return 0
    if token.upper() in ("NEW", "RE"):
        return None
    return _to_int(token)


def _split_artist_title(raw: str | None) -> tuple[str, str]:
    artist, sep, title = (raw or "").partition(" - ")
    if sep:
        return artist.strip(), title.strip()
    return (raw or "").strip(), ""


def _colmap(header: list[str]) -> dict[str, int]:
    idx = {label.strip(): i for i, label in enumerate(header)}

    def find(*names: str) -> int:
        for name in names:
            if name in idx:
                return idx[name]
        return -1

    return {
        "rank": find("Pos"),
        "change": find("P+"),
        "title": find("Artist and Title", "Artist - Title", "Track"),  # Spotify | Apple | YouTube layouts
        "days": find("Days", "Wks"),  # daily=Days, weekly=Wks
        "peak": find("Pk"),
        "streams": find("Streams"),
        "streams_delta": find("Streams+"),
        "total": find("Total"),
    }


def _cell(row: list[str], index: int) -> str | None:
    return row[index] if 0 <= index < len(row) else None


def parse_chart(html: str) -> dict[str, object]:
    """Parse a Kworb chart snapshot into {meta, entries} via header labels."""
    meta = parse_metadata(html)
    parser = _FirstTableParser()
    parser.feed(html)
    cols = _colmap(parser.header)

    entries: list[dict[str, object]] = []
    for row in parser.rows:
        rank = _to_int(_cell(row, cols["rank"]))
        if rank is None:  # spacer / malformed row
            continue
        artist, title = _split_artist_title(_cell(row, cols["title"]))
        entries.append(
            {
                "rank": rank,
                "pos_change": _parse_change(_cell(row, cols["change"])),
                "artist": artist,
                "title": title,
                "days": _to_int(_cell(row, cols["days"])),
                "peak": _to_int(_cell(row, cols["peak"])),
                "streams": _to_int(_cell(row, cols["streams"])),
                "streams_delta": _to_int(_cell(row, cols["streams_delta"])),
                "total": _to_int(_cell(row, cols["total"])),
            }
        )
    entries.sort(key=_rank_key)
    return {"meta": meta, "entries": entries}


def _rank_key(entry: dict[str, object]) -> int:
    rank = entry.get("rank")
    return rank if isinstance(rank, int) else 0
