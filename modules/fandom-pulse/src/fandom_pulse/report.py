"""Build a schema-valid report.json from facts-only IG snapshot record(s).

Public aggregate signals only — no virality/hit prediction, no popularity or
"quality" verdict (RULES.md §5, AGENTS.md §5/§0). Thresholds are *criteria* that
live in RULES.md §3 (기준 원장) and arrive as tunable params — never hidden here.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from statistics import median

from fandom_pulse.entities import match
from fandom_pulse.normalize import as_int

MODULE_ID = "fandom-pulse"

# 진입 요약(R2)의 id. `questions`·`inferences`가 앵커하는 대상이라 문자열을 한 곳에 둔다.
SUMMARY_ID = "spread-artists"

# ── 구획·문구 (D-043 · DESIGN §6.1·§7.1) ──────────────────────────────────────
#
# 이 탭은 **세 개의 다른 질문**에 답한다: 늘고 있나 · 무슨 곡이 미나 · 게시물이 어떤
# 모습인가. 진입 요약이 답하는 "그 곡은 누구의 것인가"는 넷째 질문이고, 그래서 구획이
# 아니라 첫 화면의 도형 하나로 나간다(R2 — 여기 실린 차트는 `charts`에 중복하지 않는다).
#
# 문구를 한 표에 모으는 이유: 이것은 클라이언트 대면 카피이고(DESIGN §6.1), 계산 코드
# 사이에 흩어 두면 검토가 불가능해진다.
_SECTIONS: list[dict[str, str]] = [
    {
        "id": "cadence",
        "label": "게시 흐름",
        "question": "이 태그는 지금 늘고 있나?",
        "note": "수집한 표본 안에서의 하루당 게시수다. 태그를 붙이지 않은 게시물과 수집되지 않은 게시물은 "
        "여기 없다. 창이 짧으면 방향이 쉽게 뒤집힌다.",
    },
    {
        "id": "sounds",
        "label": "사운드",
        "question": "어떤 곡이 이 태그를 움직이나?",
        "note": "사운드 라벨은 게시물이 붙인 표기 그대로다. 개인이 올린 오디오('Original audio')는 곡으로 세지 않는다.",
    },
    {
        "id": "posts",
        "label": "게시물",
        "question": "이 게시물들은 어떤 모습인가?",
        "note": "좋아요와 댓글은 공개 표시값이고 계정 규모에 크게 좌우된다. 반응의 크기이지 인기나 완성도가 아니다.",
    },
]

_CHART_META: dict[str, dict[str, str]] = {
    "daily-posts": {
        "section": "cadence",
        "title": "하루당 게시물 수",
        "question": "이 태그의 게시량이 늘고 있나, 줄고 있나?",
        "definition": "게시 시각(UTC) 기준으로 하루에 몇 건이 올라왔는지. 수집한 표본 안에서의 값이며 "
        "그날 이 태그로 올라온 전체 게시물 수가 아니다.",
    },
    "top-sounds": {
        "section": "sounds",
        "title": "가장 많이 쓰인 사운드",
        "question": "이 태그의 게시물은 어떤 곡을 쓰고 있나?",
        "definition": "게시물에 붙은 사운드 라벨을 표기 그대로 센 값. 같은 곡이라도 라벨 표기가 다르면 "
        "다른 항목으로 세어진다.",
    },
    "co-hashtags": {
        "section": "posts",
        "title": "함께 붙은 해시태그",
        "question": "이 태그를 쓰는 게시물은 어떤 태그를 같이 다나?",
        "definition": "같은 게시물에 함께 붙은 다른 해시태그의 등장 횟수. 질의한 태그 자신은 뺀다. "
        "무관한 태그를 붙인 게시물이 섞일 수 있다.",
    },
}

# 지표의 구획·정의·라벨을 한 표에 모은다. 라벨은 화면에 그대로 찍히는 카피이고,
# `로스터`처럼 우리끼리 쓰던 말은 한 번 더 생각하게 만들므로 여기서 갈아 끼운다(DESIGN §6.1).
_METRIC_META: dict[str, dict[str, str]] = {
    "게시물 수": {
        # 흐름 구획에 둔다 — 창 전체의 크기와 그 창 안의 방향(가속)은 같은 질문의 두 면이다.
        "section": "cadence",
        "definition": "이번 수집에서 저장된 공개 게시물 수. 이 태그 전체가 아니라 수집한 표본의 크기다.",
    },
    "총 참여": {
        "section": "posts",
        "definition": "표본 게시물의 좋아요와 댓글을 모두 더한 값.",
    },
    "중앙값 좋아요": {
        "section": "posts",
        "definition": "표본 게시물의 좋아요 수를 줄 세웠을 때 한가운데 값. 바이럴 한 건에 덜 흔들리도록 "
        "평균 대신 쓴다.",
    },
    "중앙값 댓글": {
        "section": "posts",
        "definition": "표본 게시물의 댓글 수를 줄 세웠을 때 한가운데 값.",
    },
    "고참여 게시물": {
        "section": "posts",
        "definition": "좋아요와 댓글의 합이 표본 상위 분위 기준선 이상인 게시물 수. 절대값이 아니라 "
        "이 표본 안에서의 상대 위치로 세며, 기준 분위는 조정 가능한 가설이다.",
    },
    "릴스 비중": {
        "section": "posts",
        "definition": "표본에서 릴스(동영상)가 차지하는 비율.",
    },
    "게시 가속": {
        "section": "cadence",
        "definition": "수집 창을 절반으로 갈라, 최근 절반의 하루 평균 게시수에서 이전 절반의 하루 평균을 뺀 값. "
        "창이 짧으면 쉽게 뒤집힌다.",
    },
    "사운드 확산 아티스트": {
        "section": "sounds",
        "label": "곡 라벨로 잡힌 팀",
        "definition": "게시물의 사운드 라벨에서 한 번이라도 아티스트로 읽힌 팀의 수.",
    },
    "로스터 밖 확산": {
        "section": "sounds",
        "label": "아티스트 사전에 없는 팀",
        "hint": "차트 수집으로 만든 사전에 없음",
        "definition": "곡 라벨로 잡힌 팀 중 공유 아티스트 사전에 없는 팀의 수. 사전은 차트 수집에서 만든 "
        "목록이라, 여기 없다는 것이 차트에 없다는 뜻은 아니다.",
    },
}


def _music_artists(music: object) -> list[str]:
    """사운드 라벨 'Artist - Song' → 아티스트(협업은 콤마 분리). UGC('Original audio')는 제외.

    한계(RULES §3): 공식 트랙 라벨만 귀속 · 곡명에 ' - ' 포함 시 오분리 · 표기차 누락.
    """
    if not isinstance(music, str) or " - " not in music:
        return []
    if "original audio" in music.lower():  # username - Original audio = UGC, 아티스트 귀속 아님
        return []
    artist_part = music.rsplit(" - ", 1)[0]
    return [a.strip() for a in artist_part.split(",") if a.strip()]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _engagement(rec: dict[str, object]) -> int:
    return as_int(rec.get("likes")) + as_int(rec.get("comments"))


def _percentile(values: list[int], pct: float) -> float:
    """Linear-interpolation percentile (deterministic; no numpy)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _date(ts: object) -> str:
    return ts[:10] if isinstance(ts, str) and len(ts) >= 10 else ""


