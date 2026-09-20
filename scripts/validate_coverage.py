"""Coverage gate. Catch the day a source goes quiet while the CLI still exits 0.

Why this exists: on 2026-09-05 the iTunes search API stopped answering for the KR
storefront. The sonic leg kept succeeding, the schema kept validating, CI stayed green,
and the report honestly printed the miss count. Nobody read that number for 16 days, so
the chart cohort ran at 8 tracks a day instead of 65 and the tabs downstream quietly
shrank. A failure that arrives as a smaller sample needs a gate that reads the sample.

What it measures: per observation day, the share of records that carry a payload.

    coverage(day) = resolved / (resolved + unresolved)

A day is RED two ways, and it needs both.

  1. DROP  coverage falls a long way under the median of the days before it. The baseline
           is a median over a window, not yesterday: yesterday can itself be the first
           broken day, and then a broken day compares against a broken day.
  2. FLOOR coverage sits under an absolute rate. The drop rule alone goes quiet once the
           window fills with broken days, which on the real data meant it fired for four
           days and then said nothing for the remaining twelve. That is the failure this
           gate exists to prevent, so a floor carries the days the drop rule drops.

    python scripts/validate_coverage.py [<snapshot dir> ...] [--window 7] [--max-drop 0.5]
    python scripts/validate_coverage.py --selftest

Exit: 0 = clean, 1 = a day is RED.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any

# Both are loaded criteria: they decide whether a human is told to go look. They live in
# modules/sonic-profile/RULES.md with their grounds, and stay on the command line so the
# domain owner can move them without touching code (AGENTS.md 2.1).
WINDOW_DEFAULT = 7
MAX_DROP_DEFAULT = 0.5
MIN_RECORDS_DEFAULT = 20

# The floor is read off the observed record, not chosen. Over data/live/sonic 2026-07-28 to
# 09-04 (39 healthy days) coverage never fell below 54.1%, and over 09-05 to 09-20 (16 broken
# days) it sat at 7.2% every day. Nothing was ever observed between those two, so 30% is
# inside an empty band: far under anything healthy, far over the broken state.
MIN_RATE_DEFAULT = 0.30


def _records(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        recs = doc.get("records")
        if isinstance(recs, list):
            return [r for r in recs if isinstance(r, dict)]
    return []


def day_coverage(path: Path) -> tuple[int, int] | None:
    """(resolved, total) for one snapshot file, or None when it carries no records.

    `features` is the payload and `unresolved` is the explicit miss. A record with
    neither is counted in neither: an empty record is a shape we do not understand, and
    reading it as a miss would invent a drop.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    recs = _records(doc)
    resolved = sum(1 for r in recs if r.get("features"))
    missed = sum(1 for r in recs if not r.get("features") and r.get("unresolved"))
    total = resolved + missed
    return (resolved, total) if total else None


def series(directory: Path) -> list[tuple[str, int, int]]:
    """(day, resolved, total) sorted by day. Filenames that are not dates are skipped."""
    out: list[tuple[str, int, int]] = []
    for f in sorted(directory.glob("*.json")):
        stem = f.stem
        if len(stem) != 10 or stem[4] != "-" or stem[7] != "-":
            continue  # cache.json, cohort.json and friends are not observation days
        got = day_coverage(f)
        if got:
            out.append((stem, got[0], got[1]))
    return out


