"""스템 축 채택 게이트 (sonic-profile TESTS §7.2.2) — D-034 ③.

**구현했다고 채택되는 것이 아니다.** 축이 실제로 무언가를 가르는지 정답지로 재고,
못 가르면 원장에 "판별력 없음"으로 적는다(RULES §3.7.1 규율 — `meter_duple_bias`
선례). 이 스크립트가 그 판정을 돌린다.

절차:
  1. `--snapshot`은 **당일 차트 코호트 + 정답지**를 한 번에 잰 스냅샷이다.
     비교 모집단이 하나여야 백분위가 의미를 갖는다(genre-impulse RULES §2.1과
     같은 규율 — 백분위는 당일 코호트 내 순위다).
  2. 축별로 정답지 트랙의 코호트 내 백분위를 낸다.
  3. TESTS §7.2.2의 통과 기준(정답지 n곡 중 k곡 이상이 상위 20%)을 적용한다.

백분위 계산은 genre-impulse의 `_percentile`을 **import해 쓴다** — 두 벌이 되면
게이트가 재는 백분위와 모니터가 쓰는 백분위가 갈라진다(AGENTS §1).

Usage:

    PYTHONPATH="modules/genre-impulse/src;modules/sonic-profile/src" \
      python scripts/stem_gate.py \
        --snapshot data/research/genre-impulse/stem_gate_snapshot.json \
        -o data/research/genre-impulse/stem_gate_result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_percentile() -> Any:
    """백분위는 genre-impulse의 것을 그대로 쓴다 — 두 벌이 되면 게이트가 재는 백분위와
    모니터가 쓰는 백분위가 갈라진다(AGENTS §1)."""
    try:
        from genre_impulse.cli import _percentile  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - 실행 환경 안내
        raise SystemExit(
            "genre_impulse를 찾을 수 없습니다 — PYTHONPATH에 modules/genre-impulse/src를 추가하세요"
        ) from exc
    return _percentile



# TESTS §7.2.2 원장. `case`는 gate 코호트의 `market` 값이고, `roles`가 비면 전 역할.
#   - jersey-club 원형 5곡 = origin (하프타임 스네어)
#   - drill 원형 3곡 = origin (슬라이딩 808)
#   - hyperpop 계보 5곡 = aespa 계보(쇠맛) — RULES §2.1의 A2.1 정답지와 같은 집합
GATES: list[dict[str, Any]] = [
    {
        "axis": "halftime_snare_ratio",
        "case": "jersey-club",
        "roles": ["origin"],
        "expect_n": 5,
        "need": 3,
        "note": "저지클럽 하프타임 스네어 (RULES §3.8.2)",
    },
    {
        "axis": "bass_glide_ratio",
        "case": "drill",
        "roles": ["origin"],
        "expect_n": 3,
        "need": 2,
        "note": "드릴 슬라이딩 808 (RULES §3.8.3) — A2.1에서 축 공백이 실증된 케이스",
    },
    {
        "axis": "vocal_tuning_hardness",
        "case": "hyperpop",
        "artists": ["aespa"],
        "expect_n": 5,
        "need": 3,
        "note": "하이퍼팝 보컬 처리 (RULES §3.8.4) — 쇠맛 계보 5곡",
    },
    {
        "axis": "vocal_pitch_shift_proxy",
        "case": "hyperpop",
        "artists": ["aespa"],
        "expect_n": 5,
        "need": 3,
        "note": "🔺 사전 등록 프록시 — 실패 시 해석을 버린다(meter_duple_bias 선례)",
    },
]

TOP_PCT = 80.0   # "상위 20%" = 백분위 80 이상


def _feat(rec: dict[str, Any], axis: str) -> float | None:
    v = (rec.get("features") or {}).get(axis)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _is_cohort(rec: dict[str, Any]) -> bool:
    """비교 모집단 = 당일 차트 코호트(KR/apple). 정답지는 market이 케이스 슬러그다."""
    return rec.get("chart_market") == "KR" and rec.get("chart_platform") == "apple"


def _answers(recs: list[dict[str, Any]], gate: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for r in recs:
        if r.get("chart_market") != gate["case"]:
            continue
        if gate.get("roles") and r.get("chart_platform") not in gate["roles"]:
            continue
        if gate.get("artists"):
            label = str(r.get("chart_label") or r.get("key") or "").casefold()
            if not any(a.casefold() in label for a in gate["artists"]):
                continue
        out.append(r)
    return out


def run(snapshot: Path) -> dict[str, Any]:
    _percentile = _load_percentile()
    recs = json.loads(snapshot.read_text(encoding="utf-8")).get("records") or []
    cohort = [r for r in recs if _is_cohort(r)]
    results = []

    for gate in GATES:
        axis = gate["axis"]
        pool = [v for r in cohort if (v := _feat(r, axis)) is not None]
        answers = _answers(recs, gate)
        rows = []
        for r in answers:
            v = _feat(r, axis)
            rows.append({
                "track": f"{r.get('chart_label') or r.get('key')} - {str(r.get('query', '')).split(' - ')[-1]}",
                "value": v,
                "percentile": _percentile(pool, v) if v is not None else None,
                "unresolved": r.get("unresolved") or r.get("stems_unresolved"),
            })
        scored = [x for x in rows if x["percentile"] is not None]
        hits = sum(1 for x in scored if x["percentile"] >= TOP_PCT)
        # **"못 쟀다"와 "못 가른다"를 뭉치면 원장에 거짓이 들어간다**(§0 결측 ≠ 0).
        # 특히 측정된 정답지가 기준(need)보다 적으면 판별력과 무관하게 산술적으로
        # 실패가 강제된다 — 그걸 "판별력 없음"으로 적으면 축을 억울하게 죽인다.
        # (2026-07-30 실측: 하프타임은 유효성 게이트가 정답지 5곡 중 3곡을
        #  떨어뜨려 2곡만 남았고, 기준 3을 넘을 방법이 원리적으로 없었다.)
        if not scored or len(pool) < 10 or len(scored) < gate["need"]:
            verdict = "unmeasured"
        else:
            verdict = "pass" if hits >= gate["need"] else "fail"
        results.append({
            "axis": axis,
            "note": gate["note"],
            "cohort_n": len(pool),
            "answers_expected": gate["expect_n"],
            "answers_measured": len(scored),
            "hits_top20": hits,
            "need": gate["need"],
            "verdict": verdict,
            "tracks": sorted(rows, key=lambda x: -(x["percentile"] or -1)),
        })
        # 축이 실제로 무엇을 재는지 — 고유값 수가 표본 수보다 훨씬 적으면 그 축은
        # 음악이 아니라 **측정기의 격자**를 재고 있다(D-031 `grid_deviation_ms` 선례).
        distinct = len({round(v, 6) for v in pool})
        quantized = bool(pool and distinct <= max(4, len(pool) // 10))
        results[-1]["distinct_values"] = distinct
        results[-1]["quantized"] = quantized
        if quantized and results[-1]["verdict"] == "fail":
            # 값이 몇 개뿐이면 백분위가 의미를 잃는다 — 이 축의 "실패"는 판별력이
            # 없다는 뜻이 아니라 **측정이 깨졌다**는 뜻이다. 원장에 잘못 적지 않는다.
            results[-1]["verdict"] = "unmeasured"
            verdict = "unmeasured"
        flag = " ⚠양자화" if quantized else ""
        print(f"  {verdict.upper():10s} {axis:26s} "
              f"상위20% {hits}/{len(scored)} (기준 {gate['need']}) · 코호트 {len(pool)}곡 "
              f"· 고유값 {distinct}{flag}",
              file=sys.stderr)
    return {
        "gate": "sonic-profile stem axes (TESTS §7.2.2)",
        "decision": "D-034 ③",
        "top_pct": TOP_PCT,
        "snapshot": str(snapshot),
        "cohort_records": len(cohort),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stem_gate", description="스템 축 채택 게이트 (TESTS §7.2.2)")
    ap.add_argument("--snapshot", required=True, help="코호트+정답지를 함께 잰 sonic 스냅샷")
    ap.add_argument("-o", "--out", help="판정 JSON 경로")
    args = ap.parse_args(argv)

    payload = run(Path(args.snapshot))
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    # 두 결론은 다른 후속을 부른다 — 뭉쳐서 보고하면 잘못된 후속이 따라온다.
    failed = [r["axis"] for r in payload["results"] if r["verdict"] == "fail"]
    unmeasured = [r["axis"] for r in payload["results"] if r["verdict"] == "unmeasured"]
    if failed:
        print(f"\n판별력 없음(원장에 그대로 적는다, RULES §3.7.1): {failed}", file=sys.stderr)
    if unmeasured:
        print(f"판정 불가(표본 부족·측정 결함 — 원인을 고친 뒤 재실행): {unmeasured}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
