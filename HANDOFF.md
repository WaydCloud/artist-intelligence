# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 🧭 다음 행선지 — **남은 4탭에 복제** (재개점)

> **완료: sonic-profile(R1~R8) · chart-history(R1~R8 + 구획)**. 남은 것은 **fandom-pulse · genre-impulse · signal-bridge · yt-pulse**.
> 계약 = D-041 · 채택 경계 = D-042 · **구획 = D-043** · 형식 정본 = [`DESIGN.md`](DESIGN.md) §7.1~§7.4.
> 요구사항 정본은 [`docs/REFERENCE-fm-data-hub.md`](docs/REFERENCE-fm-data-hub.md) §5.1.

### chart-history에서 새로 굳은 것 (2026-07-30 도메인 소유자 지시 4건)

| 지시 | 반영 |
|---|---|
| 한 채널에 최대 3가지 | `sections[]` 신설 + **구획당 차트 상한 3을 검사기가 센다**(D-043). chart-history 10차트 → 4구획 8차트(2/2/3/1) |
| 아름다워야 한다, 의도 없는 배치는 짜침 | 진입부에서 **같은 카드 두 개를 나란히 놓지 않는다**. 질문 목록은 본문 텍스트, 카드는 도형에만(`DESIGN.md` §7.1.2) |
| 억지로 쉬운 말을 쓰면 독이 된다 | `DESIGN.md` §6.1 규율 **교체**. 기준은 어휘 난이도가 아니라 **2차 해석 요구 여부**. `지리 지문`·`최광역`·`홈(KR)`·`화이트스페이스` 같은 별칭과 제목 속 `×`·`[태그]`·괄호 경고문을 걷어냈다 |
| 모던·미니멀리즘·시네마틱 | 구획 내비게이션은 번호 + 이름 + 얇은 밑줄만(알약 탭 금지 — 모듈 탭과 층이 겹친다). 구획 머리글은 라벨이 아니라 **질문** |

### 파일럿에서 굳은 것 (복제 대상)

| 요구 | 구현 |
|---|---|
| R1 | `questions[]`(`{q, chartId}`) + `TabQuestions` 블록. 끊긴 앵커는 검사기가 잡는다 |
| R2 | `summary` **단일 객체** + `RadarChart`. 배열이 아니라 객체라 도형 두 개를 낼 수 없다 |
| R3 | `charts[].question` + 카드 제목 아래 한 줄. 채택 모듈은 없으면 CI가 멈춘다 |
| R4 | `inferences[]`(5필드 required) + `InferenceBlock`(배지 → 근거 펼침, 관측 **아래** 배치) |
| R5 | `definition`(차트·지표) + `Definition` 인라인 펼침 |
| R6 | 결측에서 선·폴리곤을 **끊고** 마크는 **플롯 밖**에 둔다 + 개수 표기 |
| R7 | `notAnswered[]` + 질문 블록 하단 |
| R8 | `reliability`(최상위 ⊕ 차트별 병합) + `ReliabilityLine`을 **플롯 위**에 |

### 복제 순서 (탭 하나당)

1. **그 탭이 답하는 질문을 먼저 세어 본다.** chart-history는 넷이었고(플랫폼·규모·지리·신인) 그것이 그대로 구획이 됐다. 질문이 셋을 넘으면 구획을 나누고, 한 구획에 차트가 4개면 하나는 답이 겹치는 것이다.
2. `report.py`에 `sections` · `summary` · `questions` · `notAnswered` · `reliability` · 차트 `id`/`section`/`question`/`definition`을 채운다. 문구는 **한 표에 모은다**(`_CHART_META` · `_SECTIONS`가 원형 — 계산 코드 사이에 흩으면 카피 검토가 불가능해진다).
3. `scripts/validate_report_data.py`의 `ADOPTED_MODULES`에 모듈 id 한 줄 추가 → 그 순간부터 R1~R8이 하드 게이트.
4. 게이트: `validate_report_data.py`(+`--selftest`) · `tsc` · `next lint` · `npm run smoke:tabs`(구획까지 돈다) · **라이트/다크 육안**.

