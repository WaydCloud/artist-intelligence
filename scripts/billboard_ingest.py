"""Billboard Hot 100 이력 → 내부 파생 산출 (D-035 ② 채택 후 수집부).

`billboard_probe.py`가 소스를 **검증**한다면, 이 스크립트는 검증된 소스에서
**우리가 쓸 두 가지**만 뽑는다:

  * `cohort` — 특정 주차의 톱N을 sonic-profile `fetch --cohort` 입력 형태로.
    genre-impulse의 **동시대 US 코호트 소급**(A2 본편에서 원형↔한국 서명을
    같은 시점 모집단 위에서 비교하기 위한 기준 모집단)에 쓴다.
  * `trajectory` — 케이스 대표곡의 주간 순위 궤적. 케이스북 `trajectory` 셀의
    날짜 근거(예: "빌보드 먼저" 구간)를 증언·기사가 아니라 **차트 사실**로
    교체하기 위한 것이다.

저장 규율 (D-035 ②): **사실 필드만 내부 파생 저장 · 원문 재배포 금지.**
따라서 ① 전 주차 벌크 미러링을 하지 않는다 — 명시한 주차/곡만 물질화한다.
② 산출에 원문 부가 필드를 싣지 않는다(순위·주차·피크만).
③ `--cohort-weeks` 한 번에 물질화할 주차 수에 상한(기본 8)을 둔다. 상한에
걸리면 조용히 자르지 않고 실패한다 — 잘린 산출은 "전부 담겼다"로 읽힌다.

Usage:

    # 동시대 US 코호트 (sonic-profile fetch --cohort 입력)
    python scripts/billboard_ingest.py cohort 2021-10-02 --top 100 \
        -o data/research/genre-impulse/cohort_us_2021-10-02.json

    # 케이스 대표곡 궤적
    python scripts/billboard_ingest.py trajectory \
        --tracks data/research/genre-impulse/cohort_cases.json \
        --from 2019-01-01 --to 2024-12-31 \
        -o data/research/genre-impulse/billboard_trajectories.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 정규화·페치는 probe의 것을 그대로 쓴다 — 두 벌이 되면 대조가 검증한 규칙과
# 수집이 쓰는 규칙이 갈라진다(AGENTS §1 중복 방지).
# (이 import는 위 sys.path 설정 뒤여야 한다)
from billboard_probe import (
    artist_agrees,
    dataset_chart,
    dataset_valid_dates,
    norm_title,
    titles_agree,
)

_MAX_COHORT_WEEKS = 8


def _cache_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    import tempfile

    return Path(tempfile.gettempdir()) / "billboard_probe_cache"


def _window(valid: list[str], start: str | None, end: str | None) -> list[str]:
    lo = start or valid[0]
    hi = end or valid[-1]
    return [d for d in valid if lo <= d <= hi]


# ───────────────────────────────────────────────────────────── cohort


def build_cohort(dates: list[str], top: int, cache_dir: Path) -> dict[str, Any]:
    if len(dates) > _MAX_COHORT_WEEKS:
        raise SystemExit(
            f"주차 {len(dates)}건은 상한 {_MAX_COHORT_WEEKS}건을 넘는다. "
            "벌크 미러링은 원문 재배포 전제 위반이다(D-035 ②) — 주차를 좁히거나 "
            "필요를 문서로 올려 상한을 재조정하라."
        )
    tracks: list[dict[str, Any]] = []
    for chart_date in dates:
        rows = dataset_chart(chart_date, cache_dir)
        for row in sorted(rows, key=lambda r: r.get("this_week") or 999)[:top]:
            tracks.append({
                "artist": row.get("artist"),
                "title": row.get("song"),
                "market": "US",
                "platform": "billboard-hot100",
                "rank": row.get("this_week"),
                "chart_date": chart_date,
            })
        print(f"  {chart_date}: {min(len(rows), top)} tracks", file=sys.stderr)
    return {
        "note": (
            "Billboard Hot 100 동시대 US 코호트 (D-035 ② · 파생 사실 필드만). "
            "source=github.com/mhollingshead/billboard-hot-100 — 순위·주차 사실만 "
            "내부 저장하며 원문 재배포 금지. platform=billboard-hot100."
        ),
        "chart_dates": dates,
        "tracks": tracks,
    }


# ─────────────────────────────────────────────────────────── trajectory


def _load_targets(path: Path, only_case: str | None) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["tracks"] if isinstance(payload, dict) else payload
    out = []
    for r in rows:
        if only_case and r.get("market") != only_case:
            continue
        out.append({
            "artist": r.get("artist", ""),
            "title": r.get("title", ""),
            "case": r.get("market", ""),
            "role": r.get("platform", ""),
        })
    return out


def build_trajectories(
    targets: list[dict[str, str]], dates: list[str], cache_dir: Path
) -> dict[str, Any]:
    """윈도 안의 모든 주차를 훑어 각 대상 곡의 순위 궤적을 만든다.

    전 이력(3,548주 × 100칸)을 대상 95곡과 맞대면 곱이 3천만을 넘는다. 그래서
    주차마다 제목 정규화 **색인**을 만들고 대상은 미리 정규화해 조회만 한다 —
    정규화 규칙(`titles_agree`)은 그대로 쓰되 호출 횟수만 줄인 것이라 판정은
    바뀌지 않는다. 다만 검열 마스킹(`*`)은 사전 조회로 못 잡으므로 해당 행·
    대상만 따로 선형 대조한다.
    """
    keys = [
        {
            "strict": norm_title(t["title"]),
            "lenient": norm_title(t["title"], strip_parens=True),
            "masked": "*" in norm_title(t["title"]),
        }
        for t in targets
    ]
    hits: dict[int, list[tuple[str, int]]] = {i: [] for i in range(len(targets))}
    peak_field: dict[int, tuple[int, int]] = {}  # i -> (peak_position, weeks_on_chart)

    for n, chart_date in enumerate(dates, 1):
        rows = dataset_chart(chart_date, cache_dir)
        index: dict[str, list[dict[str, Any]]] = {}
        masked_rows: list[dict[str, Any]] = []
        for row in rows:
            song = row.get("song", "")
            strict, lenient = norm_title(song), norm_title(song, strip_parens=True)
            index.setdefault(strict, []).append(row)
            if lenient != strict:
                index.setdefault(lenient, []).append(row)
            if "*" in strict:
                masked_rows.append(row)

        for i, t in enumerate(targets):
            cands = index.get(keys[i]["lenient"]) or index.get(keys[i]["strict"]) or []
            if not cands and (masked_rows or keys[i]["masked"]):
                scan = rows if keys[i]["masked"] else masked_rows
                cands = [r for r in scan
                         if titles_agree(t["title"], r.get("song", ""), strip_parens=True)]
            for row in cands:
                if artist_agrees(t["artist"], row.get("artist", "")):
                    hits[i].append((chart_date, row.get("this_week") or 0))
                    peak_field[i] = (
                        row.get("peak_position") or 0,
                        row.get("weeks_on_chart") or 0,
                    )
                    break
        if n % 250 == 0:
            print(f"  scanned {n}/{len(dates)} weeks", file=sys.stderr)

    results = []
    for i, t in enumerate(targets):
        ranks = hits[i]
        if not ranks:
            results.append({**t, "charted": False})
            continue
        best = min(ranks, key=lambda p: p[1])
        peak_pos, weeks_total = peak_field.get(i, (best[1], len(ranks)))
        results.append({
            **t,
            "charted": True,
            "entry_date": ranks[0][0],
            "exit_date": ranks[-1][0],
            "weeks_in_window": len(ranks),
            "weeks_on_chart_reported": weeks_total,
            "peak_position": peak_pos,
            "peak_date": best[0],
            "ranks": [{"date": d, "rank": r} for d, r in ranks],
        })
    charted = sum(1 for r in results if r["charted"])
    print(f"  charted {charted}/{len(results)} targets", file=sys.stderr)
    return {
        "note": (
            "Billboard Hot 100 케이스 궤적 (D-035 ② · 파생 사실 필드만). "
            "charted=false는 **아래 window 안에서** Hot 100에 없었다는 뜻이다 — "
            "윈도가 전 이력이 아니면 발매 시점이 윈도 밖일 수 있으니 window를 먼저 볼 것. "
            "차트에 없다는 것이 '영향이 없었다'는 뜻도 아니다: 발원지 바이럴 층은 "
            "Hot 100에 원리적으로 안 잡힌다(케이스북의 리드타임 논지 그대로). "
            "매칭은 제목·아티스트 정규화 기반이라 크레딧 표기가 크게 다르면 "
            "놓칠 수 있다 — charted=false는 '못 찾았다'를 포함한다."
        ),
        "window": {"from": dates[0], "to": dates[-1], "weeks": len(dates)},
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="billboard_ingest",
        description="Billboard Hot 100 이력 → 내부 파생 산출 (D-035 ②).",
    )
    ap.add_argument("--cache-dir", help="원문 캐시 (probe와 공유). 커밋 금지")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cohort", help="주차 톱N을 sonic-profile 코호트 형태로")
    c.add_argument("dates", nargs="+", help="차트 주차 YYYY-MM-DD (유효 주차여야 한다)")
    c.add_argument("--top", type=int, default=100, help="상위 N (기본 100)")
    c.add_argument("-o", "--out", required=True)

    t = sub.add_parser("trajectory", help="케이스 대표곡 주간 순위 궤적")
    t.add_argument("--tracks", required=True, help="대상 곡 목록 JSON (cohort_cases.json 형식)")
    t.add_argument("--case", help="특정 케이스(market)만")
    t.add_argument("--from", dest="start", help="윈도 시작 YYYY-MM-DD")
    t.add_argument("--to", dest="end", help="윈도 끝 YYYY-MM-DD")
    t.add_argument("-o", "--out", required=True)

    args = ap.parse_args(argv)
    cache_dir = _cache_dir(args.cache_dir)
    valid = dataset_valid_dates(cache_dir)

    if args.cmd == "cohort":
        unknown = [d for d in args.dates if d not in valid]
        if unknown:
            near = {d: min(valid, key=lambda v: abs(date.fromisoformat(v) - date.fromisoformat(d)))
                    for d in unknown}
            raise SystemExit(
                "유효 차트 주차가 아니다: "
                + ", ".join(f"{d}(가장 가까운 주차 {near[d]})" for d in unknown)
            )
        payload = build_cohort(args.dates, args.top, cache_dir)
    else:
        targets = _load_targets(Path(args.tracks), args.case)
        if not targets:
            raise SystemExit("대상 곡이 0건이다 — --tracks/--case 를 확인하라")
        window = _window(valid, args.start, args.end)
        if not window:
            raise SystemExit("윈도 안에 유효 주차가 없다")
        print(f"targets {len(targets)} · window {window[0]}~{window[-1]} "
              f"({len(window)} weeks)", file=sys.stderr)
        payload = build_trajectories(targets, window, cache_dir)

    Path(args.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
