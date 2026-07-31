"""빌보드 궤적 → `trajectory` 셀 **연결 후보 대조** (네트워크 0).

`impulse_chart_evidence.py`가 차트 **사실**을 원장에 실었지만 그 사실은 어느 셀에도
붙어 있지 않다. 이 스크립트가 그 연결을 **제안**한다 — **배정하지 않는다.**

🔴 **왜 자동 배정하지 않는가**(스키마·`impulse_chart_evidence.py`가 이미 못 박은 것):
차트인은 "그 시장에 도달했다"는 사실이지 셀 배정을 뜻하지 않는다. 뉴진스의 Hot 100
진입은 **한국 주류화가 아니라 미국 도달**이라 자동 배정하면 정확히 틀린다. 그래서
값(어느 셀인가)은 도메인 소유자가 정하고, 이 스크립트는 **형식**만 소유한다
(AGENTS §2.1 소유 분리).

**후보는 추론이 아니라 원장 자신의 말에서 나온다.** 셀의 `evidence` 텍스트가 그 곡을
**이름으로 언급**하면 후보다. 22건 중 20건이 이미 그렇게 언급돼 있다 — 즉 원장은
이 곡들을 이미 알고 있었고, 다만 **차트 사실과 대조된 적이 없었다.**

세 가지를 **함께** 낸다. 판정하지 않는 이유가 여기 있다 — 셋 중 둘은 오류처럼 보이지만
오류가 아닐 수 있다:

  ① **시장 대조** — Hot 100은 미국 차트다. `kr-*` 셀에 이 사실을 붙이면 위 함정이다.
     그러나 한국 팀이 미국 차트에 든 시점이 한국 바이럴 구간과 겹치는 것은 **우연이
     아닐 수 있다**. 그래서 막지 않고 **표시**한다.
  ② **날짜 대조** — 셀 날짜와 차트 진입일의 관계. 차트 진입은 발매보다 늦으므로
     "셀이 몇 달 이름"은 정상이다. **"셀이 늦음"이 눈여겨볼 방향**이다.
  ③ **어긋나 보이지만 맞는 것** — 실측 예: njs `origin-scene-revival`(2016-11)이
     Finesse를 언급하는데 차트 진입은 2018-01이다. Finesse는 2016-11 앨범 수록곡이고
     2018-01은 리믹스 싱글의 진입이라 **둘 다 정확하다.** 이런 사례가 있으므로 도구가
     날짜 차이를 오류로 단정하면 원장에 거짓이 들어간다.

Usage:

    # ① 대조표를 본다 (원장 안 건드림)
    python scripts/impulse_trajectory_link.py --impulses data/research/genre-impulse/impulses

    # ② 확인용 템플릿을 뽑아 도메인 소유자가 편집한다
    python scripts/impulse_trajectory_link.py --impulses <dir> --emit-confirmations links.json

    # ③ 사람이 확정한 것만 원장에 쓴다 (멱등)
    python scripts/impulse_trajectory_link.py --impulses <dir> --apply links.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# 차트 → 시장. 이 표가 ①의 근거다. 차트가 늘면 여기 한 줄을 더한다.
CHART_MARKET = {"billboard-hot100": "US"}
# 셀 이름의 접두어 → 그 셀이 말하는 시장. 원장의 어휘 규약(스키마 description)에서 온다.
CELL_MARKET_PREFIX = {"kr-": "KR", "jp-": "JP", "origin-": "origin", "global-": "global"}


def _ref(e: dict[str, Any]) -> str:
    """차트 사실 한 줄의 참조 키. 레코드 안에서 유일함을 실측으로 확인했다(중복 0)."""
    return f"{e.get('chart', '')}|{e.get('artist', '')}|{e.get('title', '')}"


def _core_title(title: str) -> str:
    """부제·피처링·파트 표기를 떼어 낸 제목 핵심어. 원장 텍스트는 이 형태로 적는다."""
    return re.split(r"[(\[]| feat| Feat| Pt\.", title or "")[0].strip()


def _month(text: str) -> int | None:
    t = (text or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", t):
        return int(t[:4]) * 12 + int(t[5:7])
    if re.fullmatch(r"\d{4}", t):
        return int(t) * 12 + 1
    return None


def _cell_window(date: str) -> tuple[int, int | None] | None:
    """셀 date 표기를 (시작월, 끝월)로. 끝이 None이면 열린 구간. 해석 불가는 None."""
    s = (date or "").strip()
    if not s or "미도달" in s:
        return None
    if "~" in s:
        a, b = s.split("~", 1)
        lo = _month(a)
        if lo is None:
            return None
        b = b.strip()
        if not b:
            return (lo, None)                                  # "2021-01~" = 열린 구간
        hi = _month(b)
        if hi is None:
            return (lo, None)
        return (lo, hi + 11 if re.fullmatch(r"\d{4}", b) else hi)
    lo = _month(s)
    if lo is None:
        return None                                            # "2017 중반" 같은 자유 표기
    return (lo, lo + 11 if re.fullmatch(r"\d{4}", s) else lo)


def _date_relation(cell_date: str, entry_date: str) -> dict[str, Any]:
    w = _cell_window(cell_date)
    em = _month(entry_date[:7]) if entry_date else None
    if w is None or em is None:
        return {"relation": "대조 불가", "months": None,
                "why": "셀 날짜가 자유 표기이거나 미도달, 또는 진입일 없음"}
    lo, hi = w
    if lo <= em <= (hi if hi is not None else 10**9):
        return {"relation": "포함", "months": 0}
    if em < lo:
        # 차트가 셀보다 앞선다 — 원장이 늦게 잡았을 수 있는 방향이다
        return {"relation": "셀이 늦음", "months": lo - em}
    return {"relation": "셀이 이름", "months": em - (hi if hi is not None else lo)}


def _market_flag(chart: str, cell: str) -> dict[str, Any]:
    chart_market = CHART_MARKET.get(chart)
    cell_market = next((v for k, v in CELL_MARKET_PREFIX.items() if cell.startswith(k)), None)
    if chart_market is None or cell_market is None:
        return {"chart_market": chart_market, "cell_market": cell_market, "mismatch": None}
    # 🔴 미국 차트 사실을 한국 시장 셀에 붙이는 것이 문서화된 함정이다(뉴진스 선례).
    #    막지 않고 표시한다 — 시점이 겹치는 것이 우연이 아닐 수 있다.
    mismatch = cell_market in {"KR", "JP"} and chart_market not in {cell_market}
    return {"chart_market": chart_market, "cell_market": cell_market, "mismatch": mismatch}


def candidates(rec: dict[str, Any]) -> list[dict[str, Any]]:
    """이 임펄스의 (차트 사실 × 셀) 후보. 후보의 근거는 **셀 텍스트의 언급**이다."""
    out = []
    for e in rec.get("chart_evidence") or []:
        if not e.get("charted"):
            continue                                           # 미차트는 셀에 붙일 사실이 없다
        core = _core_title(e.get("title", ""))
        for cell in rec.get("trajectory") or []:
            ev = (cell.get("evidence") or "").lower()
            named = bool(core) and core.lower() in ev
            if not named:
                continue
            out.append({
                "ref": _ref(e),
                "artist": e.get("artist"),
                "title": e.get("title"),
                "entry_date": e.get("entry_date"),
                "peak_position": e.get("peak_position"),
                "cell": cell.get("cell"),
                "cell_date": cell.get("date"),
                "basis": "셀의 evidence 텍스트가 이 곡을 이름으로 언급한다",
                "date": _date_relation(cell.get("date", ""), e.get("entry_date", "")),
                "market": _market_flag(e.get("chart", ""), cell.get("cell", "")),
            })
    return out


def _load(impulses: Path) -> list[tuple[Path, dict[str, Any]]]:
    return [(p, json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(impulses.glob("*.json"))]


def report(records: list[tuple[Path, dict[str, Any]]]) -> str:
    lines = ["# 빌보드 궤적 ↔ trajectory 셀 대조 (후보 제안 — 배정 아님)", ""]
    lines.append("셀 배정은 도메인 판단이다. 이 표는 **원장 자신이 이미 언급한** 곡만 후보로 낸다.")
    lines.append("")
    total = flagged = unmatched = 0
    for _, rec in records:
        cands = candidates(rec)
        charted = [e for e in rec.get("chart_evidence") or [] if e.get("charted")]
        linked_refs = {c["ref"] for c in cands}
        orphan = [e for e in charted if _ref(e) not in linked_refs]
        total += len(charted)
        unmatched += len(orphan)
        if not charted:
            continue
        # 확정된 링크는 원장이 정본이다. 대조표가 후보만 보이면 이 문서를 여는 사람이
        # **무엇이 결정됐는지** 알 수 없다.
        confirmed = {(c.get("cell"), r)
                     for c in rec.get("trajectory") or []
                     for r in c.get("chart_evidence_refs") or []}
        n_ok = len([c for c in cands if (c["cell"], c["ref"]) in confirmed])
        lines += [f"## {rec['id']} (차트 사실 {len(charted)}건 · 후보 {len(cands)}쌍 · 확정 {n_ok}쌍)", "",
                  "| 곡 | 진입 | 셀 | 셀 날짜 | 날짜 | 시장 | 확정 |",
                  "|---|---|---|---|---|---|---|"]
        for c in cands:
            d = c["date"]
            rel = d["relation"] if d["months"] in (0, None) else f"{d['relation']} {d['months']}개월"
            mk = "🔴 불일치" if c["market"]["mismatch"] else "ok"
            flagged += bool(c["market"]["mismatch"])
            ok = "✅" if (c["cell"], c["ref"]) in confirmed else ""
            lines.append(f"| {c['artist']} - {_core_title(c['title'])} | {c['entry_date']} | "
                         f"`{c['cell']}` | {c['cell_date']} | {rel} | {mk} | {ok} |")
        for e in orphan:
            lines.append(f"| {e['artist']} - {_core_title(e['title'])} | {e.get('entry_date')} | "
                         f"**후보 없음** | | | | |")
        lines.append("")
    total_confirmed = sum(
        len(c.get("chart_evidence_refs") or [])
        for _, rec in records for c in rec.get("trajectory") or []
    )
    lines += ["## 요약", "",
              f"- 차트 사실 **{total}건** · 원장이 언급하지 않아 후보가 없는 것 **{unmatched}건**",
              (f"- **확정된 링크 {total_confirmed}쌍.** 확정 근거는 쌍마다 "
               "`data/research/genre-impulse/chart_links.confirm.json`의 `_결정근거`에 있다. "
               "`confirm`을 false로 되돌리고 `--apply`를 다시 돌리면 지워진다"),
              (f"- 🔴 시장 불일치 후보 **{flagged}쌍** — 미국 차트 사실이 한국/일본 시장 셀에 걸린 것. "
               "**막지 않았다**: 시점이 겹치는 것이 우연이 아닐 수 있고, 그 판단은 도메인 몫이다."),
              ("- ⚠ 날짜 차이가 곧 오류는 아니다. 실측 예: njs `origin-scene-revival`(2016-11)이 "
               "Finesse를 언급하는데 진입은 2018-01이다 — 앨범 수록과 리믹스 싱글 진입이라 **둘 다 맞다**.")]
    return "\n".join(lines) + "\n"


def emit_confirmations(records: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    """도메인 소유자가 편집할 템플릿. `confirm`을 true로 바꾼 쌍만 원장에 들어간다."""
    out: dict[str, Any] = {
        "_note": "confirm을 true로 바꾼 쌍만 --apply가 원장에 쓴다. 후보에 없는 쌍을 직접 "
                 "추가해도 된다(cell·ref만 맞으면 된다). 지우는 것은 confirm을 false로.",
        "links": {},
    }
    for _, rec in records:
        rows = [{"ref": c["ref"], "cell": c["cell"], "confirm": False,
                 "_곡": f"{c['artist']} - {c['title']}", "_진입": c["entry_date"],
                 "_셀날짜": c["cell_date"], "_날짜": c["date"]["relation"],
                 "_시장불일치": c["market"]["mismatch"]}
                for c in candidates(rec)]
        if rows:
            out["links"][rec["id"]] = rows
    return out


def apply_links(records: list[tuple[Path, dict[str, Any]]], conf: dict[str, Any],
                *, dry_run: bool) -> int:
    """확정된 링크만 `trajectory[].chart_evidence_refs`에 쓴다. 멱등 — 통째로 교체한다."""
    changed = 0
    for path, rec in records:
        wanted: dict[str, list[str]] = {}
        for row in (conf.get("links") or {}).get(rec["id"], []):
            if row.get("confirm") is True:
                wanted.setdefault(row["cell"], []).append(row["ref"])
        known = {_ref(e) for e in rec.get("chart_evidence") or []}
        cells = {c.get("cell") for c in rec.get("trajectory") or []}
        for cell, refs in wanted.items():
            if cell not in cells:
                raise SystemExit(f"{rec['id']}: 없는 셀 '{cell}' — 오타이거나 원장이 바뀌었다")
            bad = [r for r in refs if r not in known]
            if bad:
                raise SystemExit(f"{rec['id']}: 없는 차트 사실 참조 {bad}")
        dirty = False
        for c in rec.get("trajectory") or []:
            refs = sorted(set(wanted.get(c.get("cell"), [])))
            cur = c.get("chart_evidence_refs")
            if refs:
                if cur != refs:
                    c["chart_evidence_refs"] = refs
                    dirty = True
            elif cur is not None:
                c.pop("chart_evidence_refs")                    # 확정 해제 = 지운다
                dirty = True
        if dirty:
            changed += 1
            if not dry_run:
                path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="impulse_trajectory_link",
                                 description="빌보드 궤적 ↔ trajectory 셀 대조 (배정하지 않는다)")
    ap.add_argument("--impulses", required=True)
    ap.add_argument("--emit-confirmations", help="확인용 템플릿 JSON 경로")
    ap.add_argument("--apply", help="사람이 확정한 링크 JSON")
    ap.add_argument("-o", "--out", help="대조표 마크다운 경로 (없으면 stdout)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    records = _load(Path(args.impulses))
    if not records:
        raise SystemExit(f"임펄스가 없다: {args.impulses}")

    if args.apply:
        conf = json.loads(Path(args.apply).read_text(encoding="utf-8"))
        n = apply_links(records, conf, dry_run=args.dry_run)
        print(f"{'(dry-run) ' if args.dry_run else ''}링크 반영: {n}개 레코드 변경", file=sys.stderr)
        return 0

    if args.emit_confirmations:
        payload = emit_confirmations(records)
        Path(args.emit_confirmations).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        n = sum(len(v) for v in payload["links"].values())
        print(f"wrote {args.emit_confirmations} · 후보 {n}쌍 (전부 confirm=false)", file=sys.stderr)
        return 0

    text = report(records)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
