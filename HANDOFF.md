# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 🧭 다음 행선지 — **모션(상태 변화를 설명하는 곳만)** (재개점)

> **인터랙션은 붙었다**(D-045). 선·면에 크로스헤어 + 통합 툴팁, 격자·요약 도형에 마크 툴팁, 그리고 **키보드로 같은 값에 닿는다**. `smoke:tabs`가 이제 그것을 센다(요구가 문서에서 게이트로 옮겨졌다).
> 시각화 계약은 6모듈 전부 적용 완료(D-044) — R1~R8 + 구획이 모든 탭에서 하드 게이트다.
> 계약 = D-041 · 채택 경계 = D-042 · 구획 = D-043 · 값의 방향 = D-044 · **인터랙션 = D-045** · 형식 정본 = [`DESIGN.md`](DESIGN.md) §7.1~§7.6.

### 탭별 구획 (지금 화면의 모양)

| 탭 | 요약 도형(R2) | 구획 |
|---|---|---|
| sonic-profile | 6축 레이더 | (구획 없음 — 파일럿) |
| chart-history | 플랫폼 커버리지 레이더 | 플랫폼 · 규모 · 지리 · 신인 |
| fandom-pulse | 곡 라벨로 잡힌 팀(bar) | 게시 흐름 · 사운드 · 게시물 |
| yt-pulse | 팀별 대표 일 조회(bar) | 쌓인 조회 · 새 영상 |
| genre-impulse | **커버리지**(규칙 1 / 작업 중 1 / 없음 8) | 매치 · 기준 |
| signal-bridge | **선행 62 : 지연 44 : 동시 8** | 선행·지연 · 한 팀 보기 · 차트 밖 · 기준 |

- **구획 수는 질문의 수다.** 질문이 둘인 탭에 구획 넷을 만들지 않았다(yt-pulse·genre-impulse는 2).
- **요약 도형은 radar가 아니어도 된다.** 하중을 받는 것은 도형 종류가 아니라 그 탭에서 가장 오해받기 쉬운 지점이다 — genre-impulse는 매치가 아니라 **커버리지**, signal-bridge는 선행 수가 아니라 **반례를 포함한 구성**이 요약이다.

### 남은 시각화 작업 (우선순위 순)

1. **모션** — `motion`은 설치됐고 추론 펼침·구획 전환에만 쓰인다. 상태 변화를 설명하는 곳에만 추가한다(공식 `frontend-design` 경고를 §7이 승계: 과한 애니메이션은 AI 생성처럼 읽힌다). **크로스헤어에는 전환을 넣지 않는다** — 커서를 따라 스냅하는 것이 즉시성이 곧 정확성인 자리다.
2. **긴 목록의 형태 (도메인 판단 필요)** — signal-bridge 막대 3종은 상위 30행으로 자르고 그 사실을 적었지만, **`leadlag` 튜너는 아직 115행 전부를 세로로 쏟는다**(스크롤 세 화면). 30을 넘는 목록을 막대로 둘지, 표·검색·정렬로 바꿀지는 답하지 않았다. 지금 화면에서 실제 길이를 보고 정하는 것이 맞다.
3. **용어 설명의 자리 (결정 필요)** — `Tunable`에 **설명문 `title` 속성 5곳**이 남았다(`Tunable.tsx` 191·295·643·646·840). 전부 *라벨에 붙은 용어·기준 설명*이고, 눈에 보이는 표시가 없어서 **거기 설명이 있다는 것 자체를 모른다**. 마크 툴팁(§7.6)과는 다른 패턴이라 일괄 변환하지 않았다 — 선택지는 ① `Definition`처럼 인라인 펼침 ② 리포트의 `definition` 필드로 옮겨 계약에 싣기. ②가 §7.1 R5와 맞지만 리포트 쪽 변경이라 승인 대상이다.
4. **지표 타일 편집** — sonic-profile은 아직 타일 24개에 구획이 없다. 어느 축을 표면에 남길지는 도메인 판단이다.

