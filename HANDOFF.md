# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 🧭 다음 행선지 (재개점)

> **A2 본편이 닫혔다**(2026-07-31 · [`Handoffs/2026-07-31-a2-main-contemporaneous-cohorts.md`](Handoffs/2026-07-31-a2-main-contemporaneous-cohorts.md)). 동시대(2021-10 앵커) US·KR 두 프레임 위에서 규칙 미확정 임펄스 전부 실측 → **genre-impulse v1.2 규칙 3종**(hyperpop + 신규 ukg-origin-shuffle·moombahton-kr-tropical) · 커버리지 3/10. amapiano는 정답지 7/7인데 **베이스라인 20%라 등재 철회**(정답지가 극단이어도 그 극단이 붐비면 규칙이 아니다 — RULES §2.2).
> 시각화는 계속 닫혀 있다(D-041~D-048 · 정본 [`DESIGN.md`](DESIGN.md) §7).

> **H3이 닫혔다**(2026-07-31 · [`Handoffs/2026-07-31-h3-verdict-and-h4-gate.md`](Handoffs/2026-07-31-h3-verdict-and-h4-gate.md) · D-049). 🔴 **실패(3/12 = 25% · 기준 60%) → 하이햇 축 확장을 여기서 멈춘다. 세 번째 정의를 만들지 않는다.** 결론은 "통설이 틀렸다"가 아니라 **관측 한계의 진술**이다: 저지클럽의 하이햇 서명은 30초 발췌·믹스 고역·마디 평균 온셋 포락으로는 잡히지 않는다.
> **콜드 실행을 기다리지 않고 났다** — burst·active는 저장된 32칸 프로파일만의 함수라 소급된다(`rhythm.backfill_hihat_axes`). 덕분에 H3은 **H1이 판정된 바로 그 스냅샷**(코호트·정답지 동일)에서 돌았고, 그게 "새 정의가 나은가"에 대한 더 옳은 비교다.

> **H4도 닫혔다**(같은 날 오전 · D-050). 09:00 daily가 **v4 첫 콜드 실행으로 전 레그 완주**(부분 실패 0 · 09:25 종료)해 코호트가 채워졌고, 전날 세운 게이트를 **코드 변경 없이** 돌렸다. 🔴 **채택 안 함 — ①만 통과하고 ②가 깨졌다**(탈락 1곡 → **2곡**). 다만 이 실패는 H3과 종류가 다르다: **겨눈 곡은 실제로 구했다**(DJ Lil Man 0.4587 → 0.7396). 다른 두 곡이 대신 떨어졌을 뿐이다.
> 🔺 **배운 것 — 바닥이 함께 올라간다.** 2마디 분할은 코호트 전체를 올리고(중앙 0.8268 → 0.8798) 바닥은 자기 분포 p10이라 **바닥도 오른다**(0.4792 → 0.6756). **고르게 개선해도 탈락은 줄지 않는다 — 잘리는 곡이 바뀔 뿐이다.** 조건 ②와 상대 바닥을 함께 쓰는 형식 자체가 원리적으로 만족되기 어렵다(§3.8.4.3의 "백분위 바닥 = 기각률"의 직접 실증). **그래도 판정은 바꾸지 않았다.**
> **H3 복제**: H1 3/12→3/12 · H3 3/12→**5/12** · H2 0/3→1/3. **판정은 어느 코호트에서도 안 뒤집힌다**(기준 8). 다만 **여유는 코호트에 의존한다** — 단일 수치를 인용하지 말 것. 이 복제를 근거로 **재도전하지 않는다**(모집단을 바꾸는 것 = 정의를 바꾸는 것).

✅ **사전 등록 축 2종이 전부 판정 완료됐다** — 하이햇 축 확장(H3)도 2마디 분할(H4)도 여기서 멈춘다. **세 번째 정의를 만들지 않는다.**

✅ **빌보드 궤적 → 임펄스 원장도 형식이 섰다**(D-051). 후보 26쌍 대조표 + 확정 파일까지. **값(어느 셀인가)은 도메인 소유자 대기** — 자동 배정은 스키마가 이미 금지한 것이다.

