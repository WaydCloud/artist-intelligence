"""빌보드 궤적 → 임펄스 원장 `chart_evidence` 편입 (D-035 ② 후속).

`billboard_ingest.py trajectory`가 낸 **사실 필드**를 임펄스 레코드에 싣는다.
`trajectory`(사람이 큐레이션한 서술 근거)에 섞지 않고 **별도 배열**로 두는 것이
이 스크립트의 유일한 설계 결정이며, 이유는 둘이 반박되는 방식이 다르기 때문이다:
서술 근거는 해석을 다투고, 차트 사실은 수치를 다툰다. 섞어 두면 나중에 어느
쪽이 재조정 가능한 주장인지 알 수 없다.

**셀 배정을 하지 않는다.** Hot 100 차트인은 "미국 시장에 도달했다"는 사실이고,
그것이 원장의 어느 셀(origin-mainstream? kr-mainstream?)에 해당하는지는
도메인 판단이다 — 예컨대 뉴진스의 Hot 100 진입은 **한국 주류화가 아니라 미국
도달**이라 자동 배정하면 정확히 틀린다. 링크는 사람이 단다.

멱등: 같은 입력으로 다시 돌리면 같은 결과이며 `chart_evidence`를 통째로 교체한다.

Usage:

    python scripts/impulse_chart_evidence.py \
        --trajectories data/research/genre-impulse/billboard_trajectories.json \
        --impulses data/research/genre-impulse/impulses [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SOURCE = "github.com/mhollingshead/billboard-hot-100 (D-035 ② · 3자 대조 스모크 통과)"
# 차트 순위는 발표된 사실이고 대조에서 사실 불일치 0이었다 — 원장 등급 최상위.
_CERTAINTY = "매우 높음"


def _evidence_rows(results: list[dict[str, Any]], case: str) -> list[dict[str, Any]]:
    rows = []
    for r in results:
        if r.get("case") != case:
            continue
        row: dict[str, Any] = {
            "chart": "billboard-hot100",
            "artist": r.get("artist", ""),
            "title": r.get("title", ""),
            "role": r.get("role", ""),
            "charted": bool(r.get("charted")),
            "source": _SOURCE,
            "certainty": _CERTAINTY,
        }
        if r.get("charted"):
            for src, dst in (
                ("entry_date", "entry_date"), ("exit_date", "exit_date"),
                ("peak_position", "peak_position"), ("peak_date", "peak_date"),
                ("weeks_on_chart_reported", "weeks_on_chart"),
                ("weeks_in_window", "weeks_counted"),
            ):
                if r.get(src) is not None:
                    row[dst] = r[src]
            if row.get("weeks_on_chart") != row.get("weeks_counted"):
                row["note"] = (
                    "보고 체류주와 발행 주차 수가 다르다 — 차트 런이 2018-01-06 "
                    "연말 경계를 지났다(REVIEW-billboard-3way-smoke §3)."
                )
        else:
            row["note"] = (
                "전 이력(1958~) 조회에서 Hot 100 미검출. '영향이 없었다'가 아니라 "
                "'미국 주류 차트를 거치지 않았다'이며, 크레딧 표기가 크게 다르면 "
                "매칭이 놓쳤을 수 있다."
            )
        rows.append(row)
    return sorted(rows, key=lambda x: (not x["charted"], x.get("peak_position", 999), x["artist"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="impulse_chart_evidence",
        description="빌보드 궤적 사실을 임펄스 원장 chart_evidence로 편입 (D-035 ②).",
    )
    ap.add_argument("--trajectories", required=True)
    ap.add_argument("--impulses", required=True, help="임펄스 레코드 디렉터리")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 무엇이 바뀌는지만 출력")
    args = ap.parse_args(argv)

    traj = json.loads(Path(args.trajectories).read_text(encoding="utf-8"))
    results = traj.get("results") or []
    window = traj.get("window") or {}

    touched = 0
    for path in sorted(Path(args.impulses).glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rows = _evidence_rows(results, rec.get("id", ""))
        if not rows:
            print(f"  - {path.name}: 대상 트랙 없음 (건너뜀)", file=sys.stderr)
            continue
        charted = sum(1 for r in rows if r["charted"])
        if rec.get("chart_evidence") == rows:
            print(f"  = {path.name}: 변화 없음 ({charted}/{len(rows)} 차트인)", file=sys.stderr)
            continue
        rec["chart_evidence"] = rows
        print(f"  ~ {path.name}: {charted}/{len(rows)} 차트인", file=sys.stderr)
        touched += 1
        if args.dry_run:
            continue
        # 키 순서를 보존하되 chart_evidence는 limits 앞(근거류 끝)에 놓는다.
        ordered = {k: v for k, v in rec.items() if k not in ("chart_evidence", "limits", "casebook_ref")}
        ordered["chart_evidence"] = rows
        for k in ("limits", "casebook_ref"):
            if k in rec:
                ordered[k] = rec[k]
        path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"\n{'(dry-run) ' if args.dry_run else ''}갱신 {touched}건 · "
        f"조회 윈도 {window.get('from')}~{window.get('to')} ({window.get('weeks')}주)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
