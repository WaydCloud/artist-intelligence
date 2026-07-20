"""Reduce a raw Apify IG item to a facts-only record (no content, no PII).

§4 (원문 최소저장·지표 중심·PII 제거): only countable/public fields survive the
`fetch` step. These raw fields are DROPPED here, before anything is written to
disk, so PII never reaches an on-disk snapshot:

    caption, ownerUsername, ownerFullName, ownerId, id, url, inputUrl, displayUrl,
    images, mentions, taggedUsers, latestComments, firstComment, childPosts,
    coauthorProducers, locationId, locationName, shortCode

Kept fields are public aggregate signals only: engagement counts, timestamp,
hashtags (public tags), and a music/sound label (public track).
"""

from __future__ import annotations


def as_int(value: object) -> int:
    """Coerce a JSON scalar to int; bools and non-numbers → 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _kind(item: dict[str, object]) -> str:
    label = f"{item.get('type', '')} {item.get('productType', '')}".lower()
    return "reel" if ("video" in label or "clips" in label or "reel" in label) else "post"


def _hashtags(item: dict[str, object]) -> list[str]:
    raw = item.get("hashtags")
    if not isinstance(raw, list):
        return []
    return sorted({str(h).lower().lstrip("#") for h in raw if isinstance(h, str) and h.strip()})


def _music(item: dict[str, object]) -> str | None:
    info = item.get("musicInfo")
    if not isinstance(info, dict):
        return None
    label = f"{info.get('artist_name') or ''} - {info.get('song_name') or ''}".strip(" -")
    return label or None


def to_record(item: dict[str, object]) -> dict[str, object]:
    """Raw Apify IG item → facts-only record. Drops all content/PII fields (§4)."""
    plays = as_int(item.get("videoPlayCount"))
    return {
        "likes": as_int(item.get("likesCount")),
        "comments": as_int(item.get("commentsCount")),
        "plays": plays or None,
        "type": _kind(item),
        "timestamp": str(item.get("timestamp") or ""),
        "hashtags": _hashtags(item),
        "music": _music(item),
    }
