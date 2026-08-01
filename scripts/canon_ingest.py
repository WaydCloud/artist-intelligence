#!/usr/bin/env python
"""외부 캐논 목록 → 정답지 후보 코퍼스 (사전 등록: docs/DRAFT-answer-sheet-corpus.md).

수집(웹)은 세션이 하고 이 스크립트는 **오프라인·결정적**으로 정규화·채점만 한다
(`chart-history convert-melon`과 같은 분업 — 네트워크 0).

🔴 이 스크립트는 **정답지를 만들지 않는다.** 후보와 점수까지만 낸다. 등재 확정은 A&R
몫이며(AGENTS §2.1), 확정 전까지 어떤 게이트도 이 산출을 읽지 않는다.

가중치와 컷오프는 **원장의 6단계 확실성 등급**(D-033 ⑥)을 그대로 쓴다. 값은 아래
`WEIGHTS`·`CUTOFF`에 노출되며 코드 밖에서 조정 가능하다(`--weight`·`--cutoff`).

    python scripts/canon_ingest.py --selftest        # 네트워크 0
    python scripts/canon_ingest.py -o data/research/genre-impulse/canon_candidates.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────── 기준 원장 (값은 A&R 소유)

# D-033 ⑥ 확실성 등급 → 가중치. 새 척도를 만들지 않는다(AGENTS §1).
WEIGHTS: dict[str, float] = {
    "매우 높음": 2.0,  # 1차 출처(씬 당사자·제작진 증언) 또는 독립 복수 교차
    "높음": 1.0,  # 신뢰 매체 단일 + 정합
    "중간": 0.5,  # 2차 단일 또는 팬 비평 수렴
    "낮음": 0.0,  # 원장 사용 규칙: 하중받는 판정은 중간 이상만
    "매우 낮음": 0.0,
    "불가능한 수준": 0.0,
}
CUTOFF = 2.0  # 1차 하나 == 전문지 둘. VIBE 단독(1.0)은 미달.
MIN_MEASURED = 10  # 기존 사전 등록값 유지 — 미만이면 unmeasured

_SOURCES = Path("data/research/genre-impulse/canon_sources.json")


# ─────────────────────────────────────────────── 정규화

_PAREN = re.compile(r"\s*[\(\[][^)\]]*[\)\]]\s*")
_FEAT = re.compile(r"\s*(?:feat\.?|ft\.?|featuring|with)\s+.*$", re.IGNORECASE)
_NONWORD = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

# 🔴 리믹스·버전은 **원곡과 합치지 않는다**(사전 등록 §4). 저지클럽 리믹스는 원곡과
# 리듬이 다르므로 다른 곡이다. 그래서 이 표시들은 괄호를 지울 때 **되살려 붙인다**.
_VERSION_MARK = re.compile(
    r"\b(remix|rmx|mix|edit|version|ver|dub|bootleg|flip|rework|vip)\b", re.IGNORECASE
)


_APOS = re.compile(r"['’‘`´\"“”]")


def _clean(s: str) -> str:
    """아포스트로피는 **지우고**(칸으로 바꾸지 않는다) 나머지 기호만 칸으로."""
    s = unicodedata.normalize("NFKC", s).casefold()
    s = _APOS.sub("", s).replace("＆", "&")
    s = _NONWORD.sub(" ", s)
    return _WS.sub(" ", s).strip()


def norm_key(artist: str, title: str) -> str:
    """`아티스트|곡` 정규 키. feat.·괄호 표기 차이는 합치고 **버전은 가른다**.

    🔑 아티스트와 곡명의 정규화 **강도를 다르게** 둔다.

    아티스트는 띄어쓰기까지 지운다 — 같은 사람을 매체가 다르게 적기 때문이다
    (VIBE `DJ Lil Man` vs 우리 정답지 `DJ Lilman`). 이름은 띄어쓰기가 흔들려도
    다른 사람이 되지 않는다.

    🔴 곡명은 띄어쓰기를 **남긴다.** 여기까지 지우면 `Go In`과 `Goin`이 한 곡이 된다 --
    정답지에서 두 곡이 하나로 접히는 것은 표본을 조용히 줄이는 일이고, 그 반대(안 합쳐짐)
    보다 발견하기 어렵다.
    """
    a = _FEAT.sub("", _PAREN.sub(" ", artist or ""))
    raw_t = title or ""
    # 괄호 안에 버전 표시가 있으면 그 단어만 남겨 키에 실어 보낸다.
    marks = sorted({m.lower() for m in _VERSION_MARK.findall(raw_t)})
    t = _FEAT.sub("", _PAREN.sub(" ", raw_t))
    if marks:
        t = f"{t} {' '.join(marks)}"

    return f"{_clean(a).replace(' ', '')}|{_clean(t)}"


# ─────────────────────────────────────────────── 채점


def score(
    entries: list[dict[str, Any]], weights: dict[str, float], cutoff: float
) -> list[dict[str, Any]]:
    """출처별 지목을 곡 단위로 접어 가중 합을 낸다.

    🔴 **같은 출처의 중복 지목은 한 번만 센다**(사전 등록 §2 출처 독립성). 없으면 한
    기사가 같은 곡을 두 번 적기만 해도 컷오프를 혼자 넘는다.
    """
    by_key: dict[str, dict[str, Any]] = {}
    for e in entries:
        k = norm_key(str(e.get("artist", "")), str(e.get("title", "")))
        if k == "|":
            continue
        slot = by_key.setdefault(
            k,
            {
                "key": k,
                "artist": e.get("artist"),
                "title": e.get("title"),
                "case": e.get("case"),
                "sources": {},
                "years": set(),
            },
        )
        srcs = slot["sources"]
        sid = str(e.get("source_id"))
        # 같은 출처가 여러 번 지목해도 한 번. 등급은 그 출처의 것을 쓴다.
        srcs[sid] = str(e.get("certainty"))
        y = str(e.get("year") or "").strip()
        if y and y.lower() not in ("unknown", ""):
            slot["years"].add(y)

    out: list[dict[str, Any]] = []
    for slot in by_key.values():
        srcs = slot["sources"]
        s = round(sum(weights.get(c, 0.0) for c in srcs.values()), 3)
        years = slot["years"]
        out.append({
            "key": slot["key"],
            "case": slot["case"],
            "artist": slot["artist"],
            "title": slot["title"],
            "years": sorted(years),
            "score": s,
            "passes": s >= cutoff,
            "named_by": [{"source_id": k, "certainty": v} for k, v in sorted(srcs.items())],
        })
    out.sort(key=lambda r: (str(r["case"]), -float(r["score"]), str(r["artist"])))
    return out


def era(years: list[str]) -> str:
    """연대 구간 — 측정 필터의 편향을 보이게 하는 축(사전 등록 §5)."""
    nums = [int(m.group()) for y in years if (m := re.search(r"(19|20)\d{2}", y))]
    if not nums:
        return "미상"
    y = min(nums)
    return "~2010" if y <= 2010 else ("2011~2019" if y <= 2019 else "2020~")


def summarize(rows: list[dict[str, Any]], cutoff: float) -> dict[str, Any]:
    cases: dict[str, dict[str, Any]] = {}
    for r in rows:
        c = str(r["case"])
        s = cases.setdefault(
            c, {"candidates": 0, "passes": 0, "by_era": {}, "by_artist": {}, "min_measured_ok": False}
        )
        s["candidates"] += 1
        if r["passes"]:
            s["passes"] += 1
            e = era([str(x) for x in r["years"]])
            s["by_era"][e] = s["by_era"].get(e, 0) + 1
            a = str(r["artist"])
            s["by_artist"][a] = s["by_artist"].get(a, 0) + 1
    for s in cases.values():
        s["min_measured_ok"] = s["passes"] >= MIN_MEASURED
        by_artist = s["by_artist"]
        # 🔺 한 아티스트가 정답지의 큰 몫이면 축이 재는 것이 "장르"인지 "그 사람"인지 갈리지 않는다.
        s["top_artist_share"] = (
            round(max(by_artist.values()) / max(1, s["passes"]), 3) if by_artist else 0.0
        )
        s["by_artist"] = dict(sorted(by_artist.items(), key=lambda kv: -kv[1])[:5])
    return cases


# ─────────────────────────────────────────────── selftest (네트워크 0)


def cmd_selftest() -> int:
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    # 정규화: feat./괄호/표기 차이는 합친다
    check(
        norm_key("DJ Lil Man Feat. Ms. Porsh", "Sexy Walk") == norm_key("DJ Lilman", "Sexy Walk"),
        "feat. 표기와 띄어쓰기 차이는 같은 곡이어야 한다",
    )
    check(
        norm_key("PinkPantheress", "Boy's a liar Pt. 2")
        == norm_key("PinkPantheress", "Boy’s a liar Pt. 2"),
        "아포스트로피 차이는 같은 곡이어야 한다",
    )
    # 🔴 버전은 가른다 — 이것이 합쳐지면 리듬이 다른 곡이 한 칸에 들어간다
    check(
        norm_key("DJ Lilman", "Cant Bounce Like Me")
        == norm_key("DJ Lil Man", "Can’t Bounce Like Me"),
        "아포스트로피 유무와 이름 띄어쓰기는 같은 곡이어야 한다",
    )
    check(
        norm_key("Coi Leray", "Players") != norm_key("Coi Leray", "Players (DJ Smallz 732 Remix)"),
        "리믹스는 원곡과 다른 곡이어야 한다",
    )
    # 🔴 곡명에서 띄어쓰기까지 지우면 안 된다 -- 두 곡이 하나로 접힌다
    check(
        norm_key("Shady", "Go In") != norm_key("Shady", "Goin"),
        "곡명의 띄어쓰기는 살려야 한다 (Go In != Goin)",
    )
    check(
        norm_key("Tina Moore", "Never Letting You Go (Artful Dodger Mix)")
        != norm_key("Tina Moore", "Never Letting You Go"),
        "믹스 표기가 있으면 원곡과 갈려야 한다",
    )

    w = dict(WEIGHTS)
    # 컷오프: 1차 하나 = 통과 · 전문지 하나 = 미달 · 전문지 둘 = 통과
    e: list[dict[str, Any]] = [
        {"case": "t", "artist": "A", "title": "x", "source_id": "s1", "certainty": "매우 높음"},
        {"case": "t", "artist": "B", "title": "y", "source_id": "s2", "certainty": "높음"},
        {"case": "t", "artist": "C", "title": "z", "source_id": "s2", "certainty": "높음"},
        {"case": "t", "artist": "C", "title": "z", "source_id": "s3", "certainty": "높음"},
        {"case": "t", "artist": "D", "title": "w", "source_id": "s4", "certainty": "낮음"},
    ]
    rows = {r["artist"]: r for r in score(e, w, CUTOFF)}
    check(bool(rows["A"]["passes"]), "1차 출처 하나면 통과해야 한다 (2.0)")
    check(not rows["B"]["passes"], "전문지 하나(1.0)는 미달이어야 한다 -- VIBE 단독 규칙")
    check(bool(rows["C"]["passes"]), "독립 전문지 둘(2.0)이면 통과해야 한다")
    check(float(rows["D"]["score"]) == 0.0, "낮음 이하는 0점이어야 한다")

    # 🔴 같은 출처의 중복 지목은 한 번만
    dup: list[dict[str, Any]] = [
        {"case": "t", "artist": "E", "title": "v", "source_id": "s5", "certainty": "높음"},
        {"case": "t", "artist": "E", "title": "v", "source_id": "s5", "certainty": "높음"},
    ]
    check(
        float(score(dup, w, CUTOFF)[0]["score"]) == 1.0,
        "같은 출처의 중복 지목이 두 번 세어지면 안 된다",
    )

    check(era(["2009"]) == "~2010" and era(["2015"]) == "2011~2019" and era(["2022"]) == "2020~",
          "연대 구간 배정이 어긋난다")
    check(era([]) == "미상", "연도 없는 곡은 미상이어야 한다")

    for f in fails:
        print(f"!! selftest: {f}")
    print(f"selftest: {'FAILED' if fails else 'ok'} ({len(fails)} finding(s))")
    return 1 if fails else 0


# ─────────────────────────────────────────────── main


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="외부 캐논 목록 → 정답지 후보 (오프라인·결정적)")
    ap.add_argument("--sources", default=str(_SOURCES), help="수집한 출처 원장 JSON")
    ap.add_argument("-o", "--output", default=None, help="후보 코퍼스 출력 JSON")
    ap.add_argument("--cutoff", type=float, default=CUTOFF, help=f"등재 컷오프 (기본 {CUTOFF})")
    ap.add_argument("--selftest", action="store_true", help="오프라인 검사, 네트워크 0")
    args = ap.parse_args(argv)

    if args.selftest:
        return cmd_selftest()

    src_path = Path(args.sources)
    if not src_path.is_file():
        print(f"!! sources not found: {src_path}", file=sys.stderr)
        return 2
    doc = json.loads(src_path.read_text(encoding="utf-8"))
    sources = {s["id"]: s for s in doc["sources"]}

    entries: list[dict[str, Any]] = []
    for s in doc["sources"]:
        for t in s.get("tracks", []):
            entries.append({
                "case": s["case"],
                "artist": t.get("artist"),
                "title": t.get("title"),
                "year": t.get("year"),
                "source_id": s["id"],
                "certainty": s["certainty"],
            })

    rows = score(entries, WEIGHTS, args.cutoff)
    out = {
        "provenance": {
            "generator": "scripts/canon_ingest.py",
            "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "prereg": "docs/DRAFT-answer-sheet-corpus.md",
            "weights": WEIGHTS,
            "cutoff": args.cutoff,
            "min_measured": MIN_MEASURED,
            "status": "A&R 확정 대기 — 어떤 게이트도 이 산출을 읽지 않는다",
            "source_count": len(sources),
        },
        "summary": summarize(rows, args.cutoff),
        "candidates": rows,
    }
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.output} · {len(rows)} candidate(s) from {len(sources)} source(s)")
    for case, s in sorted(out["summary"].items()):
        print(
            f"  {case:22} 후보 {s['candidates']:>3} · 통과 {s['passes']:>3}"
            f" · 최소표본 {'OK' if s['min_measured_ok'] else 'X '}"
            f" · 최다아티스트 비중 {s['top_artist_share']:.0%} · 연대 {s['by_era']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