⏳ **1순위 — 열린 것은 대기 목록뿐이다.** 다음 후보는 **저지클럽 정답지 미해석 8곡 대체**(복제의 검정력) 또는 **케이스별 동시대 앵커 확장**(easy-listening 2023 — US는 `billboard_ingest`로 즉시).
- 🔺 **원장에 남은 열린 물음 하나**: 조건 ②(정답지 탈락 0)와 **상대 바닥(자기 분포 p10)**을 함께 쓰는 형식은 축을 개선해도 만족되기 어렵다. 절대 바닥이든 다른 형식이든 **새로 사전 등록**할 일이고, 값어치 판단은 도메인 소유자 몫이다.
- 판정 정본이 둘로 나뉜다: 스템 축 = `stem_gate_result_v2.json`(daily는 스템을 안 돌려 라이브 코호트에서 `unmeasured`가 맞다) · 격자·하이햇 축 = `stem_gate_result_2026-07-31.json`.
- 넘어야 할 선: ① 분리 실패 검출 ② **정답지 탈락 0곡**. 같은 대역 1마디 기준선은 ①만족·②**1곡 탈락**으로 fail이다 — 2마디가 넘어야 할 선은 "1곡보다 적음"이 아니라 **0곡**이다(조건 ②는 절대값).
- H3 복제는 **재도전이 아니라 확인**이다. 결과가 갈리면 적을 것은 "통과했다"가 아니라 "판정이 코호트에 의존한다"이며 그것은 축의 약점이다(RULES §3.1.5.4에 결과보다 먼저 적어 뒀다).

그다음 대기 목록 우선 후보: **빌보드 궤적 → 임펄스 원장** · **저지클럽 정답지 미해석 8곡 대체**(v4 재취득에서도 그 8곡만 iTunes 부재로 남았다 — H1·H3 둘 다 같은 12곡에서 판정됐다) · **케이스별 동시대 앵커 확장**(easy-listening은 2021 앵커가 동시대가 아니라 판정 유보 — US는 `billboard_ingest`로 즉시, KR은 Wayback 커버리지가 병목).

### 탭별 구획 (지금 화면의 모양)

| 탭 | 요약 도형(R2) | 구획 |
|---|---|---|
| sonic-profile | 6축 레이더 | 템포·박 · 리듬·태그 · 날짜별 추이 · 같은 곡만 · 발매 시기 · 워치리스트 |
| chart-history | 플랫폼 커버리지 레이더 | 플랫폼 · 규모 · 지리 · 신인 |
| fandom-pulse | 곡 라벨로 잡힌 팀(bar) | 게시 흐름 · 사운드 · 게시물 |
| yt-pulse | 팀별 대표 일 조회(bar) | 쌓인 조회 · 새 영상 |
| genre-impulse | **커버리지**(규칙 3 / 실측·미확정 4 / 작업 중 1 / 없음 2) | 매치 · 기준 |
| signal-bridge | **선행 62 : 지연 44 : 동시 8** | 선행·지연 · 한 팀 보기 · 차트 밖 · 기준 |

- **구획 수는 질문의 수다.** 질문이 둘인 탭에 구획 넷을 만들지 않았다(yt-pulse·genre-impulse는 2). 거꾸로 sonic-profile이 여섯인 것은 실제로 여섯을 묻기 때문이고, **상한(차트 3개)이 그 구조를 강제했다** — 차트 15개를 담으려면 최소 다섯이 필요하다.
- **구획 머리글은 한 줄에 든다**(§7.1.1). 폭이 `24ch`라 24~26자면 마지막 줄에 두 글자만 남는다. 채택 탭들의 질문은 15~21자다.
- **요약 도형은 radar가 아니어도 된다.** 하중을 받는 것은 도형 종류가 아니라 그 탭에서 가장 오해받기 쉬운 지점이다 — genre-impulse는 매치가 아니라 **커버리지**, signal-bridge는 선행 수가 아니라 **반례를 포함한 구성**이 요약이다.

### 시각화 작업 — 전부 완료

| 항목 | 결과 |
|---|---|
| 구획 | ✅ **6/6 탭**(D-043·D-044·D-047). 머리글 21개 전부 한 줄 |
| 인터랙션 | ✅ 크로스헤어·통합 툴팁·키보드·표 뷰(D-045) · **질문 앵커까지 스모크가 센다**(D-047) |
| 모션 | ✅ 쓰는 곳 넷 · 기각 여섯 · reduced-motion 전역 집행(D-046 · §7.7) |
| 긴 목록 | ✅ **가운데를 접는다**(D-048). `leadlag` 114행 → 30행 · 반례(양 끝) 보존 · 이름으로 좁히기 |
| 용어 설명 | ✅ `title` 속성 → 보이는 `Terms` 펼침(D-048). 리포트 계약 변경 **불필요했다** |
| 표면 인색 | ✅ 원장이 "쓰지 말라"고 적은 축을 코드가 막는다(D-048 · `_NO_MEDIAN_OR_RANK`) |
| 카피 규율 | ✅ em dash·머리 대괄호 태그를 **검사기가 센다**(D-048). 37건 수정 |

**남은 표시 판단 하나**: `sonic-profile` 타일 **23개를 더 줄일까**. 자리는 정해졌고(D-047), 무효인 축은 막혔다(D-048). 순수한 A&R 취향 판단이라 화면을 보고 답하면 된다.

