"""A2 본편 — 케이스 곡의 축별 백분위를 동시대 코호트 위에서 잰다 (genre-impulse Phase A2).

A2.1(CASEBOOK §A2.1)이 하이퍼팝 정답지 5곡을 **2026-07 라이브 차트** 근사 모집단
위에서 쟀다면, 이 스크립트는 그 근사를 걷어낸다: 케이스 곡(발원지 원형 + 한국
수용형)을 **동시대(2021-10 앵커) US·KR 코호트** 분포 위에 놓고 축별 백분위를
계산한다. 산출은 원형↔한국 서명 비교(무엇이 유지되고 무엇이 바뀌나)와 검출
규칙 후보 도출(genre-impulse RULES §2.2 해제 조건)의 **기계적 재료**다 —
어떤 축이 서명인지의 판단은 이 스크립트가 아니라 케이스북 기록이 한다.

백분위 관례는 A2.1과 같다: P = 100 · count(cohort ≤ x) / n. 극단 표기(≤20 / ≥80)는
관습값이며 CLI로 노출한다(AGENTS §2.1 — 하중받는 기준이 되는 순간 도메인
소유자가 재조정한다).

두 프레임을 모두 기록한다:
  * KR 프레임 — 데일리 모니터가 실제로 재는 프레임(당일 KR 차트 코호트 백분위).
    규칙 후보의 임계는 이 프레임에서 읽는다.
  * US 프레임 — 원형이 자기 시장에서 극단이었는지(원형의 서명이 그 시장의
    관습인지 이탈인지)를 가른다.
프레임을 하나로 합치면 코호트 차이와 곡 차이가 섞인다 — 그래서 안 합친다.

Usage:

    python scripts/a2_signature_compare.py \
        --cases data/research/genre-impulse/signature_v4_merged.json \
        --cohort-us data/research/genre-impulse/cohort_us_features_2021-10-02.json \
        --cohort-kr data/research/genre-impulse/cohort_kr_features_2021-10-02.json \
        -o data/research/genre-impulse/a2_signature_compare.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 파생 축(organic_ratio·kick_density 등)은 스냅샷에 저장되지 않고 소비 시점에
# 계산된다(derive_all — 한 곳 파생 원칙). 백분위는 genre-impulse의 `_percentile`을
# import해 쓴다 — 두 벌이 되면 이 조사가 잰 위치와 모니터가 재는 위치가 갈라진다
# (stem_gate.py와 같은 규율, AGENTS §1).
_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "modules" / "sonic-profile" / "src"))
sys.path.insert(0, str(_root / "modules" / "genre-impulse" / "src"))
from genre_impulse.cli import _percentile  # type: ignore[import-not-found]
from sonic_profile.derived import derive_all  # type: ignore[import-not-found]

# 백분위 대상에서 빼는 축: 측정 메타(패치 수)와 프리뷰 길이 — 곡의 성질이 아니다.
_EXCLUDE_AXES = {"tag_patches", "duration_s"}
# 분포 비교가 성립하는 최소 코호트 표본 (관습값 — 30 미만이면 백분위가 계단이 된다)
_MIN_COHORT_N_DEFAULT = 30


def _load_records(
    path: Path, *, min_prob: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    records = doc.get("records") or []
    for r in records:
        f = r.get("features")
        if f:
            f.update(derive_all(f, min_prob=min_prob))
    return records, doc.get("provenance") or {}


def _scalar_axes(records: list[dict[str, Any]]) -> list[str]:
    axes: set[str] = set()
    for r in records:
        for k, v in (r.get("features") or {}).items():
            if k not in _EXCLUDE_AXES and isinstance(v, (int, float)) and not isinstance(v, bool):
                axes.add(k)
    return sorted(axes)


def _cohort_values(records: list[dict[str, Any]], axes: list[str]) -> dict[str, list[float]]:
    vals: dict[str, list[float]] = {a: [] for a in axes}
    for r in records:
        f = r.get("features") or {}
        for a in axes:
            v = f.get(a)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals[a].append(float(v))
    for a in axes:
        vals[a].sort()
    return vals


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    m = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return round(m, 1)


def _rhythm_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in records:
        f = r.get("features") or {}
        label = f.get("rhythm_assigned") or ("(측정 없음)" if not f else "(배정 없음)")
        out[label] = out.get(label, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def compare(
    cases: list[dict[str, Any]],
    cohorts: dict[str, dict[str, list[float]]],
    axes: list[str],
    min_cohort_n: int,
    low_pct: float,
    high_pct: float,
) -> dict[str, Any]:
    by_case: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for r in cases:
        slug = r.get("chart_market") or "(케이스 미상)"
        role = r.get("chart_platform") or "(역할 미상)"
        by_case.setdefault(slug, {}).setdefault(role, []).append(r)

    out_cases: dict[str, Any] = {}
    for slug, roles in sorted(by_case.items()):
        role_out: dict[str, Any] = {}
        for role, recs in sorted(roles.items()):
            tracks = []
            per_axis: dict[str, dict[str, list[float]]] = {a: {"us": [], "kr": []} for a in axes}
            for r in recs:
                f = r.get("features") or {}
                row: dict[str, Any] = {
                    "artist": r.get("artist") or r.get("chart_label"),
                    "title": r.get("title") or r.get("query"),
                    "resolved": bool(f),
                }
                if not f:
                    row["unresolved"] = r.get("unresolved")
                    tracks.append(row)
                    continue
                pct: dict[str, dict[str, float]] = {}
                for a in axes:
                    v = f.get(a)
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        continue
                    entry: dict[str, float] = {}
                    for frame, cvals in cohorts.items():
                        if len(cvals.get(a) or []) >= min_cohort_n:
                            p = _percentile(cvals[a], float(v))
                            entry[frame] = p
                            per_axis[a][frame].append(p)
                    if entry:
                        pct[a] = entry
                row["percentiles"] = pct
                tracks.append(row)

            summary: dict[str, Any] = {}
            for a in axes:
                frames: dict[str, Any] = {}
                for frame in cohorts:
                    ps = per_axis[a][frame]
                    if not ps:
                        continue
                    frames[frame] = {
                        "median": _median(ps),
                        "n": len(ps),
                        "low_tail": sum(1 for p in ps if p <= low_pct),
                        "high_tail": sum(1 for p in ps if p >= high_pct),
                    }
                if frames:
                    summary[a] = frames
            role_out[role] = {
                "n_tracks": len(recs),
                "n_resolved": sum(1 for t in tracks if t["resolved"]),
                "tracks": tracks,
                "summary": summary,
                "rhythm_assigned": _rhythm_counts([r for r in recs if r.get("features")]),
            }

        # 원형↔한국 대조는 **같은 프레임(KR)** 위에서만 뺀다 — 프레임이 다르면
        # 코호트 차이가 곡 차이로 읽힌다.
        contrast: dict[str, Any] = {}
        if "origin" in role_out and "kr" in role_out:
            for a in axes:
                o = role_out["origin"]["summary"].get(a, {}).get("kr")
                k = role_out["kr"]["summary"].get(a, {}).get("kr")
                if o and k:
                    contrast[a] = {
                        "origin_median": o["median"],
                        "kr_median": k["median"],
                        "delta": round(k["median"] - o["median"], 1),
                    }
        out_cases[slug] = {"roles": role_out, "contrast_kr_frame": contrast}
    return out_cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="a2_signature_compare",
        description="케이스 곡 축별 백분위를 동시대 US·KR 코호트 위에서 계산 (A2 본편).",
    )
    ap.add_argument("--cases", required=True, nargs="+",
                    help="케이스 서명 스냅샷(sonic-profile fetch 산출) — 복수면 records를 잇는다")
    ap.add_argument("--cohort-us", required=True)
    ap.add_argument("--cohort-kr", required=True)
    ap.add_argument("--low-pct", type=float, default=20.0,
                    help="하위 극단 표기 경계 (기본 20 · 관습값, genre-impulse RULES §2.1과 동일)")
    ap.add_argument("--high-pct", type=float, default=80.0,
                    help="상위 극단 표기 경계 (기본 80 · 관습값)")
    ap.add_argument("--min-cohort-n", type=int, default=_MIN_COHORT_N_DEFAULT,
                    help=f"축별 최소 코호트 표본 (기본 {_MIN_COHORT_N_DEFAULT} — 미만이면 그 축·프레임 생략)")
    ap.add_argument("--min-prob", type=float, default=0.3,
                    help="악기 검출 확률 바닥 (기본 0.3 · 관습값 — 파생 악기 축에 쓰인다)")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args(argv)

    case_records: list[dict[str, Any]] = []
    case_prov: list[dict[str, Any]] = []
    for p in args.cases:
        recs, prov = _load_records(Path(p), min_prob=args.min_prob)
        case_records.extend(recs)
        case_prov.append({"path": p, "rhythm_feature_set":
                          (prov.get("engine_provenance") or {}).get("rhythm_feature_set")})
    us_records, us_prov = _load_records(Path(args.cohort_us), min_prob=args.min_prob)
    kr_records, kr_prov = _load_records(Path(args.cohort_kr), min_prob=args.min_prob)

    # 리듬 축은 rhythm_feature_set이 갈리면 비교가 성립하지 않는다(격자 폭이 다르다).
    sets = {p["rhythm_feature_set"] for p in case_prov}
    sets.add((us_prov.get("engine_provenance") or {}).get("rhythm_feature_set"))
    sets.add((kr_prov.get("engine_provenance") or {}).get("rhythm_feature_set"))
    if len(sets) > 1:
        raise SystemExit(f"rhythm_feature_set이 갈린다: {sorted(str(s) for s in sets)} — "
                         "같은 버전으로 재취득한 스냅샷끼리만 비교하라")

    axes = _scalar_axes(case_records + us_records + kr_records)
    cohorts = {
        "us": _cohort_values(us_records, axes),
        "kr": _cohort_values(kr_records, axes),
    }
    out_cases = compare(case_records, cohorts, axes,
                        args.min_cohort_n, args.low_pct, args.high_pct)

    payload = {
        "note": (
            "A2 본편 축별 백분위 (기계적 재료 — 서명 판단은 CASEBOOK이 한다). "
            "P = 100·count(cohort ≤ x)/n. 프레임: us=동시대 빌보드 Hot 100, "
            "kr=동시대 멜론 주간(Wayback). danceability는 원장이 무효로 판정한 "
            "축이다(천장 포화) — 표면 근거로 쓰지 말 것."
        ),
        "inputs": {
            "cases": case_prov,
            "cohort_us": {"path": args.cohort_us,
                          "n_resolved": sum(1 for r in us_records if r.get("features"))},
            "cohort_kr": {"path": args.cohort_kr,
                          "n_resolved": sum(1 for r in kr_records if r.get("features"))},
        },
        "thresholds": {"low_pct": args.low_pct, "high_pct": args.high_pct,
                       "min_cohort_n": args.min_cohort_n},
        "cohort_rhythm_assigned": {
            "us": _rhythm_counts([r for r in us_records if r.get("features")]),
            "kr": _rhythm_counts([r for r in kr_records if r.get("features")]),
        },
        "cases": out_cases,
    }
    Path(args.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    n_cases = len(out_cases)
    n_tracks = len(case_records)
    print(f"wrote {args.out} · cases {n_cases} · tracks {n_tracks}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
