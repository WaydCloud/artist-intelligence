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


# ── 시각화 계약(R1~R8)을 **채택한 모듈**. 채택 = 그 탭이 질문 블록·요약 도형·차트별
# 질문·신뢰도 라인을 전부 갖췄다는 뜻이고, 아래 검사가 그때부터 하드 게이트가 된다.
#
# 왜 목록인가: 계약을 6모듈에 동시에 강제하면 요구사항이 아니라 37개 차트에 대한
# 문구 채우기 경쟁이 된다(R3는 "질문이 없으면 차트를 뺀다"인데, 급히 채운 질문은
# 그 규율을 무력화한다). 그래서 스키마는 필드를 **선택**으로 열어 두고, 탭이 실제로
# 완성될 때 여기 한 줄을 추가한다. **이 목록에 없는 모듈은 게이트를 우회하는 것이
# 아니라 아직 계약을 채택하지 않은 것이다** — 목록이 줄지 않고 멈추면 그게 신호다.
ADOPTED_MODULES = frozenset({"sonic-profile", "chart-history"})

# 구획 하나가 담을 수 있는 차트 수 (D-043 · 도메인 소유자 지시 2026-07-30:
# "하나의 채널에는 최대 3가지의 정보만 담는다. 페이지가 극도로 길어지더라도").
#
# 왜 코드에 있나: 이 상한은 취향이 아니라 **제품 결정**이고, 리뷰어의 눈에 맡기면
# 한 개씩 늘어나 결국 예전 상태로 돌아간다. 차트를 하나 더 얹으려면 그것이 **어느
# 질문에 답하는지**를 먼저 답해야 한다(새 구획을 만들거나, 기존 것을 빼거나).
MAX_CHARTS_PER_SECTION = 3

# 추론 어법 금지(DESIGN.md §6.2). 태그가 붙어도 명령·예측·인과를 단정하면 평결이 된다.
_BANNED_DICTION: list[tuple[str, str]] = [
    (r"십시오|하세요|하십시오|해야 한다|해야 합니다|하도록 한다", "명령형"),
    (r"할 것이다|될 것이다|것으로 예상|예측된다|전망이다|할 전망", "예측 단정"),
    (r"때문이다|때문입니다|탓이다|덕분이다|원인이다|야기한다|초래한다", "인과 단정"),
    # em dash는 클라이언트 대면 문구에서 금지(DESIGN.md §6.1). 신설 필드라 유예가 없다.
    (r"—", "em dash"),
]


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

    elif ctype == "radar":
        # 계약: {axes: [{name, value: number|null, …}], max?, baseline?, scaleNote?}
        if not isinstance(data, dict):
            return ["radar data가 객체가 아니다"]
        axes = data.get("axes")
        if not isinstance(axes, list):
            return [f"radar: `axes` 배열이 필요하다 (실제 키: {sorted(data)})"]
        top = data.get("max", 100)
        if not _num(top) or top <= 0:
            out.append(f"radar: `max`가 양수가 아니다 ({top!r})")
            top = 100
        if not str(data.get("scaleNote") or "").strip():
            # 공통 스케일이 무엇인지 없으면 폴리곤은 판독 불가다 — 예쁜 도형만 남는다.
            out.append("radar: `scaleNote`가 없다 (값이 무엇으로 정규화됐는지 화면이 못 말한다)")
        base = data.get("baseline")
        if base is not None and (not _num(base) or not (0 <= base <= top)):
            out.append(f"radar: `baseline` {base!r}이 [0, {top}] 밖")
        for i, ax in enumerate(axes):
            if not isinstance(ax, dict) or not str(ax.get("name") or "").strip():
                out.append(f"radar: axes[{i}]에 `name`이 없다")
                continue
            v = ax.get("value")
            if v is None:
                # R6의 핵심. null은 허용되지만 **사유 없는 null**은 화면이 "관측 없음"만
                # 말하고 왜 없는지를 못 말하는 상태다(각주도 아니고 침묵이다).
                if not str(ax.get("missingReason") or "").strip():
                    out.append(f"radar: 축 '{ax['name']}'이 결측인데 `missingReason`이 없다")
            elif not _num(v):
                out.append(f"radar: 축 '{ax['name']}'의 value가 수치도 null도 아니다")
            elif not (0 <= v <= top):
                out.append(f"radar: 축 '{ax['name']}'의 value {v}가 [0, {top}] 밖")

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