⚠ **눈으로만 잡히는 결함이 여섯 라운드에 걸쳐 스물한 건 나왔다** — 전부 정적 게이트 4종과 탭 스모크를 **통과한 상태**였다.
- 1차(파일럿) 5건: 색 순환 · 기준 링 겹침 · 결측 마커 위치 · 순위를 막대 길이로 · 타일 값 잘림.
- 2차(6탭 확산) 6건: 부호를 막대에 · 역방향 축을 막대에 · 격자 색 방향 반대 · 미관측 구간을 0으로 · 계정명 노출 · 저장 키 노출. 공통점은 **그림의 방향과 주장의 방향이 어긋난 것**(§7.5).
- 3차(인터랙션) 5건: **툴팁이 표면 없는 맨 텍스트**(visx `unstyled`가 우리 `style`까지 버린다 — D-041의 요약 도형 툴팁이 그때부터 이 상태였다) · 결측 안내선 91개가 배경 해치 · `+127일`이 두 줄로 접힘 · **그리고 다섯 중 둘은 이 세션에 새로 쓴 코드에서 나온 것**(ⓘ 툴팁이 탭 정지 110개를 만든 것 · 사유 칸을 좁게 잡아 자른 것). 규율은 §7.6.

- 4차(모션) 1건: **행 재정렬 애니메이션이 이름과 숫자를 포갰다**(22px 행 셋이 서로를 통과 · `33`과 `14`가 한 줄에). 이것도 **이 세션에 새로 쓴 코드**에서 나왔다. 규율은 §7.7.
- 5차(sonic-profile 구획) 2건: 구획 머리글이 접혀 **마지막 줄에 `나?` 두 글자만** 남은 것(§7.1.1) · 🔴 **질문을 눌러도 아무 데도 가지 않은 것**(6탭 11개 질문 · 구획 도입 이후 줄곧 · D-047). 뒤엣것은 스크린샷으로도 안 보인다 — **눌러 봐야** 보이고, 이제 `smoke:tabs`가 대신 누른다.
- 6차(표시 결정 3건) 2건: 머리글 접힘이 **다른 두 탭에도 6건 더** 있었고(전 탭 실측으로 잡음 · 21개 전부 한 줄로) · 🔴 **원장이 "쓰지 말라"고 적은 축이 세 표면에 올라가 있던 것**(`danceability` · 리포트가 그려 놓고 "쓰지 마십시오"라고 안내하던 상태 · D-048). 뒤엣것은 눈이 아니라 **원장과 화면을 대조해야** 보인다.

**탭마다, 구획마다 렌더를 실제로 볼 것.** 스물한 건 중 정적 게이트가 잡은 것은 없다.
- 3차에서 배운 것: **인터랙션 결함은 스크린샷 한 장으로도 안 보인다**(마우스를 올려야 나타난다) — 그래서 `smoke:tabs`가 대신 센다.
- 5차에서 배운 것: **화면이 자기 사용법대로 동작하는지는 눌러 봐야 안다.** 앵커가 깨져도 콘솔 에러가 나지 않고 렌더는 완벽하다. 그래서 `smoke:tabs`가 질문을 실제로 누른다.
- 4차에서 배운 것: **모션 결함은 그보다 한 겹 더 안쪽이다.** 정지 스크린샷은 멀쩡했다(끝난 뒤 상태는 정확했으므로). **중간 프레임**을 잡아야 보였고, 그것이 상시 상태라는 것은 키가 아니라 **마우스로 실제 드래그해 보고** 알았다 — 연속 입력은 이산 입력으로 재현되지 않는다.
- 6차에서 배운 것: **원장에 금지를 적는 것과 표면에서 빼는 것은 다른 일이다.** RULES가 "쓰지 말라"고 적어 둔 축이 타일·격자·비교 막대 셋 다에 올라가 있었고, 리포트는 그것을 그려 놓고 읽는 사람에게 쓰지 말라고 안내하고 있었다. **경고를 붙여 면피하는 형태를 찾으려면 원장과 화면을 나란히 놓고 대조해야 한다.**
- **새로 고친 코드도 같은 눈으로 다시 볼 것**(3차의 절반 · 4차의 전부가 그렇게 나왔다).

### 새 모듈을 붙일 때 (복제 순서)

