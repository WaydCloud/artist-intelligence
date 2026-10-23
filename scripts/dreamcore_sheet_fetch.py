"""Answer-sheet preview features for the dreamcore pre-registration (D-064).

Purpose    Measure the answer-sheet recordings with the sonic-profile engine, unchanged.
Boundary   No new metric code. Search, verification helpers and features_from_preview are
           imported from sonic-profile. Writes only the research path given by -o.
Invariant  A record is resolved only when BOTH the artist alias and the title (or a title
           alias) match after normalisation. The chart path accepts a title-only match,
           which can land on a cover or another recording.
Failure    No verified preview, or no candidate decodes: the record keeps `unresolved` and
           no features. It is never counted as 0.
Note       Apple first, storefront KR then US then GB, then Deezer. Audio stays in memory.

Usage:

    PYTHONPATH=modules/sonic-profile/src python scripts/dreamcore_sheet_fetch.py \
        data/research/genre-impulse/dreamcore/answer_sheet.json \
        -o data/research/genre-impulse/dreamcore/sheet_features.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "modules" / "sonic-profile" / "src"))
from sonic_profile.features import (  # type: ignore[import-not-found]
    Unresolved,
    engine_provenance,
)
from sonic_profile.models import (  # type: ignore[import-not-found]
    ensure_models,
    model_dir,
    tagger_provenance,
)
from sonic_profile.preview import (  # type: ignore[import-not-found]
    _apple,
    _core,
    _deezer,
    decoder_provenance,
    features_from_preview,
    storefronts,
)
from sonic_profile.rhythm import (
    rhythm_provenance,  # type: ignore[import-not-found]
)

_FEAT = re.compile(r"(?i)^\s*(feat|ft|with|prod)\b")


def _qualifiers(s: str) -> set[str]:
    """Bracketed qualifiers other than credits. _core strips brackets, so it cannot see them."""
    return {_core(b[1:-1]) or b for b in re.findall(r"\(.*?\)|\[.*?\]", s or "") if not _FEAT.match(b[1:-1])}


def _title_ok(found: str, titles: list[str]) -> bool:
    # A qualifier the sheet does not name ("Slowed Down Version", "Bird Sounds") marks another
    # release of the song, which is a different recording (DRAFT-answer-sheet-corpus §4).
    # Measured 2026-10-23: without this check "School Rooftop (feat. WMD)" resolved to
    # "School Rooftop (Intro) [Slowed Down Version]", then to "[Bird Sounds]" (85 s, not 167 s).
    if not any(_qualifiers(found) == _qualifiers(t) for t in titles):
        return False
    f = _core(found)
    return bool(f) and any(_core(t) == f for t in titles)


def _verified(track: dict[str, Any], delay: float) -> list[dict[str, Any]]:
    aliases = [str(a) for a in (track.get("aliases") or [track["artist"]])]
    titles = [str(track["title"]), *(str(t) for t in track.get("title_aliases") or [])]
    terms = list(dict.fromkeys(f"{track['artist']} {t}" for t in titles))
    for store in storefronts("KR"):
        hits: list[dict[str, Any]] = []
        for term in terms:
            try:
                got = _apple(term, aliases, store, 10)
            except Exception:  # noqa: BLE001 - a store outage falls through to the next store
                got = []
            time.sleep(delay)
            hits.extend(c for c in got if _title_ok(str(c.get("title") or ""), titles))
        if hits:
            return list({c["track_id"]: c for c in hits}.values())
    out: list[dict[str, Any]] = []
    for term in terms:
        try:
            got = _deezer(term, aliases, 10)
        except Exception:  # noqa: BLE001 - Deezer outage means no candidate, recorded as unresolved
            got = []
        time.sleep(delay)
        out.extend(c for c in got if _title_ok(str(c.get("title") or ""), titles))
    return list({c["track_id"]: c for c in out}.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (low frequency)")
    ap.add_argument("--max-tracks", type=int, default=40, help="hard cap on recordings measured")
    args = ap.parse_args(argv)

    sheet = json.loads(Path(args.sheet).read_text(encoding="utf-8"))
    tracks = list(sheet.get("tracks") or [])
    if len(tracks) > args.max_tracks:
        print(f"sheet has {len(tracks)} tracks, cap is {args.max_tracks}", file=sys.stderr)
        return 2
    ensure_models(model_dir(None))
    eng = {**engine_provenance(), **decoder_provenance(), **rhythm_provenance(), **tagger_provenance()}
    today = time.strftime("%Y-%m-%d")
    records: list[dict[str, Any]] = []
    for t in tracks:
        rec: dict[str, Any] = {
            "role": t["role"], "scope": t.get("scope"), "sheet_artist": t["artist"],
            "sheet_title": t["title"], "sheet_source": t.get("source"), "observed_date": today,
        }
        cands = _verified(t, args.delay)
        last = "no artist+title verified preview (Apple KR/US/GB, Deezer)"
        for cand in cands:
            try:
                feats = features_from_preview(cand["preview_url"], low_hz=eng["low_hz"], suffix=cand.get("suffix", ".audio"))
            except Unresolved as exc:
                last = str(exc)
                continue
            rec.update({k: v for k, v in cand.items() if k != "preview_url"})
            rec["features"] = feats
            break
        else:
            rec["unresolved"] = last
        time.sleep(args.delay)
        state = f"{rec.get('source', '')}:{rec.get('preview_market', '')} {rec.get('artist')} - {rec.get('title')}" if rec.get("features") else f"UNRESOLVED ({last})"
        print(f"  [{t['role'][:3]}] {t['artist']} - {t['title']} -> {state}")
        records.append(rec)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "records": records,
        "provenance": {
            "script": "scripts/dreamcore_sheet_fetch.py", "collected": today, "sheet": args.sheet,
            "engine_provenance": eng, "audio_retained": False,
            "verification": "artist alias AND title core match; Apple KR>US>GB then Deezer",
        },
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in records if r.get("features"))
    print(f"wrote {out} - {ok}/{len(records)} resolved (audio not retained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