def check_diction(text: str, where: str) -> list[str]:
    """DESIGN.md §6.2 금지 어법. 태그가 붙어도 단정하면 평결이라 태그의 의미가 없어진다."""
    hits = [kind for pat, kind in _BANNED_DICTION if re.search(pat, text)]
    return [f"{where}: 금지 어법 {kind} — {text[:56]!r}" for kind in hits]


def check_visualization_contract(rep: dict[str, Any], charts: list[dict[str, Any]]) -> list[str]:
    """R1~R8 중 **스키마가 볼 수 없는** 층: 앵커 정합성 · id 중복 · 추론 어법 · 채택 모듈 강제."""
    out: list[str] = []
    module = str(rep.get("moduleId") or "")
    summary = rep.get("summary")
    # 앵커 대상 = summary + charts의 id 전체. 둘 중 어디를 가리켜도 유효하다.
    anchored = ([summary] if isinstance(summary, dict) else []) + charts
    ids = [str(c["id"]) for c in anchored if isinstance(c, dict) and c.get("id")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        # 중복 id는 앵커가 **어느 카드로 갈지 모르는 상태**이고 React key도 겹친다.
        out.append(f"차트 id 중복: {', '.join(dupes)}")
    known = set(ids)

    for field in ("questions", "inferences"):
        items = rep.get(field)
        if items is None:
            continue
        if not isinstance(items, list):
            out.append(f"`{field}`가 배열이 아니다")
            continue
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                out.append(f"{field}[{i}]가 객체가 아니다")
                continue
            cid = it.get("chartId")
            # 끊긴 앵커는 링크를 눌러도 아무 일이 없는 상태다 — R1이 고치려는 실패
            # ("무엇을 볼지 알 수 없다")를 그대로 되돌려 놓는다.
            if field == "questions" and not cid:
                out.append(f"questions[{i}]에 `chartId`가 없다")
            elif cid and str(cid) not in known:
                out.append(
                    f"{field}[{i}]의 chartId '{cid}'에 해당하는 차트가 없다"
                    + (f" (있는 id: {', '.join(sorted(known))})" if known else " (id를 가진 차트가 0개)")
                )

    for i, inf in enumerate(rep.get("inferences") or []):
        if not isinstance(inf, dict):
            continue
        # 동반 4종은 스키마 required가 잡는다. 여기서는 스키마가 못 보는 **어법**만.
        out += check_diction(str(inf.get("text") or ""), f"inferences[{i}]")

    # ── 구획(D-043). 선언한 리포트에만 적용된다 — 선언하지 않으면 예전처럼 한 줄로 렌더된다.
    sections = rep.get("sections")
    if sections is not None:
        if not isinstance(sections, list):
            out.append("`sections`가 배열이 아니다")
        else:
            sec_ids = [str(s.get("id")) for s in sections if isinstance(s, dict) and s.get("id")]
            dupe_sec = sorted({i for i in sec_ids if sec_ids.count(i) > 1})
            if dupe_sec:
                out.append(f"구획 id 중복: {', '.join(dupe_sec)}")
            known_sec = set(sec_ids)
            counts: dict[str, int] = dict.fromkeys(sec_ids, 0)
            for i, c in enumerate(charts):
                sid = c.get("section")
                label = str(c.get("id") or c.get("title") or f"charts[{i}]")[:40]
                if not sid:
                    # 구획을 선언해 놓고 배정하지 않은 차트는 화면 어디에도 놓이지 못한다.
                    out.append(f"{label} — 구획을 선언한 리포트인데 `section`이 없다")
                elif str(sid) not in known_sec:
                    out.append(
                        f"{label} — 없는 구획 '{sid}' (선언된 것: {', '.join(sorted(known_sec)) or '없음'})"
                    )
                else:
                    counts[str(sid)] += 1
            for sid, n in counts.items():
                if n > MAX_CHARTS_PER_SECTION:
                    out.append(
                        f"구획 '{sid}'에 차트 {n}개 (상한 {MAX_CHARTS_PER_SECTION}) — "
                        "구획을 나누거나 답할 질문이 겹치는 차트를 뺀다"
                    )
                elif n == 0:
                    # 빈 구획은 내비게이션에 이름만 있고 눌러도 아무것도 없는 상태다.
                    out.append(f"구획 '{sid}'에 차트가 0개")
            for i, m in enumerate(rep.get("metrics") or []):
                sid = m.get("section") if isinstance(m, dict) else None
                if sid and str(sid) not in known_sec:
                    out.append(f"metrics[{i}] — 없는 구획 '{sid}'")

    if module not in ADOPTED_MODULES:
        return out

    # ── 여기부터는 계약을 채택한 모듈에만 적용되는 하드 게이트 ──
    if not isinstance(summary, dict):
        out.append("R2: `summary`(진입 요약 하나)가 없다")
    elif not summary.get("id"):
        out.append("R2: `summary`에 `id`가 없다 (질문 블록이 앵커할 대상이 사라진다)")
    qs = rep.get("questions") or []
    if len(qs) < 3:
        out.append(f"R1: `questions`가 {len(qs)}개 (이 탭에서 답할 수 있는 질문 3개 이상)")
    if not (rep.get("notAnswered") or []):
        out.append("R7: `notAnswered`가 비었다 (못 답하는 질문을 명시하지 않았다)")
    base_rel = rep.get("reliability") if isinstance(rep.get("reliability"), dict) else {}
    for i, c in enumerate(anchored):
        if not isinstance(c, dict):
            continue
        label = str(c.get("id") or c.get("title") or f"charts[{i}]")[:48]
        if not c.get("id"):
            out.append(f"{label} — R1/R4: `id`가 없다 (앵커·추론 배치 대상이 되지 못한다)")
        if not str(c.get("question") or "").strip():
            # R3: 답할 질문이 없으면 **그 차트를 뺀다**. 빈 채로 두는 선택지는 없다.
            out.append(f"{label} — R3: `question`이 없다 (답할 질문이 없으면 차트를 뺀다)")
        rel = {**base_rel, **(c.get("reliability") or {})}
        missing = [f for f in ("sample", "engine") if not str(rel.get(f) or "").strip()]
        if missing:
            out.append(f"{label} — R8: 신뢰도 라인에 {'·'.join(missing)}이 없다 (최상위 병합 후에도 비었다)")
    return out


def check_report(path: str, views: set[str]) -> list[str]:
    rep = json.loads(Path(path).read_text(encoding="utf-8"))
    charts = rep.get("charts")
    if not isinstance(charts, list):
        return ["`charts`가 배열이 아니다"]
    out: list[str] = []
    # summary도 차트다 — 같은 데이터 검사를 받아야 한다(요약이라서 면제되지 않는다).
    summary = rep.get("summary")
    if summary is not None and not isinstance(summary, dict):
        out.append("`summary`가 객체가 아니다")
    elif isinstance(summary, dict):
        label = str(summary.get("title") or "summary")[:48]
        out += [f"[요약] {label} — {m}" for m in check_chart(summary, views)]
    for i, c in enumerate(charts):
        if not isinstance(c, dict):
            out.append(f"charts[{i}]가 객체가 아니다")
            continue
        label = str(c.get("title") or f"charts[{i}]")[:48]
        out += [f"{label} — {m}" for m in check_chart(c, views)]
    out += check_visualization_contract(rep, [c for c in charts if isinstance(c, dict)])
    return out


# --- selftest: 게이트가 실제로 잡는지. 음성 케이스가 없는 검사기는 초록인 채로 아무것도 안 한다 ---
#
# 아래 표는 **이 검사기**가 잡는 것이고, `_SCHEMA_CASES`는 **스키마**가 잡는 것이다.
# 일부(bar `name` 누락 등)는 의도적으로 겹친다: 이 스크립트는 stdlib만 쓰므로
# jsonschema가 없는 환경에서도 단독으로 돌아야 하고, 겹치는 검사가 그 보루다.
# 겹치지 않는 것 = 이 검사기만 잡는 것: **교차 필드 길이**(JSON Schema로 표현 불가),
# **렌더러 결합**(아는 view인지), **범위**(기본값이 [min,max] 안인지), 공백뿐인 이름.
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
    # radar (R2 요약 도형) — 결측 규율이 여기 걸린다.
    ("radar 정상", {"type": "radar", "data": {
        "axes": [{"name": "a", "value": 60}, {"name": "b", "value": 40}, {"name": "c", "value": 50}],
        "baseline": 50, "scaleNote": "차트 코호트 내 백분위"}}, True),
    ("radar 결측 null + 사유(유효)", {"type": "radar", "data": {
        "axes": [{"name": "a", "value": None, "missingReason": "관측 없음"}, {"name": "b", "value": 40}, {"name": "c", "value": 50}],
        "scaleNote": "백분위"}}, True),
    ("radar 사유 없는 결측(R6)", {"type": "radar", "data": {
        "axes": [{"name": "a", "value": None}, {"name": "b", "value": 40}, {"name": "c", "value": 50}],
        "scaleNote": "백분위"}}, False),
    ("radar scaleNote 없음", {"type": "radar", "data": {
        "axes": [{"name": "a", "value": 1}, {"name": "b", "value": 2}, {"name": "c", "value": 3}]}}, False),
    ("radar value 스케일 밖", {"type": "radar", "data": {
        "axes": [{"name": "a", "value": 140}, {"name": "b", "value": 40}, {"name": "c", "value": 50}],
        "scaleNote": "백분위"}}, False),
]

