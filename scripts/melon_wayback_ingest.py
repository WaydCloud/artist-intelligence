"""Wayback 멜론 주간 차트 → 동시대 KR 코호트 (REVIEW-chart-history-sources 판정 후 수집부).

`billboard_ingest.py`가 US 동시대 코호트를 만든다면, 이 스크립트는 같은 목적의
**KR 쪽 반쪽**이다: Wayback Machine에 산재한 멜론 주간 차트 스냅샷에서 톱N을
sonic-profile `fetch --cohort` 입력 형태로 뽑는다. genre-impulse A2 본편에서
한국 수용곡의 백분위를 **동시대 한국 모집단** 위에서 재는 데 쓴다.

Wayback 커버리지는 주별 불균일하다(소스 검토 실측) — 원하는 주가 없을 수 있다.
그래서 앵커 날짜를 받아 **가장 가까운 스냅샷**을 CDX로 찾고, 실제 차트 주간과
앵커의 거리를 산출물에 그대로 적는다. 거리를 숨기면 "2021-10-02의 멜론"으로
읽힌다 — 그 주가 아니라 그 언저리다.

저장 규율 (D-035 ②와 동일): **사실 필드만 내부 파생 저장 · 원문 재배포 금지.**
① 벌크 미러링을 하지 않는다 — 호출 1회 = 스냅샷 1장. ② 산출에 순위·아티스트·
곡명·주간 라벨만 싣는다(원문 HTML·이미지·링크 미저장).

Usage:

    # 2021-10-02 앵커에 가장 가까운 멜론 주간 톱100
    python scripts/melon_wayback_ingest.py cohort 2021-10-02 --top 100 \
        -o data/research/genre-impulse/cohort_kr_2021-10-02.json
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_CDX = "http://web.archive.org/cdx/search/cdx"
_CHART_URL = "melon.com/chart/week/index.htm"
_UA = "artist-intelligence research (contact: internal; derived facts only)"

# 앵커에서 이 이상 떨어진 스냅샷은 "동시대"라 부를 수 없다 — 조용히 먼 주를
# 집어오면 코호트가 다른 시장 국면을 대표하게 된다. 상한에 걸리면 실패한다.
_MAX_DISTANCE_DAYS = 45

_ROW_RE = re.compile(
    r'rank01"><span>[\s\S]*?<a[^>]*>([^<]+)</a>[\s\S]*?rank02">[\s\S]*?<a[^>]*>([^<]+)</a>',
)
_WEEK_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\s*~\s*(\d{4})\.(\d{2})\.(\d{2})")


def _http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def nearest_snapshot(anchor: date) -> tuple[str, int]:
    """앵커 ±_MAX_DISTANCE_DAYS 안에서 가장 가까운 200 스냅샷 타임스탬프를 찾는다."""
    lo = (anchor - timedelta(days=_MAX_DISTANCE_DAYS)).strftime("%Y%m%d")
    hi = (anchor + timedelta(days=_MAX_DISTANCE_DAYS)).strftime("%Y%m%d")
    url = (f"{_CDX}?url={_CHART_URL}&from={lo}&to={hi}"
           "&output=json&filter=statuscode:200&collapse=digest")
    rows = json.loads(_http_get(url).decode("utf-8") or "[]")
    stamps = [r[1] for r in rows[1:]] if rows else []
    if not stamps:
        raise SystemExit(
            f"앵커 {anchor} ±{_MAX_DISTANCE_DAYS}일 안에 멜론 주간 스냅샷이 없다. "
            "Wayback 커버리지는 주별 불균일하다 — 앵커를 옮기거나 다른 소스"
            "(D-005 정식 경로)를 검토하라."
        )
    def dist(ts: str) -> int:
        # CDX 타임스탬프는 날짜만 쓴다 — 시각·시간대는 거리 계산과 무관.
        return abs((date(int(ts[:4]), int(ts[4:6]), int(ts[6:8])) - anchor).days)
    best = min(stamps, key=dist)
    return best, dist(best)


def parse_chart(html: str, top: int) -> tuple[str, list[dict[str, Any]]]:
    """스냅샷 HTML → (주간 라벨, [{rank, artist, title}]).

    행은 문서 순서가 곧 순위다(멜론 주간 페이지는 톱100이 한 문서에 순서대로
    있다 — 2021-10-25 스냅샷 실측). 행 수가 top에 못 미치면 잘린 스냅샷이므로
    조용히 내지 않고 실패한다 — 잘린 코호트는 "전부 담겼다"로 읽힌다.
    """
    week_m = _WEEK_RE.search(html)
    if not week_m:
        raise SystemExit("주간 라벨(YYYY.MM.DD ~ YYYY.MM.DD)을 찾지 못했다 — 페이지 구조가 다르다")
    g = week_m.groups()
    week = f"{g[0]}-{g[1]}-{g[2]}~{g[3]}-{g[4]}-{g[5]}"
    rows = _ROW_RE.findall(html)
    if len(rows) < top:
        raise SystemExit(f"파싱된 행이 {len(rows)}건 — 톱{top}에 못 미친다(잘린 스냅샷?)")
    tracks = [
        {
            "artist": html_lib.unescape(a).strip(),
            "title": html_lib.unescape(t).strip(),
            "market": "KR",
            "platform": "melon-weekly",
            "rank": i,
        }
        for i, (t, a) in enumerate(rows[:top], 1)
    ]
    return week, tracks


def build_cohort(anchor: date, top: int) -> dict[str, Any]:
    stamp, days_off = nearest_snapshot(anchor)
    print(f"  snapshot {stamp} (앵커에서 {days_off}일)", file=sys.stderr)
    page_url = f"http://web.archive.org/web/{stamp}/https://www.melon.com/chart/week/index.htm"
    week, tracks = parse_chart(_http_get(page_url).decode("utf-8", errors="replace"), top)
    print(f"  chart week {week}: {len(tracks)} tracks", file=sys.stderr)
    return {
        "note": (
            "멜론 주간 톱100 동시대 KR 코호트 (Wayback 스냅샷 파생 · 사실 필드만 "
            "내부 저장 · 원문 재배포 금지). 앵커 날짜의 주가 아니라 **가장 가까운 "
            "스냅샷의 주**다 — chart_week와 anchor_date의 거리를 볼 것. "
            "platform=melon-weekly."
        ),
        "anchor_date": anchor.isoformat(),
        "snapshot_timestamp": stamp,
        "snapshot_distance_days": days_off,
        "chart_week": week,
        "tracks": tracks,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="melon_wayback_ingest",
        description="Wayback 멜론 주간 차트 → 동시대 KR 코호트 (파생 사실만).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cohort", help="앵커에 가장 가까운 주간 톱N을 코호트 형태로")
    c.add_argument("anchor", help="앵커 날짜 YYYY-MM-DD (US 코호트 주차와 맞출 것)")
    c.add_argument("--top", type=int, default=100, help="상위 N (기본 100)")
    c.add_argument("-o", "--out", required=True)
    args = ap.parse_args(argv)

    payload = build_cohort(date.fromisoformat(args.anchor), args.top)
    Path(args.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