1. **그 탭이 답하는 질문을 먼저 세어 본다.** 그 수가 곧 구획 수다. 한 구획에 차트가 4개면 하나는 답이 겹치는 것이고, 검사기가 3에서 멈춰 세운다.
2. 모듈의 report 빌더에 `_SECTIONS` · `_CHART_META`(`section` 포함) · `_METRIC_META`/`_METRIC_SECTIONS` 세 표를 두고 문구를 **거기에만** 모은다. **타일에 `section`을 빠뜨리면 화면에서 조용히 사라진다**(대시보드가 활성 구획으로 거른다) — sonic-profile은 배정이 살아남지 못한 타일을 첫 구획으로 내려 보낸다(계산 코드 사이에 흩으면 카피 검토가 불가능해진다). 요약·질문·notAnswered·reliability·inferences는 그 아래 헬퍼로.
3. `scripts/validate_report_data.py`의 `ADOPTED_MODULES`에 한 줄 추가 → 그 순간부터 R1~R8이 하드 게이트.
4. 게이트: `validate_report_data.py`(+`--selftest`) · `ruff` · `pyright` · `tsc` · `next lint` · `npm run smoke:tabs`(구획까지 돌고 **인터랙션**과 **질문 앵커**까지 센다 — 크로스헤어 히트 타깃 · 포인터와 키보드 양쪽 툴팁 · 툴팁 표면 · 떠나면 닫힘 · **질문을 눌러 대상 카드에 실제로 도착하는지**) · **라이트/다크 육안**.
   - 새 차트 프리미티브를 만들면 `data-plot="…"` 표식을 단다. 히트 타깃으로만 세면 **없는 것을 셀 수 없어** 검사가 순환한다.
5. 빈 입력에서도 계약이 서는지 본다(요약은 빈 도형으로 남고, 놓을 차트가 없으면 구획을 선언하지 않는다). 라이브 수집이 하루 비는 것은 정상이고, 그때 CI가 깨지면 안 된다.

---

## 현재 위치 (2026-07-30 기준)

- 프로젝트: `C:\Projects\artist-intelligence`. 로컬: Python 3.14.5 · Node 24 · **Windows(win32/AMD64)**.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식 / 도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 6종** 모두 핵심 흐름(`모듈 CLI → 스키마 유효 report.json → 대시보드`) 관통: chart-history v5 · fandom-pulse v3.1 · signal-bridge v2 · yt-pulse v1 · **sonic-profile v4** · **genre-impulse v1.2**(규칙 3종 · high_all 조합 · 커버리지 4구획).
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(**D-036** 차트 페이로드 제약 · **D-041** 시각화 필드 · **D-043** 구획) + PII 게이트 + `packages/entity-master`.
- **시각화 계약 채택**: **6/6 완료**(D-044). 강제 경계는 `scripts/validate_report_data.py`의 `ADOPTED_MODULES`(D-042) — 새 모듈은 여기 한 줄로 계약에 들어온다.
- **디자인 스킬 벤더링 완료**: `.claude/skills/`에 `frontend-design` + 모션 4종(MIT · LICENSE 동봉). ✅ **커밋됐다**(13파일, `bd83e87`) — "미추적이라 커밋 여부가 확인 대상"이라고 적혀 있었지만 그 커밋에 이미 들어가 있었다. 결정할 것이 남아 있지 않다.
- ✅ **git 정리 완료**: 열린 PR **0**. 최근 세션 이력은 [`Handoffs/2026-07-31-a2-main-contemporaneous-cohorts.md`](Handoffs/2026-07-31-a2-main-contemporaneous-cohorts.md)(A2 본편·규칙 2종 등재·amapiano 철회), 그 앞이 [`Handoffs/2026-07-30-preregistered-roll-continuity.md`](Handoffs/2026-07-30-preregistered-roll-continuity.md)(롤 연속성·2마디 블록 사전 등록), 그 앞이 [`Handoffs/2026-07-30-delegated-display-decisions.md`](Handoffs/2026-07-30-delegated-display-decisions.md)(표시 결정 3건 + 카피 게이트), 그 앞이 [`Handoffs/2026-07-30-sonic-profile-sections.md`](Handoffs/2026-07-30-sonic-profile-sections.md)(구획 여섯 + 앵커 게이트), 그 앞이 [`Handoffs/2026-07-30-motion-discipline.md`](Handoffs/2026-07-30-motion-discipline.md)(모션 규율 + reduced-motion 안전망), 그 앞이 [`Handoffs/2026-07-30-interaction-crosshair-tooltip.md`](Handoffs/2026-07-30-interaction-crosshair-tooltip.md)(인터랙션 + 스모크 게이트), 그 앞이 [`Handoffs/2026-07-30-visualization-six-tabs.md`](Handoffs/2026-07-30-visualization-six-tabs.md)(6/6 채택 · 값의 방향), 그 앞이 [`Handoffs/2026-07-30-visualization-pilot-and-chart-history.md`](Handoffs/2026-07-30-visualization-pilot-and-chart-history.md)(시각화 착수 → 두 탭).
- **프리미티브 일반화**(D-044 딸린 결과): `Heatmap`이 순위 전용에서 벗어나 값의 방향을 payload로 받는다(`scale: "rank" | "value"` + 범례 문구). `palette.seqColor`가 그 공통 램프다. chart-history의 순위 격자 4종은 기본값이라 무회귀.
- **인터랙션 프리미티브**(D-045): `ChartTooltip.tsx`가 `show`(마크 기준)와 `showAt`(좌표 기준 — 크로스헤어처럼 스냅된 위치)을 낸다. 🔴 `unstyled`를 쓰지 않는다(우리 `style`까지 버린다). 라인차트는 표 뷰까지 갖췄고, 격자는 `<th scope>`로 표 의미가 서 있다.
- **모션 규율**(D-046 · §7.7): 쓰는 곳 넷 · 기각 여섯. `prefers-reduced-motion`은 **`globals.css` 전역 규칙 하나**가 집행한다 — CSS 전환은 컴포넌트에서 다시 묻지 않는다. CSS 밖의 예외 둘만 호출부에서 묻는다: `motion/react`의 JS 애니메이션(`useReducedMotion`) · `scrollIntoView({behavior})`(명시값이 CSS를 이긴다).