⚠ **눈으로만 잡히는 결함이 실제로 다섯 건 나왔다** — 전부 정적 게이트 4종과 탭 스모크를 **통과한 상태**에서였다:

1. 6시리즈 라인차트가 색 토큰을 순환해 서로 다른 두 축이 **같은 보라색**이었다 → 스몰 멀티플(§7.3)
2. 요약 도형의 기준 링이 격자와 겹쳐 **비교 기준이 보이지 않았다** → 직접 라벨 + 겹치는 격자 제거(§7.2)
3. 결측 마커를 y=0에 찍어 **실값 0.01과 구별되지 않았다** → 축 아래 밴드로(§7.4)
4. `Spotify 밖` 막대가 **순위를 막대 길이로** 그렸다 → 순위 170이 순위 1보다 긴 막대. **순위는 크기가 아니라 순서**라 막대에 실을 값이 아니다. 그 차트는 결국 뺐다(답이 이웃 히트맵과 겹쳤다)
5. 지표 타일이 긴 문자열 값을 **잘라서** 없는 값을 만들었다(`RESCENE - LO...`)

**탭마다, 구획마다 렌더를 실제로 볼 것.** 정적 게이트는 이 다섯 중 어느 것도 잡지 못했다.

### 남은 시각화 작업 (파일럿 범위 밖 · 우선순위 순)

1. **선·면 크로스헤어 + 통합 툴팁** — `DESIGN.md` §7이 "기본 탑재"로 요구하는데 아직 없다. 현 라인차트는 점마다 `<title>`이라 히트 타깃이 6px이다(§7 "히트 타깃은 마크보다 크게" 미달). 프리미티브는 준비돼 있다: `components/charts/ChartTooltip.tsx`(visx 경계 계산만 빌리고 룩은 토큰으로 덮은 것)를 라인/히트맵에 꽂으면 된다.
2. **막대·셀 툴팁** — 위와 같은 프리미티브로. 현재 `title` 속성.
3. **모션** — `motion`은 설치됐고 추론 펼침에만 쓰인다. 상태 변화를 설명하는 곳에만 추가한다(공식 `frontend-design` 경고를 §7이 승계: 과한 애니메이션은 AI 생성처럼 읽힌다).
4. **지표 타일 24개의 편집** — 어느 축을 표면에 남길지는 도메인 판단이다. 요약 도형이 6축을 들고 있으므로 타일은 참고 자료로 내려갔지만, 24개는 여전히 많다.

---

## 현재 위치 (2026-07-30 기준)

- 프로젝트: `C:\Projects\artist-intelligence`. 로컬: Python 3.14.5 · Node 24 · **Windows(win32/AMD64)**.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식 / 도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 6종** 모두 핵심 흐름(`모듈 CLI → 스키마 유효 report.json → 대시보드`) 관통: chart-history v5 · fandom-pulse v3.1 · signal-bridge v2 · yt-pulse v1 · **sonic-profile v4** · genre-impulse v1.
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(**D-036** 차트 페이로드 제약 · **D-041** 시각화 필드 · **D-043** 구획) + PII 게이트 + `packages/entity-master`.
- **시각화 계약 채택**: sonic-profile · chart-history **2/6**. 강제 경계는 `scripts/validate_report_data.py`의 `ADOPTED_MODULES`(D-042).
- **디자인 스킬 벤더링 완료**: `.claude/skills/`에 `frontend-design` + 모션 4종(MIT · LICENSE 동봉). **아직 커밋되지 않았다**(미추적) — 외부 지시문을 레포에 들이는 것이라 커밋 여부는 확인 대상.
- ✅ **git 정리 완료**: 열린 PR **0**. 최근 세션 이력은 [`Handoffs/2026-07-30-visualization-pilot-and-chart-history.md`](Handoffs/2026-07-30-visualization-pilot-and-chart-history.md)(시각화 착수 → 두 탭 적용).

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
