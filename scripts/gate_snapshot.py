"""게이트 모집단 조립 — 라이브 차트 코호트 + 정답지를 **한 스냅샷**으로 (네트워크 0).

`stem_gate.py`는 코호트와 정답지가 한 파일에 있어야 한다. 비교 모집단이 하나여야
백분위가 의미를 갖기 때문이다(genre-impulse RULES §2.1과 같은 규율). 그런데 daily
레그는 **차트 코호트만** 재고, 정답지는 연구 취득분에 있다 — 그 둘을 묶는 이 단계가
지금까지 스크립트로 남아 있지 않았다(`stem_gate_snapshot_v2.json`이 어떻게 조립됐는지
재현 명령이 문서에 없다). 그래서 판정을 다시 돌리려면 매번 손으로 맞춰야 했다.

🔴 **다른 조건에서 잰 값을 한 분포에 넣지 않는다.** 이 스크립트가 존재하는 진짜 이유가
이것이다: `rhythm_feature_set`·HOP·격자 칸수가 다르면 **같은 숫자가 다른 것을 뜻한다**
(D-037/D-038 실측 — HOP을 256에서 128로 내리자 같은 곡의 대비가 1.347 → 2.003이 됐다).
그런 두 취득을 조용히 합치면 백분위가 음악이 아니라 **측정 조건의 차이**를 잰다.
그래서 엔진 지문이 어긋나면 **거부한다** — 합쳐 놓고 각주로 적는 형태를 만들지 않는다.

Usage:

    python scripts/gate_snapshot.py \
      --cohort data/live/sonic/2026-07-31.json \
      --answers data/research/genre-impulse/signature_v4_merged.json \
      -o data/research/genre-impulse/stem_gate_snapshot_2026-07-31.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 조립이 성립하려면 이 지문이 두 취득에서 같아야 한다. 포락·격자에서 파생된 축 전부가
# 여기에 종속된다 — 값만 옮겨 쓰면 D-037이 저지른 실수(다른 조건의 값 빌려 오기)다.
ENGINE_KEYS = ("rhythm_feature_set", "rhythm_hop", "rhythm_bins", "rhythm_triplet_bins",
               "engine", "sample_rate", "low_hz")


def _engine(payload: dict[str, Any]) -> dict[str, Any]:
    prov = (payload.get("provenance") or {}).get("engine_provenance") or {}
    return {k: prov.get(k) for k in ENGINE_KEYS}


def _is_cohort(rec: dict[str, Any]) -> bool:
    """비교 모집단 = 당일 차트 코호트. `stem_gate._is_cohort`와 **같은 정의**여야 한다."""
    return rec.get("chart_market") == "KR" and rec.get("chart_platform") == "apple"


def build(cohort_path: Path, answers_path: Path, *,
          cases: tuple[str, ...], strict: bool = True) -> dict[str, Any]:
    cohort_doc = json.loads(cohort_path.read_text(encoding="utf-8"))
    answers_doc = json.loads(answers_path.read_text(encoding="utf-8"))

    eng_c, eng_a = _engine(cohort_doc), _engine(answers_doc)
    mismatch = {k: (eng_c.get(k), eng_a.get(k)) for k in ENGINE_KEYS if eng_c.get(k) != eng_a.get(k)}
    if mismatch and strict:
        lines = "\n".join(f"    {k}: 코호트 {c!r} vs 정답지 {a!r}" for k, (c, a) in mismatch.items())
        raise SystemExit(
            "🔴 엔진 지문이 어긋나 조립을 거부한다 — 두 취득의 값은 같은 분포에 들어갈 수 없다\n"
            f"{lines}\n"
            "    (같은 조건으로 다시 취득하거나, 어긋난 축을 쓰지 않는 게이트만 돌릴 것)"
        )

    cohort = [r for r in cohort_doc.get("records") or [] if _is_cohort(r)]
    answers = [r for r in answers_doc.get("records") or []
               if r.get("chart_market") in cases and r.get("chart_platform")]
    if not cohort:
        raise SystemExit(f"코호트가 비었다 — {cohort_path}에 KR/apple 레코드가 없다")
    if not answers:
        raise SystemExit(f"정답지가 비었다 — {answers_path}에 {cases} 레코드가 없다")

    return {
        "records": cohort + answers,
        "provenance": {
            "assembled_by": "scripts/gate_snapshot.py",
            "note": "게이트 모집단 = 당일 차트 코호트 + 정답지. 비교 모집단이 하나여야 "
                    "백분위가 의미를 갖는다",
            "cohort": {"source": str(cohort_path), "n": len(cohort),
                       "observed_date": (cohort[0] or {}).get("observed_date")},
            "answers": {"source": str(answers_path), "n": len(answers), "cases": list(cases)},
            "engine_provenance": eng_c,
            "engine_match": not mismatch,
            "engine_mismatch": mismatch or None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate_snapshot",
                                 description="게이트 모집단 조립 (코호트 + 정답지 · 네트워크 0)")
    ap.add_argument("--cohort", required=True, help="라이브 sonic 스냅샷 (당일 차트)")
    ap.add_argument("--answers", required=True, help="정답지를 담은 스냅샷 (연구 취득분)")
    ap.add_argument("--cases", default="jersey-club,drill,hyperpop",
                    help="정답지로 실을 케이스 슬러그 (쉼표 구분)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--allow-engine-mismatch", action="store_true",
                    help="🔴 엔진 지문이 달라도 조립한다. **백분위가 측정 조건 차이를 재게 된다** — "
                         "쓰려면 왜 안전한지 원장에 적을 것")
    args = ap.parse_args(argv)

    payload = build(Path(args.cohort), Path(args.answers),
                    cases=tuple(c.strip() for c in args.cases.split(",") if c.strip()),
                    strict=not args.allow_engine_mismatch)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    prov = payload["provenance"]
    print(f"wrote {args.out} · 코호트 {prov['cohort']['n']}곡({prov['cohort']['observed_date']}) "
          f"+ 정답지 {prov['answers']['n']}곡 · 엔진 일치 {prov['engine_match']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