# 리포트 층(R1~R8) — 차트 하나로는 표현할 수 없는 계약. 채택 모듈 강제는 moduleId로 갈린다.
_REPORT_CASES: list[tuple[str, dict[str, Any], bool]] = [
    ("미채택 모듈은 R1~R8 면제", {"moduleId": "yt-pulse", "charts": []}, True),
    ("끊긴 질문 앵커", {"moduleId": "yt-pulse", "charts": [{"type": "bar", "id": "a", "data": []}],
                  "questions": [{"q": "?", "chartId": "nope"}]}, False),
    ("정상 질문 앵커", {"moduleId": "yt-pulse", "charts": [{"type": "bar", "id": "a", "data": []}],
                  "questions": [{"q": "?", "chartId": "a"}]}, True),
    ("요약을 가리키는 앵커(유효)", {"moduleId": "yt-pulse", "charts": [],
                       "summary": {"type": "radar", "id": "s", "data": {"axes": []}},
                       "questions": [{"q": "?", "chartId": "s"}]}, True),
    ("차트 id 중복", {"moduleId": "yt-pulse", "charts": [
        {"type": "bar", "id": "a", "data": []}, {"type": "bar", "id": "a", "data": []}]}, False),
    ("추론 인과 단정", {"moduleId": "yt-pulse", "charts": [], "inferences": [
        {"text": "저역이 낮기 때문이다", "basis": "b", "sample": "n=1", "confidence": "low", "limits": "l"}]}, False),
    ("추론 명령형", {"moduleId": "yt-pulse", "charts": [], "inferences": [
        {"text": "이 축을 확인하십시오", "basis": "b", "sample": "n=1", "confidence": "low", "limits": "l"}]}, False),
    ("추론 예측 단정", {"moduleId": "yt-pulse", "charts": [], "inferences": [
        {"text": "차트에 진입할 것이다", "basis": "b", "sample": "n=1", "confidence": "low", "limits": "l"}]}, False),
    ("추론 em dash", {"moduleId": "yt-pulse", "charts": [], "inferences": [
        {"text": "저역 축과 정합한다 — 표본 주의", "basis": "b", "sample": "n=1", "confidence": "low", "limits": "l"}]}, False),
    ("추론 허용 어법", {"moduleId": "yt-pulse", "charts": [], "inferences": [
        {"text": "저역이 높은 쪽과 정합하는 신호가 있다", "basis": "b", "sample": "n=1", "confidence": "low", "limits": "l"}]}, True),
    ("채택 모듈: 요약·질문·신뢰도 누락", {"moduleId": "sonic-profile", "charts": []}, False),
    ("채택 모듈: 차트에 question 없음", {
        "moduleId": "sonic-profile",
        "summary": {"type": "radar", "id": "s", "question": "q", "data": {"axes": []}},
        "questions": [{"q": "1", "chartId": "s"}, {"q": "2", "chartId": "s"}, {"q": "3", "chartId": "s"}],
        "notAnswered": ["x"], "reliability": {"sample": "n=1", "engine": "e"},
        "charts": [{"type": "bar", "id": "a", "data": []}]}, False),
    ("채택 모듈: 전부 갖춤", {
        "moduleId": "sonic-profile",
        "summary": {"type": "radar", "id": "s", "question": "q", "data": {"axes": []}},
        "questions": [{"q": "1", "chartId": "s"}, {"q": "2", "chartId": "a"}, {"q": "3", "chartId": "s"}],
        "notAnswered": ["x"], "reliability": {"sample": "n=1", "engine": "e"},
        "charts": [{"type": "bar", "id": "a", "question": "q", "data": []}]}, True),
    # ── 구획(D-043)
    ("구획 정상", {"moduleId": "yt-pulse", "sections": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                "charts": [{"type": "bar", "id": "c1", "section": "a", "data": []},
                           {"type": "bar", "id": "c2", "section": "b", "data": []}]}, True),
    ("구획 상한 초과(4개)", {"moduleId": "yt-pulse", "sections": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                      "charts": [{"type": "bar", "id": f"c{i}", "section": "a", "data": []} for i in range(4)]
                      + [{"type": "bar", "id": "cz", "section": "b", "data": []}]}, False),
    ("구획 미배정 차트", {"moduleId": "yt-pulse", "sections": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                    "charts": [{"type": "bar", "id": "c1", "section": "a", "data": []},
                               {"type": "bar", "id": "c2", "section": "b", "data": []},
                               {"type": "bar", "id": "c3", "data": []}]}, False),
    ("없는 구획 참조", {"moduleId": "yt-pulse", "sections": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                   "charts": [{"type": "bar", "id": "c1", "section": "a", "data": []},
                              {"type": "bar", "id": "c2", "section": "zz", "data": []}]}, False),
    ("빈 구획", {"moduleId": "yt-pulse", "sections": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
               "charts": [{"type": "bar", "id": "c1", "section": "a", "data": []}]}, False),
    ("구획 미선언은 면제", {"moduleId": "yt-pulse", "charts": [{"type": "bar", "id": "c1", "data": []}]}, True),
    ("채택 모듈: 신뢰도 engine 누락", {
        "moduleId": "sonic-profile",
        "summary": {"type": "radar", "id": "s", "question": "q", "data": {"axes": []}},
        "questions": [{"q": "1", "chartId": "s"}, {"q": "2", "chartId": "s"}, {"q": "3", "chartId": "s"}],
        "notAnswered": ["x"], "reliability": {"sample": "n=1"},
        "charts": [{"type": "bar", "id": "a", "question": "q", "data": []}]}, False),
]


