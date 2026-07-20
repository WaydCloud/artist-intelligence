"""YouTube Data API v3 client (stdlib only) — official rail, D-002/DATA_SOURCES §3.

Quota discipline: `search.list` (100 units) lives ONLY in `resolve` (explicit, one-time,
cached to a committed file). Daily `fetch` uses list endpoints (~1 unit each): channels →
uploads playlist → playlistItems → videos. ~12 units/day for a 9-act watchlist vs 10k
quota. Reads ``YOUTUBE_API_KEY`` from env.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

_API = "https://www.googleapis.com/youtube/v3"
_UA = "artist-intelligence/0.1 (yt-pulse; contact@orykto.xyz)"


def _key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise SystemExit("YOUTUBE_API_KEY not set (User env — see .env.example)")
    return key


def _get(endpoint: str, params: dict[str, object], timeout: int = 30) -> dict[str, object]:
    query = urllib.parse.urlencode({**params, "key": _key()})
    req = urllib.request.Request(f"{_API}/{endpoint}?{query}", headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (official API host)
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"YouTube API {exc.code} on {endpoint}: {detail}") from exc
    return data if isinstance(data, dict) else {}


def _items(data: dict[str, object]) -> list[dict[str, object]]:
    items = data.get("items")
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def search_channel(name: str) -> dict[str, str] | None:
    """search.list (100 units) — resolve 전용. 상위 3개 중 비-'Topic' 우선(자동 생성 채널 회피)."""
    data = _get("search", {"part": "snippet", "q": name, "type": "channel", "maxResults": 3})
    candidates: list[dict[str, str]] = []
    for item in _items(data):
        id_obj = item.get("id")
        snip = item.get("snippet")
        cid = id_obj.get("channelId") if isinstance(id_obj, dict) else None
        title = snip.get("channelTitle") or snip.get("title") if isinstance(snip, dict) else None
        if isinstance(cid, str):
            candidates.append({"channel_id": cid, "channel_title": str(title or "")})
    for c in candidates:  # 공식 채널 우선 — ' - Topic'은 자동 생성(업로드 재생목록 상이)
        if not c["channel_title"].endswith(" - Topic"):
            return c
    return candidates[0] if candidates else None


def channels_info(channel_ids: list[str]) -> dict[str, dict[str, object]]:
    """channels.list (1 unit / ≤50 ids) → {channel_id: {subscribers, uploads_playlist}}."""
    out: dict[str, dict[str, object]] = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        data = _get(
            "channels",
            {"part": "statistics,contentDetails", "id": ",".join(batch), "maxResults": 50},
        )
        for item in _items(data):
            cid = item.get("id")
            if not isinstance(cid, str):
                continue
            stats = item.get("statistics")
            det = item.get("contentDetails")
            subs = stats.get("subscriberCount") if isinstance(stats, dict) else None
            uploads = None
            if isinstance(det, dict):
                rel = det.get("relatedPlaylists")
                uploads = rel.get("uploads") if isinstance(rel, dict) else None
            out[cid] = {
                "subscribers": int(subs) if isinstance(subs, str) and subs.isdigit() else 0,
                "uploads_playlist": uploads if isinstance(uploads, str) else None,
            }
    return out


def playlist_recent(playlist_id: str, limit: int) -> list[str]:
    """playlistItems.list (1 unit) → 최근 업로드 video id들 (업로드 재생목록은 최신순)."""
    data = _get(
        "playlistItems",
        {"part": "contentDetails", "playlistId": playlist_id, "maxResults": min(limit, 50)},
    )
    ids: list[str] = []
    for item in _items(data):
        det = item.get("contentDetails")
        vid = det.get("videoId") if isinstance(det, dict) else None
        if isinstance(vid, str):
            ids.append(vid)
    return ids[:limit]


_DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _duration_s(iso: object) -> int:
    if not isinstance(iso, str):
        return 0
    m = _DUR.fullmatch(iso)
    if not m:
        return 0
    h, mi, s = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + s


def videos_stats(video_ids: list[str]) -> list[dict[str, object]]:
    """videos.list (1 unit / ≤50 ids) → snippet+statistics+duration facts."""
    out: list[dict[str, object]] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        data = _get(
            "videos",
            {"part": "snippet,statistics,contentDetails", "id": ",".join(batch), "maxResults": 50},
        )
        for item in _items(data):
            vid = item.get("id")
            snip = item.get("snippet")
            stats = item.get("statistics")
            det = item.get("contentDetails")
            if not (isinstance(vid, str) and isinstance(snip, dict)):
                continue

            def _stat(name: str, s: object = stats) -> int:
                v = s.get(name) if isinstance(s, dict) else None
                return int(v) if isinstance(v, str) and v.isdigit() else 0

            out.append(
                {
                    "video_id": vid,
                    "title": str(snip.get("title") or ""),
                    "published_at": str(snip.get("publishedAt") or ""),
                    "views": _stat("viewCount"),
                    "likes": _stat("likeCount"),
                    "comments": _stat("commentCount"),
                    "duration_s": _duration_s(det.get("duration") if isinstance(det, dict) else None),
                }
            )
    return out
