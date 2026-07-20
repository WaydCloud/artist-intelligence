"""Minimal reader for the shared entity-master (packages/entity-master/).

fandom-pulse joins IG sound labels → artists via the SAME shared entity data as
chart-history (D-007 공유 캐노니컬 차원). Kept module-local (no cross-module import)
so modules stay independent — entities.json is the shared *data* contract, not code.

v3 (D-013): the user-owned watchlist (packages/entity-master/watchlist.json) merges
ON TOP of entities.json — adds followed acts (key·aliases·hashtags) and applies
`overrides` last (fixes enrich mis-attributions; survives enrich regeneration).
"""

from __future__ import annotations

import json
from pathlib import Path


def _read_json(path: str | None) -> dict[str, object]:
    if not path or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _watchlist_artists(watchlist: dict[str, object]) -> list[dict[str, object]]:
    artists = watchlist.get("artists")
    return [a for a in artists if isinstance(a, dict)] if isinstance(artists, list) else []


def load_index(
    path: str | None, watchlist_path: str | None = None
) -> dict[str, dict[str, object]]:
    """entities.json (+watchlist) → {lowercased name/alias: record}.

    record = key·country·debut·agency. Watchlist artists merge on top (new acts join
    the index; roster=tracked universe), then watchlist `overrides` patch fields by
    canonical key (마지막 승리 — 정정 계층).
    """
    index: dict[str, dict[str, object]] = {}
    by_key: dict[str, dict[str, object]] = {}

    data = _read_json(path)
    artists = data.get("artists")
    if isinstance(artists, dict):
        for key, rec in artists.items():
            if not isinstance(rec, dict):
                continue
            entry: dict[str, object] = {
                "key": key,
                "country": rec.get("country"),
                "debut": rec.get("debut"),
                "agency": rec.get("agency"),
            }
            by_key[key] = entry
            names: list[object] = [key, rec.get("name")]
            aliases = rec.get("aliases")
            if isinstance(aliases, list):
                names.extend(aliases)
            for nm in names:
                if isinstance(nm, str) and nm.strip():
                    index.setdefault(nm.strip().lower(), entry)

    watchlist = _read_json(watchlist_path)
    for art in _watchlist_artists(watchlist):
        key = art.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        entry = by_key.setdefault(
            key,
            {"key": key, "country": art.get("country"), "debut": art.get("debut"), "agency": None},
        )
        for field in ("country", "debut"):
            if not entry.get(field) and art.get(field):
                entry[field] = art[field]
        names2: list[object] = [key]
        aliases2 = art.get("aliases")
        if isinstance(aliases2, list):
            names2.extend(aliases2)
        for nm in names2:
            if isinstance(nm, str) and nm.strip():
                index.setdefault(nm.strip().lower(), entry)

    overrides = watchlist.get("overrides")
    if isinstance(overrides, dict):
        for key, patch in overrides.items():
            if isinstance(patch, dict) and key in by_key:
                for field, value in patch.items():
                    if field != "note":
                        by_key[key][field] = value
    return index


def load_hashtag_index(watchlist_path: str | None) -> dict[str, str]:
    """watchlist.json → {lowercased hashtag(no #): canonical key} — 직접 귀속(D-013).

    사운드 라벨이 없는(UGC 'Original audio') pre-mainstream 게시물도 자기 해시태그로
    아티스트에 귀속된다 — 사운드-온리 귀속의 사각을 메우는 두 번째 증거 경로.

    `hashtags`(수집 타겟 겸 귀속) + `tag_aliases`(귀속 전용 — 은어·밈·팬덤명 태그,
    수집 타겟 아님·과금 없음)를 합쳐 인덱스를 만든다. 충돌 시 hashtags 우선.
    """
    out: dict[str, str] = {}
    for field in ("hashtags", "tag_aliases"):
        for art in _watchlist_artists(_read_json(watchlist_path)):
            key = art.get("key")
            tags = art.get(field)
            if not isinstance(key, str) or not isinstance(tags, list):
                continue
            for t in tags:
                if isinstance(t, str) and t.strip():
                    out.setdefault(t.strip().lstrip("#").lower(), key)
    return out


def match(index: dict[str, dict[str, object]], artist: str) -> dict[str, object] | None:
    """Lowercase name/alias match — IG sound artists are Latin/native like entity names."""
    return index.get(artist.strip().lower()) if artist else None
