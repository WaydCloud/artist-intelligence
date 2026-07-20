"""Canonical artist/title keys for robust cross-source/entity matching (v3).

v2 matched tracks by the raw ``artist|title`` string. That breaks across
sources (feat./remaster/version suffixes, collaborator ordering). These helpers
canonicalize to a stable key so joins survive formatting differences.
"""

from __future__ import annotations

import re
import unicodedata

# collaborator markers → primary artist is the part before the first one
_COLLAB = re.compile(r"\s*(?:,|&|\bfeat\.?|\bft\.?|\bvs\.?|\bx)\s+", re.IGNORECASE)
# feat/with/prod clause anywhere to end of a title
_FEAT_TAIL = re.compile(r"\s*[\(\[]?\s*(?:feat\.?|ft\.?|featuring|with|prod\.?)\b.*$", re.IGNORECASE)
# trailing version/edition qualifier on a title
_VERSION_TAIL = re.compile(
    r"\s*[-(\[]\s*(?:remaster(?:ed)?|remix|live|acoustic|instrumental|inst|version|edit|mix|mono|stereo)\b.*$",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _base(text: str) -> str:
    lowered = _strip_accents(text.strip().lower())
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)  # keep hangul/latin/digits
    return re.sub(r"\s+", " ", cleaned).strip()


def primary_artist(artist: str) -> str:
    """Readable primary artist (original case), before the first collaborator marker."""
    return _COLLAB.split(artist.strip(), maxsplit=1)[0].strip()


def canonical_artist(artist: str) -> str:
    return _base(primary_artist(artist))


def canonical_title(title: str) -> str:
    stripped = _VERSION_TAIL.sub("", _FEAT_TAIL.sub("", title))
    return _base(stripped)


def canonical_key(artist: str, title: str) -> str:
    return f"{canonical_artist(artist)}|{canonical_title(title)}"
