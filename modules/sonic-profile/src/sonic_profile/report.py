"""스냅샷 → report.json / signal-series (오프라인·결정적).

RULES §4: 관측 0이어도 크래시하지 않고 유효 report를 낸다. 한계(§3.1 발췌 제약)는
insights에 **반드시** 병기한다 — 병기는 선택이 아니라 §5 준수 요건이다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any

MODULE_ID = "sonic-profile"

# 리포트 표면에 올리는 지표. crest_factor_db는 TESTS §3 검증 통과(2026-07-28)로 활성화
_SURFACED = [
    ("tempo_bpm", "템포", "BPM"),
    ("pulse_clarity", "펄스 명료도", ""),
    ("onset_rate", "온셋 밀도", "회/초"),
    ("low_end_ratio", "저역 비율", ""),
    ("brightness_hz", "음색 밝기", "Hz"),
    ("percussive_ratio", "타악 비율", ""),
    ("crest_factor_db", "다이내믹 여유(crest)", "dB"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vals(records: list[dict[str, Any]], field: str) -> list[float]:
    out: list[float] = []
    for r in records:
        v = (r.get("features") or {}).get(field)
        if isinstance(v, (int, float)):
            out.append(float(v))
    return out


def _label(r: dict[str, Any]) -> str:
    """트랙 라벨 = `아티스트 - 곡명`.

    아티스트만 쓰면 같은 팀의 다른 곡이 구분되지 않는다(실측: 검정치마 2곡이 같은 이름으로
    나란히 표시됨). 해석된 레코드는 소스가 돌려준 정식 표기를 갖고 있으므로 그것을 쓴다.
    """
    artist = str(r.get("artist") or r.get("key") or "?").strip()
    title = str(r.get("title") or "").strip()
    return f"{artist} - {title}" if title else artist


def _labeled(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    """(라벨, 값) 쌍. 값이 있는 레코드에서 **직접** 만든다 — 별도로 필터링한 두 리스트를
    zip하면 지표가 없는 레코드에서 어긋나 엉뚱한 곡에 값이 붙는다."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in records:
        v = (r.get("features") or {}).get(field)
        if not isinstance(v, (int, float)):
            continue
        # 같은 녹음이 코호트·워치리스트 양쪽에 잡히면 한 번만
        tid = str(r.get("track_id") or "")
        dedup = tid or _label(r)
        if dedup in seen:
            continue
        seen.add(dedup)
        out.append({"name": _label(r), "value": float(v)})
    return out


def _hist(values: list[float], lo: float, hi: float, bins: int) -> list[dict[str, Any]]:
    if not values:
        return []
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        i = min(bins - 1, max(0, int((v - lo) / width)))
        counts[i] += 1
    return [
        {"name": f"{int(lo + i * width)}–{int(lo + (i + 1) * width)}", "value": c}
        for i, c in enumerate(counts)
    ]


# 분포 뷰에 쓰는 축 (0~1로 스케일이 같은 것끼리 묶어야 한 차트에 겹칠 수 있다)
_UNIT_AXES = [("pulse_clarity", "펄스 명료도"), ("low_end_ratio", "저역 비율"), ("percussive_ratio", "타악 비율")]
_ALL_AXES = [(f, la) for f, la, _ in _SURFACED]