## 🔴 가동 중 — 전향 실증 자동 수집 (매일 09:00 + 2시간 간격 재시도)

- **Task Scheduler `AI-daily-collect`** → `scripts/daily_collect.ps1`. 설정 정본은 [`scripts/register_task.ps1`](scripts/register_task.ps1)(멱등).
- **8단계**: spotify · apple · youtube · shazam(무료) → social(유료 $3/일) → yt → sonic(프리뷰·무보관) → genre-impulse.
- **재개 가능**(D-018): `data/live/state/run_<date>.json`. 완주일 재실행 = no-op. **가드**: PAUSE 파일 · `experiment_end=2026-08-19` · `AI_DRYRUN=1`. 중단: `schtasks /Delete /TN "AI-daily-collect" /F`.
- ⚠ **다음 sonic 레그(07-31 09:00)가 콜드 실행이다** — `RHYTHM_FEATURE_SET` v4(D-038: HOP 128 · 32칸 격자)로 캐시가 무효화됐다. 프리뷰 ~200건 재취득(무료). **정상 동작이며 이 실행이 32칸 격자와 하이햇 축을 라이브 스냅샷에 채운다.**
  - **원인 확정(2026-07-31)**: 07-30 실행이 v3였던 이유 = daily(09:00)가 v4 커밋(`d2f8eca`, 12:34)보다 **먼저** 돌았다. §3.1.5.4 사전 등록이 데이터보다 앞선 것은 그대로 사실이다.
  - 참고: A2 본편의 연구 코호트(케이스 101곡 + US 98 + KR 98)는 이미 v4로 취득됐다(연구 캐시 `data/research/genre-impulse/cache.json` — 라이브 캐시와 별개라 콜드 실행 비용은 그대로다).
  - 이 실행이 채우는 축이 **6종으로 늘었다**: 기존 4종 + 사전 등록한 `hihat_roll_burst_ratio`·`hihat_active_ratio`, 그리고 `bar_profile_split_half_2bar`.
- **로그에서 볼 것**(재시도 감사 실측 확인 · 미완): ① `attempt n/3`(일시 실패를 흡수한 것) ② `day left INCOMPLETE on purpose`(부분 실패가 재시도된 것) ③ Kworb 실패 사유. **세 줄 다 안 뜨면 전부 1회에 성공한 것이므로 정상.**
- **시간 깊이**: social 103일 · chart 14일 · yt 7일 · sonic 3일. 실험 종료 기준 chart ~34일 · sonic ~23일 — **시각화 완성 시점이 결과를 그릴 수 있는 시점과 맞는다.**

## 🚫 배포하지 말 것 (2026-07-29 도메인 소유자 지시)

- **Vercel 배포는 당분간 하지 않는다.** **`redslippers` 계정/팀으로는 절대 금지.**
- ✅ 단, **`waydclouds-projects` 팀의 GitHub 연동 자동 배포(PR 프리뷰 포함)는 의도된 것**이다. 위 금지는 "에이전트가 임의로 `vercel deploy`를 실행하는 것"에 대한 것이며 이 연동을 끊지 말 것.
- **교훈**: 배포 대상 계정은 로컬 설정에서 추론할 값이 아니다. `.vercel/project.json`이 있다는 건 "여기로 배포해도 된다"는 뜻이 아니다.
- ⚠ `apps/dashboard/.vercel/`(gitignore)에 죽은 링크가 남아 있다. 재개 시 **재사용하지 말고** 올바른 계정으로 새로 `vercel link`.

## ⚠ 도메인 소유자 결정 대기

### 승인이 필요한 것

