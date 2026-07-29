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

from sonic_profile.features import LOW_HZ_DEFAULT, SR, Unresolved, engine_provenance, extract
from sonic_profile.report import build_report, build_signal_series, now_iso

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


def _load(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    prov: dict[str, Any] = {}
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            records.extend(r for r in (doc.get("records") or []) if isinstance(r, dict))
            prov = prov or (doc.get("provenance") or {})
    return records, prov


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
    from sonic_profile.preview import (
        candidates,
        decoder_provenance,
        features_from_preview,
        track_candidates,
    )

    from sonic_profile.models import ensure_models, model_dir, tagger_provenance
    from sonic_profile.rhythm import rhythm_provenance

    today = time.strftime("%Y-%m-%d")
    eng = {**engine_provenance(args.low_hz), **decoder_provenance()}
    if args.rhythm:
        eng.update(rhythm_provenance())
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
        eng.get("beat_engine", "-"), eng.get("tagger", "-"),
    ])
    cache_path = Path(args.cache) if args.cache else Path(args.output).parent / "cache.json"
    cache = _cache_load(cache_path, engine_key)
    cache_hits = 0
    records: list[dict[str, Any]] = []

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
        )
        if cand.get("track_id"):
            cache[cid] = feats
        time.sleep(args.delay)
        return feats

    # ── 코호트: 차트 트랙 (분포를 만들려면 모집단이 있어야 한다)
    if args.cohort:
        cdoc = json.loads(Path(args.cohort).read_text(encoding="utf-8"))
        for t in cdoc.get("tracks") or []:
            artist, title = str(t.get("artist") or ""), str(t.get("title") or "")
            rec: dict[str, Any] = {
                "key": artist,
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

    doc = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    acts = [a for a in (doc.get("artists") or []) if isinstance(a, dict) and a.get("key")]
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
    report = build_report(records, generated_at=now_iso(), provenance=prov, watchlist=watch)
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
    for b in bars[:-1]:
        for q in (0, 4, 8, 12):                          # 16분 격자의 정박 위치
            # 프레임 인덱스는 **반올림**해야 한다 — 잘라 넣으면 0.5초가 0.4993초가 되어
            # 칸 경계에서 앞 칸으로 밀린다(4번 → 3번). 격자 정렬 픽스처의 함정.
            env[int(round((b + 2.0 * q / BINS) * SR / R_HOP))] = 1.0
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
    p_f.add_argument("-o", "--output", required=True)
    p_f.set_defaults(func=cmd_fetch)

    p_a = sub.add_parser("analyze", help="스냅샷 → report.json (오프라인)")
    p_a.add_argument("inputs", nargs="+")
    p_a.add_argument("--watchlist", default=None)
    p_a.add_argument("-o", "--output", required=True)
    p_a.set_defaults(func=cmd_analyze)

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