# 스키마가 잡아야 하는 것(키 이름·타입·required). 여기 두는 이유: 계약은 두 층으로
# 나뉘어 있고(스키마=형태 / 이 검사기=교차 필드·렌더러 결합), **분업이 실제로 성립하는지를
# 한 곳에서 증명**해야 한다. 층을 옮기려면 이 표가 먼저 바뀌어야 한다.
_SCHEMA_CASES: list[tuple[str, dict[str, Any], bool]] = [
    ("bar 정상", {"type": "bar", "data": [{"name": "a", "value": 1}]}, True),
    ("bar 빈 배열(유효)", {"type": "bar", "data": []}, True),
    ("bar label 오용(7-30 결함)", {"type": "bar", "data": [{"label": "a", "value": 1}]}, False),
    ("bar name 빈 문자열", {"type": "bar", "data": [{"name": "", "value": 1}]}, False),
    ("bar value 문자열", {"type": "bar", "data": [{"name": "a", "value": "1"}]}, False),
    ("bar 여분 키", {"type": "bar", "data": [{"name": "a", "value": 1, "hint": "x"}]}, False),
    ("bar가 객체", {"type": "bar", "data": {"name": "a"}}, False),
    ("line 정상", {"type": "line", "data": {"x": ["d"], "series": [{"name": "s", "values": [1]}]}}, True),
    ("line 결측 null(유효)", {"type": "line", "data": {"x": ["d"], "series": [{"name": "s", "values": [None]}]}}, True),
    ("line x 누락", {"type": "line", "data": {"series": []}}, False),
    ("line series name 없음", {"type": "line", "data": {"x": ["d"], "series": [{"values": [1]}]}}, False),
    ("line values에 문자열", {"type": "line", "data": {"x": ["d"], "series": [{"name": "s", "values": ["1"]}]}}, False),
    ("heatmap 정상", {"type": "heatmap", "data": {"rows": ["r"], "cols": ["c"], "cells": [[1]]}}, True),
    ("heatmap cells 1차원", {"type": "heatmap", "data": {"rows": ["r"], "cols": ["c"], "cells": [1]}}, False),
    ("heatmap cols 누락", {"type": "heatmap", "data": {"rows": ["r"], "cells": [[1]]}}, False),
    ("tunable 정상", {"type": "tunable", "data": {"view": "rhythm", "bins": 16, "templates": {}}}, True),
    ("tunable view 없음", {"type": "tunable", "data": {"bins": 16}}, False),
    ("tunable knob 필드 누락",
     {"type": "tunable", "data": {"view": "rhythm", "knobs": [{"key": "k", "label": "L", "default": 1, "min": 0, "max": 2}]}}, False),
    ("tunable knob step 0", {"type": "tunable", "data": {"view": "rhythm", "knobs": [{"key": "k", "label": "L", "default": 1, "min": 0, "max": 2, "step": 0}]}}, False),
    ("차트 여분 키", {"type": "bar", "data": [{"name": "a", "value": 1}], "color": "red"}, False),
    # 시각화 계약 신설 필드 — 스키마가 형태를 잡는 층
    ("차트 메타 정상", {"type": "bar", "id": "a-1", "question": "q", "definition": "d",
                  "reliability": {"sample": "n=1"}, "data": []}, True),
    ("차트 id 대문자", {"type": "bar", "id": "A", "data": []}, False),
    ("차트 question 빈 문자열", {"type": "bar", "id": "a", "question": "", "data": []}, False),
    ("reliability 빈 객체", {"type": "bar", "reliability": {}, "data": []}, False),
    ("reliability 여분 키", {"type": "bar", "reliability": {"sample": "n", "note": "x"}, "data": []}, False),
    ("radar 정상", {"type": "radar", "data": {"axes": [
        {"name": "a", "value": 1}, {"name": "b", "value": None}, {"name": "c", "value": 3}]}}, True),
    ("radar 축 2개", {"type": "radar", "data": {"axes": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}}, False),
    ("radar 축 9개", {"type": "radar", "data": {"axes": [{"name": str(i), "value": 1} for i in range(9)]}}, False),
    ("radar 축 여분 키", {"type": "radar", "data": {"axes": [
        {"name": "a", "value": 1, "color": "red"}, {"name": "b", "value": 2}, {"name": "c", "value": 3}]}}, False),
]