⚠ **눈으로만 잡히는 결함이 세 라운드에 걸쳐 열여섯 건 나왔다** — 전부 정적 게이트 4종과 탭 스모크를 **통과한 상태**였다.
- 1차(파일럿) 5건: 색 순환 · 기준 링 겹침 · 결측 마커 위치 · 순위를 막대 길이로 · 타일 값 잘림.
- 2차(6탭 확산) 6건: 부호를 막대에 · 역방향 축을 막대에 · 격자 색 방향 반대 · 미관측 구간을 0으로 · 계정명 노출 · 저장 키 노출. 공통점은 **그림의 방향과 주장의 방향이 어긋난 것**(§7.5).
- 3차(인터랙션) 5건: **툴팁이 표면 없는 맨 텍스트**(visx `unstyled`가 우리 `style`까지 버린다 — D-041의 요약 도형 툴팁이 그때부터 이 상태였다) · 결측 안내선 91개가 배경 해치 · `+127일`이 두 줄로 접힘 · **그리고 다섯 중 둘은 이 세션에 새로 쓴 코드에서 나온 것**(ⓘ 툴팁이 탭 정지 110개를 만든 것 · 사유 칸을 좁게 잡아 자른 것). 규율은 §7.6.

**탭마다, 구획마다 렌더를 실제로 볼 것.** 열여섯 건 중 정적 게이트가 잡은 것은 없다. 3차에서 배운 것 하나: **인터랙션 결함은 스크린샷 한 장으로도 안 보인다**(마우스를 올려야 나타나는 것이 대상이므로) — 그래서 `smoke:tabs`가 대신 센다. **새로 고친 코드도 같은 눈으로 다시 볼 것**(3차의 절반이 그렇게 나왔다).

### 새 모듈을 붙일 때 (복제 순서)

1. **그 탭이 답하는 질문을 먼저 세어 본다.** 그 수가 곧 구획 수다. 한 구획에 차트가 4개면 하나는 답이 겹치는 것이고, 검사기가 3에서 멈춰 세운다.
2. 모듈의 report 빌더에 `_SECTIONS` · `_CHART_META` · `_METRIC_META` 세 표를 두고 문구를 **거기에만** 모은다(계산 코드 사이에 흩으면 카피 검토가 불가능해진다). 요약·질문·notAnswered·reliability·inferences는 그 아래 헬퍼로.
3. `scripts/validate_report_data.py`의 `ADOPTED_MODULES`에 한 줄 추가 → 그 순간부터 R1~R8이 하드 게이트.
4. 게이트: `validate_report_data.py`(+`--selftest`) · `ruff` · `pyright` · `tsc` · `next lint` · `npm run smoke:tabs`(구획까지 돌고 **인터랙션까지 센다** — 크로스헤어 히트 타깃 · 포인터와 키보드 양쪽 툴팁 · 툴팁 표면 · 떠나면 닫힘) · **라이트/다크 육안**.
   - 새 차트 프리미티브를 만들면 `data-plot="…"` 표식을 단다. 히트 타깃으로만 세면 **없는 것을 셀 수 없어** 검사가 순환한다.
5. 빈 입력에서도 계약이 서는지 본다(요약은 빈 도형으로 남고, 놓을 차트가 없으면 구획을 선언하지 않는다). 라이브 수집이 하루 비는 것은 정상이고, 그때 CI가 깨지면 안 된다.

---

## 현재 위치 (2026-07-30 기준)

- 프로젝트: `C:\Projects\artist-intelligence`. 로컬: Python 3.14.5 · Node 24 · **Windows(win32/AMD64)**.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식 / 도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 6종** 모두 핵심 흐름(`모듈 CLI → 스키마 유효 report.json → 대시보드`) 관통: chart-history v5 · fandom-pulse v3.1 · signal-bridge v2 · yt-pulse v1 · **sonic-profile v4** · genre-impulse v1.
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(**D-036** 차트 페이로드 제약 · **D-041** 시각화 필드 · **D-043** 구획) + PII 게이트 + `packages/entity-master`.
- **시각화 계약 채택**: **6/6 완료**(D-044). 강제 경계는 `scripts/validate_report_data.py`의 `ADOPTED_MODULES`(D-042) — 새 모듈은 여기 한 줄로 계약에 들어온다.
- **디자인 스킬 벤더링 완료**: `.claude/skills/`에 `frontend-design` + 모션 4종(MIT · LICENSE 동봉). ✅ **커밋됐다**(13파일, `bd83e87`) — "미추적이라 커밋 여부가 확인 대상"이라고 적혀 있었지만 그 커밋에 이미 들어가 있었다. 결정할 것이 남아 있지 않다.
- ✅ **git 정리 완료**: 열린 PR **0**. 최근 세션 이력은 [`Handoffs/2026-07-30-interaction-crosshair-tooltip.md`](Handoffs/2026-07-30-interaction-crosshair-tooltip.md)(인터랙션 + 스모크 게이트), 그 앞이 [`Handoffs/2026-07-30-visualization-six-tabs.md`](Handoffs/2026-07-30-visualization-six-tabs.md)(6/6 채택 · 값의 방향), 그 앞이 [`Handoffs/2026-07-30-visualization-pilot-and-chart-history.md`](Handoffs/2026-07-30-visualization-pilot-and-chart-history.md)(시각화 착수 → 두 탭).
- **프리미티브 일반화**(D-044 딸린 결과): `Heatmap`이 순위 전용에서 벗어나 값의 방향을 payload로 받는다(`scale: "rank" | "value"` + 범례 문구). `palette.seqColor`가 그 공통 램프다. chart-history의 순위 격자 4종은 기본값이라 무회귀.
- **인터랙션 프리미티브**(D-045): `ChartTooltip.tsx`가 `show`(마크 기준)와 `showAt`(좌표 기준 — 크로스헤어처럼 스냅된 위치)을 낸다. 🔴 `unstyled`를 쓰지 않는다(우리 `style`까지 버린다). 라인차트는 표 뷰까지 갖췄고, 격자는 `<th scope>`로 표 의미가 서 있다.

