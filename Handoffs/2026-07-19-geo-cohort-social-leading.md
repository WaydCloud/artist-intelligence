# 2026-07-19 · 지리 리프레임 → 신인 코호트/브레드스 → 소셜 선행신호

> 세션 아카이브(비덮어쓰기). 정본 포인터는 [`../HANDOFF.md`](../HANDOFF.md), 결정 이유는 [`../docs/DECISIONS.md`](../docs/DECISIONS.md) D-008/009/010.

## 한 줄

사용자 통찰 3연쇄로 chart-history를 국내-앵커 → **다국가 지리 리프레임**(D-008) → **신인 코호트·76개국**(D-009)으로, fandom-pulse에 **소셜 선행신호**(D-010)를 붙여 두 모듈을 공유 entity-master로 조인. 전 게이트 green, 핵심 흐름 관통.

## 사용자 방향 (대화 순서)

1. "KPOP은 국내가 아니라 **글로벌 대상 기획**. **검증→기획→모니터**, 최대한 많은 국가로 **송곳 타겟팅**."
2. (기획 형태) **갭/화이트스페이스 뷰** 선택.
3. "임계값을 **대시보드에서 직접 입력**(슬라이더)하게" → 범용 파라미터화 뷰.
4. "우린 **무베이스 중소기업**. 지금 곡 범위·성격·모수가 좁아 **'대기업 아니면 불가능'** 인상." → 깊이·넓이 개선 먼저(코호트/브레드스).
5. "**무베이스의 출발점은 차트가 아니라 소셜**" → pre-mainstream 소셜 선행신호.

## D-008 · 다국가 앵커-중립 지리 리프레임 (검증+기획)

- **레일**: Kworb Spotify **일간 76개국** 공개(인덱스 실측). `fetch --country XX`.
- **앵커 편향 제거**(`report.py` `_augment_geography`): 기존 국가 heatmap은 base country Top12만 투영 → 숨김. 신규 **최광역 랭킹**(전 시장 union, reach 순) + **지리 지문**(아티스트×시장 best rank). `--geo-scope KR` = entity-master country+별칭 로스터 필터(`_roster_canon`) — raw union은 서구 팝 헤게모니라 K-pop엔 스코프 필수. base=스코프국가.
- **명제 검증 성공**: 팀별 footprint 상이 — LE SSERAFIM(EA+서구) / BTS(동남아 TH#1·중남미) / CORTIS(EA+SEA+MENA) / aespa·ATEEZ(역내) / NMIXX(EA only).
- **기획=화이트스페이스**(`_whitespace_view`): **개척 시장**(≥`market_min`팀=검증 K-pop 시장) 中 특정 팀 미진입=greenfield. LE SSERAFIM 갭=TH·VN·CORTIS=CL·BTS=SA.
- **인터랙티브 임계 = tunable 뷰**(스키마 승인): report-schema `chart.type:"tunable"` 추가(행렬+knob) → 대시보드 `Tunable.tsx` 슬라이더가 **client-side 재계산**(static-first). 범용 — 아무 모듈이나 재사용.
- 결정적 tie-break(최다 권역: 국가수→최고순위→권역순).

## D-009 · 신인 코호트 + 76개국 (대기업-전용 인상 반박)

- **엔티티 확장**(`entities.py`): `debut`(Wikidata P571)·`agency`(P264) — **MB→wikidata 링크(검증 QID)에서만**(이름검색 동명이인 Jimin=1955 회피). country **무회귀**: 신규 필드를 기존 커밋 맵에 **병합**(45/50 KR34 유지). WD 폴라이트 sleep(레이트리밋). 커버리지 debut 14·agency 25(그룹 P571 한정, 정직).
- **신인 코호트 뷰**(`_cohort_view`): 데뷔 ≥ (스냅샷연도−`ROOKIE_YEARS`=3). 5팀(CORTIS 2025·Big Hit / RESCENE 2024·The Muze=소형 / ILLIT 2024 / Hearts2Hearts 2025 / KiiiKiii 2025). 신인 최광역 **CORTIS 13개국**. "무베이스도 닿는다". 정직한 범위(CORTIS 13↔RESCENE 1).
- **브레드스**: 32→**76개국** 수집·fixture(`tests/fixtures/geo/`, 6.4M). 넓은 뷰(최광역/지문)는 진입 시장만 열-필터(75→51). 신인 뷰 13열.
- **한계**: debut 14/50 · **Kworb top-200=인컴번트 렌즈**(진짜 무명 미포착) → D-010으로.

## D-010 · pre-mainstream 소셜 선행신호 (fandom-pulse 사운드→아티스트)

- **조인**(`fandom_pulse/entities.py` 로컬 최소 매처 — chart-history **코드 import 없이 데이터만 공유**): IG 사운드 라벨 'Artist - Song'의 공식 아티스트를 공유 entity-master로 귀속. `--entities`.
- **뷰**: `Top 아티스트 · 사운드 확산` bar + `사운드 확산 아티스트`·`로스터 밖 확산` 지표 + 선행신호 insight.
- **실측 #kpopdance**: 사운드 확산 14팀 中 **로스터 밖 10팀**(izna 2024·KATSEYE·i-dle·ENHYPEN·ITZY…) = 차트로 안 잡히는 소셜 활성.
- **한계 정직**: 로스터=추적 top-50이라 established(IVE·ITZY) 혼입(미차트 단정 아님) · UGC('Original audio')·협업·표기차 누락 · **temporal 선행(소셜 t→차트 t+n)은 다일 collect가 본선**(다음).

## 상태 (전 게이트 green)

- ruff·pyright(양 모듈) · chart-history/fandom-pulse smoke·schema · PII 게이트 CLEAN · 결정성 · 하위호환(4개국 앵커, `--entities` 없이) · fandom-pulse 무회귀 · 정적 build/export(Vercel) · 대시보드 라이브(localhost:3000).
- 커밋 산출물: chart-history=76개국 KR-로스터 지리+코호트+화이트스페이스 / fandom-pulse=사운드→아티스트 선행신호.
- entity-master: 50팀(country 45·debut 14·agency 25·aliases·wd_id).

## 다음 후보 (사용자 대기)

1. **temporal 선행(본선)** — 다일 `collect`로 소셜 t → 차트 t+n. 3단계 모니터와 합류.
2. **소셜↔차트 브리지 뷰** — 대시보드 두 모듈 교차(소셜 高·차트 低=신흥 사분면). 지금 데이터로 가능.
3. **케이스 컨셉**(가상 그룹) · **댄스 모듈 v1**(플래그십, CV 툴체인 선행) · 화이트스페이스/코호트 v2(약진입 갭·ROOKIE_YEARS 슬라이더) · Vercel 배포.
