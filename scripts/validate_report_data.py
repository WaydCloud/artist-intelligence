"""report.json 차트 **데이터 형태** 게이트 — 스키마가 못 보는 계약을 검사한다.

*왜 있는가(2026-07-30)*: `report.schema.json`은 `"data": {}` 라서 차트 페이로드를
**전혀 제약하지 않는다**. 그래서 genre-impulse가 공유 계약의 bar 키(`name`)를
`label`로 낸 것이 schema-validate를 **통과했고**, 막대 11개가 이름 없이 그려졌다.
같은 날 다른 결함(대시보드가 모르는 tunable `view`)도 정적 게이트 전부를 통과했다.

**스키마를 고치는 것이 정공법이지만 그건 별도 승인 + 대시보드 동시 갱신이 전제다**
(AGENTS §0). 이 스크립트는 그 승인을 기다리는 동안 같은 부류를 CI에서 잡는다.
스키마를 건드리지 않으므로 계약 변경이 아니다 — **읽는 쪽의 기대를 명시한 것**이다.
정본은 대시보드 `apps/dashboard/lib/report.ts`의 타입이고, 여기 규칙은 그 사본이다.

    python scripts/validate_report_data.py                    # modules/**/output/report.json 전수
    python scripts/validate_report_data.py <report.json> ...   # 지정 파일만
    python scripts/validate_report_data.py --selftest          # 게이트가 실제로 잡는지 (파일 0건)

Exit: 0 = clean, 1 = 계약 위반, 2 = 대상 0건(경로가 바뀌었다는 뜻 — 조용히 통과시키지 않는다).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Any

# tunable `view`의 정본은 대시보드 렌더러다. 목록을 여기 박아두면 새 뷰가 생길 때마다
# 두 곳이 어긋나므로, 렌더러에서 직접 읽는다. 못 읽으면 **조용히 넘기지 않고** 알린다.
_TUNABLE_TSX = Path("apps/dashboard/components/charts/Tunable.tsx")


def known_tunable_views() -> tuple[set[str], str]:
    if not _TUNABLE_TSX.exists():
        return (set(), f"SKIP (렌더러를 찾지 못함: {_TUNABLE_TSX})")
    src = _TUNABLE_TSX.read_text(encoding="utf-8")
    views = set(re.findall(r'data\.view === "([a-z0-9-]+)"', src))
    if not views:
        return (set(), f"SKIP (렌더러에서 view 분기를 찾지 못함: {_TUNABLE_TSX})")
    return (views, f"{len(views)}종: {', '.join(sorted(views))}")


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_chart(chart: dict[str, Any], views: set[str]) -> list[str]:
    """한 차트의 data 형태를 검사해 위반 메시지 목록을 돌려준다."""
    out: list[str] = []
    ctype, data = chart.get("type"), chart.get("data")

    if ctype == "bar":
        # 계약: [{name: str, value: number}]  (lib/report.ts BarData)
        if not isinstance(data, list):
            return ["bar data가 배열이 아니다"]
        if not data:
            return []  # 빈 시리즈는 유효 상태다 ("데이터 없음"이 렌더된다)
        no_name = [i for i, e in enumerate(data) if not isinstance(e, dict) or not str(e.get("name") or "").strip()]
        bad_val = [i for i, e in enumerate(data) if isinstance(e, dict) and not _num(e.get("value"))]
        if no_name:
            # 이게 2026-07-30의 결함이다: `label`을 냈고 막대가 이름 없이 그려졌다.
            keys = sorted({k for e in data if isinstance(e, dict) for k in e})
            out.append(f"bar: `name` 없는 항목 {len(no_name)}/{len(data)}개 (실제 키: {keys})")
        if bad_val:
            out.append(f"bar: `value`가 수치가 아닌 항목 {len(bad_val)}/{len(data)}개")

    elif ctype == "line":
        # 계약: {x: str[], series: [{name, values: (number|null)[]}]}
        if not isinstance(data, dict):
            return ["line data가 객체가 아니다"]
        x, series = data.get("x"), data.get("series")
        if not isinstance(x, list) or not isinstance(series, list):
            return [f"line: `x`·`series`가 필요하다 (실제 키: {sorted(data)})"]
        for s in series:
            if not isinstance(s, dict) or not str(s.get("name") or "").strip():
                out.append("line: `name` 없는 series")
                continue
            vals = s.get("values")
            if not isinstance(vals, list):
                out.append(f"line: series '{s['name']}'에 `values` 배열이 없다")
            elif len(vals) != len(x):
                # 길이가 다르면 렌더는 죽지 않고 **말없이 어긋난 점을 그린다** — 더 나쁘다.
                out.append(f"line: series '{s['name']}' 길이 {len(vals)} != x {len(x)}")
            elif any(v is not None and not _num(v) for v in vals):
                out.append(f"line: series '{s['name']}'에 수치도 null도 아닌 값")

    elif ctype == "heatmap":
        # 계약: {rows: str[], cols: str[], cells: (number|null)[][]}
        if not isinstance(data, dict):
            return ["heatmap data가 객체가 아니다"]
        rows, cols, cells = data.get("rows"), data.get("cols"), data.get("cells")
        if not all(isinstance(v, list) for v in (rows, cols, cells)):
            return [f"heatmap: `rows`·`cols`·`cells`가 필요하다 (실제 키: {sorted(data)})"]
        assert isinstance(rows, list) and isinstance(cols, list) and isinstance(cells, list)
        if len(cells) != len(rows):
            out.append(f"heatmap: cells 행 {len(cells)} != rows {len(rows)}")
        for i, row in enumerate(cells):
            if not isinstance(row, list) or len(row) != len(cols):
                n = len(row) if isinstance(row, list) else "배열 아님"
                out.append(f"heatmap: cells[{i}] 폭 {n} != cols {len(cols)}")
                break

    elif ctype == "tunable":
        # 계약: {view: <렌더러가 아는 값>, ...}. 모르는 view는 이제 "모른다"고 표시되지만
        # (2026-07-30 수정) 그건 **화면에 빈 카드가 나간다는 뜻**이라 여전히 결함이다.
        if not isinstance(data, dict):
            return ["tunable data가 객체가 아니다"]
        view = data.get("view")
        if not isinstance(view, str) or not view:
            out.append("tunable: `view`가 없다")
        elif views and view not in views:
            out.append(f"tunable: 대시보드가 모르는 view '{view}' (아는 것: {', '.join(sorted(views))})")
        knobs = data.get("knobs")
        if knobs is not None:
            if not isinstance(knobs, list):
                out.append("tunable: `knobs`가 배열이 아니다")
            else:
                for k in knobs:
                    if not isinstance(k, dict) or not k.get("key") or not k.get("label"):
                        out.append("tunable: knob에 `key`·`label`이 필요하다")
                    elif not all(_num(k.get(f)) for f in ("default", "min", "max", "step")):
                        out.append(f"tunable: knob '{k.get('key')}'의 default/min/max/step이 수치가 아니다")
                    elif not (k["min"] <= k["default"] <= k["max"]):
                        # 기준 원장(AGENTS §2.1): 슬라이더 범위 밖의 기본값은 반박할 수 없는 임계다.
                        out.append(f"tunable: knob '{k['key']}' 기본값 {k['default']}이 [{k['min']}, {k['max']}] 밖")

    return out


def check_report(path: str, views: set[str]) -> list[str]:
    rep = json.loads(Path(path).read_text(encoding="utf-8"))
    charts = rep.get("charts")
    if not isinstance(charts, list):
        return ["`charts`가 배열이 아니다"]
    out: list[str] = []
    for i, c in enumerate(charts):
        if not isinstance(c, dict):
            out.append(f"charts[{i}]가 객체가 아니다")
            continue
        label = str(c.get("title") or f"charts[{i}]")[:48]
        out += [f"{label} — {m}" for m in check_chart(c, views)]
    return out


# --- selftest: 게이트가 실제로 잡는지. 음성 케이스가 없는 검사기는 초록인 채로 아무것도 안 한다 ---
_CASES: list[tuple[str, dict[str, Any], bool]] = [
    ("bar 정상", {"type": "bar", "data": [{"name": "a", "value": 1}]}, True),
    ("bar 빈 배열(유효)", {"type": "bar", "data": []}, True),
    ("bar label 오용(7-30 결함)", {"type": "bar", "data": [{"label": "a", "value": 1}]}, False),
    ("bar name 공백", {"type": "bar", "data": [{"name": "  ", "value": 1}]}, False),
    ("bar value 문자열", {"type": "bar", "data": [{"name": "a", "value": "1"}]}, False),
    ("line 정상", {"type": "line", "data": {"x": ["d1", "d2"], "series": [{"name": "s", "values": [1, None]}]}}, True),
    ("line 길이 불일치", {"type": "line", "data": {"x": ["d1", "d2"], "series": [{"name": "s", "values": [1]}]}}, False),
    ("line series name 없음", {"type": "line", "data": {"x": ["d1"], "series": [{"values": [1]}]}}, False),
    ("heatmap 정상", {"type": "heatmap", "data": {"rows": ["r"], "cols": ["c1", "c2"], "cells": [[1, None]]}}, True),
    ("heatmap 폭 불일치", {"type": "heatmap", "data": {"rows": ["r"], "cols": ["c1", "c2"], "cells": [[1]]}}, False),
    ("heatmap 행 수 불일치", {"type": "heatmap", "data": {"rows": ["r1", "r2"], "cols": ["c"], "cells": [[1]]}}, False),
    ("tunable 아는 view", {"type": "tunable", "data": {"view": "rhythm"}}, True),
    ("tunable 모르는 view(7-30 결함)", {"type": "tunable", "data": {"view": "impulse-rulez"}}, False),
    ("tunable knob 범위 밖 기본값",
     {"type": "tunable", "data": {"view": "rhythm", "knobs": [{"key": "k", "label": "L", "default": 9, "min": 0, "max": 1, "step": 0.05}]}}, False),
]


def selftest() -> int:
    views, note = known_tunable_views()
    print(f"tunable view 정본: {note}")
    if not views:
        print("!! view 검사를 못 하는 상태다 — 렌더러 경로를 확인할 것", file=sys.stderr)
        return 1
    failed = 0
    for name, chart, should_pass in _CASES:
        msgs = check_chart(chart, views)
        ok = (not msgs) if should_pass else bool(msgs)
        if not ok:
            failed += 1
        print(f"  {'ok  ' if ok else 'FAIL'} {name:38} {'통과 기대' if should_pass else '검출 기대'} → {msgs or '없음'}")
    print(f"\nselftest {len(_CASES) - failed}/{len(_CASES)}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="report.json 차트 데이터 형태 게이트")
    ap.add_argument("reports", nargs="*", help="검사할 report.json (없으면 modules/**/output/report.json 전수)")
    ap.add_argument("--selftest", action="store_true", help="음성/양성 케이스로 게이트 자체를 검사 (파일 0건)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    views, note = known_tunable_views()
    files = args.reports or sorted(glob.glob("modules/**/output/report.json", recursive=True))
    if not files:
        # 0건은 "아직 안 만들었다"가 아니라 경로가 바뀌었다는 뜻이다 (CI schema-validate와 같은 규율).
        print("::error::no report.json found — 차트 데이터 계약이 검증되지 않고 있다", file=sys.stderr)
        return 2
    print(f"validating {len(files)} report(s) · tunable view 정본: {note}")

    bad = 0
    for f in files:
        msgs = check_report(f, views)
        if msgs:
            bad += 1
            print(f"::error file={f}::{len(msgs)} 계약 위반", file=sys.stderr)
            for m in msgs:
                print(f"  - {m}", file=sys.stderr)
    if bad:
        print(f"\nFAILED: {bad}/{len(files)} report(s) 계약 이탈", file=sys.stderr)
        return 1
    print("chart data contract: CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
