"""스마트 태그 할당기(D-015) — 고정 일 예산 내에서 오늘 수집할 유료 소셜 태그를 고른다.

경계(§0): 워치리스트(누굴 팔로우)는 사용자 소유 — 이 알고리즘은 리스트를 편집하지 않고
**예산 배분**(어느 태그를 오늘 걷을지)만 결정한다. 기준 원장: docs/EXPERIMENT-forward-leading.md
(가중치·K = config 노출, 값은 사용자 소유. AGENTS §2.1).

선정 순서(결정적):
  1) 상시: genre_hashtags + watchlist `pin: true` acts의 태그 — 매일 무조건.
  2) 강제: 마지막 수집 후 `max_staleness_days` 이상 경과한 태그(오래된 순) — 기아 방지.
  3) 점수: 남은 슬롯을 우선순위 점수 내림차순으로 채움.
     score = w_stale·(경과/K, cap 1) + w_chart_entry·(차트 신규 진입 창 내 온셋)
           + w_yt_velocity·(velocity/max) + w_yield·(직전 수집 게시수/캡) + w_new·(미수집)
  무료 신호만 소비(chart_series·yt_series·social/ 파일명+게시수) — 네트워크 0, 결정적.

수집 이력 = data/live/social/<date>_<tag>.json 파일명에서 도출(별도 상태 파일 없음).
격리(quarantine)된 스냅샷은 이력에서 빠짐 → 재수집 대상(의도된 동작: 데이터가 없으니까).
결측≠무신호: 태그가 안 걷힌 날은 plan 파일(data/live/plans/)이 증거 — 온셋 해상도는
±순환주기만큼 거칠어진다(런북에 한계 명시).

    python scripts/tag_allocator.py plan --config config/collect.json \
        --watchlist packages/entity-master/watchlist.json --live data/live \
        --date 2026-07-20 -o data/live/plans/plan_2026-07-20.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date as _date
from pathlib import Path
from typing import Any

_SNAP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)\.json$")

_DEFAULTS: dict[str, float] = {
    "max_staleness_days": 5,
    "chart_entry_window_days": 2,
    "w_stale": 1.0,
    "w_chart_entry": 3.0,
    "w_yt_velocity": 1.0,
    "w_yield": 1.0,
    "w_new": 2.0,
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_history(social_dir: Path) -> dict[str, str]:
    """태그 → 마지막 수집일(파일명 도출). 격리 파일은 안 보임 = 미수집 취급."""
    last: dict[str, str] = {}
    if not social_dir.is_dir():
        return last
    for f in sorted(social_dir.glob("*.json")):
        m = _SNAP_RE.match(f.name)
        if m and (m.group(2) not in last or m.group(1) > last[m.group(2)]):
            last[m.group(2)] = m.group(1)
    return last


def _last_yield(social_dir: Path, tag: str, last_date: str | None) -> int:
    if not last_date:
        return 0
    f = social_dir / f"{last_date}_{tag}.json"
    try:
        doc = _load_json(f)
        recs = doc.get("records")
        return len(recs) if isinstance(recs, list) else 0
    except (OSError, ValueError):
        return 0


def _recent_chart_entries(chart_series: dict[str, Any], window_days: int) -> set[str]:
    """자기 일자축 마지막 window_days 내에 첫 유효 순위(온셋)가 있는 act 키들."""
    dates: list[str] = chart_series.get("dates") or []
    if not dates:
        return set()
    recent = set(dates[-window_days:])
    hits: set[str] = set()
    series: dict[str, list[Any]] = chart_series.get("series") or {}
    for key, vals in series.items():
        for d, v in zip(dates, vals):
            if isinstance(v, (int, float)):
                if d in recent:
                    hits.add(key)
                break  # 첫 유효값 = 온셋만 본다
    return hits


def _yt_velocity(yt_series: dict[str, Any]) -> dict[str, float]:
    """act 키 → 최신 velocity (views/일)."""
    out: dict[str, float] = {}
    series: dict[str, list[Any]] = yt_series.get("series") or {}
    for key, vals in series.items():
        nums = [float(v) for v in vals if isinstance(v, (int, float))]
        if nums:
            out[key] = nums[-1]
    return out


def _days_between(a: str, b: str) -> int:
    return (_date.fromisoformat(b) - _date.fromisoformat(a)).days


def plan(args: argparse.Namespace) -> int:
    cfg = _load_json(Path(args.config))
    wl = _load_json(Path(args.watchlist))
    live = Path(args.live)
    today: str = args.date

    raw_knobs: dict[str, Any] = {**_DEFAULTS, **(cfg.get("allocator") or {})}
    knobs: dict[str, float] = {k: float(raw_knobs[k]) for k in _DEFAULTS}
    per_tag_usd = float(cfg.get("per_tag_max_usd", 0.25))
    per_tag_items = int(cfg.get("per_tag_max_items", 100))
    budget = float(cfg.get("daily_budget_usd", 3.0))
    slots = int(budget / per_tag_usd + 1e-9)
    k_stale = max(1, int(knobs["max_staleness_days"]))

    # 태그 유니버스: genre(상시) + watchlist acts (워치리스트 순서, 중복 제거)
    genre: list[str] = [t for t in (cfg.get("genre_hashtags") or []) if t]
    tag_acts: dict[str, list[str]] = {}  # tag → 이 태그를 쓰는 act 키들
    pinned: set[str] = set()
    ordered: list[str] = list(genre)
    for a in wl.get("artists") or []:
        for t in a.get("hashtags") or []:
            if not t:
                continue
            if t not in tag_acts and t not in genre:
                ordered.append(t)
            tag_acts.setdefault(t, []).append(str(a.get("key")))
            if a.get("pin") is True:
                pinned.add(t)

    history = _fetch_history(live / "social")
    chart_entries: set[str] = set()
    velocity: dict[str, float] = {}
    try:
        chart_entries = _recent_chart_entries(
            _load_json(live / "chart_series.json"), int(knobs["chart_entry_window_days"])
        )
    except (OSError, ValueError):
        pass
    try:
        velocity = _yt_velocity(_load_json(live / "yt_series.json"))
    except (OSError, ValueError):
        pass
    v_max = max(velocity.values(), default=0.0) or 1.0

    detail: list[dict[str, Any]] = []
    for tag in ordered:
        acts = tag_acts.get(tag, [])
        last = history.get(tag)
        days = _days_between(last, today) if last else None
        stale = 1.0 if days is None else min(days / k_stale, 1.0)
        chart_hit = any(a in chart_entries for a in acts)
        yt = max((velocity.get(a, 0.0) for a in acts), default=0.0) / v_max
        yld = min(_last_yield(live / "social", tag, last) / max(per_tag_items, 1), 1.0)
        score = round(
            knobs["w_stale"] * stale
            + knobs["w_chart_entry"] * (1.0 if chart_hit else 0.0)
            + knobs["w_yt_velocity"] * yt
            + knobs["w_yield"] * yld
            + knobs["w_new"] * (1.0 if last is None else 0.0),
            4,
        )
        detail.append(
            {
                "tag": tag,
                "acts": acts,
                "pin": tag in genre or tag in pinned,
                "days_since": days,
                "chart_entry": chart_hit,
                "yt_norm": round(yt, 4),
                "yield_norm": round(yld, 4),
                "score": score,
            }
        )

    by_tag = {d["tag"]: d for d in detail}
    chosen: list[str] = []

    def _take(tags: list[str], reason: str) -> None:
        for t in tags:
            if len(chosen) >= slots:
                return
            if t not in chosen:
                by_tag[t]["reason"] = reason
                chosen.append(t)

    _take([d["tag"] for d in detail if d["pin"]], "pin")
    forced = [
        d for d in detail if not d["pin"] and d["days_since"] is not None and d["days_since"] >= k_stale
    ]
    forced.sort(key=lambda d: (-int(d["days_since"]), str(d["tag"])))
    _take([d["tag"] for d in forced], "stale")
    rest = sorted(
        (d for d in detail if d["tag"] not in chosen),
        key=lambda d: (-float(d["score"]), str(d["tag"])),
    )
    _take([d["tag"] for d in rest], "score")

    skipped = [d["tag"] for d in detail if d["tag"] not in chosen]
    out = {
        "date": today,
        "slots": slots,
        "per_tag_max_usd": per_tag_usd,
        "budget_usd": budget,
        "knobs": knobs,
        "tags": chosen,
        "detail": detail,
        "skipped": skipped,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_pin = sum(1 for t in chosen if by_tag[t].get("reason") == "pin")
    n_stale = sum(1 for t in chosen if by_tag[t].get("reason") == "stale")
    n_score = sum(1 for t in chosen if by_tag[t].get("reason") == "score")
    # ASCII only: ps1 log line (PS 5.1 console encoding)
    print(
        f"plan {len(chosen)}/{len(ordered)} tags | slots={slots} pin={n_pin} "
        f"stale={n_stale} score={n_score} skipped={len(skipped)} -> {out_path.as_posix()}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="daily paid-tag budget allocator (D-015)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="emit today's tag plan within daily budget")
    p.add_argument("--config", required=True)
    p.add_argument("--watchlist", required=True)
    p.add_argument("--live", required=True, help="data/live root (reads social/, chart_series, yt_series)")
    p.add_argument("--date", required=True, help="plan date YYYY-MM-DD (explicit for determinism)")
    p.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    return plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
