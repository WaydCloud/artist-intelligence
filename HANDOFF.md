# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 🧭 다음 행선지 — **시각화 착수** (재개점)

> 도메인 소유자: *"새 세션에서 본격적으로 시각화."* 데이터 체계화 단계는 닫혔다.
> 규칙 정본은 [`DESIGN.md`](DESIGN.md)(§6.2 AI추론 · §7 차트 스택 · §8 게이트) · 레퍼런스는 [`docs/REFERENCE-fm-data-hub.md`](docs/REFERENCE-fm-data-hub.md) · 결정은 D-039·D-040.

### 착수 전 확인 (딱 두 개)

1. 🔴 **`inferences` 리포트 계약 승인** — D-039(`AI추론` 태그)를 구현하려면 스키마에 객체 배열을 신설해야 한다. 현 `insights`는 `string[]`이라 태그·근거·불확실성을 실을 자리가 없고, 문자열 접두사로 때우는 것은 **D-036이 방금 닫은 그 구멍**이다. AGENTS §0에 따라 **별도 승인 + 대시보드 동시 갱신**이 전제. → 승인되면 D-036과 같은 방식(스키마 판별 분기 + 렌더러 동시 갱신 + 검사기 규칙 + selftest)으로 처리.
2. **디자인 스킬 벤더링 승인**(선택) — 공식 [`frontend-design`](https://github.com/anthropics/skills/blob/main/skills/frontend-design) + [`emilkowalski/skills`](https://github.com/emilkowalski/skills) 모션 4종을 `.claude/skills/`에 넣을지. 외부 지시문을 레포에 들이므로 AGENTS §1 대상. **없어도 시각화는 시작할 수 있다**(`dataviz` 스킬은 번들이라 이미 사용 가능).

### 파일럿 권고 — sonic-profile 탭

지표 24종·분포·튜너가 다 있어 **요구사항 8개를 한 화면에서 시험**할 수 있다. 여기서 형태가 잡히면 나머지 5탭에 복제한다.

### 요구사항 R1~R8 (FM 데이터 허브의 실패를 번역한 것 · 정본 REFERENCE §5.1)

| # | 요구사항 | 검사 |
|---|---|---|
| **R1** | 각 탭 첫 화면이 **"이 탭에서 답할 수 있는 질문 3개"**를 명시 + 해당 패널로 앵커 | 탭 스모크에 질문 블록·링크 대상 검사 추가 |
| **R2** | **진입은 요약 1개** — 첫 화면 스크롤 없는 영역에 차트 **1개**만 | 육안 + 스모크 |
| **R3** | 차트마다 **"이 차트로 답할 수 있는 질문"** 한 줄. **없으면 그 차트를 뺀다** | 리포트 계약 필수화 검토 |
| R4 | `AI추론` 태그 + 근거 열기 · 동반 4종 없으면 방출 거부 | 검사기 |
| R5 | 지표 정의를 **인라인 펼침**(원장 링크가 아니라 화면에) | 타일·축 라벨 정의 필드 |
| R6 | **결측을 0으로 그리지 않는다** — "관측 없음 + 사유" | 렌더 층 회귀 검사 |
| R7 | 화면이 **못 답하는 질문을 명시** | 커버리지 표기를 전 탭으로 |
| R8 | 신뢰도 라인을 카드마다 **1급 요소**(표본 n · 정확도 상태 · 결측 사유 · 엔진 버전) | **각주 금지** |

**R1·R3이 가장 무겁다.** FM의 최대 실패는 기능 부족이 아니라 **자기 사용법을 못 가르친 것**이고("거기 너무 많은 게 있어서 무엇을 봐야 할지 알 수 없었다"), 우리도 같은 위험 위에 있다("다 멋져 보인다, 그런데 이걸로 뭘 어떻게 도울 수 있나?").

### 이식할 설계 원칙 (검증된 것만)

1. **진입은 작은 요약 하나** — 독립 3근거가 일치한다. FM26에서 허브가 비었을 때 **작동하던 유일한 것이 General Performance Octagon**이었다(고장 상태에서 남은 하나가 하중받던 요소).
2. **두 패널의 불일치가 진짜 산출물** — "미드필더는 태클을 많이 성공한다 **그러나** 볼을 되찾는 지역은 하프라인 아래다 → 전방 3인이 압박에 기여하지 않는다". **오늘 우리 게이트 판단이 전부 이 구조였다**(측정은 건강한데 정답지가 중앙 = 주장이 틀림). ⇒ 두 축을 나란히 놓아 불일치가 보이는 레이아웃.
3. **비교 위치를 값의 기본 동반자로** — 절대값 단독 금지. 우리는 이미 **당일 코호트 백분위**를 쓰므로 이식이 아니라 노출 문제다.
4. **부호를 뒤집는 맥락을 값 옆에** — "이 값이 낮은 것은 설정 때문일 수 있다"를 화면이 먼저 말한다(각주 아님).

### 착수 순서 제안

1. `@visx/*` 저수준 패키지만 설치(`shape`·`scale`·`axis`·`tooltip`·`group`) + `motion`. **고수준 `@visx/xychart`는 쓰지 않는다.**
2. sonic-profile 탭에 R1·R2·R3 적용 — 질문 3개 블록 + 요약 1개 + 차트별 질문 한 줄.
3. 신뢰도 라인(R8) 컴포넌트 1개를 만들어 전 카드에 꽂는다.
4. 라이트/다크 육안 + `npm run smoke:tabs` + 팔레트 검증기 + 안티패턴 대조(`DESIGN.md` §8 체크리스트).

⚠ **시각화 단계의 고유 위험**: 잘 만든 차트는 그 자체로 **평결처럼 읽힌다**(AGENTS §5 압력). `DESIGN.md` §4 표면 위계가 방어선이고, **불확실성·표본·한계를 어디에 붙일지는 레이아웃 단계에서 정해야 한다** — 나중에 얹으면 각주가 되고 각주는 안 읽힌다.

---

## 현재 위치 (2026-07-30 기준)

- 프로젝트: `C:\Projects\artist-intelligence`. 로컬: Python 3.14.5 · Node 24 · **Windows(win32/AMD64)**.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식 / 도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 6종** 모두 핵심 흐름(`모듈 CLI → 스키마 유효 report.json → 대시보드`) 관통: chart-history v5 · fandom-pulse v3.1 · signal-bridge v2 · yt-pulse v1 · **sonic-profile v4** · genre-impulse v1.
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(**D-036에서 차트 페이로드 제약 추가**) + PII 게이트 + `packages/entity-master`.
- ✅ **git 정리 완료**: 열린 PR **0**. main = 머지 4건 반영 후 CI 5잡 success. 최근 세션 이력은 [`Handoffs/2026-07-30-gates-grid-and-visualization-prep.md`](Handoffs/2026-07-30-gates-grid-and-visualization-prep.md).

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
| **`inferences` 리포트 계약** | D-039 구현 전제(AGENTS §0) |
| **디자인 스킬 벤더링** | 외부 지시문을 레포에 들임(AGENTS §1) |
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
cd apps/dashboard && npm run smoke:tabs               # 전 탭 x 라이트/다크 (dev 실행 중일 때)
python -m ruff check modules/ scripts/ · python -m pyright modules/<m>
node apps/dashboard/scripts/collect-reports.mjs
cd apps/dashboard && npm run dev -- --port 3100       # 3000은 다른 프로젝트가 점유 중
#   ⚠ check-dev-off 가드가 3000에 걸리면 전면 우회(AI_ALLOW_BUILD=1) 대신
#     $env:AI_DEV_PORTS='3100' 으로 검사 범위만 좁힐 것 (우리 dev 보호는 살린다)

# ── 팔레트 검증기 (dataviz 스킬 · 색을 건드리면 필수)
node "<dataviz skill>/scripts/validate_palette.js" "#6d28d9,#b45309,#0891b2" --mode light --surface "#ffffff"
node "<dataviz skill>/scripts/validate_palette.js" "#8b5cf6,#d97706,#0891b2" --mode dark  --surface "#141419"
```