def judge(
    rows: list[tuple[str, int, int]],
    *,
    window: int,
    max_drop: float,
    min_records: int,
    min_rate: float,
) -> tuple[list[str], list[str]]:
    """Returns (red lines, note lines).

    The floor is judged from the first day on. The drop rule needs a window behind it, so a
    fresh store has no baseline, and waiting for one is how the first broken days get through.
    """
    red: list[str] = []
    notes: list[str] = []
    if len(rows) <= window:
        notes.append(f"관측일 {len(rows)}일, 창 {window}일 미만이라 하락 판정은 보류 (바닥만 본다)")
    for i, (day, res, total) in enumerate(rows):
        if total < min_records:
            notes.append(f"{day}: 레코드 {total}건 (최소 {min_records}건 미만, 판정 보류)")
            continue
        rate = res / total
        if rate < min_rate:
            red.append(
                f"{day}: 해석률 {rate:.1%} ({res}/{total}), 절대 바닥 {min_rate:.0%} 미만 [바닥]"
            )
            continue  # 같은 날을 두 번 세지 않는다. 바닥이 더 강한 진술이다
        if i < window:
            continue
        base = median(r / t for _d, r, t in rows[i - window : i])
        if base <= 0:
            notes.append(f"{day}: 앞 {window}일 기준선이 0 (판정 보류)")
            continue
        drop = (base - rate) / base
        if drop >= max_drop:
            red.append(
                f"{day}: 해석률 {rate:.1%} ({res}/{total}), 앞 {window}일 중앙값 {base:.1%}"
                f" 대비 {drop:.0%} 하락 (한계 {max_drop:.0%}) [하락]"
            )
    return (red, notes)


def check_dir(
    directory: Path, *, window: int, max_drop: float, min_records: int, min_rate: float,
    latest_only: bool = False,
) -> int:
    rows = series(directory)
    if not rows:
        print(f"{directory}: 관측일 0 (스냅샷 없음, 건너뜀)")
        return 0
    red, notes = judge(
        rows, window=window, max_drop=max_drop, min_records=min_records, min_rate=min_rate
    )
    first, last = rows[0][0], rows[-1][0]
    if latest_only:
        # daily 가 매일 부르는 자리다. 과거 RED 를 다시 찍으면 로그가 어제 일로 덮이고,
        # 그러면 오늘이 빨간지 읽으려고 스크롤해야 한다. 판정은 최신일 것만 남긴다.
        red = [r for r in red if r.startswith(last)]
        notes = [n for n in notes if n.startswith(last) or "보류" in n]
    res, total = rows[-1][1], rows[-1][2]
    print(
        f"{directory}: 관측일 {len(rows)}일 ({first}~{last}), 최신 {last} 해석 "
        f"{res}/{total} ({res / total:.1%})"
    )
    for n in notes:
        print(f"  note {n}")
    for r in red:
        print(f"::error file={directory}::커버리지 {r}")
    if red:
        print(f"  RED {len(red)}일. 소스가 조용해졌는지 확인할 것")
        return 1
    return 0


