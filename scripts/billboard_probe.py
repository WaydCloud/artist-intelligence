"""Billboard Hot 100 이력 소스 3자 대조 스모크 (D-035 ②).

채택 후보는 GitHub `mhollingshead/billboard-hot-100`(주간 전체 100위·1958~).
채택 전제는 **사실 필드(순위·주차)만 내부 파생 저장·원문 재배포 금지**이고,
"3자 대조 스모크 후 사용"이 조건이다. 이 스크립트가 그 스모크다.

대조 설계 — 두 층을 따로 재는 이유는 두 소스의 해상도가 다르기 때문이다:

  * **폭(breadth) — Wikipedia**: 연도별 "number ones" 문서는 **1위만** 준다.
    대신 한 해 52주를 통째로 훑을 수 있어 *넓게* 잰다. CC 라이선스·독립 편집.
  * **깊이(depth) — acharts.co**: 주간 **톱100 전체**를 준다. 비공식 미러라
    소스로는 2선이지만, 순위 100칸을 칸별로 맞춰볼 수 있는 유일한 무료 경로다.

두 층이 다른 것을 잰다는 점이 중요하다: 폭 층이 통과해도 2~100위는 검증되지
않았고, 깊이 층이 통과해도 그건 표본 주차에 한정된다. 리포트는 둘을 합산하지
않는다.

불일치는 **순위 오류**와 **표기 차이**(featuring 표기·리믹스 접미·이형 표기)를
구분해 센다. 표기 차이를 오류로 세면 미러 소스의 관용 차이가 데이터셋 결함으로
둔갑한다 — 이 스모크의 판정을 망치는 가장 쉬운 방법이다.

원문 재배포 금지 전제 준수: 받은 원문은 `--cache-dir`(기본 = 시스템 임시)에만
두고, 커밋 대상 산출(`-o`)에는 **집계 수치와 불일치 표본만** 남긴다.

Usage:

    # 기본 스모크 (폭 4개년 + 깊이 3주차)
    python scripts/billboard_probe.py -o docs/REVIEW-billboard-3way-smoke.json

    # 범위 조정
    python scripts/billboard_probe.py --years 2021 2023 --weeks 2021-10-02
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

_RAW = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main"
_WIKI = "https://en.wikipedia.org/w/api.php"
_ACHARTS = "https://acharts.co/us_singles_top_100"
_UA = "artist-intelligence-research/1.0 (chart-source cross-check; contact: repo owner)"

# 기본 표본 — 케이스북 사례 시기를 가로지르게 고른다(단일 시대 오버핏 방지).
#   2013 드릴 유입기 · 2018 라틴/뭄바톤 확산기 · 2021 저지클럽 태동기 · 2023 확정기
_DEFAULT_YEARS = (2013, 2018, 2021, 2023)
# 깊이 표본 — 2021-10-02는 genre-impulse 동시대 US 코호트 소급의 실제 목표 주차다.
_DEFAULT_WEEKS = ("2013-10-05", "2021-10-02", "2023-07-01")


# ─────────────────────────────────────────────────────────────── fetch


def _get(url: str, cache_dir: Path, *, ttl_days: int = 30, pause: float = 0.3) -> str:
    """GET with an on-disk cache. 캐시는 원문 보관소이며 커밋 대상이 아니다."""
    key = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[-150:]
    path = cache_dir / key
    if path.exists():
        age = time.time() - path.stat().st_mtime
        if age < ttl_days * 86400:
            return path.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # trusted hosts only
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise LookupError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise LookupError(f"network error for {url}: {exc.reason}") from exc
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    time.sleep(pause)  # 소스에 부담 주지 않는다 (조사 목적 소량 열람)
    return body


# ─────────────────────────────────────────────────── normalize / compare

_FEAT = re.compile(
    r"\b(feat(?:uring)?|ft|with|x|vs|and|&|\+|,)\b|[&+,]",
    re.IGNORECASE,
)
_PARENS = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_STOP = {"the", "a", "an"}


def _ascii_fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def norm_title(s: str, *, strip_parens: bool = False) -> str:
    """제목 비교 키. `strip_parens`는 리믹스/버전 접미 차이를 흡수하는 관대 모드.

    `*`(검열 마스킹)는 자리표시자로 살려 둔다 — 없애면 `s**t`가 `st`가 돼
    어떤 원문과도 안 맞는다. 대조는 `titles_agree`가 와일드카드로 처리한다.
    """
    s = _ascii_fold(html.unescape(s)).lower()
    if strip_parens:
        s = _PARENS.sub(" ", s)
    s = s.replace("&", " and ")  # "Safe & Sound" ↔ "Safe And Sound"
    s = re.sub(r"[^a-z0-9*]+", " ", s)
    return " ".join(s.split())


def titles_agree(a: str, b: str, *, strip_parens: bool = False) -> bool:
    """제목 동일성. 한쪽이 검열 마스킹(`*`)이면 마스크를 와일드카드로 맞춘다."""
    na, nb = norm_title(a, strip_parens=strip_parens), norm_title(b, strip_parens=strip_parens)
    if na == nb:
        return True
    masked, plain = (na, nb) if "*" in na else (nb, na)
    if "*" not in masked or "*" in plain:
        return False
    pattern = "".join("[a-z0-9]" if c == "*" else re.escape(c) for c in masked)
    return re.fullmatch(pattern, plain) is not None


def artist_tokens(s: str) -> set[str]:
    """아티스트 표기를 토큰 집합으로. 소스마다 featuring 표기가 달라 집합으로 비교한다."""
    s = _ascii_fold(html.unescape(s)).lower()
    s = _PARENS.sub(" ", s)
    s = _FEAT.sub(" ", s)
    toks = {t for t in re.split(r"[^a-z0-9]+", s) if t and t not in _STOP}
    return toks


def artist_agrees(a: str, b: str) -> bool:
    """주 아티스트가 같은가. 한쪽이 피처링을 접었어도 통과하도록 포함관계를 본다."""
    ta, tb = artist_tokens(a), artist_tokens(b)
    if not ta or not tb:
        return False
    if ta <= tb or tb <= ta:
        return True
    inter = len(ta & tb)
    return inter / min(len(ta), len(tb)) >= 0.5


# ─────────────────────────────────────────────────────── source: dataset


def dataset_valid_dates(cache_dir: Path) -> list[str]:
    return json.loads(_get(f"{_RAW}/valid_dates.json", cache_dir))


def dataset_chart(chart_date: str, cache_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads(_get(f"{_RAW}/date/{chart_date}.json", cache_dir, pause=0.05))
    data = payload.get("data", [])
    if not isinstance(data, list):
        # 원격 페이로드 형태 이상은 호출부에서 "가져오기 실패"로 다룬다(TRY004 예외).
        raise LookupError(f"dataset {chart_date}: 'data' is not a list")  # noqa: TRY004
    return data


# ────────────────────────────────────────────────────── source: wikipedia

_WIKILINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]")
_REF = re.compile(r"<ref.*?(?:/>|</ref>)", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ROWSPAN = re.compile(r"rowspan\s*=\s*\"?(\d+)\"?", re.IGNORECASE)


def _wiki_clean(cell: str) -> str:
    cell = _REF.sub("", cell)
    cell = _HTML_COMMENT.sub("", cell)
    cell = _WIKILINK.sub(r"\1", cell)
    cell = re.sub(r"\{\{[^{}]*\}\}", "", cell)
    cell = cell.replace("''", "").replace('"', "").replace("&nbsp;", " ")
    return " ".join(cell.split()).strip()


def _cell_payload(cell: str) -> tuple[str, int, bool]:
    """`| style=... | value` 형태에서 (값, rowspan, 헤더칸 여부)를 뽑는다."""
    span = 1
    is_header = False
    if "|" in cell:
        head, _, tail = cell.partition("|")
        # 속성부에만 '=' 가 있고 위키링크 '[[' 가 없어야 진짜 속성부다.
        if "=" in head and "[[" not in head and len(head) < 120:
            m = _ROWSPAN.search(head)
            if m:
                span = int(m.group(1))
            is_header = 'scope="row"' in head
            cell = tail
    return _wiki_clean(cell), span, is_header


# 셀은 줄머리 `|`/`!` 로 시작하고, 이어지는 비-셀 줄(ref 줄바꿈 등)까지 한 셀이다.
_CELL = re.compile(r"(?m)^[|!](?![-}])(.*(?:\n(?![|!]).*)*)")

# 표의 열 구성: 0=No. · 1=Issue date · 2=Song · 3=Artist · 4=Ref
_COL_DATE, _COL_SONG, _COL_ARTIST = 1, 2, 3
_N_COLS = 5


def _expand_rowspans(rows: list[str]) -> list[list[str]]:
    """rowspan을 열 단위로 전개한다.

    연속 1위 주차는 곡·아티스트 칸이 rowspan으로 접혀 **해당 행에서 통째로 빠진다**.
    행 안의 셀 개수만 보고 판단하면(예: "셀이 2개 미만이면 전부 이어받기") 곡은
    새로 바뀌었는데 아티스트만 접힌 행에서 곡까지 이전 값으로 덮어쓴다 —
    2021-07-24(Permission to Dance ← Butter)가 정확히 그 함정이었다.
    """
    carry: dict[int, tuple[str, int]] = {}  # col -> (value, 남은 행 수)
    table: list[list[str]] = []
    for row in rows:
        present = [_cell_payload(c) for c in _CELL.findall(row)]
        cursor = 0
        line = [""] * _N_COLS
        for col in range(_N_COLS):
            held = carry.get(col)
            if held and held[1] > 0:
                line[col] = held[0]
                carry[col] = (held[0], held[1] - 1)
                continue
            if cursor >= len(present):
                continue
            value, span, is_header = present[cursor]
            # 날짜 칸은 헤더(`! scope="row"`)다 — 앞 열이 비어 어긋나면 여기서 맞춘다.
            if col < _COL_DATE and is_header:
                continue
            cursor += 1
            line[col] = value
            if span > 1:
                carry[col] = (value, span - 1)
        table.append(line)
    return table


def wiki_number_ones(year: int, cache_dir: Path) -> dict[str, dict[str, str]]:
    """연도 문서 → {chart_date: {song, artist}}. rowspan(연속 1위)을 펼친다."""
    title = f"List of Billboard Hot 100 number ones of {year}"
    url = f"{_WIKI}?" + urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "formatversion": "2",
    })
    payload = json.loads(_get(url, cache_dir, pause=0.5))
    if "error" in payload:
        raise LookupError(f"wikipedia {year}: {payload['error'].get('info')}")
    text: str = payload["parse"]["wikitext"]

    # 1위 표는 'Issue date' 헤더를 가진 wikitable 하나뿐이다.
    table = None
    for block in re.findall(r"\{\|.*?\n\|\}", text, re.DOTALL):
        if "Issue date" in block and "scope=\"row\"" in block:
            table = block
            break
    if table is None:
        raise LookupError(f"wikipedia {year}: issue-date table not found")

    # 첫 조각은 표 헤더(`{| ... ! 열 이름`)라 버린다.
    rows = [r for r in table.split("\n|-")[1:] if r.strip()]
    out: dict[str, dict[str, str]] = {}
    for line in _expand_rowspans(rows):
        raw_date, song, artist = line[_COL_DATE], line[_COL_SONG], line[_COL_ARTIST]
        if not (raw_date and song and artist):
            continue
        try:
            # 차트 날짜는 시간대 없는 역일(civil date)이다 — tz 부여가 오히려 틀린다.
            chart_date = datetime.strptime(f"{raw_date} {year}", "%B %d %Y").date()  # noqa: DTZ007
        except ValueError:
            continue
        out[chart_date.isoformat()] = {"song": song, "artist": artist}
    return out


# ──────────────────────────────────────────────────────── source: acharts

_ACH_ROW = re.compile(r'<tr itemprop="itemListElement".*?</tr>', re.DOTALL)
_ACH_POS = re.compile(r'<span itemprop="position">(\d+)</span>')
_ACH_NAME = re.compile(r'<span itemprop="name">(.*?)</span>', re.DOTALL)
_ACH_STATS = re.compile(
    r"peak position:</i>\s*(\d+)\s*(?:&#8211;|–|-)\s*<i>total weeks:</i>\s*(\d+)"
)
_ACH_TITLE_DATE = re.compile(r"<title>[^(]*\(([^)]+)\)")


def _acharts_week_page(year: int, week: int, cache_dir: Path) -> tuple[date, str]:
    body = _get(f"{_ACHARTS}/{year}/{week}", cache_dir, pause=1.0)
    m = _ACH_TITLE_DATE.search(body)
    if not m:
        raise LookupError(f"acharts {year}/{week}: chart date not in <title>")
    raw = " ".join(m.group(1).split())
    return datetime.strptime(raw, "%B %d, %Y").date(), body  # noqa: DTZ007 — 역일


def acharts_chart(chart_date: str, cache_dir: Path) -> list[dict[str, Any]]:
    """acharts는 (연도, 주차) 인덱스다 — 목표 날짜에 맞을 때까지 주차를 보정한다."""
    target = date.fromisoformat(chart_date)
    year, week = target.year, target.isocalendar().week
    seen: set[tuple[int, int]] = set()
    body = ""
    for _ in range(4):
        if (year, week) in seen:
            raise LookupError(f"acharts: week index oscillated for {chart_date}")
        seen.add((year, week))
        try:
            got, body = _acharts_week_page(year, week, cache_dir)
        except LookupError:
            week += 1
            continue
        if got == target:
            break
        shift = round((target - got).days / 7)
        if shift == 0:
            raise LookupError(f"acharts: nearest week is {got}, no page for {chart_date}")
        week += shift
        if week < 1:
            year, week = year - 1, week + 52
        elif week > 53:
            year, week = year + 1, week - 52
    else:
        raise LookupError(f"acharts: could not resolve week index for {chart_date}")

    rows: list[dict[str, Any]] = []
    for block in _ACH_ROW.findall(body):
        pos = _ACH_POS.search(block)
        names = _ACH_NAME.findall(block)
        if not pos or not names:
            continue
        stats = _ACH_STATS.search(block)
        rows.append({
            "this_week": int(pos.group(1)),
            "song": html.unescape(names[0]).strip(),
            "artist": " and ".join(html.unescape(n).strip() for n in names[1:]),
            "peak_position": int(stats.group(1)) if stats else None,
            "weeks_on_chart": int(stats.group(2)) if stats else None,
        })
    return rows


# ───────────────────────────────────────────────────────────── compare


def _classify(a_song: str, a_art: str, b_song: str, b_art: str) -> str:
    """일치 등급: exact | notation(표기 차이) | mismatch(사실 불일치 의심)."""
    strict = titles_agree(a_song, b_song)
    if strict and artist_agrees(a_art, b_art):
        return "exact"
    if strict or titles_agree(a_song, b_song, strip_parens=True):
        # 부제/버전 접미나 아티스트 표기만 다른 경우 — 순위 사실은 같다.
        return "notation"
    return "mismatch"


def breadth_check(years: list[int], cache_dir: Path) -> dict[str, Any]:
    """폭 층 — 위키피디아 1위 목록 전주차 대 데이터셋 1위."""
    valid = set(dataset_valid_dates(cache_dir))
    tally = {"exact": 0, "notation": 0, "mismatch": 0}
    missing_dates: list[str] = []
    examples: list[dict[str, str]] = []
    per_year: dict[str, dict[str, int]] = {}

    for year in years:
        wiki = wiki_number_ones(year, cache_dir)
        y_tally = {"exact": 0, "notation": 0, "mismatch": 0}
        for chart_date in sorted(wiki):
            if chart_date not in valid:
                missing_dates.append(chart_date)
                continue
            top = dataset_chart(chart_date, cache_dir)
            row = next((r for r in top if r.get("this_week") == 1), None)
            if row is None:
                missing_dates.append(chart_date)
                continue
            grade = _classify(
                row.get("song", ""), row.get("artist", ""),
                wiki[chart_date]["song"], wiki[chart_date]["artist"],
            )
            tally[grade] += 1
            y_tally[grade] += 1
            if grade != "exact" and len(examples) < 25:
                examples.append({
                    "date": chart_date, "grade": grade,
                    "dataset": f"{row.get('song')} — {row.get('artist')}",
                    "wikipedia": f"{wiki[chart_date]['song']} — {wiki[chart_date]['artist']}",
                })
        per_year[str(year)] = y_tally
        print(f"  wiki {year}: {y_tally}", file=sys.stderr)

    total = sum(tally.values())
    return {
        "layer": "breadth (Wikipedia #1 only)",
        "years": years,
        "compared": total,
        "tally": tally,
        "agree_rate": round((tally["exact"] + tally["notation"]) / total, 4) if total else None,
        "exact_rate": round(tally["exact"] / total, 4) if total else None,
        "per_year": per_year,
        "dates_absent_from_dataset": missing_dates,
        "examples": examples,
    }


def depth_check(weeks: list[str], cache_dir: Path) -> dict[str, Any]:
    """깊이 층 — acharts 주간 톱100 전체 대 데이터셋 같은 주차."""
    per_week: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

    for chart_date in weeks:
        ds = {r["this_week"]: r for r in dataset_chart(chart_date, cache_dir)}
        try:
            ac = {r["this_week"]: r for r in acharts_chart(chart_date, cache_dir)}
        except LookupError as exc:
            per_week.append({"date": chart_date, "error": str(exc)})
            print(f"  acharts {chart_date}: FAILED — {exc}", file=sys.stderr)
            continue

        tally = {"exact": 0, "notation": 0, "mismatch": 0}
        stat_checked = stat_agree = 0
        for rank in sorted(set(ds) | set(ac)):
            d, a = ds.get(rank), ac.get(rank)
            if not d or not a:
                tally["mismatch"] += 1
                continue
            grade = _classify(d.get("song", ""), d.get("artist", ""),
                              a.get("song", ""), a.get("artist", ""))
            tally[grade] += 1
            # 순위 외 사실 필드(피크·체류주)도 같이 잰다 — 우리가 쓸 필드이므로.
            if a.get("peak_position") is not None:
                stat_checked += 1
                if (d.get("peak_position") == a["peak_position"]
                        and d.get("weeks_on_chart") == a["weeks_on_chart"]):
                    stat_agree += 1
            if grade != "exact" and len(examples) < 30:
                examples.append({
                    "date": chart_date, "rank": rank, "grade": grade,
                    "dataset": f"{d.get('song')} — {d.get('artist')}",
                    "acharts": f"{a.get('song')} — {a.get('artist')}",
                })
        n = sum(tally.values())
        per_week.append({
            "date": chart_date,
            "ranks_compared": n,
            "tally": tally,
            "agree_rate": round((tally["exact"] + tally["notation"]) / n, 4) if n else None,
            "peak_weeks_checked": stat_checked,
            "peak_weeks_agree": stat_agree,
        })
        print(f"  acharts {chart_date}: {tally} · peak/weeks {stat_agree}/{stat_checked}",
              file=sys.stderr)

    ok = [w for w in per_week if "tally" in w]
    total = sum(w["ranks_compared"] for w in ok)
    agreed = sum(w["tally"]["exact"] + w["tally"]["notation"] for w in ok)
    return {
        "layer": "depth (acharts full top-100)",
        "weeks": weeks,
        "compared": total,
        "agree_rate": round(agreed / total, 4) if total else None,
        "per_week": per_week,
        "examples": examples,
    }


# ────────────────────────────────────────────── layer: self-consistency


def consistency_check(start: str, weeks: int, cache_dir: Path) -> dict[str, Any]:
    """자체 정합성 층 — 데이터셋이 스스로와 모순되지 않는가.

    외부 대조 두 층은 각각 한계가 있다(위키=1위만·acharts=자기 오류 있음).
    반면 이 층은 **우리가 실제로 쓸 필드 전부**(순위·직전주·피크·체류주)를
    100칸 × N주에 걸쳐 검사한다. 전사 오류·주차 밀림은 여기서 드러난다.

    검사 3종 (연속 주차 간):
      * `last_week` = 직전 주 그 곡의 `this_week`
      * `weeks_on_chart` = 직전 주 값 + 1
      * `peak_position` = min(직전 주 피크, 이번 주 순위) — 단조 비증가
    """
    valid = dataset_valid_dates(cache_dir)
    try:
        i0 = valid.index(start)
    except ValueError:
        raise LookupError(f"consistency: {start} is not a valid chart date") from None
    dates = valid[i0:i0 + weeks]

    counts = {"last_week": 0, "weeks_on_chart": 0, "peak_position": 0}
    checked = {"last_week": 0, "weeks_on_chart": 0, "peak_position": 0}
    examples: list[dict[str, Any]] = []
    prev: dict[str, dict[str, Any]] | None = None

    for chart_date in dates:
        cur = {}
        for row in dataset_chart(chart_date, cache_dir):
            cur[f"{norm_title(row.get('song', ''))}|{norm_title(row.get('artist', ''))}"] = row
        if prev is not None:
            for key, row in cur.items():
                before = prev.get(key)
                if before is None:
                    continue  # 신규 진입·재진입은 직전 주 근거가 없다
                probes = (
                    ("last_week", row.get("last_week"), before.get("this_week")),
                    ("weeks_on_chart", row.get("weeks_on_chart"),
                     (before.get("weeks_on_chart") or 0) + 1),
                    ("peak_position", row.get("peak_position"),
                     min(before.get("peak_position") or 101, row.get("this_week") or 101)),
                )
                for field, got, want in probes:
                    if got is None:
                        continue
                    checked[field] += 1
                    if got != want:
                        counts[field] += 1
                        if len(examples) < 20:
                            examples.append({
                                "date": chart_date, "rank": row.get("this_week"),
                                "entry": f"{row.get('song')} — {row.get('artist')}",
                                "field": field, "got": got, "expected": want,
                            })
        prev = cur

    total_checked = sum(checked.values())
    total_bad = sum(counts.values())
    print(f"  self-consistency {dates[0]}~{dates[-1]}: "
          f"{total_bad}/{total_checked} violations {counts}", file=sys.stderr)
    return {
        "layer": "self-consistency (dataset vs itself)",
        "span": {"from": dates[0], "to": dates[-1], "weeks": len(dates)},
        "checks_run": checked,
        "violations": counts,
        "violation_rate": round(total_bad / total_checked, 5) if total_checked else None,
        "examples": examples,
    }


# ─────────────────────────────────────────────────────────── coverage


def coverage(cache_dir: Path) -> dict[str, Any]:
    dates = dataset_valid_dates(cache_dir)
    parsed = sorted(date.fromisoformat(d) for d in dates)
    gaps = []
    for prev, cur in itertools.pairwise(parsed):
        delta = (cur - prev).days
        if delta != 7:
            gaps.append({"from": prev.isoformat(), "to": cur.isoformat(), "days": delta})
    return {
        "charts": len(parsed),
        "first": parsed[0].isoformat(),
        "last": parsed[-1].isoformat(),
        "non_weekly_steps": len(gaps),
        "non_weekly_examples": gaps[:10],
    }


# ─────────────────────────────────────────────────────────── selftest


def selftest() -> int:
    """네트워크 0 회귀 테스트 — 대조 규칙이 조용히 바뀌면 판정이 통째로 뒤집힌다."""
    failures: list[str] = []
    ran = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal ran
        ran += 1
        print(f"  {'OK  ' if ok else 'FAIL'} {name}{f'  ({detail})' if detail else ''}")
        if not ok:
            failures.append(name)

    # 표기 관습 4종 — 전부 실측에서 나온 실제 차이다(REVIEW-billboard-3way-smoke §4).
    check("앰퍼샌드 등가", titles_agree("Safe & Sound", "Safe And Sound"))
    check("검열 마스킹 와일드카드", titles_agree("Thot Shit", "Thot S**t"))
    check("괄호 부제(관대 모드)",
          titles_agree("Dance The Night (from Barbie The Album)", "Dance The Night",
                       strip_parens=True))
    check("대괄호 부제(관대 모드)",
          titles_agree("Is It Over Now? (Taylor's Version) [From The Vault]",
                       "Is It Over Now?", strip_parens=True))
    # 관대 모드를 켜지 않으면 부제는 흡수되지 않아야 한다 — 아니면 엄격층이 무의미해진다.
    check("엄격 모드는 부제를 흡수하지 않는다",
          not titles_agree("Dance The Night (from Barbie The Album)", "Dance The Night"))
    # 마스킹이 아무거나 통과시키면 안 된다.
    check("마스킹은 길이·문자를 맞춰야 한다", not titles_agree("Thot Shirt", "Thot S**t"))
    check("서로 다른 곡은 안 맞는다", not titles_agree("Hurricane", "Hurricance 2.0"))

    check("featuring 표기 차이 흡수",
          artist_agrees("Drake Featuring 21 Savage & Project Pat",
                        "Drake and 21 Savage and Project Pat"))
    check("피처링 접힘 흡수", artist_agrees("Doja Cat Featuring SZA", "Doja Cat"))
    check("다른 아티스트는 안 맞는다",
          not artist_agrees("Kanye West", "30 Seconds To Mars"))

    # 등급 분류 — 실측 3사례 그대로.
    check("acharts 엔티티 오류는 mismatch",
          _classify("Hurricane", "Kanye West",
                    "Hurricance 2.0", "30 Seconds To Mars and Kanye West") == "mismatch")
    check("부제 차이는 notation",
          _classify("Dance The Night (from Barbie The Album)", "Dua Lipa",
                    "Dance The Night", "Dua Lipa") == "notation")
    check("완전 일치는 exact",
          _classify("Stay", "The Kid LAROI & Justin Bieber",
                    "Stay", "Kid Laroi and Justin Bieber") == "exact")

    # rowspan 전개 — 연속 1위 주차에서 곡만 바뀌는 행(2021-07-24 함정)을 재현한다.
    rows = [
        '\n| 1125\n! scope="row" | July 17\n| rowspan=2 | "Butter"\n| rowspan=4 | BTS\n|<ref/>',
        '\n! scope="row" | July 24\n|<ref/>',
        '\n| 1126\n! scope="row" | July 31\n| "Permission to Dance"\n|<ref/>',
        '\n! scope="row" | August 7\n| "Butter"\n|<ref/>',
    ]
    got = [(r[_COL_DATE], r[_COL_SONG], r[_COL_ARTIST]) for r in _expand_rowspans(rows)]
    want = [
        ("July 17", "Butter", "BTS"),
        ("July 24", "Butter", "BTS"),
        ("July 31", "Permission to Dance", "BTS"),
        ("August 7", "Butter", "BTS"),
    ]
    check("rowspan 열 단위 전개", got == want, f"{got}")

    print(f"\nselftest: {ran - len(failures)}/{ran} passed")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="billboard_probe",
        description="Billboard Hot 100 이력 소스 3자 대조 스모크 (D-035 ②).",
    )
    ap.add_argument("--selftest", action="store_true",
                    help="대조 규칙 회귀 테스트 (네트워크 0)")
    ap.add_argument("--years", nargs="*", type=int, default=list(_DEFAULT_YEARS),
                    help="폭 층 대조 연도 (Wikipedia 1위 목록)")
    ap.add_argument("--weeks", nargs="*", default=list(_DEFAULT_WEEKS),
                    help="깊이 층 대조 주차 YYYY-MM-DD (acharts 톱100)")
    ap.add_argument("--consistency-from", default="2021-01-02",
                    help="자체 정합성 층 시작 주차 (기본 2021-01-02)")
    ap.add_argument("--consistency-weeks", type=int, default=52,
                    help="자체 정합성 층 주차 수 (기본 52)")
    ap.add_argument("--cache-dir", default=None,
                    help="원문 캐시 위치 (기본: 시스템 임시). 커밋 금지 — 원문 재배포 전제 준수")
    ap.add_argument("-o", "--out", help="집계 결과 JSON 경로 (수치·불일치 표본만)")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    cache_dir = Path(args.cache_dir) if args.cache_dir else (
        Path(__import__("tempfile").gettempdir()) / "billboard_probe_cache"
    )
    print(f"cache: {cache_dir}", file=sys.stderr)

    try:
        cov = coverage(cache_dir)
        print(f"coverage: {cov['charts']} charts · {cov['first']} ~ {cov['last']} "
              f"· non-weekly steps {cov['non_weekly_steps']}", file=sys.stderr)
        print("breadth layer (Wikipedia):", file=sys.stderr)
        breadth = breadth_check(args.years, cache_dir)
        print("depth layer (acharts):", file=sys.stderr)
        depth = depth_check(args.weeks, cache_dir)
        print("self-consistency layer (dataset internal):", file=sys.stderr)
        selfc = consistency_check(args.consistency_from, args.consistency_weeks, cache_dir)
    except LookupError as exc:
        print(f"probe failed: {exc}", file=sys.stderr)
        return 1

    report = {
        "probe": "billboard-hot-100 3-way cross-check",
        "decision": "D-035 ②",
        "source_under_test": "github.com/mhollingshead/billboard-hot-100",
        "license_note": "LICENSE 부재 확인 — 사실 필드만 내부 파생 저장·원문 재배포 금지",
        "coverage": cov,
        "breadth": breadth,
        "depth": depth,
        "self_consistency": selfc,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
