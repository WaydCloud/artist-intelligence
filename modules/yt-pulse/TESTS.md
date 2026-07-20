# yt-pulse · TESTS (수용조건 · 완료조건)

> 이 조건들이 통과해야 "완료"다. **로컬 검증이 게이트**(git/CI 미가동).

## 픽스처

- `tests/fixtures/yt_snapshot.json` — **실 데이터** facts-only 스냅샷(라이브 `fetch`가 생성해 커밋; snapshot-schema 계약). 워치리스트 acts의 공식 채널 최근작 지표.
- 채널 캐시: [`../../packages/entity-master/yt_channels.json`](../../packages/entity-master/yt_channels.json) (`resolve` 산출·커밋·수동 정정 가능).

## 스모크 (핵심 흐름)

```bash
PYTHONPATH=modules/yt-pulse/src python -m yt_pulse analyze \
  modules/yt-pulse/tests/fixtures/yt_snapshot.json -o modules/yt-pulse/output/
# → output/report.json 생성 + report-schema 통과 → 대시보드 자동 탭(4번째).
# signals: python -m yt_pulse signals <snapshot(s)|dir> -o <series.json>  → yt-velocity 시리즈
# 라이브: resolve --watchlist packages/entity-master/watchlist.json -o packages/entity-master/yt_channels.json  (1회, ~100 units/act)
#        fetch --channels packages/entity-master/yt_channels.json -o data/live/yt/<date>.json  (일일, ~12 units)
```

## 수용조건

- [ ] **A. 핵심 흐름**: 유효 스냅샷 → `output/report.json` + 스키마 유효.
- [ ] **B. 값 무결성**: 모든 지표 ≥0 · `평균 일 조회 = views/max(1,경과일)` 검산 · 구독자/조회 int.
- [ ] **C. 신작 감지**: `--recent-days` 내 업로드 영상이 insight/지표에 표면화, 값 변경 시 반응(기준 원장).
- [ ] **D. signals**: `yt-velocity` 시리즈 방출 — act별 대표(최대) velocity + `subscribers`·`videos` 선택 필드. 브리지 `--youtube` 소비 가능.
- [ ] **E. 결정성**: 같은 입력 2회 → `generatedAt` 제외 동일.
- [ ] **F. 윤리·정직**: "예측/인기 총점" 문구 없음 · 공식 채널 한정·velocity 근사 한계 병기.
- [ ] **G. 게이트**: `ruff`·`pyright` 통과 · **PII 게이트 CLEAN** · 기존 모듈 무회귀.
- [ ] **H. graceful**: 캐시 미해석 act·영상 0 → 크래시 없이 유효 report + 명시.

## 검증 로그 (2026-07-19, v1 · D-014)

- **resolve** ✅ 워치리스트 9팀 → 9/9 채널 해석(~900 units 1회). **오매칭 실사례 포착·해결**: KATSEYE가 'KATSEYE - Topic'(자동 생성)으로 → 비-Topic 우선 로직 추가 + 재해석(공식 채널). 캐시 재실행 시 기존 항목 보존(수동 정정 존중).
- **fetch** ✅ 라이브 9채널 → **45 영상 레코드**(채널당 5), ~12 units. snapshot-schema 계약 + **PII 게이트 CLEAN**. 실측: 구독 BABYMONSTER 12.7M·KATSEYE 11.9M·CORTIS 5.8M / 최근작 조회 합 25.2M.
- **A/B** ✅ analyze → schema valid. KPI 5종 + bar 2종(조회 합·velocity). velocity 검산: KATSEYE 1,312,303/일(최고).
- **C** ✅ 신작 감지: 최근 14일 내 45개(신인 채널들 고빈도 업로드) — 0~1일 전 신작 insight 표면화(RESCENE·BABYMONSTER·Hearts2Hearts·ILLIT).
- **D** ✅ signals → `yt-velocity` 9 acts × 1일 + `subscribers`·`videos` 선택 필드. 브리지 `--youtube` 소비: 프로필에 `YT 구독 788.0k·'뽀로로…' +427.3k/일` 병기 + 커버리지 `YT 9/9`.
- **E** ✅ yt-series·yt-report·3-소스 브리지 모두 2회 `generatedAt` 제외 동일.
- **F** ✅ 예측·단정 문구 없음 · 공식 채널 한정/velocity 근사/§0 한계 3종 병기.
- **G** ✅ ruff·pyright 0 errors · 기존 3모듈 무회귀 · 대시보드 **4번째 탭 자동 등장**(collect 4 reports) 스크린샷 확인.
- **H** ✅ (설계상) 캐시 미해석 act는 fetch가 스킵·로그, 영상 0이면 유효 report + insight — graceful 경로 코드 확인.
- 한계 정직: 공식 채널 업로드만(레이블 채널 MV 미포착) · velocity=수명 평균(초동 과소평가) · 단일 스냅샷은 증분 아님(다일 축적이 본선).

## 실패 시 → [`../../WORKFLOW.md`](../../WORKFLOW.md) 리커버리

우회 금지. 원인 격리 → 최소 수정 → 재현 픽스처 추가.
