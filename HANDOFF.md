# HANDOFF · 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 🧭 다음 행선지 (재개점)

# 🔵 **매일 발행이 붙었다. 첫 실제 발행은 2026-10-15 09:40 이후 수집이 닫힌 다음 시도** (2026-10-15)

> 📄 이전 핸드오프 = [`Handoffs/2026-09-21-page-caught-up-50-days.md`](Handoffs/2026-09-21-page-caught-up-50-days.md) · 이번 결정 = [`docs/DECISIONS.md`](docs/DECISIONS.md) **D-062**

## VERIFY: GREEN · E2E: 미검증 (첫 무인 발행이 아직 일어나지 않았다 · 9/21 슬라이스의 6탭 E2E도 미검증)

| 게이트 | 결과 |
|---|---|
| PS 5.1 파싱 (`daily_publish` · `scan_staged_secrets` · `refresh_and_deploy` · `register_task`) | 0 오류 |
| 안전장치 (스크래치 clone + bare origin) | **11/11** |
| 커밋 · push (실코드 발췌) | 3/3: 사람 stage 보존 · 끼어든 사람 커밋 push 거부 · 리포트만 커밋 |
| 시크릿 스캔 | 패턴 7/7 검출 · 정상 통과 · 소문자 오탐 0 · hunk 내 `+++` 검출 |
| 실제 대기 리포트 7파일 스캔 | 추가 29,115줄 · 0건 |
| 스케줄러 경로 실행 (00:56) | `result=0` · "collect not done yet" |
| 독립 리뷰 | 실결함 6건 → 전부 고침 (D-062) |

## 이번 세션에 닫힌 것

- 원인: 수집과 리포트 재생성은 매일 돌았는데 **커밋 · push가 사람 몫**이라 공개 페이지가 9/20 데이터에 3주 머물렀다.
- `AI-daily-publish` 작업 등록 (09:40부터 2시간마다 14시간). `scripts/daily_publish.ps1` → `refresh_and_deploy.ps1 -DataOnly`.
- `scripts/scan_staged_secrets.ps1` 신설, `refresh_and_deploy.ps1` 커밋 단계에 연결 (수동 실행에도 걸린다).
- `register_task.ps1`에 `-Script` 인자. 수집 작업 정의는 그대로다.

## 🔴 커밋되지 않은 상태다 (의도)

스크립트 4개 · `docs/DECISIONS.md` · 이 파일 · 아카이브 이동이 **작업 트리에만** 있다.
- 로컬에 커밋만 하고 push하지 않으면 발행 안전장치가 "사람 커밋이 앞서 있다"로 **매일 멈춘다.** 그래서 커밋하지 않았다.
- 공개 저장소 push는 별도 승인 사항이다. 승인되면 커밋과 push를 한 번에 한다.
- 🔴 **이 저장소에서 작업할 때 무엇이든 stage한 채로 두면 그날 발행이 멈춘다**(안전장치 "index 비어 있음"). 커밋할 것은 바로 push까지 한다.

## 다음 세션이 할 일 (순서대로)

1. 🔴 **첫 무인 발행 확인.** `data/live/logs/publish.log` 마지막 줄이 `daily_publish done`인지, `data/live/state/publish_2026-10-15.json`의 `pageConfirmed`, 공개 페이지의 데이터 날짜.
2. 🔴 **9/21 슬라이스 E2E** (이전 핸드오프 1번): `cd apps/dashboard` → `npm run dev -- --port 3100` → 6탭.
3. 이번 변경의 커밋 · push 승인.
4. 결함 40 값 판정 (D-061 ㉠㉡㉢), 이전 핸드오프의 미결 그대로.

## 멈추는 법

- 발행만 멈춤: `data/live/PAUSE_PUBLISH` 파일 생성 (수집은 계속)
- 작업 해제: `Disable-ScheduledTask AI-daily-publish`

## 손대지 않은 것

- `scripts/daily_collect.ps1` (BOM 부재, 결함 41-1). 발행을 별도 작업으로 뺀 이유다.
- Vercel `out` 프로젝트 (결함 42). 삭제는 사용자 판단.
- 실패 알림. 지금은 `publish.log`에만 남는다. 시크릿 오탐이 나면 그날부터 발행이 멈춘다.