def _fill_days(observed: list[str]) -> list[str]:
    """관측된 첫날~마지막날 사이의 **달력 날짜를 전부** 돌려준다(게시물이 0인 날 포함)."""
    if len(observed) < 2:
        return list(observed)
    start = date.fromisoformat(observed[0])
    end = date.fromisoformat(observed[-1])
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def _apply_meta(
    metrics: list[dict[str, object]], charts: list[dict[str, object]]
) -> list[dict[str, object]]:
    """차트·지표에 구획과 문구를 붙이고, 표에 없는 차트는 **떨어낸다**.

    떨어내는 쪽을 기본으로 둔 이유(chart-history와 같다): 표에 없는 차트가 조용히 화면에
    남으면 구획 상한이 의미를 잃는다. 새 차트를 추가하면 `_CHART_META`에 한 줄을 적어야
    하고, 그 한 줄이 "이 차트로 무엇을 답하나"를 먼저 답하게 만든다(R3).
    """
    for m in metrics:
        meta = _METRIC_META.get(str(m.get("label") or ""))
        if not meta:
            continue
        m["section"] = meta["section"]
        m["definition"] = meta["definition"]
        if meta.get("hint"):
            m["hint"] = meta["hint"]
        # 라벨 갈아 끼우기는 **맨 마지막**이다 — 위 조회가 원래 라벨을 키로 쓴다.
        if meta.get("label"):
            m["label"] = meta["label"]

    kept: list[dict[str, object]] = []
    for c in charts:
        meta = _CHART_META.get(str(c.get("id") or ""))
        if meta:
            c.update(meta)
            kept.append(c)
    return kept