def _position_heatmap(
    focus: list[dict[str, Any]], cohort: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """워치리스트 트랙이 차트 코호트 분포에서 **몇 위인가** (축별).

    heatmap 계약이 rank(1=최상) semantics라 그대로 맞는다. 이 뷰가 SPEC §2의
    "분포 안에서의 위치" — 값 자체보다 *어디쯤인지*가 판단 재료다.
    """
    if not focus or not cohort:
        return None
    rows, cells = [], []
    for r in sorted(focus, key=lambda x: _label(x)):
        feats = r.get("features") or {}
        row: list[int | None] = []
        for field, _ in _ALL_AXES:
            v = feats.get(field)
            pool = _vals(cohort, field)
            if not isinstance(v, (int, float)) or not pool:
                row.append(None)
                continue
            # 코호트 + 자기 자신을 합친 모집단에서 내림차순 순위 (1 = 가장 높음)
            row.append(sum(1 for p in pool if p > float(v)) + 1)
        if any(c is not None for c in row):
            rows.append(_label(r))
            cells.append(row)
    if not rows:
        return None
    return {
        "type": "heatmap",
        "title": f"분포 위치 · 워치리스트 트랙이 차트 {len(cohort)}곡 중 몇 위인가 (1 = 가장 높음)",
        "data": {"rows": rows, "cols": [la for _, la in _ALL_AXES], "cells": cells},
    }


def _cohort_compare(focus: list[dict[str, Any]], cohort: list[dict[str, Any]]) -> dict[str, Any] | None:
    """워치리스트 중앙값 vs 차트 중앙값 (0~1 축만 — 스케일이 같아야 나란히 읽힌다)."""
    if not focus or not cohort:
        return None
    data = []
    for field, label in _UNIT_AXES:
        f_v, c_v = _vals(focus, field), _vals(cohort, field)
        if not f_v or not c_v:
            continue
        data.append({"name": f"{label} · 워치리스트", "value": round(median(f_v), 4)})
        data.append({"name": f"{label} · 차트", "value": round(median(c_v), 4)})
    return (
        {"type": "bar", "title": "코호트 비교 · 워치리스트 vs 차트 중앙값 (0~1 축)", "data": data}
        if data
        else None
    )


def _median_series(records: list[dict[str, Any]], axes: list[tuple[str, str]], title: str) -> dict[str, Any] | None:
    """축별 중앙값의 날짜 시계열 — 트렌드는 **분포가 움직이는가**로만 보인다.

    단면 순위는 트렌드가 아니다. 날짜가 하나뿐이면 점 하나가 찍히고 축적되며 채워진다.
    """
    by_date: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        if r.get("features") and r.get("observed_date"):
            by_date.setdefault(str(r["observed_date"]), []).append(r)
    dates = sorted(by_date)
    if not dates:
        return None
    series = []
    for field, label in axes:
        vals = [
            round(median(v), 4) if (v := _vals(by_date[d], field)) else None for d in dates
        ]
        if any(x is not None for x in vals):
            series.append({"name": label, "values": vals})
    return (
        {"type": "line", "title": title, "data": {"x": dates, "series": series}} if series else None
    )


def _counts_chart(pairs: list[tuple[str, int]], title: str) -> dict[str, Any] | None:
    if not pairs:
        return None
    data = [{"name": k, "value": v} for k, v in sorted(pairs, key=lambda kv: (-kv[1], kv[0]))]
    return {"type": "bar", "title": title, "data": data}


def _rhythm_mix(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """코호트에서 각 킥 패턴이 최고 정합인 곡 수 — "지금 차트의 리듬 구성".

    최고 정합은 **순위이지 판정이 아니다**(템플릿끼리 직교하지 않는다, RULES §3.1.5).
    """
    counts: dict[str, int] = {}
    for r in records:
        top = (r.get("features") or {}).get("rhythm_top")
        if isinstance(top, str):
            counts[top] = counts.get(top, 0) + 1
    return _counts_chart(
        list(counts.items()),
        "리듬 패턴 구성 · 마디 안 킥 배치가 가장 가까운 유형 (판정 아닌 순위)",
    )


def _instrument_mix(records: list[dict[str, Any]], thresh: float = 0.3, top: int = 12) -> dict[str, Any] | None:
    """악기별 검출 곡 수. 임계값은 표시용이며 도메인 소유자가 조정한다(RULES §3.1.6)."""
    counts: dict[str, int] = {}
    for r in records:
        for d in (r.get("features") or {}).get("instruments") or []:
            if isinstance(d, dict) and float(d.get("p") or 0) >= thresh:
                counts[str(d["label"])] = counts.get(str(d["label"]), 0) + 1
    chart = _counts_chart(list(counts.items()), f"악기 구성 · 확률 {thresh} 이상 검출된 곡 수 (정확도 미측정)")
    if chart:
        chart["data"] = chart["data"][:top]
    return chart


def _style_mix(records: list[dict[str, Any]], top: int = 12) -> dict[str, Any] | None:
    """1순위 스타일별 곡 수 (Discogs 택소노미)."""
    counts: dict[str, int] = {}
    for r in records:
        st = (r.get("features") or {}).get("styles") or []
        if st and isinstance(st[0], dict):
            counts[str(st[0]["label"])] = counts.get(str(st[0]["label"]), 0) + 1
    chart = _counts_chart(list(counts.items()), "스타일 구성 · 1순위 라벨별 곡 수 (참고 · 정확도 미측정)")
    if chart:
        chart["data"] = chart["data"][:top]
    return chart


def build_report(
    records: list[dict[str, Any]],
    *,
    generated_at: str,
    provenance: dict[str, Any],
    watchlist: list[str] | None = None,
) -> dict[str, Any]:
    resolved = [r for r in records if r.get("features")]
    unresolved = [r for r in records if not r.get("features")]
    n, n_un = len(resolved), len(unresolved)

    metrics: list[dict[str, Any]] = [
        {"label": "관측 트랙", "value": n, "unit": "곡", "hint": "프리뷰 해석 성공"},
        {
            "label": "미해석",
            "value": n_un,
            "unit": "곡",
            "hint": "프리뷰 없음·디코드 실패·과단축 — 0이 아니라 결측으로 집계 제외",
        },
    ]
    for field, label, unit in _SURFACED:
        vs = _vals(resolved, field)
        if vs:
            metrics.append(
                {
                    "label": f"{label} 중앙값",
                    "value": round(median(vs), 3),
                    "unit": unit,
                    "hint": f"관측 {len(vs)}곡의 중앙값 · 분포 지표(단일 곡 비교 아님)",
                }
            )

    charts: list[dict[str, Any]] = []
    tempos = _vals(resolved, "tempo_bpm")
    if tempos:
        charts.append(
            {"type": "bar", "title": "템포 분포 (BPM)", "data": _hist(tempos, 60, 180, 8)}
        )
    pulsed = _labeled(resolved, "pulse_clarity")
    if pulsed:
        charts.append(
            {
                "type": "bar",
                "title": "펄스 명료도 상위 · 아티스트 - 곡명 (박이 또렷한 순 · 춤 적합도 아님)",
                "data": sorted(pulsed, key=lambda d: (-d["value"], d["name"]))[:15],
            }
        )

    # ── 리듬 패턴 · 악기 · 스타일 (RULES §3.1.5·§3.1.6)
    for view in (_rhythm_mix(resolved), _instrument_mix(resolved), _style_mix(resolved)):
        if view:
            charts.append(view)

    # ── 트렌드·비교 뷰 (SPEC §2). 단면 순위만으로는 트렌드가 보이지 않는다.
    latest = max((str(r.get("observed_date") or "") for r in resolved), default="")
    today_rec = [r for r in resolved if str(r.get("observed_date") or "") == latest]
    cohort = [r for r in today_rec if r.get("cohort") == "chart"]
    focus = [r for r in today_rec if r.get("cohort") == "watchlist"]
    for view in (
        _median_series(resolved, _UNIT_AXES, "분포 추이 · 0~1 축 중앙값 (날짜가 쌓이며 채워짐)"),
        _median_series(resolved, [("tempo_bpm", "템포 중앙값")], "분포 추이 · 템포 중앙값 (BPM)"),
        _position_heatmap(focus, cohort),
        _cohort_compare(focus, cohort),
    ):
        if view:
            charts.append(view)

    insights: list[str] = []
    if not resolved:
        insights.append("관측 없음 — 이 입력에서 해석된 프리뷰가 없습니다(수집·매칭 점검 대상).")
    else:
        insights.append(
            f"프리뷰 {n}곡 해석 · 미해석 {n_un}곡 (커버리지 {n}/{n + n_un}). "
            "미해석은 0이 아니라 **결측**으로 집계에서 빠집니다"
        )
    # ── 한계 병기(RULES §4 필수) — 빠지면 §5 위반
    insights.append(
        "⚠ 30초 발췌 · **발췌 위치 비결정**(Apple이 어느 구간을 주는지 비공개) — "
        "**곡 간 단일 비교 금지**. 허용되는 사용은 다수 곡의 **분포**와 같은 모집단의 **시계열**뿐입니다"
    )
    insights.append(
        "⚠ 곡 구조(인트로/벌스/훅)·전곡 다이내믹 아크·드롭 타이밍은 30초로 측정 불가 — 범위 밖(SPEC §6)"
    )
    insights.append(
        "다이내믹 여유(crest factor) = peak/RMS(dB). 낮을수록 압축이 강합니다. "
        "TESTS §3 검증(2026-07-28) — 10곡 표본에서 프리뷰 RMS 스프레드 19.46dB로 **정규화 없음** 확인 "
        "(US 스토어프론트·n=10·단일 시점 — Apple이 정책을 바꾸면 재검증 필요)"
    )
    insights.append(
        "펄스 명료도 = 온셋 포락 자기상관의 주 피크. **danceability가 아니며** 춤 실력·인기·품질과 무관합니다(RULES §5)"
    )
    eng = provenance.get("engine_provenance") or {}
    if any((r.get("features") or {}).get("rhythm_top") for r in resolved):
        insights.append(
            "리듬 패턴 = 마디를 16분음 16칸으로 나눠 저역(20–120Hz) 킥 배치를 접은 뒤 "
            "이름 붙은 유형과 맞춰 본 것입니다. 유형끼리 서로 겹치므로 **가장 가까운 유형은 순위이지 판정이 아닙니다**. "
            "정합도가 낮으면 '다른 유형'이 아니라 '해당 없음'입니다"
        )
        insights.append(
            "⚠ 트랩·저지클럽의 특징인 하이햇 롤과 하프타임 스네어는 아직 측정하지 못합니다 — "
            "믹스에서 스네어가 분리되지 않습니다(중역 대비 1.22 대 저역 1.71). 지금 내는 것은 "
            "정박·3+3+2·싱코페이션 여부까지입니다"
        )
    if any((r.get("features") or {}).get("styles") for r in resolved):
        insights.append(
            "⚠ 장르·악기는 **참고용이며 정확도를 아직 재지 않았습니다**(사람 라벨 대조 전). "
            "단독 근거로 쓰지 마시고, 1순위 라벨을 그 곡의 장르로 확정하지 마십시오. "
            "확률은 서로 배타적이지 않습니다"
        )
        insights.append(
            "저지클럽·뭄바톤·아마피아노는 이 태거의 라벨 목록에 없습니다 — 그 축은 리듬 패턴이 담당합니다"
        )
        if eng.get("attribution"):
            insights.append(f"장르·악기 모델 출처 {eng['attribution']} · {eng.get('tagger_license')}")
    insights.append(
        f"엔진 {eng.get('engine')} {eng.get('engine_version')} · {eng.get('sample_rate')}Hz 모노 · "
        f"저역 경계 {eng.get('low_hz')}Hz"
        + (f" · 비트 {eng.get('beat_engine')}({eng.get('beat_checkpoint')})" if eng.get("beat_engine") else "")
        + ". 엔진·설정이 바뀌면 과거 값과 비교할 수 없습니다(RULES §2)"
    )
    if any((r.get("features") or {}).get("tempo_source") == "beat_this-fit" for r in resolved):
        insights.append(
            "템포는 비트 시각에 직선을 맞춰 구합니다. 이전 방식은 값이 고정 격자에만 떨어져 "
            "130BPM 부근에서 6.5BPM보다 작은 변화를 볼 수 없었습니다(101곡이 18개 값만 산출). "
            "격자 값은 `tempo_bpm_grid`로 남겨 과거와 비교할 수 있게 했습니다"
        )
    if watchlist:
        hit = sorted({str(r.get("key")) for r in resolved if r.get("key") in set(watchlist)})
        insights.append(
            f"워치리스트 커버리지 {len(hit)}/{len(watchlist)}"
            + (f" — {', '.join(hit[:8])}" if hit else " — 관측 없음(무신호도 정보)")
        )

    return {
        "moduleId": MODULE_ID,
        "title": "소닉 프로파일 · 30초 프리뷰 기반 소리 지표",
        "subtitle": "분포 안에서의 위치를 보는 증거 · 단일 곡 평결 아님",
        "generatedAt": generated_at,
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": [
            "차트 진입 직후 트랙만 좁혀 관측하면 비용·법적 노출을 최소화하면서 트렌드를 볼 수 있습니다",
            "지표 해석은 분포 대비 위치로 — 임계값이 필요하면 도메인 소유자가 근거를 보기 전에 정하십시오",
        ],
    }


def build_signal_series(
    records: list[dict[str, Any]], *, field: str = "pulse_clarity", provenance: dict[str, Any] | None = None
) -> dict[str, Any]:
    """act × 날짜 → 지표 시리즈 (공유 signal-series 계약)."""
    dates = sorted({str(r.get("observed_date")) for r in records if r.get("observed_date")})
    idx = {d: i for i, d in enumerate(dates)}
    series: dict[str, list[Any]] = {}
    for r in records:
        key, d = r.get("key"), r.get("observed_date")
        v = (r.get("features") or {}).get(field)
        if not key or d not in idx or not isinstance(v, (int, float)):
            continue
        series.setdefault(str(key), [None] * len(dates))[idx[str(d)]] = v
    return {
        "moduleId": MODULE_ID,
        "signal": field,
        "unit": "",
        "higherIsStronger": True,
        "dates": dates,
        "series": series,
        "roster": {k: True for k in series},
        "provenance": provenance or {},
    }
