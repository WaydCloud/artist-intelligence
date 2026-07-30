"""sonic-profile CLI.

    python -m sonic_profile fetch --watchlist <watchlist.json> -o <snapshot.json>  (라이브)
    python -m sonic_profile analyze <snapshot.json ...|dir> -o <outdir>            (오프라인)
    python -m sonic_profile signals <snapshot.json ...|dir> -o <series.json>       (오프라인)
    python -m sonic_profile selftest                                              (오프라인·합성)
    python -m sonic_profile validate <report.json>

`analyze`/`signals`/`selftest`(오프라인·결정적)가 스모크 경로다. `fetch`만 네트워크를
타며, 오디오는 그 안에서 처리되고 폐기된다(RULES §1 무보관 불변식).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

from sonic_profile.features import (
    LOW_HZ_DEFAULT,
    SR,
    Unresolved,
    engine_provenance,
    extract,
)
from sonic_profile.report import (
    MIN_PROB_DEFAULT,
    NEW_RELEASE_DAYS,
    build_report,
    build_signal_series,
    now_iso,
)
from sonic_profile.rhythm import MIN_MATCH_DEFAULT, TIE_GAP_DEFAULT
from sonic_profile.stems import (
    BASS_GLIDE_MIN_MS_DEFAULT,
    BASS_GLIDE_MIN_ST_PER_SEC_DEFAULT,
    HALFTIME_MIN_RATIO_DEFAULT,
    SNARE_MIN_CONTRAST_DEFAULT,
    VOCAL_NOTE_MAX_DRIFT_DEFAULT,
    VOCAL_NOTE_MIN_MS_DEFAULT,
    StemOpts,
)

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
    schema_path = find_schema()
    if schema_path is None:
        return (False, [])
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return (False, [])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return (
        True,
        [
            f"{list(e.path)}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(cast(Any, report))
        ],
    )


def _snapshot_paths(inputs: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        out.extend(sorted(p.glob("*.json")) if p.is_dir() else [p])
    return out


def _alias_map(acts: list[dict[str, Any]]) -> dict[str, str]:
    """워치리스트 별칭(casefold) → 정본 키. 코호트 키 해석용(RULES §1 정체성)."""
    amap: dict[str, str] = {}
    for act in acts:
        key = str(act.get("key") or "")
        if not key:
            continue
        for al in [key, *(str(a) for a in (act.get("aliases") or []))]:
            amap[al.casefold()] = key
    return amap


def _merge_dup(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """코호트·워치리스트 양 경로로 이중 저장된 같은 관측을 한 레코드로(RULES §1).
    워치리스트 레코드(정본 키)를 몸통으로, 차트 필드를 보존한다."""
    chart = a if a.get("cohort") == "chart" else (b if b.get("cohort") == "chart" else None)
    watch = a if a.get("cohort") == "watchlist" else (b if b.get("cohort") == "watchlist" else None)
    if chart is None or watch is None:
        return a  # 같은 역할의 중복(비정상 입력) — 먼저 온 것 유지
    merged = dict(watch)
    for f in ("chart_rank", "chart_market", "chart_platform", "chart_label"):
        if chart.get(f) is not None:
            merged[f] = chart[f]
    if not merged.get("features") and chart.get("features"):
        merged["features"] = chart["features"]
    return merged


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """(source, track_id, observed_date) 기준 병합 — 멱등. fetch(저장 전)와
    _load(과거 스냅샷 방어) 양쪽에서 쓴다(RULES §1 정체성)."""
    index: dict[tuple[Any, Any, Any], int] = {}
    out: list[dict[str, Any]] = []
    for r in records:
        tid = r.get("track_id")
        if not tid:
            out.append(r)
            continue
        ident = (r.get("source"), tid, r.get("observed_date"))
        if ident not in index:
            index[ident] = len(out)
            out.append(r)
        else:
            out[index[ident]] = _merge_dup(out[index[ident]], r)
    return out


def _load(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    prov: dict[str, Any] = {}
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            records.extend(r for r in (doc.get("records") or []) if isinstance(r, dict))
            prov = prov or (doc.get("provenance") or {})
    return _dedupe(records), prov


def _cache_load(path: Path, engine_key: str) -> dict[str, Any]:
    """트랙 지표 캐시. 지표는 **녹음의 성질**이라 날마다 다시 잴 이유가 없다 —
    같은 trackId면 재다운로드하지 않는다(요청량·법적 노출 모두 감소).
    엔진 설정이 값의 일부이므로 캐시는 엔진 키로 무효화된다(RULES §2)."""
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 캐시 손상은 치명적이지 않다
        return {}
    return doc.get("features") or {} if doc.get("engine_key") == engine_key else {}


def _cache_save(path: Path, engine_key: str, features: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"engine_key": engine_key, "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )


def cmd_fetch(args: argparse.Namespace) -> int:
    from sonic_profile.models import ensure_models, model_dir, tagger_provenance
    from sonic_profile.preview import (
        candidates,
        decoder_provenance,
        features_from_preview,
        track_candidates,
    )
    from sonic_profile.rhythm import rhythm_provenance

    today = time.strftime("%Y-%m-%d")
    eng = {**engine_provenance(args.low_hz), **decoder_provenance()}
    if args.rhythm:
        eng.update(rhythm_provenance())
    # 스템은 마디 격자 위에 얹히므로 리듬이 꺼져 있으면 낼 수 없다(RULES §3.8).
    # 조용히 빈 값을 내지 않고 여기서 꺼 버린다 — 결측 사유가 레코드마다 반복되면
    # "스템을 켰는데 왜 없나"를 사람이 100번 읽어야 한다.
    if getattr(args, "stems", False) and not args.rhythm:
        print("  !! --stems는 리듬 격자가 필요하다(--no-rhythm과 함께 쓸 수 없다) — 스템 없이 진행")
        args.stems = False
    if getattr(args, "stems", False):
        from sonic_profile.stems import stem_provenance

        eng.update(stem_provenance())
    if args.tags:
        try:
            ensure_models(model_dir(args.model_dir))
            eng.update(tagger_provenance())
        except Exception as exc:  # noqa: BLE001 — 모델을 못 받으면 태깅만 끈다
            print(f"  !! 태거 모델 준비 실패 ({type(exc).__name__}) — 태깅 없이 진행")
            args.tags = False
    # 엔진 설정이 값의 일부다 — 리듬·태깅이 켜지면 키가 바뀌어 과거 캐시가 무효화된다(RULES §2).
    engine_key = "|".join([
        f"{eng['engine']}{eng['engine_version']}", str(eng["sample_rate"]), str(eng["low_hz"]),
        # 지표 집합 버전 — 지표를 늘렸는데 이게 빠지면 캐시가 적중해 **새 지표가 빠진
        # 옛 레코드가 그대로 되살아난다**(D-031). 절단본 함정과 같은 구조다.
        str(eng.get("feature_set", "-")),
        eng.get("beat_engine", "-"), eng.get("tagger", "-"),
        # 리듬 파생 지표(grid_deviation 등)가 늘면 리듬 엔진 산출도 달라진다.
        str(eng.get("rhythm_feature_set", "-")),
        eng.get("mood_head", "-"), eng.get("valence_head", "-"),
        # 저장 라벨 수가 늘면 옛 캐시(잘린 라벨)는 무효다 — 안 그러면 다음 수집이
        # 캐시 적중으로 절단본을 다시 써 넣어 과소집계가 되살아난다(RULES §3.1.6.1).
        str(eng.get("tagger_top_k_instrument", "-")),
        # 스템 축(RULES §3.8). 스템을 켜면 키가 갈라져 비-스템 캐시를 재사용하지 않는다 —
        # 안 그러면 캐시 적중으로 **스템 축이 빈 레코드**가 그대로 되살아난다.
        str(eng.get("stem_set", "-")),
    ])
    cache_path = Path(args.cache) if args.cache else Path(args.output).parent / "cache.json"
    cache = _cache_load(cache_path, engine_key)
    cache_hits = 0
    records: list[dict[str, Any]] = []
    # 하중받는 기준은 코드에 은닉하지 않는다(AGENTS §2.1) — CLI에서 받아 그대로 내려보낸다.
    stem_opts: StemOpts | None = StemOpts(
        min_ratio=args.halftime_min_ratio,
        min_st_per_sec=args.bass_glide_min_st_per_sec,
        min_ms=args.bass_glide_min_ms,
        min_contrast=args.snare_min_contrast,
        note_min_ms=args.vocal_note_min_ms,
        note_max_drift=args.vocal_note_max_drift,
    ) if getattr(args, "stems", False) else None

    def measure(cand: dict[str, Any]) -> dict[str, Any]:
        """캐시 우선. 미스일 때만 프리뷰를 내려받아 잰다(오디오는 즉시 폐기)."""
        nonlocal cache_hits
        cid = f"{cand['source']}:{cand.get('track_id')}"
        if cand.get("track_id") and cid in cache:
            cache_hits += 1
            return cache[cid]
        feats = features_from_preview(
            cand["preview_url"], low_hz=args.low_hz, suffix=cand.get("suffix", ".audio"),
            rhythm=args.rhythm, tags=args.tags,
            stems=getattr(args, "stems", False), stem_opts=stem_opts,
        )
        if cand.get("track_id"):
            cache[cid] = feats
        time.sleep(args.delay)
        return feats

    doc = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    acts = [a for a in (doc.get("artists") or []) if isinstance(a, dict) and a.get("key")]
    amap = _alias_map(acts)

    # ── 코호트: 차트 트랙 (분포를 만들려면 모집단이 있어야 한다)
    if args.cohort:
        cdoc = json.loads(Path(args.cohort).read_text(encoding="utf-8"))
        for t in cdoc.get("tracks") or []:
            artist, title = str(t.get("artist") or ""), str(t.get("title") or "")
            # 키는 정본으로 해석해 넣는다(RULES §1 정체성) — 아니면 시리즈에서
            # 같은 팀이 차트 표기('키키')와 정본 키('KiiiKiii')로 쪼개진다.
            rec: dict[str, Any] = {
                "key": amap.get(artist.casefold(), artist),
                "chart_label": artist,
                "query": f"{artist} - {title}",
                "observed_date": today,
                "cohort": "chart",
                "chart_rank": t.get("rank"),
                "chart_market": t.get("market"),
                "chart_platform": t.get("platform"),
            }
            cands = track_candidates(artist, title, country=args.country)
            if not cands:
                rec["unresolved"] = "no verified preview (artist/title mismatch)"
                records.append(rec)
                continue
            last = "no candidate decoded"
            for cand in cands:
                try:
                    feats = measure(cand)
                except Unresolved as exc:
                    last = str(exc)
                    continue
                rec.update({k: v for k, v in cand.items() if k != "preview_url"})
                rec["features"] = feats
                break
            else:
                rec["unresolved"] = last
            records.append(rec)
        ok_c = sum(1 for r in records if r.get("features"))
        print(f"  코호트(차트): {ok_c}/{len(records)} 해석 · 캐시 적중 {cache_hits}")

    for act in acts:
        key = str(act["key"])
        aliases = [str(a) for a in (act.get("aliases") or [])] or [key]
        rec: dict[str, Any] = {"key": key, "query": key, "observed_date": today, "cohort": "watchlist"}
        cands = candidates(key, aliases, country=args.country)
        if not cands:
            rec["unresolved"] = "no alias-verified preview found"
            records.append(rec)
            print(f"  {key}: 미해석 (별칭 검증된 프리뷰 없음)")
            continue
        # 후보를 순서대로 시도 — 디코드 못 하는 컨테이너는 다음 후보로(무보관 유지)
        last = "no candidate decoded"
        for cand in cands:
            try:
                feats = measure(cand)
            except Unresolved as exc:
                last = str(exc)
                continue
            rec.update({k: v for k, v in cand.items() if k != "preview_url"})
            rec["features"] = feats
            print(
                f"  {key}: {feats['tempo_bpm']}BPM · pulse {feats['pulse_clarity']} "
                f"· {cand['artist']} - {cand['title']} [{cand['source']}]"
            )
            break
        else:
            rec["unresolved"] = last
            print(f"  {key}: 미해석 ({last})")
        records.append(rec)

    # 같은 트랙이 코호트·워치리스트 양 경로로 잡히면 한 레코드로(RULES §1 정체성).
    records = _dedupe(records)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "records": records,
        "provenance": {
            "module": "sonic-profile",
            "version": MODULE_VERSION,
            "collected": today,
            "country": args.country,
            "engine_provenance": eng,
            "cohort": {"chart": sum(1 for r in records if r.get("cohort") == "chart"),
                       "watchlist": sum(1 for r in records if r.get("cohort") == "watchlist")},
            "cache_hits": cache_hits,
            # 무보관 불변식(RULES §1): 오디오는 저장하지 않는다. 여기 남는 것은 수치뿐.
            "audio_retained": False,
            "note": "30s preview, features only; audio processed in memory and discarded",
        },
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _cache_save(cache_path, engine_key, cache)
    ok = sum(1 for r in records if r.get("features"))
    print(f"wrote {out} · {ok}/{len(records)} resolved · 캐시 적중 {cache_hits} (오디오 미저장)")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    records, prov = _load(_snapshot_paths(args.inputs))
    watch: list[str] = []
    if args.watchlist and Path(args.watchlist).exists():
        doc = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
        watch = [a["key"] for a in (doc.get("artists") or []) if isinstance(a, dict) and a.get("key")]
    report = build_report(
        records,
        generated_at=now_iso(),
        provenance=prov,
        watchlist=watch,
        min_match=args.rhythm_min_match,
        tie_gap=args.rhythm_tie_gap,
        min_prob=args.min_prob,
        new_days=args.new_release_days,
    )
    checked, errors = validate_report(report)
    if errors:
        print(f"report is schema-INVALID ({len(errors)} error(s)) — not writing:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    status = "schema valid" if checked else "UNCHECKED (jsonschema/schema not found)"
    print(f"wrote {outdir / 'report.json'} · {len(records)} record(s) · {status}")
    return 0


def cmd_retag(args: argparse.Namespace) -> int:
    """상위 k 절단으로 라벨이 잘린 과거 레코드를 **복구**한다 (RULES §3.1.6.1).

    임계로 곡 수를 세는 축에서 라벨 절단은 조용한 과소집계다. 태깅에는 오디오가 필요한데
    오디오는 저장하지 않으므로(§1) 복구하려면 프리뷰를 다시 받는 수밖에 없다. 그래서
    **잘린 레코드만** 골라 **ID 정확 조회**로 같은 녹음을 받고 **악기 라벨만** 덮어쓴다.

    - 멱등: 두 번째 실행은 복구 대상이 0이라 네트워크를 타지 않는다.
    - 무보관 유지: 오디오는 `tags_from_preview` 안에서 폐기된다.
    - 감사 가능: 바뀌는 필드가 `features.instruments` 하나뿐이라 diff로 확인된다.
    """
    from sonic_profile.models import ensure_models, model_dir
    from sonic_profile.preview import lookup_preview, tags_from_preview
    from sonic_profile.tagging import TOP_K_INSTRUMENT

    paths = _snapshot_paths(args.inputs)
    # (source, track_id) → 그 녹음을 담고 있는 (파일, 레코드) 전부. 같은 트랙이 여러 날짜에
    # 걸쳐 있으므로 한 번 받아서 **전부** 고쳐야 한다 — 안 그러면 날짜마다 값이 갈린다.
    targets: dict[tuple[str, str], list[tuple[Path, dict[str, Any]]]] = {}
    docs: dict[Path, dict[str, Any]] = {}
    total = 0
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        docs[p] = doc
        for rec in doc.get("records") or []:
            feats = rec.get("features") or {}
            inst = feats.get("instruments")
            if not isinstance(inst, list) or not inst:
                continue
            total += 1
            if len(inst) >= TOP_K_INSTRUMENT:
                continue
            src, tid = str(rec.get("source") or ""), str(rec.get("track_id") or "")
            if not src or not tid:
                continue
            targets.setdefault((src, tid), []).append((p, rec))

    if not targets:
        print(f"복구 대상 없음 — 태깅된 {total}개 레코드가 모두 완전합니다 (no-op)")
        return 0
    print(f"태깅 레코드 {total}개 중 절단 {sum(len(v) for v in targets.values())}개 "
          f"· 고유 녹음 {len(targets)}개 → 프리뷰 재취득 (오디오 미저장)")
    if args.dry_run:
        for (src, tid), hits in list(targets.items())[:10]:
            print(f"  [dry-run] {src}:{tid} · {len(hits)}개 레코드 · {hits[0][1].get('title')}")
        print(f"  [dry-run] 총 {len(targets)}개 녹음 — 실제 변경 없음")
        return 0

    ensure_models(model_dir(args.model_dir))
    fixed = failed = 0
    touched: set[Path] = set()
    for (src, tid), hits in sorted(targets.items()):
        cand = lookup_preview(src, tid, country=args.country)
        if not cand:
            failed += 1
            print(f"  !! {src}:{tid} 프리뷰 재조회 실패 — 원래 라벨 유지")
            continue
        try:
            tags = tags_from_preview(cand["preview_url"], suffix=cand.get("suffix", ".audio"))
        except Exception as exc:  # noqa: BLE001 — 한 곡 실패가 전체를 멈추지 않는다
            failed += 1
            print(f"  !! {src}:{tid} 태깅 실패 ({type(exc).__name__}) — 원래 라벨 유지")
            continue
        inst = tags.get("instruments")
        if not isinstance(inst, list) or len(inst) < TOP_K_INSTRUMENT:
            failed += 1
            print(f"  !! {src}:{tid} 여전히 불완전 — 건너뜀")
            continue
        for path, rec in hits:
            rec["features"]["instruments"] = inst
            touched.add(path)
        fixed += 1
        print(f"  {cand['artist']} - {cand['title']}: 악기 라벨 {len(inst)}개로 복구 "
              f"({len(hits)}개 레코드)")
        time.sleep(args.delay)

    for path in sorted(touched):
        doc = docs[path]
        # 복구 사실을 스냅샷에 남긴다 — 값이 언제 왜 바뀌었는지 추적 가능해야 한다
        prov = doc.setdefault("provenance", {})
        log = prov.setdefault("retag_log", [])
        log.append({"date": time.strftime("%Y-%m-%d"), "field": "instruments",
                    "reason": "top-k truncation repair", "k": TOP_K_INSTRUMENT})
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"복구 {fixed}개 녹음 · 실패 {failed}개 · 스냅샷 {len(touched)}개 갱신 (오디오 미저장)")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    records, prov = _load(_snapshot_paths(args.inputs))
    series = build_signal_series(records, field=args.field, provenance=prov)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(series, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} · {len(series['series'])} act(s) × {len(series['dates'])} date(s)")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """합성 신호로 지표 엔진 검증 (TESTS §1·§2) — 저작물 미사용, 네트워크 0."""
    import numpy as np

    def clicks(bpm: float, seconds: float = 10.0) -> np.ndarray:
        y = np.zeros(int(SR * seconds), dtype=np.float32)
        step = int(SR * 60.0 / bpm)
        for i in range(0, len(y) - 64, step):
            y[i : i + 64] += np.hanning(64).astype(np.float32)
        return y

    def sine(hz: float, seconds: float = 10.0) -> np.ndarray:
        t = np.arange(int(SR * seconds), dtype=np.float32) / SR
        return (0.5 * np.sin(2 * np.pi * hz * t)).astype(np.float32)

    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}: {name}{(' — ' + detail) if detail else ''}")
        if not cond:
            fails.append(name)

    f120 = extract(clicks(120))
    check("120BPM 클릭 → tempo≈120 (옥타브 오류 회귀)", abs(f120["tempo_bpm"] - 120) < 3, f"측정 {f120['tempo_bpm']}")
    f90 = extract(clicks(90))
    check("90BPM 클릭 → tempo≈90 (옥타브 오류 회귀)", abs(f90["tempo_bpm"] - 90) < 3, f"측정 {f90['tempo_bpm']}")
    noise = np.random.default_rng(0).standard_normal(SR * 10).astype(np.float32) * 0.1
    fn = extract(noise)
    check("클릭 > 백색잡음 펄스 명료도", f120["pulse_clarity"] > fn["pulse_clarity"],
          f"{f120['pulse_clarity']} vs {fn['pulse_clarity']}")
    flo, fhi = extract(sine(50)), extract(sine(4000))
    check("50Hz 정현파 저역 비율 ≈ 1", flo["low_end_ratio"] > 0.9, f"{flo['low_end_ratio']}")
    check("4kHz 정현파 저역 비율 ≈ 0", fhi["low_end_ratio"] < 0.05, f"{fhi['low_end_ratio']}")
    check("밝기 단조 증가 (50Hz < 4kHz)", flo["brightness_hz"] < fhi["brightness_hz"],
          f"{flo['brightness_hz']} < {fhi['brightness_hz']}")
    for name, y in (("무음", np.zeros(SR * 10, dtype=np.float32)), ("과단축(1초)", clicks(120, 1.0))):
        try:
            extract(y)
            check(f"{name} → 미해석", False, "예외가 나지 않음")
        except Unresolved:
            check(f"{name} → 미해석 (0으로 채우지 않음)", True)
    a, b = extract(clicks(128)), extract(clicks(128))
    check("결정성: 같은 입력 → 같은 값", a == b)
    # crest는 TESTS §3 검증(2026-07-28) 통과 — 상태 문자열이 검증 날짜를 달고 있어야 한다.
    # 미검증으로 되돌아가면 리포트 표면에서 내려야 하므로 회귀 가드로 남긴다.
    check(
        "crest_factor 상태가 검증 표기(날짜 포함)",
        str(f120.get("crest_factor_status", "")).startswith("validated-"),
        str(f120.get("crest_factor_status")),
    )
    check("crest_factor 값이 양수 dB", isinstance(f120.get("crest_factor_db"), float) and f120["crest_factor_db"] > 0)

    # ── 리듬 순수 함수 (RULES §3.1.5) — 모델 없이 검증 가능한 부분만. 네트워크 0.
    from sonic_profile.rhythm import (
        BINS,
        RhythmUnavailable,
        bar_profile,
        match_templates,
        tempo_from_beats,
    )

    # 50fps 격자에 붙인 비트 시각 → 적합이 양자화를 씻는가 (RULES §3.2)
    for bpm in (128.0, 143.0):
        exact = np.arange(40) * (60.0 / bpm)
        quant = np.round(exact / 0.02) * 0.02            # beat_this의 0.02초 격자 재현
        fit = tempo_from_beats(quant)
        med = 60.0 / float(np.median(np.diff(quant)))
        check(
            f"{bpm}BPM 격자 비트 → 적합 오차 < 0.2% (median 방식보다 정확)",
            abs(fit - bpm) / bpm < 0.002 and abs(fit - bpm) <= abs(med - bpm),
            f"적합 {fit:.2f} vs median {med:.2f}",
        )
    try:
        tempo_from_beats(np.array([0.0, 1.0]))
        check("비트 부족 → 미해석", False, "예외가 나지 않음")
    except RhythmUnavailable:
        check("비트 부족 → 미해석 (0으로 채우지 않음)", True)

    # 정박 킥만 있는 합성 포락 → four-on-floor가 최고 정합이어야 한다
    from sonic_profile.rhythm import HOP as R_HOP

    bars = np.arange(9) * 2.0                            # 2초짜리 마디 8개
    frames = int(bars[-1] * SR / R_HOP) + 8
    env = np.zeros(frames, dtype=np.float64)
    # 정박 위치는 **칸 수에서 파생**시킨다 — 상수 (0,4,8,12)로 박아 두면 격자를 32칸으로
    # 바꾼 순간 이 픽스처가 조용히 8분음 4개를 찍는다(D-038에서 실제로 걸렸다).
    for b in bars[:-1]:
        for q in (0, BINS // 4, BINS // 2, 3 * BINS // 4):
            # 프레임 인덱스는 **반올림**해야 한다 — 잘라 넣으면 0.5초가 0.4993초가 되어
            # 칸 경계에서 앞 칸으로 밀린다. 격자 정렬 픽스처의 함정.
            env[round((b + 2.0 * q / BINS) * SR / R_HOP)] = 1.0
    prof = bar_profile(env, SR, bars)
    m = match_templates(prof)
    top = max(m, key=lambda k: m[k])
    check("정박 킥 합성 → four-on-floor 최고 정합", top == "four-on-floor", f"{top} {m[top]:.3f}")
    check("프로파일 합 = 1 (정규화)", abs(float(np.sum(prof)) - 1.0) < 1e-9)
    check("리듬 결정성: 같은 입력 → 같은 값", match_templates(prof) == m)
    try:
        bar_profile(env, SR, np.array([0.0, 2.0]))
        check("다운비트 부족 → 미해석", False, "예외가 나지 않음")
    except RhythmUnavailable:
        check("다운비트 부족 → 미해석", True)

    # ── 템플릿 원장 무결성 · 임계 규약 (TESTS §5 · RULES §3.1.5)
    from fractions import Fraction

    from sonic_profile.rhythm import (
        LEGACY_BINS,
        TEMPLATES,
        TRIPLET_BINS,
        classify_rhythm,
        fold_profile,
        render_template,
        unrenderable_templates,
    )

    # 원장은 **마디 상대 분수**다(D-038). 이름과 위치가 어긋나면 도메인 소유자가 원장을
    # 읽고 조정할 수 없다(2026-07-29 결함, D-027). 격자 두 곳에서 같은 음악적 위치를
    # 가리키는지 확인한다 — 이게 분수 정의의 요점이다.
    tres8 = TEMPLATES.get("tresillo(8분 3+3+2)")
    check(
        "8분 3+3+2 tresillo = (0, ⅜, ¾) — 격자와 무관한 분수 정의",
        tres8 == (Fraction(0), Fraction(3, 8), Fraction(3, 4)),
        str(tres8),
    )
    r16 = render_template(tres8 or (), LEGACY_BINS)
    r32 = render_template(tres8 or (), BINS)
    check(
        "같은 원장이 16칸 → 0·6·12 / 32칸 → 0·12·24로 렌더된다",
        r16 is not None and r32 is not None
        and list(np.flatnonzero(r16)) == [0, 6, 12]
        and list(np.flatnonzero(r32)) == [0, 12, 24],
    )
    # 제거된 `tresillo(16분·반마디)`가 왜 관용 패턴이 아니었는지를 **고정**한다 —
    # 근거가 코드에서 사라지면 누군가 다시 넣는다(RULES §3.1.5 결함 ①, 2026-07-30 제거).
    half = (Fraction(0), Fraction(3, 16), Fraction(3, 8))
    tiled = tuple(sorted(set(half) | {q + Fraction(1, 2) for q in half}))
    check(
        "16분 3+3+2를 마디 끝까지 이으면 dembow와 동일 → 반마디 조각은 원장에서 제거",
        tiled == tuple(sorted(TEMPLATES.get("dembow") or ()))
        and "tresillo(16분·반마디)" not in TEMPLATES,
        f"{tiled} vs {TEMPLATES.get('dembow')}",
    )
    # 앨리어싱은 조용히 흘리지 않는다 — 트리플렛 위치는 이진 격자에서 표현 불가다
    check(
        "트리플렛 위치(⅓)는 32칸에서 렌더 불가 → None (반올림 금지)",
        render_template((Fraction(1, 3),), BINS) is None
        and render_template((Fraction(1, 3),), TRIPLET_BINS) is not None,
    )
    check("현 원장은 32칸에서 전부 렌더된다", unrenderable_templates(BINS) == [],
          str(unrenderable_templates(BINS)))
    # 32 → 16 접기 무손실 (TESTS §7.3)
    folded = fold_profile(prof, LEGACY_BINS)
    check("32 → 16 접기: 합 보존", abs(float(folded.sum()) - 1.0) < 1e-9)
    check("32 → 16 접기 후에도 four-on-floor 최고 정합",
          max(match_templates(folded), key=lambda k: match_templates(folded)[k])
          == "four-on-floor")
    try:
        fold_profile(prof, 24)                          # 32는 24로 나뉘지 않는다
        check("접기 불가 조합 → 미해석", False, "예외가 나지 않음")
    except RhythmUnavailable:
        check("접기 불가 조합 → 미해석 (반올림해 흘리지 않음)", True)

    # ── 하이햇 축 · 반쪽 재현성 (TESTS §7.3·§7.2.5 · RULES §3.1.5.3·§3.8.4.4)
    from sonic_profile.rhythm import (
        bar_profile_split_half,
        bar_profile_split_half_2bar,
        hihat_active_ratio,
        hihat_roll_burst_ratio,
        hihat_roll_ratio,
        hihat_triplet_bias,
    )

    sixteenth = np.zeros(BINS)
    sixteenth[::2] = 1.0                        # 16분 위치에만(32칸의 짝수 칸)
    offgrid = np.zeros(BINS)
    offgrid[1::2] = 1.0                         # 32분 위치에만(홀수 칸) — 16칸에선 안 보였다
    check("hihat_roll 하한(16분만) = 0", hihat_roll_ratio(sixteenth / sixteenth.sum()) == 0.0)
    check("hihat_roll 상한(32분만) = 1", hihat_roll_ratio(offgrid / offgrid.sum()) == 1.0)
    check("hihat_roll: 16칸 프로파일은 미해석 (정의상 0이 아니다)",
          hihat_roll_ratio(np.full(LEGACY_BINS, 1.0 / LEGACY_BINS)) is None)

    # ── 롤의 연속성 축 (RULES §3.1.5.4 · 사전 등록. **정답지 검증 전 표면 금지**)
    # 이 축의 존재 이유는 "점유율이 같아도 산발이면 낮고 몰리면 높다"이므로,
    # 그 구별이 실제로 되는지를 먼저 재는 것이 채택 조건의 바닥이다.
    burst3 = np.zeros(BINS)
    burst3[:3] = 1.0                            # 32분 3연타 한 군데 = 롤의 최소 단위
    check("burst 상한(연타 3칸만) = 1", hihat_roll_burst_ratio(burst3 / burst3.sum()) == 1.0)
    check("burst 하한(16분 산발) = 0", hihat_roll_burst_ratio(sixteenth / sixteenth.sum()) == 0.0)
    check("burst: 32분 산발(홀수 칸만)도 0 — 점유율은 같고 연속성만 다르다",
          hihat_roll_burst_ratio(offgrid / offgrid.sum()) == 0.0
          and hihat_roll_ratio(offgrid / offgrid.sum()) == 1.0)
    pair2 = np.zeros(BINS)
    pair2[:2] = 1.0                             # 2연타는 롤이 아니다(최소 단위 미만)
    check("burst: 연타 2칸은 0 (3칸이 최소 단위)", hihat_roll_burst_ratio(pair2 / pair2.sum()) == 0.0)
    wrap = np.zeros(BINS)
    wrap[[BINS - 2, BINS - 1, 0]] = 1.0         # 마디선을 넘는 롤
    check("burst: 마디선을 넘는 롤을 센다(순환)", hihat_roll_burst_ratio(wrap / wrap.sum()) == 1.0)
    # 🔴 사전 명시한 최대 위험: 상시 하이햇은 전 칸 활성이라 1.0이 된다. 그건 롤이 아니고,
    # 짝 축이 그 사실을 말한다 — 위험을 검사로 고정해 둔다.
    flat = np.full(BINS, 1.0 / BINS)
    check("burst: 상시 하이햇은 1.0이지만 active_ratio도 1.0 (짝 축이 판별 불가를 말한다)",
          hihat_roll_burst_ratio(flat) == 1.0 and hihat_active_ratio(flat) == 1.0)
    check("active_ratio: 16분만이면 0.5", hihat_active_ratio(sixteenth / sixteenth.sum()) == 0.5)
    check("burst: 16칸 프로파일은 미해석", hihat_roll_burst_ratio(np.full(LEGACY_BINS, 1 / LEGACY_BINS)) is None)
    tri = np.zeros(TRIPLET_BINS)
    tri[::3] = 1.0                              # 8분 이진 위치
    tri_only = np.zeros(TRIPLET_BINS)
    for i in range(TRIPLET_BINS):
        if i % 2 == 0 and i % 3:
            tri_only[i] = 1.0                   # 트리플렛 전용
    check("hihat_triplet_bias 하한(8분 이진만) = 0", hihat_triplet_bias(tri / tri.sum()) == 0.0)
    check("hihat_triplet_bias 상한(트리플렛 전용만) = 1",
          hihat_triplet_bias(tri_only / tri_only.sum()) == 1.0)
    check("hihat_triplet_bias: 이진 격자 입력은 미해석",
          hihat_triplet_bias(np.full(BINS, 1.0 / BINS)) is None)


    # 비직교성이 이 이상 올라가면 두 이름이 같은 것을 재고 있다는 뜻 → 원장 재검토 신호
    def _unit(pos: tuple[Fraction, ...]) -> np.ndarray:
        rendered = render_template(pos, BINS)
        assert rendered is not None
        t = rendered - rendered.mean()
        return t / float(np.linalg.norm(t))

    names = list(TEMPLATES)
    pairs = [
        (abs(float(_unit(TEMPLATES[a]) @ _unit(TEMPLATES[b]))), a, b)
        for i, a in enumerate(names)
        for b in names[i + 1 :]
    ]
    worst, wa, wb = max(pairs)
    check("템플릿 최악 쌍 상관 ≤ 0.85 (초과 시 원장 재검토)", worst <= 0.85,
          f"{wa} ↔ {wb} = {worst:.2f}")

    # θ 규약: 저정합·음의 상관·평탄은 유형 이름을 받지 않는다("해당 없음"이지 "다른 유형" 아님)
    # 어느 템플릿도 쓰지 않는 칸(1·5·9·13)에만 킥이 있는 프로파일 → 전 템플릿과 음의 상관.
    # 정박의 반대 위상(2·6·10·14)으로는 부족하다 — four-on-floor와는 음이지만 trap-synco와
    # +0.33이라 argmax가 이름을 뱉는다. 임계가 막아야 하는 건 이 "다른 이름으로의 도피"다.
    inv = np.zeros(BINS)
    inv[1 :: BINS // 4] = 1.0        # 어느 템플릿도 쓰지 않는 칸(격자에서 파생)
    c_inv = classify_rhythm(inv / inv.sum())
    check("전 템플릿 음의 상관 → 해당 없음 (argmax가 이름을 뱉지 않음)",
          c_inv["assigned"] is None and c_inv["top_score"] < 0,
          f"top={c_inv['top']} {c_inv['top_score']}")
    flat = np.full(BINS, 1.0 / BINS)
    c_flat = classify_rhythm(flat)
    check("평탄 프로파일 → 해당 없음 (사전 첫 키 폴백 차단)",
          c_flat["assigned"] is None and c_flat["top_score"] == 0.0,
          f"top={c_flat['top']} {c_flat['top_score']}")
    check("θ=0으로 내리면 폴백 경로가 되살아난다 (임계가 유일한 방어선임을 고정)",
          classify_rhythm(flat, min_match=0.0)["assigned"] is not None)
    # 동점은 지우지 않고 표시만 한다
    c_beat = classify_rhythm(prof)
    check("정박 킥 → 유형 배정됨 (four-on-floor)", c_beat["assigned"] == "four-on-floor",
          f"{c_beat['assigned']} {c_beat['top_score']}")
    check("동점 폭을 1.0으로 열면 동점으로 표시된다 (행 삭제 아님)",
          classify_rhythm(prof, tie_gap=1.0)["tie"]
          and classify_rhythm(prof, tie_gap=1.0)["assigned"] == "four-on-floor")
    check("분류 결정성: 같은 프로파일 → 같은 배정", classify_rhythm(prof) == c_beat)

    # ── D-031 신규 지표 (TESTS §6) ───────────────────────────────────────────
    from sonic_profile.features import stereo_width
    from sonic_profile.rhythm import (
        bar_profile_contrast,
        beat_grid_fit,
        syncopation_ratio,
    )

    # §6.1 리듬 파생 — 저장된 프로파일에서 재계산되므로 오디오가 필요 없다
    on_beat = [1.0 if i % 4 == 0 else 0.0 for i in range(16)]
    off_beat = [0.0 if i % 4 == 0 else 1.0 for i in range(16)]
    check("싱코페이션 하한: 정박만 → 0.0", syncopation_ratio(on_beat) == 0.0,
          f"{syncopation_ratio(on_beat)}")
    check("싱코페이션 상한: 정박 칸이 빔 → 1.0", syncopation_ratio(off_beat) == 1.0,
          f"{syncopation_ratio(off_beat)}")
    flat16 = [1.0 / 16] * 16
    check("마디 대비 기준점: 완전 균일 → 정확히 1.0", bar_profile_contrast(flat16) == 1.0,
          f"{bar_profile_contrast(flat16)}")
    spike = [1.0] + [0.0] * 15
    check("마디 대비 상한: 한 칸 집중 → bins(16)", abs(bar_profile_contrast(spike) - 16.0) < 1e-9,
          f"{bar_profile_contrast(spike)}")
    # 그리드 편차: 완벽 등간격은 ≈0, 지터를 키우면 단조 증가해야 한다
    perfect = np.arange(32, dtype=np.float64) * 0.5
    _, dev0 = beat_grid_fit(perfect)
    devs = []
    for sigma in (0.002, 0.010, 0.030):
        jit = perfect + np.random.default_rng(7).normal(0, sigma, perfect.size)
        devs.append(beat_grid_fit(jit)[1])
    check("그리드 편차 하한: 완벽 등간격 → ≈0", dev0 < 1e-6, f"{dev0:.3e} ms")
    check("그리드 편차 단조 증가: 지터 σ↑ → 잔차↑",
          devs[0] < devs[1] < devs[2], " < ".join(f"{d:.1f}" for d in devs))

    # §6.2 신규 DSP
    quiet = extract(sine(1000) * 0.5)
    loud = extract(sine(1000))
    if isinstance(quiet.get("loudness_lufs"), float) and isinstance(loud.get("loudness_lufs"), float):
        delta = quiet["loudness_lufs"] - loud["loudness_lufs"]
        # K-weighting은 선형이라 진폭 절반 = 정확히 −6.02 LUFS. 구현 정오를 가르는 검사다.
        check("라우드니스 선형성: 진폭 −6dB → −6 LUFS 이동", abs(delta + 6.02) < 0.05,
              f"{delta:+.2f} LUFS")
    else:
        check("라우드니스 선형성: 진폭 −6dB → −6 LUFS 이동", False, "값이 나오지 않음")
    check("스펙트럼 평탄도 하한: 순음 → ≈0", fhi["spectral_flatness"] < 0.01,
          f"{fhi['spectral_flatness']}")
    check("스펙트럼 평탄도: 잡음 > 순음", fn["spectral_flatness"] > fhi["spectral_flatness"],
          f"{fn['spectral_flatness']} > {fhi['spectral_flatness']}")
    mono_sig = sine(440)
    other = sine(660)
    check("스테레오 폭 하한: L=R → 0.0", stereo_width(np.stack([mono_sig, mono_sig])) == 0.0)
    check("스테레오 폭 상한: L=−R → 1.0", stereo_width(np.stack([mono_sig, -mono_sig])) == 1.0)
    mid_w = stereo_width(np.stack([mono_sig, other]))
    check("스테레오 폭 중간값: 다른 채널 → (0,1)", mid_w is not None and 0.0 < mid_w < 1.0,
          f"{mid_w}")
    # 모노 소스는 0.0("좁다")이 아니라 None("정보 없음")이다 — 결측 ≠ 0(§0)
    check("모노 소스 → None (0.0으로 채우지 않음)", stereo_width(mono_sig) is None)
    # 🔴 무회귀: 스테레오를 넘겨도 모노 지표는 한 톨도 바뀌지 않아야 한다(RULES §2)
    base = extract(clicks(128))
    with_st = extract(clicks(128), stereo=np.stack([clicks(128), other]))
    drift = {k for k in base if k != "stereo_width" and base[k] != with_st.get(k)}
    check("🔴 모노 무회귀: stereo 인자가 기존 지표를 바꾸지 않는다", not drift, str(sorted(drift)))

    # ── D-032 T0 축 묶음 (TESTS §7) ──────────────────────────────────────────
    from sonic_profile.derived import derive_all, organic_ratio, profile_shape
    from sonic_profile.features import (
        _k_weight,
        _loudness_range_lu,
        production_qc,
        stereo_detail,
    )
    from sonic_profile.rhythm import HOP as HOP_R
    from sonic_profile.rhythm import ioi_entropy, rhythm_self_similarity, swing_ratio

    # 파생(라벨) — 오디오 없이 도는 순수 함수
    def ins(pairs: list[tuple[str, float]]) -> list[dict[str, Any]]:
        return [{"label": k, "p": v} for k, v in pairs]

    check("organic_ratio 상한: 유기음만 → 1.0",
          organic_ratio(ins([("piano", 0.9), ("violin", 0.8)]))["organic_ratio"] == 1.0)
    check("organic_ratio 하한: 전자음만 → 0.0",
          organic_ratio(ins([("synthesizer", 0.9), ("drummachine", 0.5)]))["organic_ratio"] == 0.0)
    mixed = organic_ratio(ins([("piano", 0.5), ("synthesizer", 0.5), ("bass", 0.9)]))
    check("organic_ratio 모호 라벨은 분모에서 빠진다 (0.5)", mixed["organic_ratio"] == 0.5,
          f"배제 질량 {mixed['organic_excluded_mass']}")
    check("모호 라벨만 있으면 미해석 (0으로 채우지 않음)",
          "organic_ratio" not in organic_ratio(ins([("bass", 0.9), ("guitar", 0.8)])))
    flat_prof = [1.0 / 16] * 16
    check("bar_profile_entropy: 완전 균일 → 1.0",
          profile_shape(flat_prof)["bar_profile_entropy"] == 1.0)
    check("bar_half_asymmetry: 앞 반마디에만 킥 → 1.0",
          profile_shape([1.0] * 8 + [0.0] * 8)["bar_half_asymmetry"] == 1.0)
    check("derive_all은 기존 키를 덮어쓰지 않는다",
          "organic_ratio" not in derive_all({"instruments": ins([("piano", 1.0)]),
                                             "organic_ratio": 0.123}))

    # 라우드니스 레인지 — 일정 신호는 0, 크고 작은 구간이 섞이면 커야 한다
    steady = sine(1000, 20.0)
    varied = np.concatenate([sine(1000, 10.0) * 0.05, sine(1000, 10.0)]).astype(np.float32)
    lra_s = _loudness_range_lu(_k_weight(steady, SR), SR)
    lra_v = _loudness_range_lu(_k_weight(varied, SR), SR)
    check("LRA 하한: 일정 진폭 → ≈0", lra_s < 0.2, f"{lra_s:.3f} LU")
    check("LRA 단조성: 기복 있는 신호 > 일정 신호", lra_v > lra_s + 10, f"{lra_v:.1f} vs {lra_s:.1f} LU")

    # 프로덕션 QC — "클리핑"이 아니라 0dBFS 초과다
    qc = production_qc(sine(1000) * 3.0, SR, 1.5)
    check("over_unity_ratio: 진폭 1.5 정현파는 상당 부분이 1.0 초과", qc["over_unity_ratio"] > 0.3,
          f"{qc['over_unity_ratio']}")
    check("over_unity_ratio: 정상 신호는 0", production_qc(sine(1000), SR, 0.5)["over_unity_ratio"] == 0.0)
    check("silence_ratio: 무음 절반 → ≈0.5",
          abs(production_qc(np.concatenate([sine(1000, 5.0), np.zeros(SR * 5, dtype=np.float32)]),
                            SR, 0.5)["silence_ratio"] - 0.5) < 0.05)

    # 스테레오 상세 — L=R이면 밴드별 폭이 전부 0이고 위상 상관은 1
    same = np.stack([sine(440), sine(440)])
    sd = stereo_detail(same, SR)
    check("밴드별 스테레오 폭: L=R → 전 대역 0",
          all(abs(sd.get(f"stereo_width_{b}", 0.0)) < 1e-6 for b in ("low", "mid", "high")))
    check("위상 상관: L=R → 1.0", abs(sd.get("phase_correlation", 0.0) - 1.0) < 1e-6)
    inv = stereo_detail(np.stack([sine(440), -sine(440)]), SR)
    check("위상 상관: L=−R → −1.0", abs(inv.get("phase_correlation", 0.0) + 1.0) < 1e-6)

    # 리듬 부가 축
    reg = np.arange(0.0, 12.0, 0.5)
    # `or`로 기본값을 주면 **0.0이 falsy라 기본값으로 바뀐다** — 하한 검사에서는 치명적이다
    reg_e = ioi_entropy(reg)
    check("ioi_entropy 하한: 완전 등간격 → 0 (미해석 아님)", reg_e == 0.0, f"{reg_e}")
    beats_s = np.arange(0.0, 12.0, 0.5)
    straight = np.sort(np.concatenate([beats_s, beats_s + 0.25]))
    sw = swing_ratio(beats_s, straight)
    check("swing_ratio: 정확히 중간에 앉은 온셋 → 0.5", sw is not None and abs(sw - 0.5) < 0.02,
          f"{sw}")
    swung = np.sort(np.concatenate([beats_s, beats_s + 1.0 / 3]))
    sw2 = swing_ratio(beats_s, swung)
    check("swing_ratio 단조성: 셔플 온셋 > 스트레이트", sw2 is not None and sw is not None and sw2 > sw,
          f"{sw2} > {sw}")
    # 같은 마디를 반복하면 자기유사도가 높아야 한다.
    # ⚠ **픽스처의 해상도가 격자를 따라가야 한다**(D-038에서 실제로 걸렸다): 마디당
    # 프레임을 64로 박아 두면 32칸에서 칸당 2프레임이 되고, 그러면 부동소수 경계 오차가
    # 임펄스를 옆 칸으로 밀어 **코드가 아니라 픽스처 때문에** 자기유사도가 0.43으로
    # 떨어진다. 실측이 정한 예산(칸당 ~10프레임, RULES §3.1.5.2)을 픽스처도 지킨다 —
    # "불일치가 나오면 측정기를 먼저 의심하라"의 자기적용.
    frames_per_bar = BINS * 8                       # 칸당 8프레임
    step = frames_per_bar // 4
    one_bar = np.zeros(frames_per_bar, dtype=np.float64)
    # 임펄스를 칸 **안쪽**(칸 중앙)에 둔다 — 경계에 놓으면 앞 칸으로 밀린다
    one_bar[[i * step + 4 for i in range(4)]] = 3.0
    env_rep = np.tile(one_bar, 6)
    db = np.arange(7, dtype=np.float64) * (frames_per_bar * HOP_R / SR)
    ss = rhythm_self_similarity(env_rep, SR, db)
    check("마디 자기유사도: 같은 패턴 반복 → 높음", ss is not None and ss > 0.9, f"{ss}")
    # 반쪽 재현성: **대비는 속고 재현성은 안 속는다**가 이 축의 존재 이유다
    sh_rep = bar_profile_split_half(env_rep, SR, db)
    check("반쪽 재현성: 모든 마디 동일 → ≈1", sh_rep is not None and sh_rep > 0.99, f"{sh_rep}")
    # 홀수 마디와 짝수 마디가 **서로 다른 자리**에 큰 피크를 갖는 포락: 접으면 대비가
    # 높지만(피크 2개) 마디마다 형태가 다르다 — 대비는 "형태가 있다"고 말하고 재현성은
    # "반복되지 않는다"고 말한다. 이 조합을 가르는 것이 §3.8.4.4의 존재 이유다.
    alt = np.zeros(frames_per_bar * 6, dtype=np.float64)
    for i in range(6):
        alt[i * frames_per_bar + (4 if i % 2 == 0 else frames_per_bar // 2 + 4)] = 10.0
    sh_alt = bar_profile_split_half(alt, SR, db)
    c_alt = bar_profile_contrast(bar_profile(alt, SR, db))
    check("대비는 속고 재현성은 안 속는다(마디마다 다른 자리: 대비 높음 · 재현성 ≈0)",
          c_alt > 5.0 and sh_alt is not None and abs(sh_alt) < 0.2,
          f"contrast={c_alt:.1f} split_half={sh_alt}")
    # 한쪽 반에만 에너지가 있으면 **미해석**이다(결측 ≠ 0) — 0으로 채우면 "구조 없음"이
    # 되지만 참인 것은 "비교할 짝이 없다"다
    one_side = np.zeros(frames_per_bar * 6, dtype=np.float64)
    one_side[4] = 10.0
    check("반쪽 한 곳이 비면 미해석 (0이 아니다)",
          bar_profile_split_half(one_side, SR, db) is None)
    check("마디 2개 → 반쪽 재현성 미해석 (반쪽이 각 1마디)",
          bar_profile_split_half(env_rep, SR, db[:3]) is None)

    # ── 2마디 블록 분할 (RULES §3.1.5.4 ② · 사전 등록. 정답지 검증 전 표면 금지)
    # 위 `alt`가 바로 **2마디 루프**다(마디마다 피크 자리가 번갈아 든다). 1마디 분할은
    # 이것을 "구조 없음"으로 읽고(위 검사에서 ≈0), 그래서 D-142에서 정답지 2곡이
    # 탈락했다. 2마디 블록은 두 반쪽이 같은 형태를 담으므로 살아나야 한다 —
    # **그 차이가 이 정의의 전부**라 검사로 고정한다.
    sh2_alt = bar_profile_split_half_2bar(alt, SR, db)
    check("2마디 블록: 2마디 루프를 구조로 읽는다 (1마디 분할은 ≈0인 같은 신호)",
          sh2_alt is not None and sh2_alt > 0.9,
          f"1마디={sh_alt} 2마디={sh2_alt}")
    sh2_rep = bar_profile_split_half_2bar(env_rep, SR, db)
    check("2마디 블록: 모든 마디 동일해도 ≈1 (회귀 없음)",
          sh2_rep is not None and sh2_rep > 0.99, f"{sh2_rep}")
    check("2마디 블록: 마디 3개면 미해석 (블록 2개를 못 채운다 · 0이 아니다)",
          bar_profile_split_half_2bar(alt, SR, db[:4]) is None)


    # ── 레코드 정체성·병합 (RULES §1) — 이중 저장이 분포를 이중 가중하던 결함의 가드
    amap = _alias_map([{"key": "KiiiKiii", "aliases": ["키키"]}])
    check("별칭 해석: 차트 표기 → 정본 키 (casefold)", amap.get("키키") == "KiiiKiii", f"{amap}")
    chart_rec = {"key": "KiiiKiii", "chart_label": "키키", "cohort": "chart", "chart_rank": 8,
                 "source": "apple", "track_id": "t1", "observed_date": "2026-07-29",
                 "features": {"tempo_bpm": 120}}
    watch_rec = {"key": "KiiiKiii", "cohort": "watchlist", "source": "apple", "track_id": "t1",
                 "observed_date": "2026-07-29", "features": {"tempo_bpm": 120}}
    other_day = {**watch_rec, "observed_date": "2026-07-28"}
    merged = _dedupe([chart_rec, watch_rec, other_day])
    check("병합: 같은 (source,track_id,date) 2건 → 1건 (다른 날은 유지)", len(merged) == 2,
          f"{len(merged)}")
    m = merged[0]
    check("병합 결과: cohort=watchlist + 차트 필드 보존", m.get("cohort") == "watchlist"
          and m.get("chart_rank") == 8 and m.get("chart_label") == "키키", f"{m.get('cohort')}·{m.get('chart_rank')}")
    check("병합 멱등성: 재적용해도 불변", _dedupe(merged) == merged)

    # ── 스템 분리 축 (TESTS §7.2.1) — 순수 함수만이라 모델도 네트워크도 필요 없다.
    from sonic_profile.stems import selftest_stems

    print("\n[스템 분리 축 · TESTS §7.2.1]")
    stem_ran, stem_fails = selftest_stems()
    fails.extend(f"stems:{n}" for n in stem_fails)
    print(f"  스템 {stem_ran - len(stem_fails)}/{stem_ran}")

    print(f"\n{'all checks passed' if not fails else f'{len(fails)} check(s) FAILED: {fails}'}")
    return 1 if fails else 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    checked, errors = validate_report(report)
    if not checked:
        print("UNCHECKED — jsonschema not installed or schema not found", file=sys.stderr)
        return 2
    if errors:
        print(f"{args.report} · schema INVALID ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"{args.report} · schema valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sonic_profile", description="소리 지표 (30초 프리뷰·무보관)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_f = sub.add_parser("fetch", help="워치리스트 → 프리뷰 지표 스냅샷 (라이브·오디오 미저장)")
    p_f.add_argument("--watchlist", required=True)
    p_f.add_argument("--cohort", default=None,
                     help="chart_history tracks 산출 JSON — 분포용 차트 코호트(데이터로 전달, D-007)")
    p_f.add_argument("--cache", default=None,
                     help="트랙 지표 캐시 경로 (기본: 출력 폴더의 cache.json)")
    p_f.add_argument("--country", default="KR")
    p_f.add_argument("--low-hz", type=float, default=LOW_HZ_DEFAULT, help=f"저역 경계 (기본 {LOW_HZ_DEFAULT})")
    p_f.add_argument("--delay", type=float, default=0.5, help="요청 간 간격(초) — 저빈도 접근")
    p_f.add_argument("--no-rhythm", dest="rhythm", action="store_false",
                     help="리듬 패턴(비트·다운비트·킥 마디 프로파일) 생략")
    p_f.add_argument("--no-tags", dest="tags", action="store_false",
                     help="장르·악기 태깅 생략")
    p_f.add_argument("--model-dir", default=None,
                     help="태거 모델 경로 (기본 data/models — 없으면 내려받음)")
    # ── 스템 분리 (RULES §3.8) — **opt-in**. 곡당 +6~7초(코호트 200곡이면 +20~25분)라
    # TESTS §7.2.2 채택 게이트를 통과하기 전에 상시 비용을 지불하지 않는다.
    p_f.add_argument("--stems", action="store_true",
                     help="스템 분리 축(하프타임 스네어·슬라이딩 808·보컬 처리) 추가. "
                          "곡당 +6~7초 · 엔진 키가 갈라져 콜드 실행이 된다")
    # 임계값은 도메인 소유자(A&R) 소유다 — 코드에 은닉하지 않는다(AGENTS §2.1).
    p_f.add_argument("--halftime-min-ratio", type=float, default=HALFTIME_MIN_RATIO_DEFAULT,
                     help=f"하프타임 판정 비율 (기본 {HALFTIME_MIN_RATIO_DEFAULT} · 관습값)")
    p_f.add_argument("--bass-glide-min-st-per-sec", type=float,
                     default=BASS_GLIDE_MIN_ST_PER_SEC_DEFAULT,
                     help=f"글라이드 최소 기울기 세미톤/초 (기본 {BASS_GLIDE_MIN_ST_PER_SEC_DEFAULT} · 관습값)")
    p_f.add_argument("--bass-glide-min-ms", type=float, default=BASS_GLIDE_MIN_MS_DEFAULT,
                     help=f"글라이드 최소 지속 ms (기본 {BASS_GLIDE_MIN_MS_DEFAULT} · 관습값)")
    p_f.add_argument("--snare-min-contrast", type=float, default=SNARE_MIN_CONTRAST_DEFAULT,
                     help=f"스네어 축 유효성 게이트 대비 (기본 {SNARE_MIN_CONTRAST_DEFAULT} = "
                          "이 축 분포의 p10, RULES §3.8.4.3. 미만이면 스네어 축을 결측 처리)")
    p_f.add_argument("--vocal-note-min-ms", type=float, default=VOCAL_NOTE_MIN_MS_DEFAULT,
                     help=f"지속 노트 최소 길이 ms (기본 {VOCAL_NOTE_MIN_MS_DEFAULT} — "
                          "vocal_note_f0_spread, RULES §3.8.4)")
    p_f.add_argument("--vocal-note-max-drift", type=float, default=VOCAL_NOTE_MAX_DRIFT_DEFAULT,
                     help=f"지속 노트로 볼 프레임 간 최대 변화 센트 (기본 "
                          f"{VOCAL_NOTE_MAX_DRIFT_DEFAULT} — 초과하면 음이 바뀐 것으로 끊는다)")
    p_f.add_argument("-o", "--output", required=True)
    p_f.set_defaults(func=cmd_fetch)

    p_a = sub.add_parser("analyze", help="스냅샷 → report.json (오프라인)")
    p_a.add_argument("inputs", nargs="+")
    p_a.add_argument("--watchlist", default=None)
    # 하중받는 기준 — 코드에 은닉하지 않는다(AGENTS §2.1). 값은 도메인 소유자(A&R) 소유.
    # 유형은 저장된 kick_bar_profile에서 재계산되므로 이 값을 바꿔도 오디오를 다시 받지 않는다.
    p_a.add_argument(
        "--rhythm-min-match", type=float, default=MIN_MATCH_DEFAULT,
        help=f"리듬 유형 배정 최소 정합도 — 미만은 '해당 없음' (기본 {MIN_MATCH_DEFAULT}, 관습값)",
    )
    p_a.add_argument(
        "--rhythm-tie-gap", type=float, default=TIE_GAP_DEFAULT,
        help=f"1위−2위 차가 이 값 미만이면 동점 표시 (기본 {TIE_GAP_DEFAULT}, 관습값)",
    )
    p_a.add_argument(
        "--min-prob", type=float, default=MIN_PROB_DEFAULT,
        help=f"악기 검출로 볼 최소 확률 (기본 {MIN_PROB_DEFAULT}, 관습값)",
    )
    p_a.add_argument(
        "--new-release-days", type=int, default=NEW_RELEASE_DAYS,
        help=f"'신곡'으로 볼 발매 경과일 상한 (기본 {NEW_RELEASE_DAYS}, 관습값)",
    )
    p_a.add_argument("-o", "--output", required=True)
    p_a.set_defaults(func=cmd_analyze)

    p_r = sub.add_parser(
        "retag", help="상위 k 절단으로 잘린 과거 악기 라벨 복구 (라이브·멱등·오디오 미저장)"
    )
    p_r.add_argument("inputs", nargs="+")
    p_r.add_argument("--country", default="KR")
    p_r.add_argument("--delay", type=float, default=0.5, help="요청 간 간격(초) — 저빈도 접근")
    p_r.add_argument("--model-dir", default=None)
    p_r.add_argument("--dry-run", action="store_true", help="대상만 세고 아무것도 바꾸지 않는다")
    p_r.set_defaults(func=cmd_retag)

    p_s = sub.add_parser("signals", help="스냅샷 → signal-series (오프라인)")
    p_s.add_argument("inputs", nargs="+")
    p_s.add_argument("--field", default="pulse_clarity")
    p_s.add_argument("-o", "--output", required=True)
    p_s.set_defaults(func=cmd_signals)

    p_t = sub.add_parser("selftest", help="합성 신호로 지표 엔진 검증 (네트워크 0)")
    p_t.set_defaults(func=cmd_selftest)

    p_v = sub.add_parser("validate", help="report.json 스키마 검증")
    p_v.add_argument("report")
    p_v.set_defaults(func=cmd_validate)

    args = ap.parse_args(argv)
    return int(args.func(args))