## 🔴 가동 중 — 전향 실증 자동 수집 (매일 09:00 + 2시간 간격 재시도)

- **Task Scheduler `AI-daily-collect`** → `scripts/daily_collect.ps1`. 설정 정본은 [`scripts/register_task.ps1`](scripts/register_task.ps1)(멱등).
- **8단계**: spotify · apple · youtube · shazam(무료) → social(유료 $3/일) → yt → sonic(프리뷰·무보관) → genre-impulse.
- **재개 가능**(D-018): `data/live/state/run_<date>.json`. 완주일 재실행 = no-op. **가드**: PAUSE 파일 · `experiment_end=2026-08-19` · `AI_DRYRUN=1`. 중단: `schtasks /Delete /TN "AI-daily-collect" /F`.
- ⚠ **다음 sonic 레그는 콜드 실행이다** — `RHYTHM_FEATURE_SET` v4(D-038: HOP 128 · 32칸 격자)로 캐시가 무효화됐다. 프리뷰 ~200건 재취득(무료). **정상 동작이며 이 실행이 32칸 격자와 하이햇 축 4종을 라이브 스냅샷에 채운다.**
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
| **긴 목록의 형태** | `leadlag` 튜너가 **115행을 세로로 쏟는다**(스크롤 세 화면). 막대로 둘지 표·검색·정렬로 바꿀지는 "이 목록을 어떻게 쓰는가"에 달렸다 — 훑는 것이면 표, 상위만 보는 것이면 자르는 것이 맞다(D-045 딸림) |
| **용어 설명의 자리** | `Tunable`에 설명문 `title` 5곳. 리포트 `definition` 필드로 옮기면 §7.1 R5와 맞지만 **리포트 계약 변경**이라 승인 대상(대시보드 안에서 인라인 펼침으로 끝내는 선택지도 있다) |
| **유료 소셜 레그 재시도** | 재시도는 돈에 관한 결정이라 제외해 둠 |
| **저지클럽 정답지 20곡 확정** | [초안](docs/DRAFT-jersey-club-answer-sheet.md) 확인 포인트 4건 — VIBE 캐논 단독 근거를 수용할지 |
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

1. **sonic 축 후속(사전 등록 필요 · 결과를 보고 만들지 않는다)**: ① 하이햇 **연타 몰림**(연속 3칸 이상 구간의 비중 — H1 실패의 원인 후보) ② 반쪽 재현성의 **4마디 주기 분할**(탈락 2곡이 2마디 루프였다) ③ 저지클럽 정답지 **미해석 8곡** 대체 후보.
2. **A2 본편**: 원형↔한국 서명 비교(`data/research/genre-impulse/signature_merged.json`) + US 동시대 코호트(`cohort_us_2021-10-02.json` — `fetch --cohort` 입력 형태 그대로) + 동시대 KR 코호트(Wayback 멜론 CDX).
3. **빌보드 궤적 → 임펄스 원장**: `chart_evidence` 22건을 `trajectory` 셀에 연결(확실성 등급 부여가 도메인 판단이라 분리).
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

# ── 스템·격자 축 채택 게이트 (오디오 0 — 저장 프로파일에서 재게이트)
PYTHONPATH="modules/genre-impulse/src;modules/sonic-profile/src" python scripts/stem_gate.py \
  --snapshot data/research/genre-impulse/stem_gate_snapshot_v2.json \
  -o data/research/genre-impulse/stem_gate_result_v2.json

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