| 항목 | 왜 |
|---|---|
| ~~**`inferences` 리포트 계약**~~ | ✅ 승인·구현 완료(D-041·D-042) |
| ~~**디자인 스킬 벤더링**~~ | ✅ 승인·완료 — `.claude/skills/`에 `frontend-design` + 모션 4종(`animation-vocabulary`·`find-animation-opportunities`·`improve-animations`·`review-animations`). 둘 다 MIT, LICENSE 동봉 |
| ~~**긴 목록의 형태**~~ | ✅ 위임 구현 완료(D-048). **위에서 자르지 않고 가운데를 접는다** — 위에서 자르면 반례(차트 선행)가 통째로 사라진다. 114행 → 30행 · 이름으로 좁히는 한 줄 |
| **타일 23개를 더 줄일까** | `sonic-profile`의 중앙값 타일. **자리는 정해졌고**(D-047: 6·6·5·0·0·6) **원장이 무효라고 적은 축은 코드가 막는다**(D-048: `danceability`를 중앙값·순위 표면에서 제외). 남은 것은 순수한 A&R 취향 판단이다. 뺀 축도 스냅샷·시리즈에 그대로 남는다 |
| ~~**용어 설명의 자리**~~ | ✅ 위임 구현 완료(D-048). 남은 `title` 4곳은 전부 **대시보드가 계산하는 집계 라벨**이라 리포트가 소유할 값이 아니었다 — **계약 변경이 필요 없었다.** 보이는 `Terms` 펼침으로 전환 |
| **빌보드 링크 확정 26쌍** | 형식은 섰다(D-051). [`docs/REVIEW-impulse-chart-links.md`](docs/REVIEW-impulse-chart-links.md)를 보고 [`chart_links.confirm.json`](data/research/genre-impulse/chart_links.confirm.json)의 `confirm`을 true로 → `impulse_trajectory_link.py --apply`. **11쌍이 시장 불일치 표시**를 달고 있다(미국 차트 사실 ↔ `kr-*` 셀). 겹침이 우연인지 아닌지가 정확히 도메인 판단이라 엔지니어가 채우지 않았다 |
| **유료 소셜 레그 재시도** | 재시도는 돈에 관한 결정이라 제외해 둠 |
| **저지클럽 정답지 20곡 확정** | [초안](docs/DRAFT-jersey-club-answer-sheet.md) 확인 포인트 4건 — VIBE 캐논 단독 근거를 수용할지 |
| **신규 검출 규칙 2종 임계 검토** | `ukg-origin-shuffle`·`moombahton-kr-tropical`(genre-impulse RULES §2.1.2~3) — 임계는 공유 관습값 P20/P80이며 튜너로 재조정 가능. 베이스라인(7~10%·5~8%)·재현(3/6·5/7) 병기 |
| **hyperpop 규칙 over_unity 갈래** | A2 본편 재검: 동시대 프레임에서 over_unity가 중앙(P66) — A2.1의 극단은 2026 라이브 코호트(리미팅 상향) 의존이었다. OR 조합이라 규칙은 유효하나 갈래 유지 여부는 취향 판단 |
| **틱톡 워치리스트 v0** | [초안](docs/DRAFT-tiktok-watchlist-v0.md) 검토 포인트 8건 (D-035 ①, 월 상한 $15) |
| **사람 라벨 50~100곡** | 장르·악기 **정확도 미측정**. 태그를 화면 중심에 놓고 디자인한 뒤 정확도가 낮으면 중심을 다시 만들어야 한다. **리드타임이 길어 먼저 걸어둘 것** |

### 관습값 (결과를 보기 전에 정하는 것이 옳다 — AGENTS §2.1)

| 기준 | 기본값 | 어디에 |
|---|---|---|
| 리듬 유형 배정 임계 θ | 0.30 | `--rhythm-min-match` · 튜너 |
| 동점 폭 | 0.05 | `--rhythm-tie-gap` · 튜너 |
| 악기 검출 확률 | 0.30 | `--min-prob` · 튜너 |
| 신곡 경계 | 90일 | `--new-release-days` |
| 빈티지 칸 최소 표본 | 3곡 | `VINTAGE_MIN_N` |
| 소셜 최소 표본 | 20건 | `--min-posts` |
| 하프타임 판정 비율 | 1.0 | `--halftime-min-ratio` |
| 글라이드 최소 기울기·지속 | 6.0 st/s · 80 ms | `--bass-glide-min-*` |
| 지속 노트 최소 길이·최대 드리프트 | 120 ms · 40센트 | `--vocal-note-*` |
| 스네어 유효성 바닥 | **1.80**(v4 분포 p10 — 형식은 엔지니어 소유, D-037) | `--snare-min-contrast` |

- **`tresillo(16분·반마디)`는 제거됐다**(D-038 승인). `dembow`의 정체(킥+스네어 합주인데 프로파일은 킥만 접는다)는 여전히 불확실(6곡).