def _place_sections(
    metrics: list[dict[str, object]], charts: list[dict[str, object]]
) -> list[dict[str, str]]:
    """실제로 차트가 놓인 구획만 남기고, 구획을 잃은 지표를 되찾아 준다.

    차트는 데이터가 있을 때만 만들어지므로(사운드 라벨이 하나도 없는 스냅샷 등) 구획이
    통째로 비는 날이 있다. 그때 지표가 사라진 구획을 계속 가리키면 화면 어디에도 놓이지
    못한 채 조용히 빠진다 — 렌더러는 활성 구획의 지표만 그린다.
    """
    sections = [dict(s) for s in _SECTIONS if any(c.get("section") == s["id"] for c in charts)]
    # 구획이 하나뿐이면 내비게이션이 할 일이 없다. 그때는 예전처럼 한 줄로 렌더한다(하위 호환).
    if len(sections) < 2:
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


def _spread_summary(artist_posts: Counter[str], attributed: int, n: int) -> dict[str, object]:
    """진입 요약 하나(R2) — 이 태그를 움직인 곡이 **누구의 것인가**.

    이 탭의 주장은 화력의 크기가 아니라 *차트로는 아직 잘 안 보이는 이름이 여기 있다*는
    것이라, 첫 화면에 놓는 도형도 그것이다. 막대에 싣는 값은 게시물 수(셀 수 있는 크기)다
    — 순위처럼 순서만 있는 값은 막대 길이가 될 수 없다(DESIGN §7.3 실측).
    """
    return {
        "type": "bar",
        "id": SUMMARY_ID,
        "title": "곡 라벨로 잡힌 팀",
        "question": "이 태그에서 이름이 도는 팀은 누구인가?",
        "definition": "사운드 라벨 'Artist - Song'의 앞부분을 아티스트로 읽어 그 팀의 게시물 수를 센 값(상위 8팀). "
        "개인이 올린 오디오('Original audio')는 곡으로 세지 않고, 협업 표기와 표기 차이로 일부가 빠진다. "
        "게시물 수이며 재생이나 판매가 아니다.",
        "reliability": {
            "sample": f"곡 라벨로 귀속된 게시물 {attributed}건 / {n}건 · {len(artist_posts)}팀",
            "missing": "곡 라벨이 없거나 개인이 올린 오디오로 표기된 게시물은 아티스트 귀속에서 빠진다",
        },
        "data": [{"name": a, "value": c} for a, c in artist_posts.most_common(8)],
    }


