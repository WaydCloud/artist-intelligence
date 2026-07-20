"""Entity master: MusicBrainz (primary) + Wikidata fallback (v3.1).

MusicBrainz resolves most acts but misses romanized/native-name variants
(임영웅·JANNABI·Kenshi Yonezu…). Wikidata's multilingual label/alias search
recovers those and yields origin country. Both are open (CC0) and structured.

Live lookup runs in `enrich`; the result is cached to a committed JSON map that
`analyze` reads OFFLINE (keeps the smoke deterministic). Facts only: id, name,
origin country, type, source.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

_MB_ARTIST = "https://musicbrainz.org/ws/2/artist/"
_WD_API = "https://www.wikidata.org/w/api.php"
_UA = "artist-intelligence/0.1 (chart-history; contact@orykto.xyz)"

# Common country QID → ISO 3166-1 alpha-2 (fetched via P297 on miss, then cached)
_ISO_CACHE: dict[str, str | None] = {
    "Q884": "KR", "Q17": "JP", "Q30": "US", "Q145": "GB", "Q16": "CA", "Q38": "IT",
    "Q142": "FR", "Q183": "DE", "Q29": "ES", "Q408": "AU", "Q865": "TW", "Q148": "CN",
    "Q155": "BR", "Q96": "MX", "Q20": "NO", "Q34": "SE", "Q35": "DK", "Q55": "NL",
}
# P31 (instance of) values that indicate a group rather than a person
_GROUP_TYPES = {"Q215380", "Q9212979", "Q2088357", "Q105756498", "Q281643", "Q5741069"}


def _get_json(url: str, timeout: int) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted hosts)
        data = json.load(resp)
    return data if isinstance(data, dict) else {}


def _mb_extras(mbid: str, timeout: int) -> tuple[list[str], str | None]:
    """Fetch aliases (native Hangul + romanized) + the artist's Wikidata QID (url-rels).

    The Wikidata link is MB-verified → lets us pull debut/agency from the *correct*
    entity, avoiding name-search disambiguation (e.g. 'Jimin' → wrong 1955 person)."""
    try:
        data = _get_json(f"{_MB_ARTIST}{mbid}?inc=aliases+url-rels&fmt=json", timeout)
    except Exception:  # noqa: BLE001 (best-effort enrichment)
        return [], None
    raw = data.get("aliases")
    aliases = (
        [a["name"] for a in raw if isinstance(a, dict) and isinstance(a.get("name"), str)]
        if isinstance(raw, list)
        else []
    )
    wd_qid: str | None = None
    rels = data.get("relations")
    if isinstance(rels, list):
        for rel in rels:
            if not (isinstance(rel, dict) and rel.get("type") == "wikidata"):
                continue
            url = rel.get("url")
            resource = url.get("resource") if isinstance(url, dict) else None
            if isinstance(resource, str) and "/wiki/Q" in resource:
                wd_qid = resource.rsplit("/", 1)[-1]
                break
    return aliases, wd_qid


def lookup_artist_mb(
    name: str, *, min_score: int = 90, timeout: int = 20, with_aliases: bool = True
) -> dict[str, object] | None:
    """Resolve via MusicBrainz (+ aliases for cross-language matching), or None below min_score."""
    query = urllib.parse.quote(f'artist:"{name}"')
    data = _get_json(f"{_MB_ARTIST}?query={query}&fmt=json&limit=1", timeout)
    artists = data.get("artists")
    if not isinstance(artists, list) or not artists:
        return None
    top = artists[0]
    if not isinstance(top, dict) or int(top.get("score") or 0) < min_score:
        return None
    mbid = top.get("id")
    rec: dict[str, object] = {
        "source": "MusicBrainz",
        "id": mbid,
        "name": top.get("name"),
        "country": top.get("country"),
        "type": top.get("type"),
        "score": int(top.get("score") or 0),
    }
    if with_aliases and isinstance(mbid, str):
        time.sleep(1.1)  # MB rate limit (1 req/s)
        aliases, wd_qid = _mb_extras(mbid, timeout)
        rec["aliases"] = aliases
        if wd_qid:
            rec["wd_id"] = wd_qid  # MB-verified Wikidata QID (debut/agency 근거)
    return rec


def alias_index(entity_map: dict[str, object]) -> dict[str, str]:
    """Map every known name/alias (lowercased) → the entity's primary map key.

    Lets cross-language matching recognize e.g. '코르티스' == 'CORTIS'.
    """
    index: dict[str, str] = {}
    for primary, rec in entity_map.items():
        names: list[object] = [primary]
        if isinstance(rec, dict):
            names.append(rec.get("name"))
            aliases = rec.get("aliases")
            if isinstance(aliases, list):
                names.extend(aliases)
        for candidate in names:
            if isinstance(candidate, str) and candidate.strip():
                index[candidate.strip().lower()] = primary
    return index


def _wd_claim_ids(claims: dict[str, object], pid: str) -> list[str]:
    out: list[str] = []
    entries = claims.get(pid)
    if not isinstance(entries, list):
        return out
    for c in entries:
        try:
            value = c["mainsnak"]["datavalue"]["value"]["id"]  # type: ignore[index]
        except (KeyError, TypeError):
            continue
        if isinstance(value, str):
            out.append(value)
    return out


def _country_iso(qid: str, timeout: int) -> str | None:
    if qid in _ISO_CACHE:
        return _ISO_CACHE[qid]
    iso: str | None = None
    try:
        data = _get_json(f"{_WD_API}?action=wbgetentities&ids={qid}&props=claims&format=json", timeout)
        entities = data.get("entities")
        claims = entities[qid]["claims"] if isinstance(entities, dict) else {}  # type: ignore[index]
        raw = claims["P297"][0]["mainsnak"]["datavalue"]["value"]  # type: ignore[index]
        iso = raw if isinstance(raw, str) else None
    except (KeyError, TypeError, IndexError):
        iso = None
    _ISO_CACHE[qid] = iso
    return iso


def _wd_inception_year(claims: dict[str, object]) -> str | None:
    """P571 (inception) → 4-digit year string. 그룹 결성연도 ≈ 데뷔 시기(코호트 근거)."""
    try:
        time_val = claims["P571"][0]["mainsnak"]["datavalue"]["value"]["time"]  # type: ignore[index]
    except (KeyError, TypeError, IndexError):
        return None
    return time_val[1:5] if isinstance(time_val, str) and len(time_val) >= 5 else None


def _wd_label_en(qid: str, timeout: int) -> str | None:
    try:
        data = _get_json(f"{_WD_API}?action=wbgetentities&ids={qid}&props=labels&languages=en&format=json", timeout)
        raw = data["entities"][qid]["labels"]["en"]["value"]  # type: ignore[index]
        return raw if isinstance(raw, str) else None
    except (KeyError, TypeError, IndexError):
        return None


def lookup_artist_wikidata(name: str, *, timeout: int = 20) -> dict[str, object] | None:
    """Resolve via Wikidata multilingual search → origin country + type + debut + agency."""
    search = urllib.parse.quote(name)
    hit = _get_json(
        f"{_WD_API}?action=wbsearchentities&search={search}&language=en&limit=1&type=item&format=json",
        timeout,
    )
    results = hit.get("search")
    if not isinstance(results, list) or not results:
        return None
    top = results[0]
    if not isinstance(top, dict):
        return None
    qid = top.get("id")
    if not isinstance(qid, str):
        return None

    time.sleep(0.3)  # WD 폴라이트(연속 호출 레이트리밋 회피)
    data = _get_json(f"{_WD_API}?action=wbgetentities&ids={qid}&props=claims&format=json", timeout)
    entities = data.get("entities")
    claims_obj = entities.get(qid, {}).get("claims", {}) if isinstance(entities, dict) else {}
    claims = claims_obj if isinstance(claims_obj, dict) else {}

    p31 = _wd_claim_ids(claims, "P31")
    country_qids = _wd_claim_ids(claims, "P495") or _wd_claim_ids(claims, "P27")
    country = next((iso for q in country_qids if (iso := _country_iso(q, timeout))), None)
    desc = str(top.get("description") or "").lower()
    is_group = any(q in _GROUP_TYPES for q in p31) or any(w in desc for w in ("band", "group", "duo", "trio"))
    artist_type = "Group" if is_group else ("Person" if "Q5" in p31 else None)
    # debut/agency는 여기서 넣지 않는다 — 이름 검색은 동명이인 오매칭(Jimin=1955) 위험.
    # 정확한 데뷔·에이전시는 resolve()가 MB→Wikidata 링크(검증된 QID)에서만 가져온다.
    return {"source": "Wikidata", "id": qid, "name": top.get("label") or name, "country": country, "type": artist_type}


def _wd_details_by_qid(qid: str, timeout: int) -> dict[str, object]:
    """검증된 Wikidata QID(예: MB의 wikidata 링크)에서 데뷔연도·에이전시 — 동명이인 위험 없음."""
    try:
        data = _get_json(f"{_WD_API}?action=wbgetentities&ids={qid}&props=claims&format=json", timeout)
        claims_raw = data["entities"][qid]["claims"]  # type: ignore[index]
    except (KeyError, TypeError, IndexError):
        return {}
    claims = claims_raw if isinstance(claims_raw, dict) else {}
    label_qids = _wd_claim_ids(claims, "P264")  # record label ≈ 소속사(K-pop)
    return {
        "debut": _wd_inception_year(claims),  # P571 결성연도 ≈ 데뷔 시기
        "agency": _wd_label_en(label_qids[0], timeout) if label_qids else None,
    }


def resolve(name: str, *, min_score: int = 90, use_wiki: bool = True, timeout: int = 20) -> dict[str, object] | None:
    """MusicBrainz first (country); Wikidata fallback (country) + 데뷔·에이전시 병합.

    country 해석은 MB 우선 무회귀. debut/agency는 MB에 없으므로 Wikidata에서만 —
    country 소스와 무관하게 병합(코호트·에이전시 뷰 근거, RULES §3)."""
    mb = lookup_artist_mb(name, min_score=min_score, timeout=timeout)
    wd = lookup_artist_wikidata(name, timeout=timeout) if use_wiki else None
    if mb and mb.get("country"):
        rec = mb
    elif wd and wd.get("country"):
        rec = wd
    else:
        rec = mb
    # 데뷔·에이전시: MB→Wikidata 링크(검증된 QID)에서만 — 이름 검색 동명이인 오염 방지.
    mb_qid = mb.get("wd_id") if isinstance(mb, dict) else None
    if rec is not None and isinstance(mb_qid, str):
        time.sleep(0.3)  # WD 폴라이트
        details = _wd_details_by_qid(mb_qid, timeout)
        for key in ("debut", "agency"):
            if details.get(key) and not rec.get(key):
                rec[key] = details[key]
    return rec


def load_entities(path: str | None, watchlist_path: str | None = None) -> dict[str, object]:
    """Load a committed entity map ({artists: {name: {...}}}) → {name: rec}.

    D-013: the user-owned watchlist (packages/entity-master/watchlist.json) merges on
    top — followed acts join the map (with aliases, so charts recognize them the day
    they enter), and `overrides` patch enrich mis-attributions last (정정 계층)."""
    artists: dict[str, object] = {}
    if path and Path(path).exists():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        raw = data.get("artists") if isinstance(data, dict) else None
        if isinstance(raw, dict):
            artists = dict(raw)
    if watchlist_path and Path(watchlist_path).exists():
        wdata = json.loads(Path(watchlist_path).read_text(encoding="utf-8"))
        wlist = wdata.get("artists") if isinstance(wdata, dict) else None
        if isinstance(wlist, list):
            for art in wlist:
                if not isinstance(art, dict):
                    continue
                key = art.get("key")
                if not isinstance(key, str) or not key.strip():
                    continue
                if key not in artists or not isinstance(artists[key], dict):
                    artists[key] = {
                        "source": "watchlist",
                        "name": key,
                        "country": art.get("country"),
                        "debut": art.get("debut"),
                        "aliases": art.get("aliases") or [],
                    }
                else:
                    rec = artists[key]
                    if isinstance(rec, dict):
                        merged = list(rec.get("aliases") or [])
                        for a in art.get("aliases") or []:
                            if a not in merged:
                                merged.append(a)
                        rec["aliases"] = merged
        overrides = wdata.get("overrides") if isinstance(wdata, dict) else None
        if isinstance(overrides, dict):
            for key, patch in overrides.items():
                rec = artists.get(key)
                if isinstance(patch, dict) and isinstance(rec, dict):
                    for field, value in patch.items():
                        if field != "note":
                            rec[field] = value
    return artists
