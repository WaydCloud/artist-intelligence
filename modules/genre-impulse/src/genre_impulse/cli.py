"""genre-impulse CLI — 임펄스 원장과 일일 sonic 코호트를 대조한다.

무단정(RULES §1): 출력은 "검출 규칙 매치 + 과거 사례 문맥"까지이며 도달/성공을
말하지 않는다. 실행에는 PYTHONPATH에 이 모듈과 sonic-profile의 src가 모두
필요하다(organic_ratio 파생 재사용 — RULES §3의 문서화된 한시 예외).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from genre_impulse import MODULE_ID, MODULE_VERSION

# 하중받는 기준 — 값은 도메인 소유자 소유, CLI로 노출(RULES §2.1).
LOW_PCT_DEFAULT = 20.0
HIGH_PCT_DEFAULT = 80.0

# 표면에 올릴 수 있는 확실성 등급(D-033 보완⑥ — 중간 이상만, 등급 병기).
SURFACE_GRADES = ("매우 높음", "높음", "중간")

# 검출 규칙 원장(RULES §2). 사전 등록·실측 검증을 거친 규칙만 올린다.
# 조합 형식 셋: low_all(전건 하위) · high_all(전건 상위) · high_any(하나 이상 상위).
RULES: list[dict[str, Any]] = [
    {
        "id": "hyperpop-texture",
        "impulse_id": "hyperpop",
        # short = 격자 행 접두용 표시명. 전체 id를 행에 붙이면 곡명이 잘린다
        # (2026-07-31 육안: "moombahton-kr-tropical · ★코르티…"에서 주어가 사라졌다).
        "short": "하이퍼팝",
        "low_all": ["organic_ratio"],
        "high_all": [],
        "high_any": ["spectral_flatness", "over_unity_ratio"],
        "basis": "A2.1 실측 2026-07-30. Savage organic P2.2·flatness P87.9·over_unity P80.2 (CASEBOOK §A2.1). "
                 "A2 본편 재검(2026-07-31): organic↓·flatness↑은 동시대 프레임에서도 성립, "
                 "over_unity는 프레임 의존(동시대 중앙 P66, RULES §2.1 한계 참조)",
    },
    # amapiano는 **등재 철회**(2026-07-31): 예측 2축(onset_rate_high·silence_ratio)이
    # 정답지 7/7 상위 20%였으나 조합의 코호트 베이스라인이 20~21%(세 코호트 일관 —
    # 축이 어디서나 양의 상관)라 규칙이 아니라 넓은 텍스처 통이다. RULES §2.2 참조.
    {
        "id": "ukg-origin-shuffle",
        "impulse_id": "ukg-dnb",
        "short": "UKG 원형",
        "low_all": [],
        "high_all": ["swing_ratio", "tempo_bpm"],
        "high_any": [],
        "basis": "A2 본편 실측 2026-07-31. 원형 swing P91.3(▲4/6)·tempo P96.0(▲5/6). "
                 "한국 수용형은 스윙 소거(P37.8)로 안 걸린다. 원형 진입 감지용 (CASEBOOK §A2 본편)",
    },
    {
        "id": "moombahton-kr-tropical",
        "impulse_id": "moombahton-tropical",
        "short": "뭄바톤 KR",
        "low_all": ["spectral_contrast_mean"],
        "high_all": [],
        "high_any": ["brightness_hz"],
        "basis": "A2 본편 실측 2026-07-31. 한국 수용형 contrast ▼7/7(P17.3)·brightness ▲5/7(P88.8). "
                 "청량 변형 검출용, 원형(명도 P73)은 경계 아래 (CASEBOOK §A2 본편)",
    },
]


def _rule_axes(rule: dict[str, Any]) -> list[str]:
    return [*rule["low_all"], *rule["high_all"], *rule["high_any"]]


def _rule_short(rule_id: str) -> str:
    return next((str(r["short"]) for r in RULES if r["id"] == rule_id), rule_id)


RULE_AXES = sorted({ax for r in RULES for ax in _rule_axes(r)})

# 축의 화면 표기(DESIGN §6.1). 저장 키(`organic_ratio`)를 그대로 찍으면 데이터 키가 새어
# 나온 것처럼 읽힌다. 표기는 sonic-profile의 타일 라벨과 같은 말을 쓴다 — 두 탭에서 같은
# 축이 다른 이름으로 불리면 읽는 사람이 다른 것으로 여긴다.
# `over_unity_ratio`는 **클리핑(결함)이 아니다**(sonic-profile RULES §3.7.1) — 손실 압축을
# 디코드하면 인터샘플 피크가 1.0을 넘는다. 이름이 그 사실을 들고 있게 한다.
AXIS_LABELS: dict[str, str] = {
    "organic_ratio": "유기음 비율",
    "spectral_flatness": "스펙트럼 평탄도",
    "over_unity_ratio": "인터샘플 피크 비율",
    # §2.1.2~4 (A2 본편). 템포·음색 밝기는 sonic-profile 타일 라벨과 같은 말.
    "onset_rate_high": "고역 온셋 밀도",
    "silence_ratio": "무음 비율",
    "swing_ratio": "스윙 비율",
    "tempo_bpm": "템포",
    "brightness_hz": "음색 밝기",
    "spectral_contrast_mean": "스펙트럼 대비",
}


def axis_label(ax: str) -> str:
    return AXIS_LABELS.get(ax, ax)

# 단정 어휘 가드(TESTS §4.11) — report 직렬화에 있으면 안 되는 표현.
FORBIDDEN = ("차트인할", "뜰 것", "데뷔감")

# 진입 요약(R2)의 id. `questions`·`inferences`가 앵커하는 대상이라 한 곳에 둔다.
SUMMARY_ID = "impulse-coverage"

# ── 구획·문구 (D-043 · DESIGN §6.1·§7.1) ──────────────────────────────────────
#
# 이 탭은 **두 개의 다른 질문**에 답한다: 오늘 무엇이 걸렸나 · 기준을 움직이면 어떻게
# 달라지나. 요약이 답하는 "애초에 무엇을 관측할 수 있나"는 셋째 질문이고, 이 모듈에서
# 가장 하중을 받는 사실이라 첫 화면의 도형 하나로 나간다(커버리지 1/10 — 화면의 침묵을
# '신호 없음'으로 읽지 않게 하는 것이 이 탭의 첫 번째 일이다).
_SECTIONS: list[dict[str, str]] = [
    {
        "id": "matches",
        "label": "매치",
        "question": "오늘 규칙에 걸린 곡은 무엇인가?",
        "note": "백분위는 그날 코호트 안에서의 상대 위치다. 코호트가 바뀌면 같은 곡의 값도 바뀐다. "
        "걸렸다는 것은 요소가 닮았다는 뜻이며 도달이나 성공이 아니다.",
    },
    {
        "id": "tuner",
        "label": "기준",
        "question": "기준을 움직이면 어느 곡이 달라지나?",
        "note": "컷 값은 A&R이 소유한다. 여기서 움직이는 것은 화면 안의 계산이고 원장은 바뀌지 않는다.",
    },
]

_CHART_META: dict[str, dict[str, str]] = {
    "match-axes": {
        "section": "matches",
        "title": "규칙에 걸린 곡의 축별 위치",
        "question": "그 곡들은 어느 축에서 그렇게 걸렸나?",
        "definition": "칸의 값은 그날 코호트 안에서의 백분위(0~100)이고, 진할수록 코호트 상위다. "
        "행은 규칙과 곡의 짝이다. 한 곡이 여러 규칙에 걸리면 규칙마다 한 행씩 나오며, 어느 규칙의 "
        "어느 축이 걸렸는지는 행 머리의 규칙 이름과 기준 구획의 규칙 정의로 읽는다. 이름 앞의 ★는 "
        "워치리스트 팀이라는 표시다.",
    },
    "impulse-tuner": {
        "section": "tuner",
        "title": "컷을 움직여 다시 세기",
        "question": "컷을 바꾸면 어느 곡이 들어오고 나가나?",
        "definition": "두 슬라이더는 규칙의 하한·상한 백분위다. 화면 안에서 매치를 다시 계산할 뿐 "
        "원장의 기준값을 바꾸지 않는다. 기준은 버전 매겨진 가설이다.",
    },
}

_METRIC_META: dict[str, dict[str, str]] = {
    "원장 임펄스": {
        "section": "tuner",
        "definition": "임펄스 원장에 등재된 장르 흐름의 수. 스키마를 어긴 항목은 세지 않고 따로 보고한다.",
    },
    "검출 규칙 확정": {
        "section": "tuner",
        "label": "관측 가능한 임펄스",
        "definition": "실측으로 검증된 검출 규칙이 있는 임펄스의 수. 나머지는 이 화면에서 관측되지 않으며, "
        "관측되지 않는 것과 일어나지 않는 것은 다르다.",
    },
    "당일 코호트": {
        "section": "matches",
        "label": "오늘 본 곡",
        "definition": "이번 스냅샷에서 특질이 계산된 곡의 수. 백분위의 분모이며, 이 집합이 바뀌면 "
        "같은 곡의 백분위도 바뀐다.",
    },
    "규칙 매치": {
        "section": "matches",
        "label": "규칙에 걸린 곡",
        "definition": "확정된 검출 규칙의 하한·상한 조건을 모두 만족한 곡의 수. 여러 규칙에 걸린 곡도 "
        "한 번만 센다. 검토 후보이지 판정이 아니다.",
    },
}


def _derive(features: dict[str, Any]) -> dict[str, Any]:
    """sonic-profile 파생 재계산 재사용 — 재구현 금지(AGENTS §1)."""
    try:
        from sonic_profile.derived import derive_all  # type: ignore[import-not-found]
    except ImportError as exc:  # PYTHONPATH 안내가 없으면 원인을 알 수 없는 실패가 된다
        raise SystemExit(
            "sonic_profile을 찾을 수 없습니다 — PYTHONPATH에 modules/sonic-profile/src를 추가하세요"
        ) from exc
    out = dict(features)
    out.update(derive_all(features))
    return out


def _percentile(pool: list[float], x: float) -> float:
    """코호트 내 백분위 — `이하 비율` 정의(동값 결정적, TESTS §3.9)."""
    if not pool:
        return 0.0
    below = sum(1 for v in pool if v <= x)
    return round(100.0 * below / len(pool), 1)


def load_impulses(path: Path, schema_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """원장 로드 — 스키마 위반은 스킵하되 보고한다(조용한 무시 금지, RULES §3)."""
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    for f in sorted(path.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as exc:
            skipped.append(f"{f.name}: {exc.message[:80]}")
            continue
        records.append(doc)
    return records, skipped


def load_cohort(path: Path) -> tuple[list[dict[str, Any]], str]:
    """sonic 스냅샷 로드 — 디렉터리면 최신 일자 파일, 코호트=features 있는 레코드."""
    if path.is_dir():
        dated = sorted(p for p in path.glob("????-??-??.json"))
        if not dated:
            return [], ""
        path = dated[-1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    recs = [r for r in doc.get("records", []) if isinstance(r.get("features"), dict)]
    return recs, path.name


def evaluate(
    cohort: list[dict[str, Any]], low_pct: float, high_pct: float
) -> tuple[list[dict[str, Any]], dict[str, list[float]], list[dict[str, Any]]]:
    """규칙 평가 — 축별 코호트 백분위 계산 후 조합 판정.

    셋째 반환값은 **곡별 백분위 전건**이다. 튜너가 임계를 움직여 매치를 다시
    계산하려면 매치된 곡만이 아니라 후보 전부의 백분위가 필요하다 — 매치만 보내면
    임계를 낮춰도 새 곡이 나타날 수 없다.
    """
    feats = [(r, _derive(r["features"])) for r in cohort]
    pools: dict[str, list[float]] = {
        # 0.0은 유효값이다 — falsy 검사 금지(TESTS §3.10, D-032 함정).
        ax: [f[ax] for _, f in feats if isinstance(f.get(ax), (int, float))]
        for ax in RULE_AXES
    }
    # 곡별 백분위는 한 번만 계산해 매치·튜너가 같은 값을 쓴다. 결측 축은 키를 만들지
    # 않는다(§0 결측 ≠ 0) — 규칙 판정은 자기 축이 전부 있을 때만 한다.
    all_pcts: list[dict[str, float]] = [
        {
            ax: _percentile(pools[ax], float(v))
            for ax in RULE_AXES
            if isinstance((v := f.get(ax)), (int, float))
        }
        for _, f in feats
    ]

    matches: list[dict[str, Any]] = []
    for rule in RULES:
        axes = _rule_axes(rule)
        for (rec, _f), pcts in zip(feats, all_pcts):
            if any(ax not in pcts for ax in axes):
                continue  # 규칙 축이 하나라도 결측이면 이 규칙은 평가 불능
            low_ok = all(pcts[ax] <= low_pct for ax in rule["low_all"])
            high_all_ok = all(pcts[ax] >= high_pct for ax in rule["high_all"])
            # any([]) == False라 빈 목록을 그대로 넘기면 high_any 없는 규칙이 전부
            # 죽는다 — 빈 조합은 "조건 없음"으로 읽는다.
            high_any_ok = not rule["high_any"] or any(pcts[ax] >= high_pct for ax in rule["high_any"])
            if low_ok and high_all_ok and high_any_ok:
                matches.append({
                    "rule": rule["id"],
                    "impulse_id": rule["impulse_id"],
                    "key": str(rec.get("key") or rec.get("query") or "?"),
                    # 격자 행이 되므로 규칙 축만이 아니라 **가진 축 전부**를 싣는다 —
                    # 규칙 축만 실으면 나머지 칸이 "축 결측"으로 그려진다(있는 값인데).
                    "label": f"{rec.get('artist', rec.get('key', '?'))} - {rec.get('title', '?')}",
                    "pcts": pcts,
                })
    # 정렬 극단 축은 규칙마다 다르다 — 첫 규칙의 축을 전 매치에 쓰면 그 축이 없는
    # 매치에서 죽는다(규칙이 하나일 때만 우연히 성립하던 정렬).
    def _extremity(m: dict[str, Any]) -> float:
        rule = next(r for r in RULES if r["id"] == m["rule"])
        if rule["low_all"]:
            return m["pcts"][rule["low_all"][0]]          # 낮을수록 부합 → 오름차순
        return -m["pcts"][_rule_axes(rule)[0]]             # 높을수록 부합 → 내림차순

    matches.sort(key=lambda m: (m["rule"], _extremity(m), m["label"]))

    scored: list[dict[str, Any]] = []
    for (rec, _f), pcts in zip(feats, all_pcts):
        # 어느 한 규칙이라도 평가 가능하면 튜너에 남긴다 — 전 축(9종)을 요구하면
        # 리듬 축이 없는 곡이 통째로 사라져 임계를 낮춰도 나타날 수 없다.
        if not any(all(ax in pcts for ax in _rule_axes(r)) for r in RULES):
            continue
        scored.append({
            "key": str(rec.get("key") or rec.get("query") or "?"),
            "name": f"{rec.get('artist', rec.get('key', '?'))} - {rec.get('title', '?')}",
            "pcts": pcts,
        })
    primary = RULES[0]["low_all"][0] if RULES and RULES[0]["low_all"] else (RULE_AXES[0] if RULE_AXES else "")
    scored.sort(key=lambda t: (t["pcts"].get(primary, 101.0), t["name"]))
    return matches, pools, scored


def _context_lines(impulse: dict[str, Any]) -> list[str]:
    """원장 문맥 인용 — 확실성 중간 이상만 표면에(RULES §1)."""
    lines: list[str] = []
    mode = impulse.get("adoption_mode", {}).get("mode", "?")
    lines.append(f"'{impulse.get('name_ko', impulse['id'])}' 수용 모드: {mode} (원장 {impulse.get('version')})")
    eb = impulse.get("element_borrowing")
    if isinstance(eb, dict):
        for t in eb.get("anchor_tracks", []):
            grade = str(t.get("certainty", ""))
            if grade in SURFACE_GRADES:
                lines.append(
                    f"과거 차용 앵커: {t.get('artist')} - {t.get('title')}"
                    f" ({t.get('date')}, 확실성 {grade})"
                )
    idf = impulse.get("identity_formation")
    if isinstance(idf, dict) and idf.get("occurred"):
        lines.append(
            f"정체성화 전례: {idf.get('group')} '{idf.get('fandom_slang')}'"
            f" (언론 공식화 {idf.get('press_formalization_date')})"
        )
    return lines


def _coverage_lines(impulses: list[dict[str, Any]], ruled_ids: set[str]) -> list[str]:
    """R7 — 규칙이 없어 **이 화면이 답하지 못하는** 질문. 인사이트가 아니라 답하지 않는 목록이다.

    2026-07-30까지 이 아홉 줄은 인사이트 맨 아래에 쌓여 있었다. 없는 것을 없다고 먼저
    말하는 자리가 화면에 생겼으므로(D-041 R7) 그리로 옮긴다 — 사용자가 물으러 왔을 수
    있는 질문이 인사이트 목록의 꼬리보다 위에 있어야 한다.
    """
    lines: list[str] = []
    for imp in impulses:
        if imp["id"] in ruled_ids:
            continue
        sig = imp.get("signature", {})
        locks = sig.get("locks") or []
        measured = sig.get("measured") or {}
        if locks:
            reason = "; ".join(locks)
        elif measured:
            # A2 실측까지 갔는데 규칙이 안 선 경우 — "서명이 없다"고 말하면 거짓이다.
            reason = str(measured.get("rule") or "실측 완료, 규칙 미확정")
        else:
            reason = f"서명이 아직 도출되지 않아 규칙이 없다(상태 {sig.get('status', '?')})"
        # `흐름이`를 붙여 이름 뒤 조사를 고정한다 — 받침 유무로 조사를 갈라 쓰면 문장이 깨진다.
        lines.append(f"{imp.get('name_ko', imp['id'])} 흐름이 지금 도는지. {reason}")
    return lines


# ── 시각화 계약 헬퍼 (D-041 · D-043) ──────────────────────────────────────────
#
# 다른 모듈에도 같은 모양의 함수가 있다. 공유 모듈로 묶지 않는 것이 이 레포의 구조다
# (D-007: 모듈은 코드가 아니라 데이터·계약을 공유한다). 공통 규격의 정본은
# `report.schema.json`과 `scripts/validate_report_data.py`다.


def _apply_meta(
    metrics: list[dict[str, Any]], charts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """차트·지표에 구획과 문구를 붙이고, 표에 없는 차트는 **떨어낸다**(R3)."""
    for m in metrics:
        meta = _METRIC_META.get(str(m.get("label") or ""))
        if not meta:
            continue
        m["section"] = meta["section"]
        m["definition"] = meta["definition"]
        if meta.get("label"):  # 라벨 갈아 끼우기는 맨 마지막 — 위 조회가 원래 라벨을 키로 쓴다
            m["label"] = meta["label"]

    kept: list[dict[str, Any]] = []
    for c in charts:
        meta = _CHART_META.get(str(c.get("id") or ""))
        if meta:
            c.update(meta)
            kept.append(c)
    return kept


def _place_sections(
    metrics: list[dict[str, Any]], charts: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """차트가 실제로 놓인 구획만 남기고, 구획을 잃은 지표를 되찾아 준다."""
    sections = [dict(s) for s in _SECTIONS if any(c.get("section") == s["id"] for c in charts)]
    if len(sections) < 2:  # 구획이 하나뿐이면 내비게이션이 할 일이 없다 → 한 줄 렌더
        sections = []
    live = {s["id"] for s in sections}
    for m in metrics:
        sid = str(m.get("section") or "")
        if not sid or sid in live:
            continue
        if sections:
            m["section"] = str(sections[0]["id"])
        else:
            m.pop("section", None)
    return sections


def _coverage_summary(impulses: list[dict[str, Any]], ruled_ids: set[str]) -> dict[str, Any]:
    """진입 요약 하나(R2) — **애초에 무엇을 관측할 수 있나**.

    이 모듈에서 가장 하중을 받는 사실은 오늘의 매치가 아니라 커버리지다. 규칙이 없는
    임펄스의 신호는 이 화면에 아예 없고, 그 침묵을 '신호 없음'으로 읽으면 이 도구는
    없는 것을 없다고 말하지 못한 채 안심만 주는 물건이 된다(RULES §1).
    """
    ruled = sum(1 for i in impulses if i["id"] in ruled_ids)
    working = sum(
        1
        for i in impulses
        if i["id"] not in ruled_ids and (i.get("signature", {}).get("locks") or [])
    )
    # A2 실측까지 갔는데 규칙이 안 선 상태를 "서명 없음"으로 부르면 거짓이다 —
    # 실측 결과(판별력 없음·표본 부족·프레임 부적합)도 원장에 적힌 정보다.
    measured_no_rule = sum(
        1
        for i in impulses
        if i["id"] not in ruled_ids
        and not (i.get("signature", {}).get("locks") or [])
        and (i.get("signature", {}).get("measured") or {})
    )
    return {
        "type": "bar",
        "id": SUMMARY_ID,
        "title": "원장에서 관측 가능한 임펄스",
        "question": "이 화면이 지금 관측할 수 있는 임펄스는 얼마나 되나?",
        "definition": "검출 규칙이 확정된 임펄스만 이 화면에서 관측된다. 실측·규칙 미확정은 서명을 "
        "쟀으나 규칙이 서지 않은 상태(사유는 답하지 않는 것 목록), 서명 작업 중은 무엇이 막고 "
        "있는지가 원장에 적혀 있는 상태, 나머지는 아직 서명 자체가 없다. 관측되지 않는 것과 "
        "일어나지 않는 것은 다르다.",
        "reliability": {"sample": f"원장 {len(impulses)}건"},
        "data": [
            {"name": "검출 규칙 확정", "value": ruled},
            {"name": "실측·규칙 미확정", "value": measured_no_rule},
            {"name": "서명 작업 중", "value": working},
            {"name": "아직 서명 없음", "value": max(0, len(impulses) - ruled - working - measured_no_rule)},
        ],
    }


def _questions(have: set[str]) -> list[dict[str, str]]:
    """R1 — 이 탭에서 답할 수 있는 질문(상한 4). 끊긴 앵커는 검사기가 잡는다."""
    kept = [
        q
        for q in (
            {"q": "이 화면이 지금 관측할 수 있는 임펄스는 얼마나 되나?", "chartId": SUMMARY_ID},
            {"q": "오늘 코호트에서 규칙에 걸린 곡은 무엇인가?", "chartId": "match-axes"},
            {"q": "그 곡들은 어느 축에서 걸렸나?", "chartId": "match-axes"},
            {"q": "컷을 바꾸면 어느 곡이 들어오고 나가나?", "chartId": "impulse-tuner"},
        )
        if q["chartId"] in have
    ]
    for spare in (
        {"q": "규칙이 없는 임펄스는 몇 건인가?", "chartId": SUMMARY_ID},
        {"q": "서명 작업이 막혀 있는 임펄스는 몇 건인가?", "chartId": SUMMARY_ID},
    ):
        if len(kept) >= 3:
            break
        kept.append(spare)
    return kept


def _impulse_inferences(
    *,
    impulses: list[dict[str, Any]],
    ruled_ids: set[str],
    matches: list[dict[str, Any]],
    cohort_n: int,
    watch_keys: set[str],
    low_pct: float,
    high_pct: float,
) -> list[dict[str, Any]]:
    """태그된 자동 추론(R4 · D-039). 전부 관측에서 계산한다.

    허용 어법은 "~와 정합한다"·"~신호가 있다"·"~로 읽힌다"뿐이고, 명령·예측·인과 단정과
    em dash는 scripts/validate_report_data.py가 CI에서 잡는다.
    """
    out: list[dict[str, Any]] = []
    ruled = sum(1 for i in impulses if i["id"] in ruled_ids)

    # ① 커버리지 — 이 화면의 침묵이 무엇인지. 매치가 0건이어도 나가야 하는 문장이다.
    if impulses and ruled < len(impulses):
        out.append({
            "text": f"이 화면의 침묵을 신호 없음으로 읽을 수 없는 상태와 정합한다. 원장 "
            f"{len(impulses)}건 중 규칙이 있는 것은 {ruled}건이다.",
            "basis": f"검출 규칙 {ruled}건 · 규칙 없는 임펄스 {len(impulses) - ruled}건",
            "sample": f"원장 {len(impulses)}건",
            "confidence": "high",
            "limits": "규칙이 없다는 것은 서명을 아직 못 뽑았다는 뜻이며, 그 임펄스가 조용하다는 뜻이 아니다.",
            "chartId": SUMMARY_ID,
        })

    # ② 매치의 규모가 컷에 매여 있다는 것. 임계값이 결과를 만든다는 사실을 화면이 들고 있게 한다.
    # ⚠ "곡"을 셀 때는 매치(곡×규칙 쌍)가 아니라 **유일 곡**을 센다 — 한 곡이 규칙
    # 셋에 걸리면 매치는 3이지만 곡은 1이다(2026-07-31 육안 검사에서 잡힌 과대 집계).
    matched_tracks = len(dict.fromkeys(m["label"] for m in matches))
    if cohort_n and matches:
        out.append({
            "text": f"코호트 {cohort_n}곡 중 {matched_tracks}곡이 지금 컷에서 규칙에 걸린 상태와 정합한다.",
            "basis": f"컷 P{low_pct:g}/P{high_pct:g} · 매치 {len(matches)}건 · 곡 {matched_tracks}/{cohort_n} "
            f"({100.0 * matched_tracks / cohort_n:.0f}%)",
            "sample": f"코호트 {cohort_n}곡",
            "confidence": "medium",
            "limits": "이 수는 컷을 움직이면 함께 움직인다. 백분위는 그날 코호트 안에서의 상대 위치라 "
            "코호트 구성이 바뀌면 같은 곡도 다른 값을 받는다.",
            "chartId": "match-axes",
        })

    # ③ 워치리스트가 걸렸는가 — 이 도구를 보는 사람이 실제로 담당하는 팀인지.
    watched_names = list(dict.fromkeys(m["label"] for m in matches if m["key"] in watch_keys))
    if watched_names:
        names = ", ".join(watched_names)[:120]
        out.append({
            "text": f"워치리스트 팀의 곡도 규칙에 걸린 것으로 읽힌다. {len(watched_names)}곡이다.",
            "basis": f"매치된 {matched_tracks}곡 중 워치리스트 {len(watched_names)}곡 · {names}",
            "sample": f"워치리스트 {len(watch_keys)}팀",
            "confidence": "medium",
            "limits": "걸렸다는 것은 축의 위치가 규칙과 맞았다는 뜻이며 그 곡이 그 장르라는 판정이 아니다.",
            "chartId": "match-axes",
        })
    return out


def build_report(
    impulses: list[dict[str, Any]],
    skipped: list[str],
    cohort: list[dict[str, Any]],
    snapshot_name: str,
    low_pct: float,
    high_pct: float,
    watch_keys: set[str],
) -> dict[str, Any]:
    matches, pools, scored = evaluate(cohort, low_pct, high_pct) if cohort else ([], {}, [])
    ruled_ids = {r["impulse_id"] for r in RULES}
    by_id = {i["id"]: i for i in impulses}

    insights: list[str] = [
        "유사는 도달이 아니다. 매치는 검토 후보이지 예측이 아니며 판단은 A&R의 몫이다.",
        f"검출 규칙 커버리지 {len(RULES)}/{len(impulses) or '?'}. 대부분의 임펄스는 아직 규칙이 없다(아래 관측 불가 표).",
        "백분위는 당일 코호트 내 상대 위치다. 코호트 구성이 바뀌면 같은 곡도 값이 달라진다.",
    ]
    for s in skipped:
        insights.append(f"원장에서 건너뛴 항목(스키마 위반): {s}")
    # 곡별 백분위는 **격자가 보여준다**(match-axes). 예전에는 여기에 곡마다 한 줄씩
    # `organic_ratio P1.0 · over_unity_ratio P62.7 …`을 찍었는데, 저장 키가 그대로 나가는
    # 데다 같은 값을 두 번 말하는 열한 줄이었다. 규칙 귀속만 남긴다.
    for rule in RULES:
        hit = [m for m in matches if m["rule"] == rule["id"]]
        if hit:
            insights.append(f"규칙 {rule['id']}에 걸린 곡 {len(hit)}곡. 곡별 위치는 격자 참조")
    for rule in RULES:
        imp = by_id.get(rule["impulse_id"])
        if imp and any(m["rule"] == rule["id"] for m in matches):
            insights.extend(_context_lines(imp))
        insights.append(f"규칙 근거 {rule['id']}: {rule['basis']}")
    if not cohort:
        insights.append("코호트 0곡. sonic 스냅샷이 비어 있어 매치를 계산하지 않았다.")

    charts: list[dict[str, Any]] = []
    if matches:
        # 매치를 **축별 백분위 격자**로 낸다. 예전에는 하한 축 하나만 막대 길이로 그렸는데,
        # 그 축은 "낮을수록 규칙 부합"이라 **긴 막대가 덜 부합**을 뜻했다(길이의 방향과
        # 주장의 방향이 반대인 상태). 세 축의 값은 전부 같은 단위(코호트 백분위)라
        # 하나의 눈금으로 나란히 놓을 수 있고, 규칙의 모양(왼쪽 낮고 오른쪽 하나 높음)이
        # 격자에서 그대로 보인다.
        charts.append({
            "type": "heatmap",
            "id": "match-axes",
            "reliability": {"sample": f"매치 {len(matches)}건 / 코호트 {len(cohort)}곡"},
            # 공유 계약의 bar 항목 키는 **`name`**이다(대시보드 BarChart·타 모듈 전부).
            # 2026-07-30까지 여기만 `label`을 내보내 막대 11개가 **이름 없이** 그려졌다.
            # report-schema는 data를 제약하지 않아(`"data": {}`) 검증도 통과했다 —
            # 스키마가 못 잡는 계약은 이런 식으로 조용히 어긋난다.
            "data": {
                # 행 = "규칙(짧은 표시명) · 곡". 규칙 셋의 매치가 한 격자에 섞이므로
                # 귀속을 행이 들고 있어야 한다 — 없으면 여러 규칙에 걸린 곡이 중복 행
                # 결함처럼 읽힌다(2026-07-31 육안 검사 실측). 전체 규칙 id는 길어서
                # 곡명을 잘라먹으므로 short를 쓴다(전체 id는 기준 구획·인사이트에 있다).
                "rows": [f"{_rule_short(m['rule'])} · " + ("★" if m["key"] in watch_keys else "") + m["label"]
                         for m in matches],
                "cols": [axis_label(ax) for ax in RULE_AXES],
                "cells": [[m["pcts"].get(ax) for ax in RULE_AXES] for m in matches],
                # 값의 방향을 명시한다 — 격자 프리미티브의 기본은 순위(작을수록 강함)라,
                # 백분위를 그냥 실으면 낮은 값이 가장 진하게 칠해지고 범례가 그것을
                # "상위"라고 부른다(정반대로 읽히는 그림).
                "scale": "value",
                "strongLabel": "코호트 상위",
                "weakLabel": "코호트 하위",
                "emptyLabel": "축 결측",
                "valuePrefix": "백분위 ",
            },
        })
    if cohort:
        # 튜너가 임계를 움직여 **어느 곡이 매치인지** 다시 계산하려면 곡별 백분위가
        # 있어야 한다. 분포(pools)만 실으면 컷 값은 그려도 매치는 못 바꾼다 —
        # 2026-07-30까지 이 payload가 그 상태였고, 뷰가 아예 렌더되지 않아(대시보드에
        # 핸들러가 없었다) 드러나지 않았다. 백분위는 이미 계산돼 있으므로 오디오
        # 재접근은 없다(RULES §4).
        tunable_tracks = [
            {"name": t["name"], "watch": t["key"] in watch_keys, "pcts": t["pcts"]}
            for t in scored
        ]
        charts.append({
            "type": "tunable",
            "id": "impulse-tuner",
            "reliability": {"sample": f"코호트 {len(cohort)}곡 · 축 {len(RULE_AXES)}종"},
            "data": {
                "view": "impulse-rules",
                "lowPct": low_pct,
                "highPct": high_pct,
                "axes": RULE_AXES,
                # 화면 표기는 저장 키와 따로 보낸다 — 클라이언트가 키를 그대로 찍지 않게.
                "axisLabels": {ax: axis_label(ax) for ax in RULE_AXES},
                "pools": {ax: sorted(v) for ax, v in pools.items()},
                # 규칙의 형식(어느 축이 하한이고 어느 축이 상한인가)도 함께 보낸다 —
                # 클라이언트가 규칙을 추측하면 원장과 갈라진다.
                "rules": [
                    {"id": r["id"], "impulseId": r["impulse_id"],
                     "lowAll": r["low_all"], "highAll": r["high_all"], "highAny": r["high_any"]}
                    for r in RULES
                ],
                "tracks": tunable_tracks,
                "knobs": [
                    {"key": "lowPct", "label": "하위 백분위 P_low", "default": low_pct,
                     "min": 0, "max": 50, "step": 1},
                    {"key": "highPct", "label": "상위 백분위 P_high", "default": high_pct,
                     "min": 50, "max": 100, "step": 1},
                ],
                "note": "유사 ≠ 도달. 매치는 후속 검토 후보이지 판정이 아니다.",
            },
        })

    metrics: list[dict[str, Any]] = [
        {"label": "원장 임펄스", "value": len(impulses), "unit": "건"},
        {"label": "검출 규칙 확정", "value": len(RULES), "unit": "건",
         "hint": f"원장 {len(impulses) or 0}건 중 · 축 공백·스템 잠금은 RULES §2.2"},
        {"label": "당일 코호트", "value": len(cohort), "unit": "곡"},
        # 유일 곡 수 — 매치(곡×규칙 쌍) 수를 "곡"으로 내보내면 과대 집계다.
        {"label": "규칙 매치", "value": len(dict.fromkeys(m["label"] for m in matches)), "unit": "곡"},
    ]
    charts = _apply_meta(metrics, charts)
    sections = _place_sections(metrics, charts)
    have = {str(c["id"]) for c in charts} | {SUMMARY_ID}
    extra: dict[str, Any] = {
        "summary": _coverage_summary(impulses, ruled_ids),
        "questions": _questions(have),
        # R7 — 규칙이 없는 임펄스는 "인사이트"가 아니라 **답하지 않는 질문**이다.
        "notAnswered": [
            "이 곡들이 실제로 그 장르로 읽히는지. 사람 라벨이 없어 규칙의 정확도는 재지 않았다",
            "요소 차용이 정체성으로 굳는지. 원장은 과거 전례를 들 뿐 지금 것을 판정하지 않는다",
            *_coverage_lines(impulses, ruled_ids),
        ],
        "reliability": {
            "sample": f"원장 {len(impulses)}건 · 코호트 {len(cohort)}곡 · 매치 {len(matches)}건",
            "accuracy": "검출 규칙은 과거 사례에서 뽑은 가설이다. 사람 라벨이 없어 정확도 미측정",
            "missing": "세 축 중 하나라도 계산되지 않은 곡은 규칙을 적용하지 않는다(결측을 0으로 읽지 않는다)",
            "engine": f"genre-impulse v{MODULE_VERSION} · 스냅샷 {snapshot_name or '입력 없음'} "
            f"· 컷 P{low_pct:g}/P{high_pct:g}",
        },
        "inferences": _impulse_inferences(
            impulses=impulses,
            ruled_ids=ruled_ids,
            matches=matches,
            cohort_n=len(cohort),
            watch_keys=watch_keys,
            low_pct=low_pct,
            high_pct=high_pct,
        ),
    }
    if sections:
        extra["sections"] = sections

    return {
        "moduleId": MODULE_ID,
        "title": "장르 임펄스 모니터",
        "subtitle": f"원장 {len(impulses)}건 × 코호트 {len(cohort)}곡 ({snapshot_name or '입력 없음'}) · v{MODULE_VERSION}",
        "generatedAt": datetime.now(UTC).isoformat(),
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": [
            "매치 트랙은 요소 차용 관점의 청취 검토 후보다. 과거 사례 문맥(모드·리드타임)과 함께 볼 것.",
            "규칙이 없는 임펄스의 신호는 이 리포트에 없다. 부재를 '신호 없음'으로 읽지 말 것.",
        ],
        **extra,
    }


def cmd_analyze(args: argparse.Namespace) -> int:
    impulses, skipped = load_impulses(Path(args.impulses), Path(args.impulse_schema))
    cohort, snap_name = load_cohort(Path(args.sonic))
    watch_keys: set[str] = set()
    if args.watchlist and Path(args.watchlist).exists():
        doc = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
        watch_keys = {str(a["key"]) for a in doc.get("artists", []) if isinstance(a, dict) and a.get("key")}
    report = build_report(impulses, skipped, cohort, snap_name, args.low_pct, args.high_pct, watch_keys)
    out = Path(args.output) / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # 매치 수는 지표에서 읽는다. 인사이트 줄을 세면 문구를 다듬는 순간 수가 바뀐다
    # (실제로 곡별 줄을 규칙별 한 줄로 줄였을 때 11 → 1로 잘못 찍혔다).
    matched = next((m["value"] for m in report["metrics"] if m["label"] == "규칙에 걸린 곡"), 0)
    print(f"wrote {out} · 매치 {matched}곡")
    return 0


# ── selftest ──────────────────────────────────────────────────────────────

def _fx_track(
    key: str, organic: float, flat: float, over: float,
    onset_high: float = 5.0, silence: float = 0.05, swing: float = 0.5,
    tempo: float = 120.0, bright: float = 2000.0, contrast: float = 20.0,
) -> dict[str, Any]:
    """합성 코호트 트랙 — 규칙 축 9종 전부. 기본값은 중앙(어느 규칙에도 안 걸린다)."""
    return {"key": key, "artist": key, "title": key, "cohort": "chart",
            "features": {"organic_ratio": organic, "spectral_flatness": flat, "over_unity_ratio": over,
                         "onset_rate_high": onset_high, "silence_ratio": silence, "swing_ratio": swing,
                         "tempo_bpm": tempo, "brightness_hz": bright, "spectral_contrast_mean": contrast}}


def _fx_impulse(iid: str, grade: str = "매우 높음") -> dict[str, Any]:
    return {
        "id": iid, "name_ko": iid, "version": "1.0.0", "updated": "2026-07-30",
        "case_type": "import",
        "adoption_mode": {"mode": "element"},
        "trajectory": [{"cell": "kr-mainstream", "date": "2022-12", "evidence": "픽스처", "certainty": "높음"}],
        "leadtimes": [{"from_cell": "origin-viral", "to_cell": "kr-mainstream", "months": 12}],
        "early_signals": [{"source_type": "shortform-viral", "date": "2021-01", "evidence": "픽스처", "certainty": "높음"}],
        "element_borrowing": {"elements": ["금속성 신스"], "stage_reached": "identity",
                              "anchor_tracks": [{"artist": "A", "title": "T", "date": "2021-10", "certainty": grade}]},
        "identity_formation": None,
        "signature": {"status": "pending-a2", "locks": ["stem-separation: 보컬 처리"]},
        "limits": ["픽스처"],
    }


def cmd_selftest(_args: argparse.Namespace) -> int:
    import tempfile

    import jsonschema

    root = Path(__file__).resolve().parents[4]
    report_schema = json.loads((root / "packages/report-schema/report.schema.json").read_text(encoding="utf-8"))
    impulse_schema_path = root / "data/research/genre-impulse/impulse.schema.json"

    passed = failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))

    # 새 축(§2.1.2~4)은 **반상관**으로 흩는다: 한 축이 커질 때 짝 축이 작아지게 —
    # 단조로 같이 키우면 꼭대기 트랙이 high_all 조합(둘 다 상위)에 우연히 걸려
    # "중앙 트랙 무매치"(검사 7)가 성립하지 않는다.
    cohort = [_fx_track(f"mid{i}", 0.5 + i * 0.01, 0.010 + i * 0.001, 0.02 + i * 0.001,
                        onset_high=4 + i * 0.1, silence=0.06 - i * 0.002,
                        swing=0.45 + i * 0.005, tempo=140 - i * 3,
                        bright=1500 + i * 50, contrast=18 + i * 0.5) for i in range(8)]
    planted = _fx_track("planted", 0.01, 0.09, 0.20)  # organic 최하위 + flat/over 최상위
    cohort_pos = [*cohort, planted]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        imp_dir = tmp / "impulses"
        imp_dir.mkdir()
        (imp_dir / "hyperpop.json").write_text(json.dumps(_fx_impulse("hyperpop")), encoding="utf-8")
        (imp_dir / "ruleless.json").write_text(json.dumps(_fx_impulse("ruleless")), encoding="utf-8")
        (imp_dir / "broken.json").write_text(json.dumps({"id": "broken"}), encoding="utf-8")
        (tmp / "sonic").mkdir()
        (tmp / "sonic" / "2026-07-30.json").write_text(
            json.dumps({"records": cohort_pos}), encoding="utf-8")

        impulses, skipped = load_impulses(imp_dir, impulse_schema_path)
        recs, snap = load_cohort(tmp / "sonic")
        rep = build_report(impulses, skipped, recs, snap, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())

        errors = list(jsonschema.Draft202012Validator(report_schema).iter_errors(rep))
        check("1 스키마 유효", not errors, "; ".join(e.message[:60] for e in errors[:2]))

        rep2 = build_report(impulses, skipped, recs, snap, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())
        strip = lambda r: json.dumps({**r, "generatedAt": ""}, ensure_ascii=False, sort_keys=True)
        check("2 결정성", strip(rep) == strip(rep2))

        empty = build_report(impulses, skipped, [], "", LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())
        check("3 빈 코호트 graceful", any("코호트 0곡" in i for i in empty["insights"]))

        # 문구가 아니라 **뜻**을 본다. 예전에는 "[원장 스킵]" 접두어를 문자열로 맞췄는데,
        # 카피 규율(§6.1)로 태그를 걷어내자 기능은 그대로인 채 검사만 깨졌다.
        check("4 위반 레코드 스킵+보고", len(impulses) == 2 and any("broken" in s for s in skipped)
              and any("건너뛴" in i and "스키마 위반" in i for i in rep["insights"]))

        low_grade_dir = tmp / "imp2"
        low_grade_dir.mkdir()
        (low_grade_dir / "hyperpop.json").write_text(json.dumps(_fx_impulse("hyperpop", grade="낮음")), encoding="utf-8")
        imps_low, _ = load_impulses(low_grade_dir, impulse_schema_path)
        rep_low = build_report(imps_low, [], recs, snap, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT, set())
        check("5 중간 미만 등급 미표면", not any("과거 차용 앵커" in i for i in rep_low["insights"])
              and any("과거 차용 앵커" in i for i in rep["insights"]))

        m, _pools, _sc = evaluate(cohort_pos, LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("6 양성 매치", any(x["key"] == "planted" for x in m))
        check("7 음성 무매치", not any(x["key"].startswith("mid") for x in m))
        m_tight, _, _ = evaluate(cohort_pos, 1.0, 99.9)
        check("8 임계 극단 → 매치 0", not m_tight)
        check("9 n=1 백분위", _percentile([0.5], 0.5) == 100.0 and evaluate([planted], 20, 80) is not None)
        m_zero, _, _ = evaluate([_fx_track("z", 0.0, 0.09, 0.2), *cohort], LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("10 organic 0.0은 유효값", any(x["key"] == "z" for x in m_zero))

        blob = json.dumps(rep, ensure_ascii=False)
        check("11 단정 어휘 없음", not any(w in blob for w in FORBIDDEN))
        # ⚠ 이 검사는 **이 세션 전부터 실패하고 있었다**(2026-07-30 확인): "커버리지"라는
        # 낱말을 hint에서 찾는데 타일 문구가 '관측 가능한 임펄스 / 원장 N건 중'으로 바뀐 뒤
        # 낱말이 사라졌다. 커버리지 KPI 자체는 화면에 그대로 있었으므로 **기능이 아니라
        # 검사가 낡은 것**이다. 낱말이 아니라 분모가 붙은 KPI가 있는지를 본다.
        check(
            "12 커버리지 KPI",
            any(
                x.get("label") == "관측 가능한 임펄스" and "원장" in str(x.get("hint", ""))
                for x in rep["metrics"]
            ),
        )
        check("13 정직성 인사이트", "예측이 아니" in rep["insights"][0])

        # §3.18~21 — high_all 조합과 다규칙 견고성 (TESTS 2026-07-31)
        ukg_pos = _fx_track("ukg", 0.55, 0.014, 0.024, swing=0.99, tempo=200.0)
        ukg_half = _fx_track("half", 0.55, 0.014, 0.024, swing=0.99, tempo=90.0)
        m18, _, _ = evaluate([*cohort, ukg_pos], LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("18 high_all 양성", any(x["key"] == "ukg" and x["rule"] == "ukg-origin-shuffle" for x in m18))
        m19, _, _ = evaluate([*cohort, ukg_half], LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("19 high_all 반쪽은 무매치", not any(x["key"] == "half" for x in m19),
              "any로 구현하면 상한 하나로 걸린다")
        m20, _, _ = evaluate([*cohort, planted, ukg_pos], LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("20 다규칙 매치 정렬이 죽지 않는다",
              {x["rule"] for x in m20} >= {"hyperpop-texture", "ukg-origin-shuffle"})
        # 리듬 축이 없는 트랙(hyperpop 축만 보유)이 튜너 목록에서 통째로 사라지면 안 된다.
        bare = {"key": "bare", "artist": "bare", "title": "bare", "cohort": "chart",
                "features": {"organic_ratio": 0.5, "spectral_flatness": 0.014, "over_unity_ratio": 0.024}}
        _, _, sc21 = evaluate([*cohort, bare], LOW_PCT_DEFAULT, HIGH_PCT_DEFAULT)
        check("21 부분 결측 튜너 잔류", any(t["key"] == "bare" for t in sc21))

    print(f"selftest: {passed} passed · {failed} failed")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="genre_impulse",
        description="임펄스 원장 × 일일 sonic 코호트 대조 (PYTHONPATH에 sonic-profile/src 필요)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_a = sub.add_parser("analyze", help="원장 × 스냅샷 → report.json (오프라인)")
    p_a.add_argument("--impulses", default="data/research/genre-impulse/impulses")
    p_a.add_argument("--impulse-schema", default="data/research/genre-impulse/impulse.schema.json")
    p_a.add_argument("--sonic", required=True, help="sonic 스냅샷 파일 또는 디렉터리(최신 일자 사용)")
    p_a.add_argument("--watchlist", default=None)
    # 하중받는 기준 — 코드에 은닉하지 않는다(AGENTS §2.1). 값=도메인 소유자 소유.
    p_a.add_argument("--low-pct", type=float, default=LOW_PCT_DEFAULT,
                     help=f"하위 백분위 컷 (기본 {LOW_PCT_DEFAULT}, 관습값)")
    p_a.add_argument("--high-pct", type=float, default=HIGH_PCT_DEFAULT,
                     help=f"상위 백분위 컷 (기본 {HIGH_PCT_DEFAULT}, 관습값)")
    p_a.add_argument("-o", "--output", required=True)
    p_a.set_defaults(func=cmd_analyze)

    p_s = sub.add_parser("selftest", help="네트워크 0 자체 검증 (TESTS)")
    p_s.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
