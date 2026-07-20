# 2026-07-18 · fandom-pulse v1 + 데이터 정제·관리 체계 (D-006/D-007)

> Handoffs/ 아카이브 — 이 시점 스냅샷. (다음 행선지는 루트 `HANDOFF.md`)

## 이 구간에 한 일

### 바닥 전제 명문화 (D-006)
- **책임소재 불변식**(`DOMAIN.md` §0): 소비적 판단은 책임질 인간에게, 도구 출력은 증거·신호·옵션에서 종료. *설득력은 책임에서 파생* → 판단을 도구에 넘기면 책임 사슬이 끊겨 출력이 무효.
- **기준 원장**(`AGENTS.md` §2.1): 미시 판단 기준은 명시·도메인근거·검증가능·불확실성병기·튜닝가능. **엔지니어=기준의 형식 / 도메인 소유자=기준의 값(임계값)**.
- PRODUCT 차별점·AGENTS §5·WORKFLOW DoD·chart-history RULES §3에 반영.

### fandom-pulse v1 (Apify 스킬화, 2번째 세로 슬라이스)
- 검증된 Apify IG 해시태그 레일 → 스키마 유효 report.json. `fetch`(라이브·PII 즉시 폐기)/`analyze`(오프라인·결정)/`validate`.
- **기준 원장 실증**: RULES §3에 지표별 정의·하중여부·튜닝 임계값·도메인근거·한계. 하중 기준(`--high-pct`·`--momentum-min-days`) CLI 노출. `--high-pct` 90→50 → 고참여 변화.
- 실측(reels 30건): 총 참여 54,968·중앙값 좋아요 969·게시 가속 +2.4/일 + 3차트(공동해시태그·일별게시량·**Top 사운드** ATEEZ-BAD 등 = DD 신호). facts-only 무결.

### 데이터 정제·관리 체계 (D-007) — 계약·게이트·공유 차원
- **`packages/snapshot-schema`**: 수집물(입력측) 공유 규격 = report-schema의 짝. `provenance{source,tool,tool_version,fetched_at,license,tos_class,params,pii_policy} + quality + records`.
- **`scripts/validate_snapshot.py`**: facts-only/PII 게이트. records에 PII/원문 키(유저명·id·url·caption·mentions·댓글원문 등) 있으면 REJECT. denylist는 카운트 필드(`comments`)를 오탐 안 하게 정밀 설계. → §4를 관습→검증 게이트.
- **`packages/entity-master`**: `entities.json`을 chart-history 로컬에서 **공유 레이어로 승격** + `entity.schema.json`. 모듈 공통 캐노니컬 차원(사운드→아티스트, 해시태그→그룹 조인 기반).
- 스냅샷 계약은 **거버넌스 메타데이터를 보편 표준화**, records는 모듈 형태이되 PII 게이트로 검증. **chart-history HTML은 강제 리팩터 없이** 프로버넌스 헤더 주석으로 편입(grandfather).
- CI(`ci.yml`)에 데이터 계약 게이트(스냅샷·엔티티) + fandom-pulse 스모크 추가.

## 검증 (로컬 = 게이트)

- 스냅샷 게이트: fandom-pulse 두 픽스처(reels 30건·empty) **CLEAN**(SCHEMA OK·PII OK). 구 형식은 SCHEMA REJECT로 리트로핏 견인.
- 엔티티 마스터: 50팀·해석 45/50, `entity.schema.json` **0 errors**.
- chart-history **무회귀**: 엔티티 경로 이동(→packages) 후 base 200·4 snapshots·entities 50·schema valid. ruff·pyright(7 files 0).
- fandom-pulse: 재스모크(신규 계약)·graceful·결정성·ruff·pyright(6 files 0)·schema-validate.

## 배운 것 / 한계

- **출력엔 계약, 입력엔 없었다** → 스냅샷 계약이 그 대칭을 채움. §4는 *희망*이 아니라 *게이트*여야 추궁 가능(책임소재 불변식의 귀결).
- Windows cp949 콘솔: 파이썬 stdout/파일 읽기에 `PYTHONIOENCODING=utf-8`·`encoding='utf-8'` 명시. CLI stdout은 ASCII로(셸 무관). 제품 JSON은 항상 UTF-8.
- fandom-pulse 사운드→아티스트 실제 조인은 엔티티 레이어 위 **v2 과제**.

## 세션 로테이션 진입점

→ 루트 [`HANDOFF.md`](../HANDOFF.md) — 후보: **대시보드**(데이터 층 성숙 완료, 렌더 대상 2모듈) / 케이스 스터디 컨셉 / fandom-pulse v2(collect 모멘텀·엔티티 조인·센티먼트) / 댄스 v1 / chart-history v3.5 / Bright Data.