def selftest() -> int:
    """Synthetic days only. No disk, no network.

    Several cases pass `min_rate=0.0` on purpose: that isolates the drop rule so a case
    about baselines is not answered by the floor instead.
    """
    fails: list[str] = []
    ran = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ran
        ran += 1
        print(f"  {'PASS' if cond else 'FAIL'}: {name}{(' · ' + detail) if detail else ''}")
        if not cond:
            fails.append(name)

    def run(rows, *, window=7, max_drop=0.5, min_records=20, min_rate=0.30):
        return judge(rows, window=window, max_drop=max_drop,
                     min_records=min_records, min_rate=min_rate)

    flat = [(f"2026-09-{d:02d}", 60, 100) for d in range(1, 9)]
    red, _ = run(flat)
    check("안정된 커버리지는 빨개지지 않는다", not red, f"{red}")

    # The shape that went unseen for 16 days: 65/110 a day, then 8/110 and stuck.
    broke = [(f"2026-09-{d:02d}", 65, 110) for d in range(1, 8)]
    broke += [(f"2026-09-{d:02d}", 8, 110) for d in range(8, 12)]
    red, _ = run(broke)
    check("결함 39의 모양을 잡는다 (65/110 에서 8/110)", len(red) == 4, f"RED {len(red)}일")
    check("첫 빨간 날을 정확히 짚는다", bool(red) and red[0].startswith("2026-09-08"),
          red[0][:22] if red else "-")

    # The hole the floor exists to close. Sixteen broken days, drop rule alone.
    stuck = [(f"2026-09-{d:02d}", 65, 110) for d in range(1, 8)]
    stuck += [(f"2026-09-{d:02d}", 8, 110) for d in range(8, 25)]
    red_drop, _ = run(stuck, min_rate=0.0)
    red_both, _ = run(stuck)
    check("하락 규칙만 두면 창이 차는 순간 조용해진다", len(red_drop) < len(stuck) - 7,
          f"끊김 17일 중 {len(red_drop)}일만 빨감")
    check("바닥이 나머지 날을 들고 간다", len(red_both) == 17, f"RED {len(red_both)}일")

    # A slow slide must not fire: this gate is for a break, not for a trend.
    drift = [(f"2026-09-{d:02d}", 70 - d, 100) for d in range(1, 15)]
    red, _ = run(drift)
    check("완만한 하락은 빨개지지 않는다 (끊김을 잡는 게이트다)", not red, f"{red}")

    # Baseline is a median over the window, so one broken day cannot become the new normal.
    # 100/110 = 90.9% 기준선에서 45/110 = 40.9% 는 55% 하락이면서 바닥 30% 위다.
    # 두 규칙이 같은 날을 물면 이 검사가 무엇을 재는지 알 수 없어진다.
    late = [(f"2026-09-{d:02d}", 100, 110) for d in range(1, 8)]
    late += [("2026-09-08", 45, 110), ("2026-09-09", 45, 110)]
    red, _ = run(late, window=1, min_rate=0.0)
    check("창 1일이면 둘째 날을 놓친다 (중앙값 창이 필요한 이유)", len(red) == 1, f"RED {len(red)}일")
    red, _ = run(late, min_rate=0.0)
    check("창 7일이면 둘째 날도 잡는다", len(red) == 2, f"RED {len(red)}일")

    tiny = [(f"2026-09-{d:02d}", 6, 10) for d in range(1, 8)] + [("2026-09-08", 0, 10)]
    red, notes = run(tiny)
    check("표본이 작은 날은 판정하지 않는다 (분모 없는 비율은 판별력이 없다)",
          not red and any("최소" in n for n in notes), f"{notes}")

    short = [(f"2026-09-{d:02d}", 60, 100) for d in range(1, 5)]
    red, notes = run(short)
    check("이력이 창보다 짧으면 하락 판정을 보류한다 (조용한 통과 금지)",
          not red and any("보류" in n for n in notes), f"{notes}")

    fresh = [("2026-09-01", 2, 100), ("2026-09-02", 2, 100)]
    red, _ = run(fresh)
    check("이력이 없어도 바닥은 첫날부터 본다", len(red) == 2, f"RED {len(red)}일")

    tag = f" FAILED {fails}" if fails else ""
    print()
    print(f"selftest {ran - len(fails)}/{ran}{tag}")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validate_coverage", description="커버리지 게이트")
    ap.add_argument("dirs", nargs="*", help="스냅샷 디렉터리 (기본 data/live/sonic)")
    ap.add_argument("--window", type=int, default=WINDOW_DEFAULT,
                    help=f"기준선을 잡는 앞선 관측일 수 (기본 {WINDOW_DEFAULT})")
    ap.add_argument("--max-drop", type=float, default=MAX_DROP_DEFAULT,
                    help=f"기준선 대비 허용 하락폭 (기본 {MAX_DROP_DEFAULT})")
    ap.add_argument("--min-rate", type=float, default=MIN_RATE_DEFAULT,
                    help=f"절대 해석률 바닥 (기본 {MIN_RATE_DEFAULT})")
    ap.add_argument("--min-records", type=int, default=MIN_RECORDS_DEFAULT,
                    help=f"판정에 필요한 최소 레코드 수 (기본 {MIN_RECORDS_DEFAULT})")
    ap.add_argument("--latest-only", action="store_true",
                    help="최신 관측일만 판정 (daily 용, 과거 RED 재출력 안 함)")
    ap.add_argument("--selftest", action="store_true",
                    help="합성 날짜로 게이트 자체를 검증 (디스크 0)")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    dirs = args.dirs or ["data/live/sonic"]
    print(f"커버리지 게이트 · 창 {args.window}일 · 허용 하락 {args.max_drop:.0%} "
          f"· 바닥 {args.min_rate:.0%} · 최소 {args.min_records}건"
          + (" · 최신일만" if args.latest_only else ""))
    worst = 0
    for d in dirs:
        rc = check_dir(Path(d), window=args.window, max_drop=args.max_drop,
                       min_records=args.min_records, min_rate=args.min_rate,
                       latest_only=args.latest_only)
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