def _fandom_inferences(
    *,
    tag: str,
    n: int,
    attributed: int,
    artist_posts: Counter[str],
    outside: list[str],
    cadence: tuple[list[str], float, float] | None,
    high: int,
    high_eng: int,
    total_eng: int,
) -> list[dict[str, object]]:
    """태그된 자동 추론(R4 · D-039). 전부 관측에서 계산한다.

    허용 어법은 "~와 정합한다"·"~신호가 있다"·"~로 읽힌다"뿐이고, 명령·예측·인과 단정과
    em dash는 scripts/validate_report_data.py가 CI에서 잡는다.
    """
    out: list[dict[str, object]] = []
    grade = "medium" if n >= 100 else "low"

    # ① 사전에 없는 이름 — 이 모듈이 존재하는 이유. 사전의 정체를 limits에 반드시 적는다.
    if outside:
        ranked = sorted(outside, key=lambda a: (-artist_posts[a], a))
        out.append({
            "text": f"차트 수집으로 만든 아티스트 사전에 없는 팀이 이 태그에서 곡으로 퍼지고 있는 신호가 있다. "
            f"{', '.join(ranked[:5])} 등 {len(outside)}팀이다.",
            "basis": f"곡 라벨로 잡힌 {len(artist_posts)}팀 중 {len(outside)}팀이 사전에 없음 · "
            + " · ".join(f"{a} {artist_posts[a]}건" for a in ranked[:5]),
            "sample": f"#{tag} 공개 게시물 {n}건 · 곡 라벨로 귀속된 {attributed}건",
            "confidence": grade,
            "limits": "사전은 차트 수집에서 만든 목록이라 '사전에 없다'가 '차트에 없다'는 뜻이 아니다. "
            "표기가 다르면 같은 팀이 다른 이름으로 세어지고, 공개 표본이라 편향이 있다.",
            "chartId": SUMMARY_ID,
        })

    # ② 게시 흐름의 방향. **창의 성격을 limits에 적는다** — 태그 수집은 과거 게시물을 함께
    #    가져오므로 창의 양 끝이 실제 흐름의 시작·끝과 다를 수 있다.
    if cadence:
        days, early, late = cadence
        if abs(late - early) >= 0.1:
            way = "높은" if late > early else "낮은"
            out.append({
                "text": f"최근 절반 구간의 하루 평균 게시수가 이전 절반보다 {way} 상태와 정합한다.",
                "basis": f"{days[0]}~{days[len(days) // 2 - 1]} 하루 평균 {early:.1f}건 → "
                f"{days[len(days) // 2]}~{days[-1]} 하루 평균 {late:.1f}건",
                "sample": f"{len(days)}일 · 게시물 {n}건",
                "confidence": "low",
                "limits": "해시태그 수집은 과거 게시물을 함께 가져오므로 창의 양 끝이 실제 흐름과 어긋날 수 있다. "
                "창이 짧아 하루의 스파이크 하나로 방향이 뒤집힌다.",
                "chartId": "daily-posts",
            })

    # ③ 참여의 쏠림. 어느 차트에도 매이지 않는 관측이라 chartId를 붙이지 않는다
    #    (렌더러가 카드 밖 맨 아래로 모은다).
    if high and total_eng and high_eng / total_eng >= 0.5:
        out.append({
            "text": f"참여가 소수 게시물에 몰린 것으로 읽힌다. 상위 {high}건이 전체 참여의 "
            f"{100.0 * high_eng / total_eng:.0f}%를 차지한다.",
            "basis": f"상위 {high}건 참여 합 {high_eng:,} / 전체 {total_eng:,}",
            "sample": f"게시물 {n}건",
            "confidence": grade,
            "limits": "계정 규모가 크면 같은 반응률에서도 절대값이 커진다. 이 값은 참여의 분포이지 "
            "인기의 순위가 아니다.",
        })
    return out


def _questions(have: set[str]) -> list[dict[str, str]]:
    """R1 — 이 탭에서 답할 수 있는 질문(상한 4). 끊긴 앵커는 검사기가 잡는다.

    차트는 데이터가 있을 때만 만들어지므로 후보를 실재 여부로 거른다. 그 결과가 셋에
    못 미치면 **요약 도형에 대한 질문으로 채운다** — 요약은 항상 있다.
    """
    kept = [
        q
        for q in (
            {"q": "이 태그에서 이름이 도는 팀은 누구인가?", "chartId": SUMMARY_ID},
            {"q": "이 태그는 지금 늘고 있나?", "chartId": "daily-posts"},
            {"q": "어떤 곡이 이 태그를 움직이나?", "chartId": "top-sounds"},
            {"q": "이 게시물들은 어떤 태그를 같이 다나?", "chartId": "co-hashtags"},
        )
        if q["chartId"] in have
    ]
    for spare in (
        {"q": "곡 라벨로 몇 팀이 잡혔나?", "chartId": SUMMARY_ID},
        {"q": "가장 많은 게시물에 쓰인 팀은 누구인가?", "chartId": SUMMARY_ID},
    ):
        if len(kept) >= 3:
            break
        kept.append(spare)
    return kept


