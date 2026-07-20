# 2026-07-18 · chart-history 모듈 v1+v2 (첫 세로 슬라이스 좌반부)

> Handoffs/ 아카이브 — 이 시점 스냅샷. (다음 행선지는 루트 `HANDOFF.md`)

## 이 구간에 한 일

- **데이터 레일 2종 실측 검증** (직전 구간 이어서 마무리):
  - Firecrawl: 나무위키 사실추출 ✅(`includeTags:["table"]`), 써클차트 **TDM 금지 → 배제(D-005)**, Kworb ✅.
  - YouTube Data API: `videos.list`·`commentThreads.list` ✅ (PII 미적재).
- **chart-history 모듈 빌드 (v1+v2)** — `모듈 CLI → 스키마 유효 report.json` 핵심 흐름 **최초 관통**.
  - **v1**: Kworb 단일 스냅샷 → KPI + Top10/Top아티스트 bar.
  - **v2**: 다중 스냅샷 `analyze` — 국가 교차 heatmap(KR/Global/US/JP 실데이터) + 날짜 라인 시계열(축적 시).
  - **stdlib만**(html.parser·urllib), 검증만 jsonschema. `analyze`/`fetch`/`validate` 서브커맨드.
  - SPEC/RULES/TESTS 하네스 + 4개국 픽스처(사실만) + ci.yml 스모크(미빌드 모듈 skip 가드).

## 검증 (로컬 = 게이트, git/CI 미가동)

- smoke v1(단일)·v2(4개국) → schema valid · graceful(빈입력) · 결정성(v1·v2) · ruff · pyright · schema-validate glob · **live fetch→analyze 왕복**. 전부 통과.
- v2 신호: KR 히트가 JP·Global엔 닿고 **US엔 대부분 미진입**(전 시장 진입 0, 최광역 CORTIS 3개국).

## 배운 것 / 결정

- **D-005**: 써클차트 직접 스크랩 배제(TDM 금지·JS 로드) → Kworb 등 오픈 애그리게이터 1차.
- 툴체인: 로컬 **uv 미설치**·**git 아님** → `PYTHONPATH`로 실행, 로컬 검증이 게이트. jsonschema/ruff/pyright는 Python 3.14에서 pip 정상.
- 모듈 계약: `charts[].data` 규약 정의(bar `[{name,value}]` · heatmap `{rows,cols,cells}` · line `{x,series}`) — 대시보드 렌더 계약(RULES §4.1).
- MediaPipe/OpenCV는 Python 3.14 휠 미지원 가능성 → 댄스 모듈은 3.12/3.13 별도 환경 필요(예상).

## 다음 세션 진입점

→ 루트 [`HANDOFF.md`](../HANDOFF.md) — 후보: 대시보드(보류·언제든) / 케이스 스터디 컨셉 / 댄스 v1 / Apify / chart-history v3.
