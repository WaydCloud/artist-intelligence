"""genre-impulse CLI — 임펄스 원장과 일일 sonic 코호트를 대조한다.

무단정(RULES §1): 출력은 "검출 규칙 매치 + 과거 사례 문맥"까지이며 도달/성공을
말하지 않는다. 실행에는 PYTHONPATH에 이 모듈과 sonic-profile의 src가 모두
필요하다(organic_ratio 파생 재사용 — RULES §3의 문서화된 한시 예외).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from genre_impulse import MODULE_ID, MODULE_VERSION

# 하중받는 기준 — 값은 도메인 소유자 소유, CLI로 노출(RULES §2.1).
LOW_PCT_DEFAULT = 20.0
HIGH_PCT_DEFAULT = 80.0

# 표면에 올릴 수 있는 확실성 등급(D-033 보완⑥ — 중간 이상만, 등급 병기).
SURFACE_GRADES = ("매우 높음", "높음", "중간")

# 검출 규칙 원장(RULES §2). 사전 등록·실측 검증을 거친 규칙만 올린다.
RULES: list[dict[str, Any]] = [
    {
        "id": "hyperpop-texture",
        "impulse_id": "hyperpop",
        "low_all": ["organic_ratio"],
        "high_any": ["spectral_flatness", "over_unity_ratio"],
        "basis": "A2.1 실측 2026-07-30 — Savage organic P2.2·flatness P87.9·over_unity P80.2 (CASEBOOK §A2.1)",
    },
]

RULE_AXES = sorted({ax for r in RULES for ax in [*r["low_all"], *r["high_any"]]})

# 단정 어휘 가드(TESTS §4.11) — report 직렬화에 있으면 안 되는 표현.
FORBIDDEN = ("차트인할", "뜰 것", "데뷔감")


def _derive(features: dict[str, Any]) -> dict[str, Any]:
    """sonic-profile 파생 재계산 재사용 — 재구현 금지(AGENTS §1)."""
    try:
        from sonic_profile.derived import derive_all  # type: ignore[import-not-found]
    except ImportError as exc:  # PYTHONPATH 안내가 없으면 원인을 알 수 없는 실패가 된다
        raise SystemExit(
            "sonic_profile을 찾을 수 없습니다 — PYTHONPATH에 modules/sonic-profile/src를 추가하세요"
        ) from exc
    out = dict(features)
    out.update(derive_all(features))
    return out


def _percentile(pool: list[float], x: float) -> float:
    """코호트 내 백분위 — `이하 비율` 정의(동값 결정적, TESTS §3.9)."""
    if not pool:
        return 0.0
    below = sum(1 for v in pool if v <= x)
    return round(100.0 * below / len(pool), 1)


def load_impulses(path: Path, schema_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """원장 로드 — 스키마 위반은 스킵하되 보고한다(조용한 무시 금지, RULES §3)."""
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    for f in sorted(path.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as exc:
            skipped.append(f"{f.name}: {exc.message[:80]}")
            continue
        records.append(doc)
    return records, skipped


def load_cohort(path: Path) -> tuple[list[dict[str, Any]], str]:
    """sonic 스냅샷 로드 — 디렉터리면 최신 일자 파일, 코호트=features 있는 레코드."""
    if path.is_dir():
        dated = sorted(p for p in path.glob("????-??-??.json"))
        if not dated:
            return [], ""
        path = dated[-1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    recs = [r for r in doc.get("records", []) if isinstance(r.get("features"), dict)]
    return recs, path.name


def evaluate(
    cohort: list[dict[str, Any]], low_pct: float, high_pct: float
) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
    """규칙 평가 — 축별 코호트 백분위 계산 후 조합 판정."""
    feats = [(r, _derive(r["features"])) for r in cohort]
    pools: dict[str, list[float]] = {
        # 0.0은 유효값이다 — falsy 검사 금지(TESTS §3.10, D-032 함정).
        ax: [f[ax] for _, f in feats if isinstance(f.get(ax), (int, float))]
        for ax in RULE_AXES
    }
    matches: list[dict[str, Any]] = []
    for rule in RULES:
        for rec, f in feats:
            pcts: dict[str, float] = {}
            evaluable = True
            for ax in [*rule["low_all"], *rule["high_any"]]:
                v = f.get(ax)
                if not isinstance(v, (int, float)):
                    evaluable = False
                    break
                pcts[ax] = _percentile(pools[ax], float(v))
            if not evaluable:
                continue
            low_ok = all(pcts[ax] <= low_pct for ax in rule["low_all"])
            high_ok = any(pcts[ax] >= high_pct for ax in rule["high_any"])
            if low_ok and high_ok:
                matches.append({
                    "rule": rule["id"],
                    "impulse_id": rule["impulse_id"],
                    "key": str(rec.get("key") or rec.get("query") or "?"),
                    "label": f"{rec.get('artist', rec.get('key', '?'))} - {rec.get('title', '?')}",
                    "pcts": pcts,
                })
    matches.sort(key=lambda m: (m["rule"], m["pcts"][RULES[0]["low_all"][0]], m["label"]))
    return matches, pools


def _context_lines(impulse: dict[str, Any]) -> list[str]:
    """원장 문맥 인용 — 확실성 중간 이상만 표면에(RULES §1)."""
    lines: list[str] = []
    mode = impulse.get("adoption_mode", {}).get("mode", "?")
    lines.append(f"[문맥] '{impulse.get('name_ko', impulse['id'])}' 수용 모드: {mode} (원장 {impulse.get('version')})")
    eb = impulse.get("element_borrowing")
    if isinstance(eb, dict):
        for t in eb.get("anchor_tracks", []):
            grade = str(t.get("certainty", ""))
            if grade in SURFACE_GRADES:
                lines.append(
                    f"[문맥] 과거 차용 앵커: {t.get('artist')} - {t.get('title')}"
                    f" ({t.get('date')}, 확실성 {grade})"
                )
    idf = impulse.get("identity_formation")
    if isinstance(idf, dict) and idf.get("occurred"):
        lines.append(
            f"[문맥] 정체성화 전례: {idf.get('group')} '{idf.get('fandom_slang')}'"
            f" (언론 공식화 {idf.get('press_formalization_date')})"
        )
    return lines


def _coverage_lines(impulses: list[dict[str, Any]], ruled_ids: set[str]) -> list[str]:
    lines: list[str] = []
    for imp in impulses:
        if imp["id"] in ruled_ids:
            continue
        sig = imp.get("signature", {})
        locks = sig.get("locks") or []
        reason = "; ".join(locks) if locks else f"서명 상태 {sig.get('status', '?')} — 규칙 미도출"
        lines.append(f"[관측 불가] {imp.get('name_ko', imp['id'])}: {reason}")
    return lines


def build_report(
    impulses: list[dict[str, Any]],
    skipped: list[str],
    cohort: list[dict[str, Any]],
    snapshot_name: str,
    low_pct: float,
    high_pct: float,
    watch_keys: set[str],
) -> dict[str, Any]:
    matches, pools = evaluate(cohort, low_pct, high_pct) if cohort else ([], {})
    ruled_ids = {r["impulse_id"] for r in RULES}
    by_id = {i["id"]: i for i in impulses}

    insights: list[str] = [
        "[정직성] 유사 ≠ 도달 — 매치는 검토 후보이지 예측이 아니다. 판단은 A&R의 몫.",
        f"[정직성] 검출 규칙 커버리지 {len(RULES)}/{len(impulses) or '?'} — 대부분의 임펄스는 아직 규칙이 없다(아래 관측 불가 표).",
        "[정직성] 백분위는 당일 코호트 내 상대 위치다 — 코호트 구성이 바뀌면 같은 곡도 값이 달라진다.",
    ]
    for s in skipped:
        insights.append(f"[원장 스킵] 스키마 위반: {s}")
    for m in matches:
        px = " · ".join(f"{ax} P{p}" for ax, p in sorted(m["pcts"].items()))
        star = "★" if m["key"] in watch_keys else ""
        insights.append(f"[매치] {star}{m['label']} — 규칙 {m['rule']} ({px})")
    for rule in RULES:
        imp = by_id.get(rule["impulse_id"])
        if imp and any(m["rule"] == rule["id"] for m in matches):
            insights.extend(_context_lines(imp))
        insights.append(f"[규칙 근거] {rule['id']}: {rule['basis']}")
    insights.extend(_coverage_lines(impulses, ruled_ids))
    if not cohort:
        insights.append("[입력] 코호트 0곡 — sonic 스냅샷이 비어 있어 매치를 계산하지 않았다.")

    charts: list[dict[str, Any]] = []
    if matches:
        low_ax = RULES[0]["low_all"][0]
        charts.append({
            "type": "bar",
            "title": f"검출 매치 · {low_ax} 코호트 백분위 (낮을수록 규칙 부합)",
            "data": [
                {"label": ("★" if m["key"] in watch_keys else "") + m["label"], "value": m["pcts"][low_ax]}
                for m in matches
            ],
        })
    if cohort:
        charts.append({
            "type": "tunable",
            "title": "임계 튜너 — 백분위 컷 재계산 (값=A&R 소유)",
            "data": {
                "view": "impulse-rules",
                "lowPct": low_pct,
                "highPct": high_pct,
                "axes": RULE_AXES,
                "pools": {ax: sorted(v) for ax, v in pools.items()},
            },
        })

    return {
        "moduleId": MODULE_ID,
        "title": "장르 임펄스 모니터",
        "subtitle": f"원장 {len(impulses)}건 × 코호트 {len(cohort)}곡 ({snapshot_name or '입력 없음'}) · v{MODULE_VERSION}",
        "generatedAt": datetime.now(UTC).isoformat(),
        "metrics": [
            {"label": "원장 임펄스", "value": len(impulses), "unit": "건"},
            {"label": "검출 규칙 확정", "value": len(RULES), "unit": "건",
             "hint": f"커버리지 {len(RULES)}/{len(impulses) or 0} — 축 공백·스템 잠금은 RULES §2.2"},
            {"label": "당일 코호트", "value": len(cohort), "unit": "곡"},
            {"label": "규칙 매치", "value": len(matches), "unit": "곡"},
        ],
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": [
            "매치 트랙은 요소 차용 관점의 청취 검토 후보다 — 과거 사례 문맥(모드·리드타임)과 함께 볼 것.",
            "규칙이 없는 임펄스의 신호는 이 리포트에 없다 — 부재를 '신호 없음'으로 읽지 말 것.",
        ],
    }


def cmd_analyze(args: argparse.Namespace) -> int:
    impulses, skipped = load_impulses(Path(args.impulses), Path(args.impulse_schema))
    cohort, snap_name = load_cohort(Path(args.sonic))
    watch_keys: set[str] = set()
    if args.watchlist and Path(args.watchlist).exists():
        doc = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
        watch_keys = {str(a["key"]) for a in doc.get("artists", []) if isinstance(a, dict) and a.get("key")}
    report = build_report(impulses, skipped, cohort, snap_name, args.low_pct, args.high_pct, watch_keys)
    out = Path(args.output) / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} · 매치 {sum(1 for i in report['insights'] if i.startswith('[매치]'))}건")
    return 0


# ── selftest ──────────────────────────────────────────────────────────────

def _fx_track(key: str, organic: float, flat: float, over: float) -> dict[str, Any]:
    return {"key": key, "artist": key, "title": key, "cohort": "chart",
            "features": {"organic_ratio": organic, "spectral_flatness": flat, "over_unity_ratio": over}}


def _fx_impulse(iid: str, grade: str = "매우 높음") -> dict[str, Any]:
    return {
        "id": iid, "name_ko": iid, "version": "1.0.0", "updated": "2026-07-30",
        "case_type": "import",
        "adoption_mode": {"mode": "element"},
        "trajectory": [{"cell": "kr-mainstream", "date": "2022-12", "evidence": "픽스처", "certainty": "높음"}],
        "leadtimes": [{"from_cell": "origin-viral", "to_cell": "kr-mainstream", "months": 12}],
        "early_signals": [{"source_type": "shortform-viral", "date": "2021-01", "evidence": "픽스처", "certainty": "높음"}],
        "element_borrowing": {"elements": ["금속성 신스"], "stage_reached": "identity",
                              "anchor_tracks": [{"artist": "A", "title": "T", "date": "2021-10", "certainty": grade}]},
        "identity_formation": None,
        "signature": {"status": "pending-a2", "locks": ["stem-separation: 보컬 처리"]},
        "limits": ["픽스처"],
    }


def cmd_selftest(_args: argparse.Namespace) -> int:
    import tempfile

    import jsonschema

    root = Path(__file__).resolve().parents[4]
    report_schema = json.loads((root / "packages/report-schema/report.schema.json").read_text(encoding="utf-8"))
    impulse_schema_path = root / "data/research/genre-impulse/impulse.schema.json"

    passed = failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))

    cohort = [_fx_track(f"mid{i}", 0.5 + i * 0.01, 0.010 + i * 0.001, 0.02 + i * 0.001) for i in range(8)]
    planted = _fx_track("planted", 0.01, 0.09, 0.20)  # organic 최하위 + flat/over 최상위
    cohort_pos = [*cohort, planted]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        imp_dir = tmp / "impulses"
        imp_dir.mkdir()
        (imp_dir / "hyperpop.json").write_text(json.dumps(_fx_impulse("hyperpop")), encoding="utf-8")
        (imp_dir / "ruleless.json").write_text(json.dumps(_fx_impulse("ruleless")), encoding="utf-8")
        (imp_dir / "broken.json").write_text(json.dumps({"id": "broken"}), encoding="utf-8")
        (tmp / "sonic").mkdir()
        (tmp / "sonic" / "2026-07-30.json").write_text(
            json.dumps({"records": cohort_pos}), encoding="utf-8")

        impulses, skipped = load_impulses(imp_dir, impulse_schema_path)
        recs, snap = load_cohort(tmp / "sonic")
        rep = build_report(impulses, skipped, recs, snap, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())

        errors = list(jsonschema.Draft202012Validator(report_schema).iter_errors(rep))
        check("1 스키마 유효", not errors, "; ".join(e.message[:60] for e in errors[:2]))

        rep2 = build_report(impulses, skipped, recs, snap, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())
        strip = lambda r: json.dumps({**r, "generatedAt": ""}, ensure_ascii=False, sort_keys=True)
        check("2 결정성", strip(rep) == strip(rep2))

        empty = build_report(impulses, skipped, [], "", LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())
        check("3 빈 코호트 graceful", any("코호트 0곡" in i for i in empty["insights"]))

        check("4 위반 레코드 스킵+보고", len(impulses) == 2 and any("broken" in s for s in skipped)
              and any("[원장 스킵]" in i for i in rep["insights"]))

        low_grade_dir = tmp / "imp2"
        low_grade_dir.mkdir()
        (low_grade_dir / "hyperpop.json").write_text(json.dumps(_fx_impulse("hyperpop", grade="낮음")), encoding="utf-8")
        imps_low, _ = load_impulses(low_grade_dir, impulse_schema_path)
        rep_low = build_report(imps_low, [], recs, snap, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())
        check("5 중간 미만 등급 미표면", not any("과거 차용 앵커" in i for i in rep_low["insights"])
              and any("과거 차용 앵커" in i for i in rep["insights"]))

        m, _pools = evaluate(cohort_pos, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("6 양성 매치", any(x["key"] == "planted" for x in m))
        check("7 음성 무매치", not any(x["key"].startswith("mid") for x in m))
        m_tight, _ = evaluate(cohort_pos, 1.0, 99.9)
        check("8 임계 극단 → 매치 0", not m_tight)
        check("9 n=1 백분위", _percentile([0.5], 0.5) == 100.0 and evaluate([planted], 20, 80) is not None)
        m_zero, _ = evaluate([_fx_track("z", 0.0, 0.09, 0.2), *cohort], LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("10 organic 0.0은 유효값", any(x["key"] == "z" for x in m_zero))

        blob = json.dumps(rep, ensure_ascii=False)
        check("11 단정 어휘 없음", not any(w in blob for w in FORBIDDEN))
        check("12 커버리지 KPI", any("커버리지" in str(x.get("hint", "")) for x in rep["metrics"]))
        check("13 정직성 인사이트", rep["insights"][0].startswith("[정직성]"))

    print(f"selftest: {passed} passed · {failed} failed")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="genre_impulse",
        description="임펄스 원장 × 일일 sonic 코호트 대조 (PYTHONPATH에 sonic-profile/src 필요)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_a = sub.add_parser("analyze", help="원장 × 스냅샷 → report.json (오프라인)")
    p_a.add_argument("--impulses", default="data/research/genre-impulse/impulses")
    p_a.add_argument("--impulse-schema", default="data/research/genre-impulse/impulse.schema.json")
    p_a.add_argument("--sonic", required=True, help="sonic 스냅샷 파일 또는 디렉터리(최신 일자 사용)")
    p_a.add_argument("--watchlist", default=None)
    # 하중받는 기준 — 코드에 은닉하지 않는다(AGENTS §2.1). 값=도메인 소유자 소유.
    p_a.add_argument("--low-pct", type=float, default=LOW_PCT_DEFAULT,
                     help=f"하위 백분위 컷 (기본 {LOW_PCT_DEFAULT}, 관습값)")
    p_a.add_argument("--high-pct", type=float, default=HIGH_PCT_DEFAULT,
                     help=f"상위 백분위 컷 (기본 {HIGH_PCT_DEFAULT}, 관습값)")
    p_a.add_argument("-o", "--output", required=True)
    p_a.set_defaults(func=cmd_analyze)

    p_s = sub.add_parser("selftest", help="네트워크 0 자체 검증 (TESTS)")
    p_s.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