def _reliability(tag: str, n: int, source: str, fetched: str, days: list[str]) -> dict[str, str]:
    """R8 — 화면 전체의 기본 신뢰도. 차트별 값이 이것을 필드 단위로 덮는다."""
    window = f" · {days[0]}~{days[-1]}" if days else ""
    return {
        "sample": f"#{tag} 공개 게시물 {n}건{window}",
        "accuracy": "좋아요·댓글은 수집 시점의 공개 표시값. 귀속과 분류의 정확도는 미측정",
        "missing": "태그를 붙이지 않았거나 이번 수집에 들어오지 않은 게시물은 이 표본에 없다",
        "engine": f"{source} · 스냅샷 {fetched}",
    }


def _not_answered() -> list[str]:
    """R7 — 이 화면이 **답하지 않는** 질문. 한계 서술(insights)과 다르다."""
    return [
        "이 곡이 차트에 오를지. 이 화면은 게시량과 반응까지만 다룬다",
        "틱톡·유튜브 쇼츠의 확산. 이 화면이 보는 표면은 인스타그램 해시태그 하나뿐이다",
        "게시물을 올린 쪽이 팬인지 홍보인지. 공개 게시물에서 계정 성격을 구분하지 않는다",
        "실제로 얼마나 들었는지. 게시수와 좋아요는 재생이나 판매가 아니다",
        "태그를 붙이지 않은 확산. 태그가 없으면 이 표본에 들어오지 않는다",
    ]


