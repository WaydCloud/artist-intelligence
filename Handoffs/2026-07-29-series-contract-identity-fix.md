# 2026-07-29 · signal-series 계약 기계화 + 레코드 정체성 결함 수정

> 앞 이력 [`2026-07-29-axis-catalog-t0-expansion.md`](2026-07-29-axis-catalog-t0-expansion.md)(D-032)에서 이어진다.
> 시작점: "개발을 이어서 진행" → 재개 첫 액션(육안 확인 빚) 청산 → D-030 잔여 구멍 → 사용자 문의("404가 danceability 1?")가 **진짜 데이터 결함**을 끌어냈다.

## 1. AGENTS §7 빚 청산 — 라이트/다크 육안 확인

Playwright(headless Chromium, `chromium_headless_shell-1228` 명시)로 `localhost:3100` sonic-profile 탭을 실제 렌더로 확인. 요주의 3지점(`<details>` 펼침 · 동점 겹침 막대 `--series2` · `해당 없음` muted 막대) 전부 다크에서 정상 분리. 콘솔 에러 0. 타일 24종 양쪽 테마 정상.

## 2. PR 2건 생성 — 전 잡 초록, 머지 대기

- **PR #3** `sonic-metrics-d031`: D-031 + D-032 + 육안 확인 기록 + 아래 수정 2건.
- **PR #4** `signal-series-schema`: **D-030 잔여 구멍 메움** — `packages/signal-series/` 스키마(SPEC 정본의 기계검증형, 최상위 additionalProperties:false) + `scripts/validate_series.py`(길이=dates·정렬·roster 짝) + CI `data-contracts` 게이트(픽스처 4종, 0건=실패). **음성 케이스 5종으로 게이트가 실제로 잡는 것을 확인**하고, CI 로그에서 `4 fixture(s) checked`까지 봤다(D-030 교훈: 초록≠검증).

## 3. 스키마가 곧바로 밥값을 했다 — 드리프트 2건 검출

라이브 산출물 5종에 검증기를 돌리자:

1. **`sonic_series.json` 계약 이탈** — unit 빈 문자열 · provenance에 source/generatedAt/window 없음. RULES가 계약 준수를 명시하므로 방출부 결함 → PR #3에서 수정(`_SURFACED` 단위 조회 + provenance 3필드).
2. **레코드 정체성 결함** (danceability 문의를 검증하다 발견 — 아래).

## 4. 레코드 정체성 결함 — 이중 저장·비정본 키

**증상**: 키키 - 404가 한 스냅샷에 두 번(`key='키키'` 코호트 경로 + `key='KiiiKiii'` 워치리스트 경로, **같은 track_id**). 7곡/일 이중 저장 → 분포 중앙값 이중 가중. 추가로 **일 18레코드**(코르티스 8·리센느 5·아일릿 4·키키 1)가 비정본 키 → 시리즈에서 같은 팀이 두 키로 쪼개져 브리지 조인 오염.

**원인**: fetch의 코호트 루프가 차트 표기를 그대로 `key`에 넣고, 워치리스트 루프와 병합 시 track_id 중복 제거가 없었다.

**수정** (RULES §1에 규칙 신설 후 구현 — 문서 먼저):

- 정체성 = `(source, track_id, observed_date)`. 코호트 키는 워치리스트 별칭으로 **정본 해석**(원 표기는 `chart_label` 보존, casefold 완전일치만).
- 이중 소속은 한 레코드로 병합(`cohort="watchlist"` + 차트 필드 보존). 차트 모집단 선별은 `chart_rank` 보유로 확장.
- 병합은 `fetch`(저장 전)와 `_load`(과거 스냅샷 방어) **같은 함수, 멱등**. selftest 4건 추가(총 64).
- 저장 스냅샷 2일치 일회 보수: 111→104·105 레코드, 시리즈 64→60 acts(분리 키 소멸).

**한편 danceability 1.0 자체는 결함이 아니다** — 모델 천장(D-031 기록: 코호트 13곡 ≥0.9999, 정확히 1.0이 4곡 동점). "97곡 중 1위"는 동점 정렬의 우연이며 신호가 아니다. 도메인 소유자 답: **"데이터가 잘못되지만 않으면 됩니다. 클라이언트 콘솔은 대대적으로 손을 볼 예정"** — 표면(히트맵 열 구성)은 콘솔 개편에서 다룬다.

## 5. 그 외

- Vercel `waydclouds-projects` GitHub 연동 자동 배포는 **의도된 것**(도메인 소유자 확인) — HANDOFF 배포 금지 섹션에 예외 명시.
- gitleaks 전체 스캔 후속은 PR #2로 이미 해소돼 있었다 — HANDOFF의 낡은 "미결정" 표기 정정.
- **신규 지시 수신**: 장르 임펄스 트래킹(차트인 전 흐름 · 임펄스 기록 · 유사 패턴 일일 모니터링 · 조사 80%). **기획 먼저, 구현 금지** — HANDOFF 🧭 섹션이 정본.

## 다음 세션에 넘기는 것

1. **장르 임펄스 기획**(HANDOFF 🧭 — 의도 파악 → 조사 전략 → 기획. 구현은 그 후).
2. PR #3·#4 머지 결과 확인.
3. 다음 daily 실행에서 dedup·정본 키가 실데이터로 도는 첫 날 — `wrote ... resolved` 로그와 레코드 수(~104)로 확인.
