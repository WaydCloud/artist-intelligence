"""yt-pulse CLI.

    python -m yt_pulse resolve --watchlist <watchlist.json> -o <yt_channels.json>   (라이브·1회)
    python -m yt_pulse fetch --channels <yt_channels.json> -o <snapshot.json>       (라이브·일일)
    python -m yt_pulse analyze <snapshot.json ...> -o <outdir>                      (오프라인)
    python -m yt_pulse signals <snapshot.json ...|dir> -o <series.json>             (오프라인)
    python -m yt_pulse validate <report.json>

`analyze`/`signals` (offline, deterministic) are the smoke path; `resolve`/`fetch` are
the live collectors (official API, quota-disciplined — RULES §1).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

from yt_pulse import api
from yt_pulse.report import build_report, build_signal_series, now_iso

MODULE_VERSION = "0.1.0"


def find_schema() -> Path | None:
    rel = Path("packages") / "report-schema" / "report.schema.json"
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        node = base
        for _ in range(8):
            if (node / rel).exists():
                return node / rel
            if node.parent == node:
                break
            node = node.parent
    return None


def validate_report(report: dict[str, object]) -> tuple[bool, list[str]]:
    """Returns (checked, errors). checked=False means validation was skipped."""
    schema_path = find_schema()
    if schema_path is None:
        return (False, [])
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return (False, [])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = [
        f"{list(e.path)}: {e.message}"
        for e in Draft202012Validator(schema).iter_errors(cast(Any, report))
    ]
    return (True, errors)


def _load_snapshot(path: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return ([r for r in doc if isinstance(r, dict)], {})
    records = doc.get("records") if isinstance(doc, dict) else None
    prov = doc.get("provenance") if isinstance(doc, dict) else None
    return (
        [r for r in records if isinstance(r, dict)] if isinstance(records, list) else [],
        prov if isinstance(prov, dict) else {},
    )


def _snapshot_paths(inputs: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in inputs:
        path = Path(p)
        if path.is_dir():
            out.extend(sorted(path.glob("*.json")))
        else:
            out.append(path)
    return out


def cmd_resolve(args: argparse.Namespace) -> int:
    """watchlist → 채널 검색(100 units/act) → 커밋 캐시. 오매칭은 캐시에서 수동 정정."""
    wdoc = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    artists = wdoc.get("artists") if isinstance(wdoc, dict) else None
    keys = [a["key"] for a in artists if isinstance(a, dict) and isinstance(a.get("key"), str)] if isinstance(artists, list) else []
    existing: dict[str, object] = {}
    out_path = Path(args.output)
    if out_path.exists():  # 재실행 시 기존 캐시 보존(수동 정정 존중) — 신규 act만 검색
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        ch = prev.get("channels") if isinstance(prev, dict) else None
        if isinstance(ch, dict):
            existing = ch
    channels: dict[str, object] = dict(existing)
    searched = 0
    for key in keys:
        if key in channels:
            continue
        hit = api.search_channel(key)
        searched += 1
        channels[key] = hit or {"channel_id": None, "channel_title": None, "note": "unresolved"}
        print(f"  {key}: {hit['channel_title'] if hit else 'UNRESOLVED'}")
        time.sleep(0.2)
    payload = {
        "$comment": "yt-pulse resolve 캐시 (search.list 1회성) — 오매칭은 channel_id를 직접 정정하세요(사용자 소유).",
        "resolved_at": now_iso(),
        "channels": channels,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"resolved {searched} new / {len(channels)} total → {out_path} (~{searched * 100} units)")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """캐시 채널들 → 구독자 + 최근 업로드 + 영상 통계 → facts-only 스냅샷 (~12 units)."""
    cache = json.loads(Path(args.channels).read_text(encoding="utf-8"))
    ch = cache.get("channels") if isinstance(cache, dict) else None
    acts: dict[str, str] = {}  # act key → channel_id
    if isinstance(ch, dict):
        for key, rec in ch.items():
            cid = rec.get("channel_id") if isinstance(rec, dict) else None
            if isinstance(cid, str) and cid:
                acts[key] = cid
    if not acts:
        print("no resolved channels in cache — run `resolve` first", file=sys.stderr)
        return 1
    info = api.channels_info(sorted(set(acts.values())))
    records: list[dict[str, object]] = []
    raw = 0
    for key in sorted(acts):
        cid = acts[key]
        meta = info.get(cid) or {}
        uploads = meta.get("uploads_playlist")
        if not isinstance(uploads, str):
            print(f"  ! {key}: uploads playlist not found", file=sys.stderr)
            continue
        vids = api.playlist_recent(uploads, args.per_channel)
        stats = api.videos_stats(vids)
        raw += len(stats)
        subs = meta.get("subscribers")
        for v in stats:
            records.append({"artist": key, **v, "subscribers": subs if isinstance(subs, int) else 0})
    records.sort(key=lambda r: (str(r.get("artist")), str(r.get("video_id"))))
    doc = {
        "provenance": {
            "source": "YouTube Data API v3 (official)",
            "tool": "yt-pulse.fetch",
            "tool_version": MODULE_VERSION,
            "fetched_at": now_iso(),
            "license": "yt-api-metrics",
            "tos_class": "official-api",
            "params": {"per_channel": args.per_channel, "acts": len(acts)},
            "pii_policy": "facts-only: 공개 집계 지표만(§4), 댓글·시청자 데이터 없음",
        },
        "quality": {"records": len(records), "raw": raw, "dropped": raw - len(records), "notes": []},
        "records": records,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} | {len(records)} video records | {len(acts)} acts")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    records: list[dict[str, object]] = []
    provenance: dict[str, object] = {}
    asof = ""
    for path in _snapshot_paths(args.input):
        recs, prov = _load_snapshot(str(path))
        records.extend(recs)
        fetched = str(prov.get("fetched_at") or "")
        if fetched >= asof:  # 최신 스냅샷 기준일·프로버넌스
            asof, provenance = fetched, prov
    report = build_report(
        records,
        provenance=provenance,
        generated_at=now_iso(),
        asof=asof or now_iso(),
        recent_days=args.recent_days,
    )
    checked, errors = validate_report(report)
    if errors:
        print(f"report is schema-INVALID ({len(errors)} error(s)) — not writing:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = "valid" if checked else "UNCHECKED (jsonschema/schema not found)"
    print(f"wrote {out} | {len(records)} video records | schema {status}")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    snapshots: list[tuple[str, list[dict[str, object]], dict[str, object]]] = []
    for path in _snapshot_paths(args.input):
        recs, prov = _load_snapshot(str(path))
        asof = str(prov.get("fetched_at") or "")[:10] or path.stem[:10]
        snapshots.append((asof, recs, prov))
    series = build_signal_series(snapshots, generated_at=now_iso())
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(series, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n_acts = len(cast(dict[str, object], series["series"]))
    n_dates = len(cast(list[str], series["dates"]))
    print(f"wrote {out} | {n_acts} acts × {n_dates} days | yt-velocity series")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    checked, errors = validate_report(report)
    if not checked:
        print("UNCHECKED — jsonschema not installed or schema not found", file=sys.stderr)
        return 2
    if errors:
        print(f"INVALID ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"{args.report} · schema valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yt_pulse", description="Watchlist official-channel firepower/velocity — facts-only"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser("resolve", help="watchlist → 채널 캐시 (라이브·1회, search 100u/act)")
    p_resolve.add_argument("--watchlist", required=True, help="packages/entity-master/watchlist.json")
    p_resolve.add_argument("-o", "--output", required=True, help="채널 캐시 출력(커밋 대상)")
    p_resolve.set_defaults(func=cmd_resolve)

    p_fetch = sub.add_parser("fetch", help="채널 캐시 → facts-only 스냅샷 (라이브·일일 ~12u)")
    p_fetch.add_argument("--channels", required=True, help="yt_channels.json 캐시")
    p_fetch.add_argument("--per-channel", type=int, default=5, help="채널당 최근 업로드 수 (기준 원장, 기본 5)")
    p_fetch.add_argument("-o", "--output", required=True, help="스냅샷 .json 경로")
    p_fetch.set_defaults(func=cmd_fetch)

    p_analyze = sub.add_parser("analyze", help="스냅샷(들) → 스키마 유효 report.json")
    p_analyze.add_argument("input", nargs="+", help="스냅샷 JSON(들) 또는 디렉터리")
    p_analyze.add_argument("-o", "--output", required=True, help="report.json 출력 디렉터리")
    p_analyze.add_argument("--recent-days", type=int, default=14, help="신작 감지 창(일, 기준 원장, 기본 14)")
    p_analyze.set_defaults(func=cmd_analyze)

    p_signals = sub.add_parser("signals", help="스냅샷(들) → yt-velocity signal-series (브리지 소비)")
    p_signals.add_argument("input", nargs="+", help="스냅샷 JSON(들) 또는 디렉터리")
    p_signals.add_argument("-o", "--output", required=True, help="signal-series .json 경로")
    p_signals.set_defaults(func=cmd_signals)

    p_validate = sub.add_parser("validate", help="report.json을 report-schema로 검증")
    p_validate.add_argument("report", help="report.json 경로")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))