def build_report(
    records: list[dict[str, object]],
    *,
    hashtag: str,
    provenance: dict[str, object],
    generated_at: str,
    high_pct: float = 90.0,
    momentum_min_days: int = 2,
    top_tags: int = 10,
    top_sounds: int = 8,
    entity_index: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    n = len(records)
    source = str(provenance.get("source") or "Instagram (Apify)")
    fetched = str(provenance.get("fetched_at") or "snapshot")
    params_obj = provenance.get("params")
    params = params_obj if isinstance(params_obj, dict) else {}
    tag = (hashtag or str(params.get("hashtag") or "")).lstrip("#")

    metrics: list[dict[str, object]] = [{"label": "게시물 수", "value": n, "unit": "건"}]
    charts: list[dict[str, object]] = []
    insights: list[str] = []

    if n == 0:
        # 빈 스냅샷도 계약을 지킨다(R1·R2·R7·R8). 요약 도형은 빈 막대로 남아 "데이터 없음"을
        # 스스로 말하고, 구획은 선언하지 않는다 — 놓을 차트가 없으면 내비게이션도 없다.
        insights.append("게시물 없음. 입력 스냅샷과 해시태그 확인 필요")
        charts = _apply_meta(metrics, charts)
        _place_sections(metrics, charts)
        return _wrap(
            tag,
            source,
            fetched,
            n,
            generated_at,
            metrics,
            charts,
            insights,
            _recos(),
            {
                "summary": _spread_summary(Counter(), 0, 0),
                "questions": _questions({SUMMARY_ID}),
                "notAnswered": _not_answered(),
                "reliability": _reliability(tag, n, source, fetched, []),
            },
        )

    eng = [_engagement(r) for r in records]
    likes = [as_int(r.get("likes")) for r in records]
    comments = [as_int(r.get("comments")) for r in records]
    reels = sum(1 for r in records if r.get("type") == "reel")
    threshold = _percentile(eng, high_pct)
    high = sum(1 for e in eng if e >= threshold)

    metrics.append({"label": "총 참여", "value": sum(eng), "unit": "likes+comments"})
    metrics.append({"label": "중앙값 좋아요", "value": int(median(likes)), "unit": "likes"})
    metrics.append({"label": "중앙값 댓글", "value": int(median(comments)), "unit": "comments"})
    metrics.append(
        {
            "label": "고참여 게시물",
            "value": high,
            "unit": "건",
            "hint": f"이 표본 상위 {round(100 - high_pct)}% 기준선 ≥ {int(threshold):,}",
        }
    )
    metrics.append({"label": "릴스 비중", "value": round(100 * reels / n), "unit": "%"})

    # Chart 1 — top co-occurring hashtags (spread/reach signal)
    tag_counts: Counter[str] = Counter()
    for r in records:
        hs = r.get("hashtags")
        if isinstance(hs, list):
            for h in hs:
                if isinstance(h, str) and h and h != tag:
                    tag_counts[h] += 1
    top_co = tag_counts.most_common(top_tags)
    tagged = sum(1 for r in records if isinstance(r.get("hashtags"), list) and r["hashtags"])
    if top_co:
        charts.append(
            {
                "type": "bar",
                "id": "co-hashtags",
                "reliability": {"sample": f"해시태그가 붙은 게시물 {tagged}건 / {n}건"},
                "data": [{"name": f"#{h}", "value": c} for h, c in top_co],
            }
        )

    # Chart 2 — daily posting cadence (line); posting-acceleration if it spans enough days
    #
    # ⚠ 관측된 날짜만 x축에 세우면 **비어 있는 날이 화면에서 사라지고**, 선이 그 위를
    # 곧게 지나가 "그동안 계속 그 정도였다"로 읽힌다(2026-07-30 육안 검사: 6/29와 7/9
    # 사이 열흘이 한 칸으로 접혀 있었다). 창 안쪽의 빈 날은 결측이 아니라 **0건**이다
    # — 표본은 최신순이라 창 안에 있는 날의 게시물은 이미 다 들어와 있다. 그래서 달력
    # 날짜를 전부 채운다. 창의 **첫날만** 수집 상한에 잘린 경계이고, 그 사실은 limits에 있다.
    day_counts: Counter[str] = Counter(d for r in records if (d := _date(r.get("timestamp"))))
    observed = sorted(day_counts)
    days = _fill_days(observed)
    cadence: tuple[list[str], float, float] | None = None
    if len(observed) >= max(2, momentum_min_days):
        charts.append(
            {
                "type": "line",
                "id": "daily-posts",
                "reliability": {
                    "sample": f"{days[0]}~{days[-1]} {len(days)}일(게시물이 있는 날 {len(observed)}일) · {n}건"
                },
                "data": {
                    "x": days,
                    "series": [{"name": f"#{tag} 게시물", "values": [day_counts[d] for d in days]}],
                },
            }
        )
        mid = len(days) // 2
        early_avg = sum(day_counts[d] for d in days[:mid]) / mid
        late_avg = sum(day_counts[d] for d in days[mid:]) / (len(days) - mid)
        cadence = (days, early_avg, late_avg)
        metrics.append(
            {
                "label": "게시 가속",
                "value": round(late_avg - early_avg, 1),
                "unit": "건/일",
                "hint": "최근 절반 − 이전 절반",
            }
        )

    # Chart 3 — trending sounds (challenge/dance early signal), when present
    #
    # 🔴 UGC 라벨(`<계정명> - Original audio`)은 **화면에 싣지 않는다**. 그 문자열의 앞부분은
    # 곡이 아니라 **개인 계정명**이고, 이 모듈은 팬 개인을 다루지 않는다(RULES §5 · AGENTS §5).
    # fetch가 `ownerUsername`을 폐기하는데 사운드 라벨로 같은 것이 새어 나오고 있었다
    # (2026-07-30 육안 검사에서 막대 4개가 계정명이었다). 구획 안내문과도 어긋난 상태였다.
    labeled = 0
    sound_counts: Counter[str] = Counter()
    for r in records:
        s = r.get("music")
        if not isinstance(s, str) or not s:
            continue
        labeled += 1
        if "original audio" not in s.lower():
            sound_counts[s] += 1
    ugc = labeled - sum(sound_counts.values())
    top_snd = sound_counts.most_common(top_sounds)
    if top_snd:
        charts.append(
            {
                "type": "bar",
                "id": "top-sounds",
                "reliability": {
                    "sample": f"곡 라벨이 있는 게시물 {sum(sound_counts.values())}건 / {n}건",
                    "missing": f"개인이 올린 오디오로 표기된 {ugc}건은 곡이 아니라 제외(계정명은 싣지 않는다)",
                },
                "data": [{"name": s, "value": c} for s, c in top_snd],
            }
        )

    # 진입 요약(R2) — sound→artist join (pre-mainstream 선행신호, RULES §3):
    # 사운드 라벨의 공식 아티스트를 공유 entity-master로 귀속 → 차트로 안 잡히는 소셜 활성 표면화.
    # 첫 화면의 도형 하나가 이것이므로 `charts`에는 싣지 않는다.
    artist_posts: Counter[str] = Counter()
    attributed = 0
    for r in records:
        names_of = _music_artists(r.get("music"))
        attributed += 1 if names_of else 0
        for a in names_of:
            artist_posts[a] += 1
    outside: list[str] = []
    if artist_posts:
        metrics.append({"label": "사운드 확산 아티스트", "value": len(artist_posts), "unit": "팀"})
        if entity_index:
            outside = [a for a in artist_posts if match(entity_index, a) is None]
            metrics.append({"label": "로스터 밖 확산", "value": len(outside), "unit": "팀"})
        insights.append(
            "사운드→아티스트 귀속은 공식 트랙 라벨 기준('Original audio'·협업 표기·표기차로 일부 누락). 참고 신호"
        )

    # Insights — signals with explicit limits (증폭 원칙: 신호 제시, 단정 금지 — §0/§5)
    insights.append(f"#{tag} 공개 게시물 {n}건 기준 · 총 참여 {sum(eng):,}(좋아요+댓글).")
    insights.append(
        f"중앙값 좋아요 {int(median(likes)):,} · 댓글 {int(median(comments)):,} "
        "· 평균 대신 중앙값 사용(바이럴 1건에 덜 흔들림)"
    )
    if top_co:
        names = ", ".join(f"#{h}" for h, _c in top_co[:3])
        insights.append(f"공동 해시태그 상위: {names} · 확산과 도달 맥락 참고용")
    if len(days) < max(2, momentum_min_days):
        insights.append("하루 스냅샷 기준. 게시 가속은 여러 날 쌓인 뒤 산출")
    insights.append(
        "공개 인스타그램 표본이라 편향 가능. 공식 지표가 아니며 인기·품질의 단정 아님"
    )

    charts = _apply_meta(metrics, charts)
    sections = _place_sections(metrics, charts)
    extra: dict[str, object] = {
        "summary": _spread_summary(artist_posts, attributed, n),
        "questions": _questions({str(c["id"]) for c in charts} | {SUMMARY_ID}),
        "notAnswered": _not_answered(),
        "reliability": _reliability(tag, n, source, fetched, days),
        "inferences": _fandom_inferences(
            tag=tag,
            n=n,
            attributed=attributed,
            artist_posts=artist_posts,
            outside=outside,
            cadence=cadence,
            high=high,
            high_eng=sum(e for e in eng if e >= threshold),
            total_eng=sum(eng),
        ),
    }
    if sections:
        extra["sections"] = sections

    return _wrap(tag, source, fetched, n, generated_at, metrics, charts, insights, _recos(), extra)


def build_signal_series(
    records: list[dict[str, object]],
    *,
    entity_index: dict[str, dict[str, object]] | None,
    generated_at: str,
    hashtag: str = "",
    hashtag_index: dict[str, str] | None = None,
) -> dict[str, object]:
    """Per-(date × artist) social-buzz series for the cross-module bridge (signal-bridge).

    Buckets IG posts by day and by the SAME shared entity-master canonical the
    single-day report uses — so chart-history's chart-rank series joins on the
    identical key. Attribution is TWO evidence paths (RULES §3, D-013):
    ① sound label 'Artist - Song' (D-010) · ② watchlist hashtag (#izna → izna) —
    covers pre-mainstream posts whose sound is UGC('Original audio'). One post
    counts once per act (set semantics). Also emits magnitude (engagement sum) and
    drivers (top sounds·tags per act) for the 얼마나/왜 layer. Un-rostered artists
    keep their raw label (roster=false). Counts only; no verdict (§0).
    Contract: modules/signal-bridge/SPEC.md.
    """
    idx = entity_index or {}
    tag_idx = hashtag_index or {}
    day_artist: dict[str, dict[str, int]] = {}  # date → {canonical: post count}
    roster: dict[str, bool] = {}
    engagement: dict[str, int] = {}
    drv_sounds: dict[str, Counter[str]] = {}
    drv_tags: dict[str, Counter[str]] = {}
    for r in records:
        d = _date(r.get("timestamp"))
        if not d:
            continue
        attributed: dict[str, bool] = {}  # key → rostered? (this post)
        for a in _music_artists(r.get("music")):
            hit = match(idx, a)
            key = str(hit["key"]) if hit else a
            attributed[key] = attributed.get(key, False) or hit is not None
        tags = r.get("hashtags")
        matched_tags: dict[str, str] = {}
        if isinstance(tags, list):
            for h in tags:
                if isinstance(h, str) and h.lower() in tag_idx:
                    key = tag_idx[h.lower()]
                    attributed[key] = True  # watchlist act = tracked universe
                    matched_tags[key] = h.lower()
        eng = _engagement(r)
        music = r.get("music")
        for key, rostered in attributed.items():
            day_artist.setdefault(d, {})[key] = day_artist.setdefault(d, {}).get(key, 0) + 1
            roster[key] = roster.get(key, False) or rostered
            engagement[key] = engagement.get(key, 0) + eng
            if isinstance(music, str) and music and "original audio" not in music.lower():
                drv_sounds.setdefault(key, Counter())[music] += 1
            if key in matched_tags:
                drv_tags.setdefault(key, Counter())[f"#{matched_tags[key]}"] += 1
    dates = sorted(day_artist)
    keys = sorted({k for day in day_artist.values() for k in day})
    series = {k: [day_artist.get(d, {}).get(k, 0) for d in dates] for k in keys}
    drivers = {
        k: {
            "sounds": [s for s, _c in drv_sounds.get(k, Counter()).most_common(3)],
            "tags": [t for t, _c in drv_tags.get(k, Counter()).most_common(3)],
        }
        for k in keys
    }
    window = f"{dates[0]}..{dates[-1]}" if dates else ""
    return {
        "moduleId": MODULE_ID,
        "signal": "social-buzz",
        "unit": "posts/day",
        "higherIsStronger": True,
        "dates": dates,
        "series": series,
        "roster": {k: roster[k] for k in sorted(roster)},
        "engagement": {k: engagement[k] for k in sorted(engagement)},
        "drivers": drivers,
        "provenance": {
            "source": "IG hashtag sound+tag→artist (fandom-pulse)",
            "hashtag": hashtag.lstrip("#"),
            "generatedAt": generated_at,
            "window": window,
            "attribution": "sound-label + watchlist-hashtag (D-013)" if tag_idx else "sound-label",
            "note": "일자별 게시수 · 사운드 라벨 + 워치리스트 해시태그 귀속 · 참고 신호(단정 아님)",
        },
    }


def _recos() -> list[str]:
    return [
        "특정 그룹/컴백 해시태그로 fetch하면 그 캠페인의 화력·참여 신호를 집중 관측할 수 있습니다.",
        "다일 축적(collect)하면 게시 가속(모멘텀)을 실데이터 라인으로 볼 수 있습니다(v2).",
        "고참여 기준값은 도메인 판단으로 조정 가능. 기준은 조정 가능한 가설",
    ]


def _wrap(
    tag: str,
    source: str,
    fetched: str,
    n: int,
    generated_at: str,
    metrics: list[dict[str, object]],
    charts: list[dict[str, object]],
    insights: list[str],
    recommendations: list[str],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    # 부제에서 기계 문자열을 걷어낸다(DESIGN §6.1). 액터 id와 초 단위 타임스탬프는 읽는
    # 사람의 판단을 바꾸지 않는다 — 정확한 출처는 신뢰도 라인의 `engine`이 그대로 들고 있다.
    where = source.split(" / ")[0].strip() or source
    when = fetched[:10] if len(fetched) >= 10 and fetched[4] == "-" else fetched
    return {
        "moduleId": MODULE_ID,
        "title": f"팬덤 펄스 · #{tag}",
        "subtitle": f"{where} 공개 해시태그 · 수집 {when} · {n}건",
        "generatedAt": generated_at,
        "metrics": metrics,
        "charts": charts,
        "media": [],
        "insights": insights,
        "recommendations": recommendations,
        **(extra or {}),
    }