## 대기 목록 (시각화와 병행 가능 — 전부 "행"만 늘린다)

1. ~~**sonic 축 후속**~~ ✅ **①② 전부 판정 완료**(2026-07-31 · D-049·D-050): **H3 실패**(하이햇 축 확장 종료 · 코호트 54.6%가 0.0인 바닥 뭉침) · **H4 채택 안 함**(①통과 ②2곡 탈락 · 바닥이 함께 오른다). 값은 계속 저장하되 **표면 금지**. ③ 저지클럽 정답지 **미해석 8곡 대체 후보**만 열려 있다(표본을 채우면 **복제의 검정력**이 오른다 — 판정을 뒤집는 경로가 아니다).
2. ~~**A2 본편**~~ ✅ **완료**(2026-07-31): 동시대 두 프레임(US 빌보드 · KR = Wayback 멜론, 신규 `scripts/melon_wayback_ingest.py`) 위 백분위 실측(`scripts/a2_signature_compare.py` · `a2_signature_compare.json`) → 규칙 2종 등재 + amapiano 철회 + 원장 10건 measured. **후속**: 케이스별 동시대 앵커 확장(easy-listening 2023 등).
3. **빌보드 궤적 → 임펄스 원장** — ✅ **형식 완료**(2026-07-31 · D-051), ⏳ **값은 도메인 대기**. 후보 26쌍을 [`docs/REVIEW-impulse-chart-links.md`](docs/REVIEW-impulse-chart-links.md)에 냈고 확정 파일은 [`chart_links.confirm.json`](data/research/genre-impulse/chart_links.confirm.json)(전부 `confirm=false`). **자동 배정은 스키마·기존 스크립트가 이미 금지한 것**이라(뉴진스 Hot 100 = 미국 도달) 값을 채우지 않았다.
4. **멜론 복구**: 대화형 세션에서 `/mcp` 재연결 → 4콜 → `convert-melon`이면 4번째 렌즈 복귀. 화이트리스트 회신 대기.
5. **1958~2012 빌보드 스모크**(현 스모크 표본은 2013~2023뿐) · 크레딧 레지스트리 설계(D-034 ④) · "2021 저지클럽 관측" 실체 도메인 소유자 인터뷰.
6. **yt-pulse v2** · **댄스 모듈 v1**(문서만) · 케이스 스터디 · 써클차트 제휴.

## 🟡 논의 중 — 상시 서버 / 트랙 원장 저장 형태 (미결정)

- **세 관심사가 한 덩어리인데 따로 풀린다**: (a) 수집이 내 PC에 묶임 · (b) 데이터 저장 형태 · (c) 조회·서빙.
- **(a)가 실제 통증인데 NestJS는 그걸 풀지 않는다** — 수집·분석이 전부 Python이라 NestJS는 Python 워커 오케스트레이터가 될 뿐이고 그 서버도 어딘가에서 돌아야 한다.
- **(a)만의 최저비용 답**: **GitHub Actions cron** 이전 → 서버·DB 없이 PC 의존 소멸, git이 곧 이력. 걸리는 것: 유료 키를 CI 시크릿으로, **MCP 레그(멜론)는 대화형 인증이라 헤드리스 불가**, 모델·torch 캐시.
- **D-003**은 이미 "라이브 분석이 필요해지면 Python 비동기 워커(Modal 1순위)"로 정해져 있다 — NestJS는 규칙 위반이 아니라 **결정 번복**이며 근거를 새 결정으로 남기면 된다.
- **서버가 정당해지는 조건 3개**(여러 사람 쓰기 · 온디맨드 분석 · JSON-in-git 규모 초과)가 아직 셋 다 아니다. **시각화를 해보면 온디맨드 요구가 실제로 있는지 알게 된다.**
- ⚠ **`data/live/`는 gitignore** — 복구한 101곡 악기 라벨이 **이 PC에만** 있다. `retag`로 재복구는 되지만(멱등) 관측 이력이 git 밖이라는 점이 이 논의의 실질 쟁점이다.

## 참고 — 종료된 조사 (재조사 불필요)

- MERT·MuQ·CLaMP 3 = 라이선스 배제 · CLAP 제로샷 = 붕괴 · AST 악기 = 실패 · AudioSet에 저지클럽·뭄바톤 라벨 없음. 상세 [`docs/INVESTIGATION-audio-engine.md`](docs/INVESTIGATION-audio-engine.md).
- **Essentia**: Windows 휠 없음(ONNX 직접 구동으로 우회, D-026) · **madmom**: `numpy<1.20` 고착 · **Demucs**: 저장소 아카이브(현 SOTA는 BS-RoFormer) · **AcousticBrainz**: 2022 수집 중단.
- **한국 저작권법에 TDM 면책 없음** · YouTube ToS 다운로드 금지 → 오디오 취득은 프리뷰(회색) 또는 라이선스(백색)뿐.
- **차트 라이브러리 선정 완료**(D-040): visx + motion. Recharts·Nivo·ApexCharts는 자기 룩 강제로 배제, ECharts는 규모 근거 부족으로 배제(재검토 조건 명시).