# 스키마가 잡는 **리포트 층** 필드(차트 배열 밖). _SCHEMA_CASES와 달리 리포트 전체를 준다.
_SCHEMA_REPORT_CASES: list[tuple[str, dict[str, Any], bool]] = [
    ("inference 정상", {"inferences": [
        {"text": "t", "basis": "b", "sample": "n=1", "confidence": "low", "limits": "l"}]}, True),
    ("inference basis 누락(동반 4종)", {"inferences": [
        {"text": "t", "sample": "n=1", "confidence": "low", "limits": "l"}]}, False),
    ("inference limits 누락(동반 4종)", {"inferences": [
        {"text": "t", "basis": "b", "sample": "n=1", "confidence": "low"}]}, False),
    ("inference confidence 자유문자열", {"inferences": [
        {"text": "t", "basis": "b", "sample": "n=1", "confidence": "아마도", "limits": "l"}]}, False),
    ("questions 정상", {"questions": [{"q": "?", "chartId": "a"}]}, True),
    ("questions chartId 누락", {"questions": [{"q": "?"}]}, False),
    ("questions 5개(상한 4)", {"questions": [{"q": str(i), "chartId": "a"} for i in range(5)]}, False),
    ("summary가 배열", {"summary": [{"type": "bar", "data": []}]}, False),
    ("summary 정상", {"summary": {"type": "radar", "id": "s", "data": {"axes": [
        {"name": "a", "value": 1}, {"name": "b", "value": 2}, {"name": "c", "value": 3}]}}}, True),
    ("notAnswered 빈 문자열 항목", {"notAnswered": [""]}, False),
    ("metric definition 정상", {"metrics": [{"label": "L", "value": 1, "definition": "d"}]}, True),
]

