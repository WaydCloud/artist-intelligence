"""Turn the analysis into a schema-valid report.json for the dashboard tab.

Purpose    Lay out three question sections, one summary figure, tagged inferences and the reliability line.
Boundary   Formats numbers that `analyze` computed. Computes no statistic itself.
Invariant  Every number on screen comes from the analysis dict. Copy that states a number must read it
           from there, or the screen stops aging with the data and silently goes wrong.
           Inference wording follows the analysis: "no relation found" only when the exact p is at or above alpha.
Failure    An untestable table prints its reason in place of the test numbers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from cohort_size import MODULE_ID, MODULE_VERSION

MEASURE_LABEL = {"any": "종합", "win": "음방 1위", "melon": "멜론", "circle": "써클", "spotify": "Spotify"}
VARIANT_LABEL = {"default": "기본", "range": "범위 포함", "units": "유닛 포함"}
SUMMARY_ID = "any-by-size"
TREND_LABEL = {"ordinal": "구간 순서", "median": "구간 중앙 인원"}
PROGRAM_LABEL = {"Music Bank": "뮤직뱅크", "Inkigayo": "인기가요", "M Countdown": "엠카운트다운",
                 "Show! Music Core": "쇼! 음악중심", "Show Champion": "쇼챔피언", "The Show": "더쇼"}

_SECTIONS = [
    {
        "id": "size",
        "label": "인원",
        "question": "인원에 따라 성공률이 다른가?",
        "note": "성공은 데뷔 연도부터 {w}년 안의 기록만 센다. 차이를 찾지 못한 것은 차이가 없다는 뜻이 아니다. "
        "구간마다 팀 수가 적어 작은 차이는 이 검정으로 가려지지 않는다.",
    },
    {
        "id": "era",
        "label": "시기",
        "question": "데뷔 시기마다 달랐나?",
        "note": "시기를 나눠 따로 검정했다. 여러 번 검정하면 낮은 p가 우연히 나올 수 있어 홀름 보정 p를 함께 적었다. "
        "{inc} 데뷔는 관측 창이 아직 닫히지 않아 따로 표시하고 보정에 넣지 않았다.",
    },
    {
        "id": "who",
        "label": "성공한 팀",
        "question": "성공한 팀은 몇 명이었나?",
        "note": "성공한 팀은 음방 1위·멜론·써클 중 하나라도 있는 팀이다. 성공한 팀이 적은 시기는 몇 팀의 값으로 "
        "중앙값이 정해진다.",
    },
]


def _p(v: float | None) -> str:
    if v is None:
        return "없음"
    return "<0.001" if v < 0.001 else f"{v:.3f}"


def _pct(x: float | None) -> str:
    return "" if x is None else f"{x * 100:.0f}%"


def _ci(r: dict[str, Any]) -> str:
    return f"{r['lo'] * 100:.0f}~{r['hi'] * 100:.0f}%"


def _rate_rows(rows: list[dict[str, Any]], prefix: str = "") -> list[dict[str, Any]]:
    # Buckets with no team are left out: a zero-length bar would read as a 0% rate.
    return [
        {"name": f"{prefix}{r['label']} · {r['k']}/{r['n']}팀 · 구간 {_ci(r)}", "value": round(r["rate"] * 100, 1)}
        for r in rows
        if r["n"]
    ]


def _test_line(t: dict[str, Any]) -> str:
    if "reason" in t:
        return f"검정 없음({t['reason']})"
    return (f"V {t['v']:.2f} ({t['vLo']:.2f}~{t['vHi']:.2f}) · 정확 p {_p(t['pExact'])} · 추세 p {_p(t['pTrend'])}")


def _w(a: dict[str, Any]) -> int:
    return int(a["config"]["window"])


def _tested_span(a: dict[str, Any]) -> str:
    ys = [c["year"] for c in a["cohorts"] if c["tested"]]
    return f"{min(ys)}~{max(ys)}" if ys else "없음"


def _inc(a: dict[str, Any]) -> str:
    return "·".join(str(y) for y in a["incompleteYears"]) or "없음"


def _summary(a: dict[str, Any]) -> dict[str, Any]:
    b = a["pooled"]["default"]["measures"]["any"]
    t = b["test"]
    return {
        "type": "bar",
        "id": SUMMARY_ID,
        "title": "인원 구간별 종합 성공률",
        "question": "인원 구간마다 성공한 팀의 비율은 얼마인가?",
        "definition": f"종합 성공은 데뷔 연도부터 {_w(a)}년 안에 음악방송 1위, 멜론 연말 가요 TOP100, 써클 연말 앨범 "
        "TOP100 중 하나라도 있는 경우다. 막대 길이와 오른쪽 수는 성공 비율(%), 이름 옆 수는 성공 팀/전체 팀과 "
        "95% 윌슨 신뢰구간이다.",
        "reliability": {"sample": f"{t['n']}팀 · 성공 {t['k']}팀 · {_tested_span(a)} 데뷔"},
        "data": _rate_rows(b["rows"]),
    }


def _measure_chart(a: dict[str, Any]) -> dict[str, Any]:
    pooled = a["pooled"]["default"]["measures"]
    data = []
    for m in ("win", "melon", "circle"):
        data += _rate_rows(pooled[m]["rows"], f"{MEASURE_LABEL[m]} · ")
    tests = " · ".join(f"{MEASURE_LABEL[m]} 정확 p {_p(pooled[m]['test'].get('pExact'))}" for m in ("win", "melon", "circle"))
    return {
        "type": "bar",
        "id": "measure-by-size",
        "section": "size",
        "title": "기준별 성공률",
        "question": "음방·멜론·써클 기준마다 결과가 같은가?",
        "definition": "음방 1위는 뮤직뱅크·인기가요·엠카운트다운·쇼! 음악중심·쇼챔피언·더쇼 중 한 곳에서라도 1위. "
        "멜론은 연말 가요 TOP100에 곡이 오른 것, 써클은 연말 앨범 TOP100에 앨범이 오른 것. 셋 다 데뷔 연도부터 "
        f"{_w(a)}년 안. 오른쪽 수는 성공 비율(%), 이름 옆 수는 성공 팀/전체 팀과 95% 신뢰구간.",
        "reliability": {"sample": f"{pooled['any']['test']['n']}팀 · {tests}"},
        "data": data,
    }


def _tests_chart(a: dict[str, Any]) -> dict[str, Any]:
    data = []
    for v in ("default", "range", "units"):
        for m in ("any", "win", "melon", "circle"):
            t = a["pooled"][v]["measures"][m]["test"]
            if "reason" in t:
                continue
            data.append({"name": f"{MEASURE_LABEL[m]} · {VARIANT_LABEL[v]} {t['n']}팀 · {_test_line(t)}",
                         "value": round(t["v"], 3)})
    c = a["counts"]
    return {
        "type": "bar",
        "id": "tests-by-population",
        "section": "size",
        "title": "모집단을 바꾼 검정",
        "question": "모집단을 바꾸면 결과가 움직이나?",
        "definition": "막대 길이는 크라메르 V다. 0이면 인원 구간과 성공이 따로 놀고, 1이면 구간이 성공을 완전히 가른다. "
        "관계가 없어도 표본이 작으면 V는 0보다 크게 나온다. 괄호는 부트스트랩 95% 구간, 정확 p는 몬테카를로 "
        "정확검정, 추세 p는 구간 순서(작은 팀에서 큰 팀으로)를 따라 비율이 한쪽으로 움직이는지 보는 검정이다. "
        "범위 포함은 데뷔 인원을 판정하지 못한 팀을 현재와 전 멤버 수의 합(상한)으로 넣은 것, 유닛 포함은 "
        "서브유닛·프로젝트 그룹을 넣은 것이다.",
        "reliability": {"sample": f"기본 {c['default']['tested']}팀 · 범위 포함 {c['range']['tested']}팀 · "
                                  f"유닛 포함 {c['units']['tested']}팀"},
        "data": data,
    }


def _spotify_chart(a: dict[str, Any]) -> dict[str, Any]:
    b = a["pooled"]["default"]["measures"]["spotify"]
    sp = a["sources"]["spotify"]
    return {
        "type": "bar",
        "id": "spotify-by-size",
        "section": "size",
        "title": "Spotify 월간 청취자 상위 (보조)",
        "question": "지금 Spotify 상위권에 있는 팀은 구간마다 얼마인가?",
        "definition": f"kworb가 집계한 Spotify 월간 청취자 상위 {sp['rows']:,} 아티스트 안에 이름이 정확히 같은 팀. "
        "수집일 하루의 값이라 데뷔 후 몇 년째인지와 관계가 없다. 그래서 종합 성공과 검정에 넣지 않았다.",
        "reliability": {"sample": f"{sum(r['n'] for r in b['rows'])}팀 · 스냅샷 {sp['retrieved'][:10]}"},
        "data": _rate_rows(b["rows"]),
    }


def _era_label(e: dict[str, Any]) -> str:
    return e["label"] if e["complete"] else f"{e['label']} 창 미완"


def _era_rate_chart(a: dict[str, Any]) -> dict[str, Any]:
    data = []
    for e in a["eras"]:
        data += _rate_rows(e["measures"]["any"]["rows"], f"{_era_label(e)} · ")
    return {
        "type": "bar",
        "id": "era-by-size",
        "section": "era",
        "title": "시기별 종합 성공률",
        "question": "데뷔 시기마다 인원 구간별 성공 비율은 얼마인가?",
        "definition": "종합 성공 비율을 데뷔 시기와 인원 구간으로 나눴다. 팀이 없는 구간은 줄을 뺐다. "
        "창 미완은 관측 창이 아직 닫히지 않은 시기라 비율이 더 오를 수 있다.",
        "reliability": {"sample": " · ".join(f"{_era_label(e)} {e['n']}팀" for e in a["eras"])},
        "data": data,
    }


def _era_test_chart(a: dict[str, Any]) -> dict[str, Any]:
    data = []
    for e in a["eras"]:
        t = e["measures"]["any"]["test"]
        if "reason" in t:
            continue
        holm = f" · 보정 p {_p(t['pHolm'])}" if "pHolm" in t else ""
        data.append({"name": f"{_era_label(e)} · {t['n']}팀 · {_test_line(t)}{holm}", "value": round(t["v"], 3)})
    fam = next((e["measures"]["any"]["test"].get("holmFamily") for e in a["eras"]
                if "holmFamily" in e["measures"]["any"]["test"]), 0)
    return {
        "type": "bar",
        "id": "era-tests",
        "section": "era",
        "title": "시기별 검정",
        "question": "어느 시기에서 인원 구간과 성공이 함께 움직였나?",
        "definition": "막대 길이는 크라메르 V(종합 기준). 보정 p는 관측 창이 닫힌 시기 "
        f"{fam}개를 한 묶음으로 본 홀름 보정 값이다. 시기마다 팀 수가 적어 구간이 크게 흔들린다.",
        "reliability": {"sample": " · ".join(f"{_era_label(e)} {e['n']}팀" for e in a["eras"])},
        "data": data,
    }


def _share_chart(a: dict[str, Any]) -> dict[str, Any]:
    d = a["pooled"]["default"]["dist"]
    data = []
    for s, al in zip(d["success"]["shares"], d["all"]["shares"], strict=True):
        if s["n"]:
            data.append({"name": f"{s['label']} · 성공한 팀 {s['k']}/{s['n']}", "value": round(100 * s["k"] / s["n"], 1)})
        if al["n"]:
            data.append({"name": f"{al['label']} · 전체 {al['k']}/{al['n']}", "value": round(100 * al["k"] / al["n"], 1)})
    return {
        "type": "bar",
        "id": "size-share",
        "section": "who",
        "title": "성공한 팀과 전체 팀의 인원 분포",
        "question": "성공한 팀의 인원 분포는 전체와 다른가?",
        "definition": "막대 길이는 각 묶음(성공한 팀, 전체 팀) 안에서 그 인원 구간이 차지하는 비율이다. "
        "두 줄의 길이가 비슷하면 성공한 팀의 인원 구성이 데뷔한 팀 전체와 비슷하다는 뜻이다.",
        "reliability": {"sample": f"성공 {d['success']['n']}팀 · 전체 {d['all']['n']}팀"},
        "data": data,
    }


def _median_chart(a: dict[str, Any]) -> dict[str, Any]:
    eras = a["eras"]
    return {
        "type": "line",
        "id": "era-median",
        "section": "who",
        "title": "시기별 중앙 인원",
        "question": "성공한 팀의 중앙 인원은 시기마다 어떻게 움직였나?",
        "definition": "데뷔 인원의 중앙값. 성공한 팀이 없는 시기는 점을 찍지 않는다. 성공한 팀이 열 팀 안팎인 "
        "시기가 많아 한두 팀이 값을 움직인다.",
        "reliability": {"sample": " · ".join(
            f"{_era_label(e)} 성공 {e['dist']['success']['n']}/{e['dist']['all']['n']}" for e in eras)},
        "data": {
            "x": [_era_label(e) for e in eras],
            "series": [
                {"name": "성공한 팀", "values": [e["dist"]["success"]["median"] for e in eras]},
                {"name": "전체 팀", "values": [e["dist"]["all"]["median"] for e in eras]},
            ],
        },
    }


def _focus_chart(a: dict[str, Any]) -> dict[str, Any]:
    f = a["config"]["focusSize"]
    data = []
    for e in a["eras"]:
        s, al = e["dist"]["success"], e["dist"]["all"]
        if s["n"]:
            data.append({"name": f"{_era_label(e)} · 성공한 팀 중 {f}명 {s['focus']}/{s['n']}",
                         "value": round(100 * s["focus"] / s["n"], 1)})
        if al["n"]:
            data.append({"name": f"{_era_label(e)} · 전체 중 {f}명 {al['focus']}/{al['n']}",
                         "value": round(100 * al["focus"] / al["n"], 1)})
    return {
        "type": "bar",
        "id": "era-focus",
        "section": "who",
        "title": f"시기별 {f}인조 비율",
        "question": f"{f}인조는 성공한 팀 안에서 더 많았나?",
        "definition": f"성공한 팀 중 {f}명으로 데뷔한 팀의 비율과, 같은 시기 전체 팀 중 {f}명 팀의 비율. "
        "막대 길이는 비율이다.",
        "reliability": {"sample": " · ".join(f"{_era_label(e)} {e['n']}팀" for e in a["eras"])},
        "data": data,
    }


def _metrics(a: dict[str, Any]) -> list[dict[str, Any]]:
    t = a["pooled"]["default"]["measures"]["any"]["test"]
    d = a["pooled"]["default"]["dist"]
    m: list[dict[str, Any]] = [
        {"label": "분석한 팀", "value": t["n"], "unit": "팀", "section": "size",
         "definition": f"{_tested_span(a)} 데뷔 걸그룹 중 데뷔 인원을 판정한 팀. 서브유닛·프로젝트 그룹 제외."},
        {"label": "종합 성공", "value": t["k"], "unit": "팀", "section": "size",
         "definition": f"데뷔 연도부터 {_w(a)}년 안에 음방 1위·멜론·써클 중 하나라도 있는 팀."},
    ]
    if "reason" in t:
        m.append({"label": "검정", "value": t["reason"], "section": "size",
                  "definition": "표가 검정할 수 있는 모양이 아니다."})
        return m
    m += [
        {"label": "정확검정 p", "value": round(t["pExact"], 3), "section": "size",
         "hint": f"몬테카를로 {t['exactB']:,}회 · 표준오차 {t['mcSe']:.4f}",
         "definition": "인원 구간과 종합 성공 사이에 관계가 없다고 가정할 때 지금만큼 치우친 표가 나올 확률. "
         "칸의 기대 빈도가 작아도 쓸 수 있는 검정이다."},
        {"label": "크라메르 V", "value": round(t["v"], 2), "section": "size",
         "hint": f"부트스트랩 95% 구간 {t['vLo']:.2f}~{t['vHi']:.2f}",
         "definition": "관계의 크기(0~1). 관계가 없어도 표본이 작으면 0보다 크게 나온다."},
        {"label": "추세 p", "value": round(t["pTrend"], 3) if t["pTrend"] is not None else "없음", "section": "size",
         "hint": "코크란-아미티지",
         "definition": "인원 구간을 작은 쪽에서 큰 쪽으로 세웠을 때 성공 비율이 한 방향으로 움직이는지 보는 검정."},
        {"label": "카이제곱 p", "value": round(t["pChi2"], 3), "section": "size",
         "hint": f"기대 빈도 5 미만 칸 {t['lowExpected']}/{t['cells']}",
         "definition": "피어슨 카이제곱 독립성 검정. 기대 빈도가 5 미만인 칸이 있으면 근사가 흔들려 정확검정을 함께 본다."},
        {"label": "성공한 팀 중앙 인원", "value": d["success"]["median"], "unit": "명", "section": "who",
         "definition": "종합 성공한 팀의 데뷔 인원 중앙값."},
        {"label": "전체 중앙 인원", "value": d["all"]["median"], "unit": "명", "section": "who",
         "definition": "분석한 팀 전체의 데뷔 인원 중앙값."},
    ]
    return m


def _inferences(a: dict[str, Any]) -> list[dict[str, Any]]:
    alpha = float(a["config"]["alpha"])
    out: list[dict[str, Any]] = []
    t = a["pooled"]["default"]["measures"]["any"]["test"]
    limits = (f"회사 규모·예산·데뷔 경쟁은 통제하지 않았다. 표본이 {t['n']}팀이라 약한 관계는 가려지지 않는다. "
              "관계를 찾지 못한 것과 관계가 없는 것은 다르다.")
    basis = (f"정확검정 p {_p(t.get('pExact'))} · 카이제곱 p {_p(t.get('pChi2'))} · 추세 p {_p(t.get('pTrend'))} · "
             f"V {t.get('v', 0):.2f} ({t.get('vLo', 0):.2f}~{t.get('vHi', 0):.2f})")
    if "reason" not in t:
        if t["pExact"] >= alpha and (t["pTrend"] is None or t["pTrend"] >= alpha):
            text = (f"이 표본에서 데뷔 인원 구간과 종합 성공 사이 관계를 찾지 못한 결과로 읽힌다. 있더라도 크라메르 V "
                    f"{t['vHi']:.2f} 이하 수준과 정합한다.")
        else:
            text = (f"이 표본에서 데뷔 인원 구간과 종합 성공 사이에 관계 신호가 있다. 크라메르 V {t['v']:.2f} "
                    f"({t['vLo']:.2f}~{t['vHi']:.2f}) 수준으로 읽힌다.")
        out.append({"text": text, "basis": basis, "sample": f"{t['n']}팀 중 성공 {t['k']}팀",
                    "confidence": "medium", "limits": limits, "chartId": SUMMARY_ID})

    # Does the reading move when the population changes? Compare the alpha calls on both tests.
    calls = {}
    for v in ("default", "range", "units"):
        tv = a["pooled"][v]["measures"]["any"]["test"]
        if "reason" not in tv:
            calls[v] = (tv["pExact"] < alpha, tv["pTrend"] is not None and tv["pTrend"] < alpha, tv)
    if len(calls) == 3:
        moved = [v for v in ("range", "units") if calls[v][:2] != calls["default"][:2]]
        detail = " · ".join(
            f"{VARIANT_LABEL[v]} 정확 p {_p(calls[v][2]['pExact'])}, 추세 p {_p(calls[v][2]['pTrend'])}"
            for v in ("default", "range", "units"))
        if moved:
            text = (f"모집단 정의에 따라 읽기가 바뀌는 것으로 읽힌다. {', '.join(VARIANT_LABEL[v] for v in moved)}에서 "
                    f"p {alpha:g} 기준의 판단이 기본과 다르다.")
        else:
            text = f"모집단 정의를 바꿔도 p {alpha:g} 기준의 판단은 기본과 같은 것으로 읽힌다."
        out.append({"text": text, "basis": detail,
                    "sample": " · ".join(f"{VARIANT_LABEL[v]} {calls[v][2]['n']}팀" for v in calls),
                    "confidence": "medium",
                    "limits": "범위 포함은 인원을 상한으로 넣어 큰 구간이 부풀 수 있다. 유닛 포함은 기존 팀의 인기를 "
                    "물려받은 팀이 섞인다.",
                    "chartId": "tests-by-population"})

    flagged = [e for e in a["eras"] if e["complete"] and e["measures"]["any"]["test"].get("pHolm", 1.0) < alpha]
    if flagged:
        names = ", ".join(e["label"] for e in flagged)
        e0 = flagged[0]["measures"]["any"]["test"]
        out.append({
            "text": f"{names} 데뷔 팀에서는 인원 구간에 따라 종합 성공 비율이 다른 신호가 있다. 보정 뒤에도 p {alpha:g} 아래다.",
            "basis": " · ".join(
                f"{e['label']} {_test_line(e['measures']['any']['test'])} · 보정 p "
                f"{_p(e['measures']['any']['test']['pHolm'])}" for e in flagged),
            "sample": " · ".join(f"{e['label']} {e['n']}팀 중 성공 {e['measures']['any']['test']['k']}팀" for e in flagged),
            "confidence": "low",
            "limits": f"한 시기 안의 팀 수가 적어 V 구간이 넓다(첫 시기 {e0['vLo']:.2f}~{e0['vHi']:.2f}). 같은 시기의 "
            "회사·장르 구성이 함께 움직였을 수 있다. 결과를 본 뒤 시기를 다시 나누면 이 신호는 판단 근거가 되지 못한다.",
            "chartId": "era-tests",
        })
    return out


def _reliability(a: dict[str, Any]) -> dict[str, Any]:
    c = a["config"]
    ex = a["excludedDefault"]
    return {
        "sample": f"기본 {a['counts']['default']['tested']}팀({_tested_span(a)} 데뷔, 데뷔 인원 판정) · "
        f"인원 미판정 {ex['undetermined']}팀과 유닛·프로젝트 {ex['units']}팀은 기본에서 제외",
        "accuracy": "성공은 이름 대조로 셌다. 오탐은 규칙과 검토 목록으로 걸렀고 놓친 비율은 재지 않았다(정확도 미측정)",
        "missing": f"음방 1위 목록이 없는 프로그램·연도 {len(a['coverage']['gaps'])}건({_gaps(a)})은 "
        f"0승이 아니라 결측이다. {_inc(a)} 데뷔는 관측 창이 닫히지 않아 검정에서 뺐다",
        "engine": f"cohort-size v{MODULE_VERSION} · 창 {c['window']}년 · 구간 {', '.join(c['buckets'])} · "
        f"정확검정 {c['exactB']:,}회 · 부트스트랩 {c['bootB']:,}회 · 시드 {c['seed']} · 추세 점수 {TREND_LABEL[c['trendScores']]}",
    }


def _gaps(a: dict[str, Any]) -> str:
    return ", ".join(f"{PROGRAM_LABEL.get(g['program'], g['program'])} {g['year']}" for g in a["coverage"]["gaps"])


def _insights(a: dict[str, Any]) -> list[str]:
    gaps = _gaps(a)
    sp = a["sources"]["spotify"]
    return [
        "그룹 목록과 데뷔 인원은 Kpop Wiki(팬 위키), 음방 1위는 위키백과 목록에서 읽었다. 둘 다 3차 출처다.",
        "Kpop Wiki가 어떤 그룹을 싣는지 기준이 확인되지 않았다. 실린 팀만 분모가 되어 아주 작은 팀이 빠졌을 수 있다.",
        (
            "데뷔 인원은 문서 첫머리의 데뷔 문장에서 읽고, 없으면 전 멤버가 없는 팀만 현재 인원으로 판정했다. "
            "멤버가 바뀐 팀 대부분은 판정되지 않아 기본 분석에서 빠졌고, 범위 포함 변형에서만 상한으로 들어간다."
        ),
        f"음방 1위 목록이 없는 프로그램·연도: {gaps}. 위키백과에 해당 연도 목록이 없다.",
        (
            "음방 1위는 표의 아티스트 칸만 읽고 각주·날짜·곡명은 지운 뒤 이름을 대조했다. 흔한 낱말과 같은 이름은 "
            "그룹 문서로 가는 링크일 때만 센다. 멜론은 아티스트 표기에 이름이 들어 있으면, 써클은 괄호로 나눈 "
            "이름 조각이 영문 이름이나 한글 이름과 같으면 센다."
        ),
        f"Spotify 월간 청취자는 {sp['retrieved'][:10]} 하루의 스냅샷이라 관측 창이 없다. 종합 성공과 검정에서 뺐다.",
        "데뷔 연도의 1월에 데뷔한 팀과 12월에 데뷔한 팀은 같은 3년 창을 받는다. 늦게 데뷔한 팀의 실제 관측 기간이 짧다.",
    ]


def _not_answered() -> list[str]:
    return [
        "인원이 성공을 만드는가. 이 화면은 함께 나타나는지만 본다",
        "회사 규모·예산·데뷔 경쟁을 뺀 인원의 몫. 통제하지 않았다",
        "팀이 왜 성공했는가",
        "데뷔 3년 뒤의 성공. 늦게 뜬 팀은 이 창에서 실패로 남는다",
        "보이그룹·혼성·솔로. 걸그룹만 봤다",
    ]


def build_report(a: dict[str, Any]) -> dict[str, Any]:
    w = _w(a)
    sections = [
        {**s, "note": s["note"].format(w=w, inc=_inc(a))} for s in _SECTIONS
    ]
    charts = [
        _measure_chart(a), _tests_chart(a), _spotify_chart(a),
        _era_rate_chart(a), _era_test_chart(a),
        _share_chart(a), _median_chart(a), _focus_chart(a),
    ]
    t = a["pooled"]["default"]["measures"]["any"]["test"]
    return {
        "moduleId": MODULE_ID,
        "title": "데뷔 인원과 성공",
        "subtitle": f"걸그룹 {t['n']}팀 · {_tested_span(a)} 데뷔 · 데뷔 후 {w}년 관측 · v{MODULE_VERSION}",
        "generatedAt": datetime.now(UTC).isoformat(),
        "metrics": _metrics(a),
        "charts": charts,
        "media": [],
        "insights": _insights(a),
        "recommendations": [],
        "summary": _summary(a),
        "sections": sections,
        "questions": [
            {"q": "인원 구간마다 성공 비율이 다른가?", "chartId": SUMMARY_ID},
            {"q": "음방·멜론·써클 기준마다 결과가 같은가?", "chartId": "measure-by-size"},
            {"q": "데뷔 시기마다 달랐나?", "chartId": "era-tests"},
            {"q": "성공한 팀은 몇 명이었나?", "chartId": "size-share"},
        ],
        "notAnswered": _not_answered(),
        "reliability": _reliability(a),
        "inferences": _inferences(a),
    }