## 로컬 실행 메모

```bash
# ── 전체 daily 1회 (재개 가능·멱등, 완주일이면 no-op)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_collect.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_task.ps1 [-WhatIf]

# ── sonic-profile  (콘솔이 cp949라 PYTHONIOENCODING=utf-8 필요)
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile selftest       # 네트워크 0
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile analyze data/live/sonic \
  --watchlist packages/entity-master/watchlist.json -o "$TMP/"
#   ⚠ -o modules/sonic-profile/output/ 은 커밋된 라이브 산출을 덮는다. 검증만 할 때는 임시 디렉터리로.

# ── A2 본편 재현 (오디오 0 — 저장 스냅샷에서 백분위 재계산)
python scripts/a2_signature_compare.py \
  --cases data/research/genre-impulse/signature_v4_merged.json \
  --cohort-us data/research/genre-impulse/cohort_us_features_2021-10-02.json \
  --cohort-kr data/research/genre-impulse/cohort_kr_features_2021-10-02.json \
  -o data/research/genre-impulse/a2_signature_compare.json
# KR 동시대 코호트 목록(네트워크 = Wayback만): python scripts/melon_wayback_ingest.py cohort 2021-10-02 -o <out>

# ── 게이트 모집단 조립 (네트워크 0) — daily는 차트 코호트만 잰다. 정답지는 연구 취득분에 있다
#   🔴 엔진 지문(rhythm_feature_set·HOP·격자)이 어긋나면 **거부한다** — 다른 조건의 값을 한
#      분포에 넣으면 백분위가 음악이 아니라 측정 조건 차이를 잰다(D-037/D-038).
python scripts/gate_snapshot.py \
  --cohort data/live/sonic/<날짜>.json \
  --answers data/research/genre-impulse/signature_v4_merged.json \
  -o data/research/genre-impulse/stem_gate_snapshot_<날짜>.json

# ── 스템·격자 축 채택 게이트 (오디오 0 — 저장 프로파일에서 재게이트 + 하이햇 축 소급)
#   H1·H3(하이햇)·H4(2마디 분할)가 한 실행에서 나온다. H4는 코호트에 축이 차야 판정된다
#   (그 전에는 사유와 함께 unmeasured — 09:00 콜드 실행 뒤 같은 명령을 그대로 돌린다).
PYTHONPATH="modules/genre-impulse/src;modules/sonic-profile/src" python scripts/stem_gate.py \
  --snapshot data/research/genre-impulse/stem_gate_snapshot_v2.json \
  -o data/research/genre-impulse/stem_gate_result_v2.json
#   ⚠ 결과 파일은 스냅샷 하나당 하나로 유지한다. 축을 추가하면 **같은 파일에 행이 는다** —
#     v3를 새로 만들면 같은 축의 판정이 두 개가 되고 유리한 쪽이 인용된다(GATES의 옛 절대값 행 선례).

# ── 상태·게이트
python scripts/validate_report_data.py [--selftest]   # 차트 데이터 계약(스키마가 못 보는 것)
cd apps/dashboard && npm run smoke:tabs               # 전 탭 x 구획 x 라이트/다크 (dev 실행 중일 때)
python -m ruff check modules/ scripts/ · python -m pyright modules/<m>
node apps/dashboard/scripts/collect-reports.mjs
cd apps/dashboard && npm run dev -- --port 3100       # 3000은 다른 프로젝트가 점유 중
#   ⚠ check-dev-off 가드가 3000에 걸리면 전면 우회(AI_ALLOW_BUILD=1) 대신
#     $env:AI_DEV_PORTS='3100' 으로 검사 범위만 좁힐 것 (우리 dev 보호는 살린다)
#   🔴 build는 **dev를 끄고** 돌린다. distDir를 갈아 끼우는 우회는 통하지 않는다
#     (2026-07-30 실측: .next가 프로덕션 산출물로 덮여 dev가 하이드레이션 없는 HTML을
#      내보냈다 — 화면은 그려지는데 탭이 안 눌리는 상태). 끝나면 dev 재시작 + .next 삭제.

# ── 팔레트 검증기 (dataviz 스킬 · 색을 건드리면 필수)
node "<dataviz skill>/scripts/validate_palette.js" "#6d28d9,#b45309,#0891b2" --mode light --surface "#ffffff"
node "<dataviz skill>/scripts/validate_palette.js" "#8b5cf6,#d97706,#0891b2" --mode dark  --surface "#141419"
```