_SCHEMA_PATH = Path("packages/report-schema/report.schema.json")
_EMPTY_REPORT: dict[str, Any] = {
    "moduleId": "selftest", "title": "T", "generatedAt": "2026-01-01T00:00:00Z",
    "metrics": [], "charts": [], "media": [], "insights": [], "recommendations": [],
}


def _schema_selftest() -> tuple[int, int]:
    """스키마 층: `report.schema.json`이 형태 위반을 실제로 잡는지."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("  SKIP 스키마 층 — jsonschema 미설치", file=sys.stderr)
        return (0, 1)  # 검사 못 했으면 실패로 센다 (0건 통과 금지)
    if not _SCHEMA_PATH.exists():
        print(f"  SKIP 스키마 층 — {_SCHEMA_PATH} 없음", file=sys.stderr)
        return (0, 1)
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    failed = 0
    cases = [(n, {**_EMPTY_REPORT, "charts": [c]}, p) for n, c, p in _SCHEMA_CASES]
    cases += [(n, {**_EMPTY_REPORT, **r}, p) for n, r, p in _SCHEMA_REPORT_CASES]
    for name, rep, should_pass in cases:
        errs = list(v.iter_errors(rep))
        ok = (not errs) if should_pass else bool(errs)
        if not ok:
            failed += 1
        why = errs[0].message[:64] if errs else "없음"
        print(f"  {'ok  ' if ok else 'FAIL'} [스키마]  {name:34} {'통과 기대' if should_pass else '검출 기대'} → {why}")
    return (len(cases) - failed, failed)


def selftest() -> int:
    views, note = known_tunable_views()
    print(f"tunable view 정본: {note}\n")
    if not views:
        print("!! view 검사를 못 하는 상태다 — 렌더러 경로를 확인할 것", file=sys.stderr)
        return 1

    s_ok, s_bad = _schema_selftest()
    print()
    failed = 0
    for name, chart, should_pass in _CASES:
        msgs = check_chart(chart, views)
        ok = (not msgs) if should_pass else bool(msgs)
        if not ok:
            failed += 1
        print(f"  {'ok  ' if ok else 'FAIL'} [검사기] {name:34} {'통과 기대' if should_pass else '검출 기대'} → {msgs or '없음'}")
    print()
    r_failed = 0
    for name, rep, should_pass in _REPORT_CASES:
        msgs = check_visualization_contract(rep, [c for c in rep.get("charts") or [] if isinstance(c, dict)])
        ok = (not msgs) if should_pass else bool(msgs)
        if not ok:
            r_failed += 1
        print(f"  {'ok  ' if ok else 'FAIL'} [리포트] {name:34} {'통과 기대' if should_pass else '검출 기대'} → {msgs or '없음'}")
    n_unit = len(_CASES) + len(_REPORT_CASES)
    n_bad = failed + r_failed
    total_ok, total_bad = s_ok + n_unit - n_bad, s_bad + n_bad
    print(
        f"\nselftest {total_ok}/{total_ok + total_bad} "
        f"(스키마 {s_ok}/{s_ok + s_bad} · 차트 {len(_CASES) - failed}/{len(_CASES)} · "
        f"리포트 {len(_REPORT_CASES) - r_failed}/{len(_REPORT_CASES)})"
    )
    return 1 if total_bad else 0


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
