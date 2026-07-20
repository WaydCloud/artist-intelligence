# chart-history · TESTS (수용조건 · 완료조건)

> 이 조건들이 통과해야 "완료"다. CI 스모크가 핵심을 자동 검증한다([`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).

## 픽스처

- `tests/fixtures/kworb_spotify_{kr,global,us,jp}_daily.html` — Kworb Spotify Daily **테이블 스냅샷**(사이트 크롬 제외, 메타 주석에 `country` 포함). 각 200곡, 동일 일자.
- **엔티티 맵**은 공유 레이어로 승격 → [`../../packages/entity-master/entities.json`](../../packages/entity-master/entities.json) (KR 상위 50 아티스트, CC0 사실: id·name·country·type·source·**aliases**·**debut**·**agency**·wd_id). `enrich`(MusicBrainz+별칭 + Wikidata 폴백/링크)로 생성. 별칭(코르티스↔CORTIS)은 크로스언어 매칭용, debut/agency(v3.6)는 코호트 근거. (D-007)
- `tests/fixtures/kworb_spotify_kr_weekly.html` — (v3.2) KR **주간** 스냅샷(`Wks` 컬럼). 헤더 파서·크로스뷰 모멘텀 테스트용.
- `tests/fixtures/kworb_apple_kr.html` — (v3.3) **Apple** KR 스냅샷(3컬럼 `Artist - Title`, 아티스트 한글, 헤더 `</tr>` 생략). 파서 견고성·크로스소스 테스트용.
- `tests/fixtures/geo/*.html` — (v3.5/v3.6) Kworb Spotify Daily **다국가 스냅샷 76개국 + global**(동일 일자, 전 권역). 앵커-중립 지리 리프레임 + 신인 코호트([`RULES.md`](RULES.md) §4.5) 테스트용. `fetch --country XX`로 수집(레일 실측 76개국 전량).

## 스모크 (핵심 흐름)

```bash
# v3 (커밋 산출물) — 국가 교차 + 엔티티 원산지. 로컬(uv 미사용 시) PYTHONPATH 지정:
PYTHONPATH=modules/chart-history/src python -m chart_history analyze \
  modules/chart-history/tests/fixtures/kworb_spotify_kr_daily.html \
  modules/chart-history/tests/fixtures/kworb_spotify_global_daily.html \
  modules/chart-history/tests/fixtures/kworb_spotify_us_daily.html \
  modules/chart-history/tests/fixtures/kworb_spotify_jp_daily.html \
  --entities packages/entity-master/entities.json \
  -o modules/chart-history/output/
# v1(단일)·v2(다중, --entities 생략)도 유효 — 하위호환.
# 엔티티 맵 갱신(라이브): python -m chart_history enrich <snapshot> --top 50 -o <entities.json>
# → output/report.json 이 생성되고 report-schema 를 통과해야 한다.
```

## 수용조건

- [ ] **A. 핵심 흐름**: 유효 스냅샷 → `output/report.json` 생성 + 스키마 유효.
- [ ] **B. 값 무결성**: `차트 진입 곡` == 엔트리 수, 모든 스트림 `value ≥ 0`, `1위 일간 스트림`은 number.
- [ ] **C. 필수 지표/차트**: `metrics`에 진입곡·1위 포함, `charts`에 "Top 10 · 일간 스트림" 존재.
- [ ] **D. graceful(엔트리 0)**: 빈/형식오류 스냅샷 → 크래시 없이 유효 report + `insights`에 "엔트리 없음" 명시.
- [ ] **E. 결정성**: 같은 입력 2회 실행 → `generatedAt` 제외 동일 산출.
- [ ] **F. 윤리**: 리포트에 "히트/스타 예측·인기·실력 총점" 류 문구 없음. **Kworb 집계값 한계 + 단일 스냅샷 한계** 명시.
- [ ] **G. 게이트**: `ruff check` · `pyright` 통과.
- [ ] **H. (v2) 국가 교차**: 다중 국가 스냅샷 → `heatmap` 차트(rows/cols/cells) + 교차 지표, 매칭 한계 insight. 결정적.
- [ ] **I. (v2) 날짜 시계열**: 같은 국가·다른 날짜 스냅샷 → `line` 차트(x/series) + 기간 최고 상승.
- [ ] **J. (v3) 엔티티 조인**: `--entities` 제공 시 원산지 분포 bar + 국내(KR) 비중 지표 + 커버리지/출처/미해석 한계 insight. 미제공 시 하위호환(생략). 결정적.
- [ ] **K. (v3.1) Wikidata 폴백**: `enrich`가 MB 미해석분을 Wikidata로 보강, 레코드에 `source` 기록, 해석률 상승.
- [ ] **L. (v3.2) 헤더 파서**: daily(`Days`)·weekly(`Wks`) 둘 다 헤더 라벨로 정확 파싱. daily 무회귀.
- [ ] **M. (v3.2) 크로스뷰 모멘텀**: 같은 국가·날짜, 다른 chart 라벨(일간×주간) → `모멘텀` bar + 상승세 곡/최고 모멘텀 지표. 결정적.
- [ ] **N. (v3.2) 축적**: `collect`가 `<store>/<date>.html` 적재. `analyze <store-dir>`가 디렉터리 스냅샷을 날짜순 → 라인.
- [ ] **O. (v3.3) 크로스소스**: 같은 국가·다른 서비스(Spotify×Apple) → 제목 매칭 positioning heatmap + 양대 진입·편중 지표 + 커버리지 한계 insight. Apple(3컬럼·헤더 `</tr>`생략) 200곡 파싱. 결정적.
- [ ] **P. (v3.4) 엔티티 별칭 크로스언어**: `enrich`가 별칭 수집. 크로스소스가 별칭으로 크로스언어 아티스트 인식(코르티스↔CORTIS)·콜리전 방지. 커버리지 무회귀(엔티티 유무 동일). 결정적.
- [ ] **Q. (v3.5) 다국가 지리 리프레임**: `tests/fixtures/geo/`(≥6개국·GLOBAL 제외) → **앵커-중립** 뷰 2종(`최광역 랭킹`·`지리 지문` heatmap) + `조사 국가`·`최광역 곡/팀`·`최다 권역` 지표. `--geo-scope KR`이면 KR 로스터로 스코프(base=KR 홈차트)·타이틀 `[KR 로스터]`. 스코프 미지정 시 전 시장 union(서구 팝 지형, insight로 명시). **한계 필수**: reach는 조사 국가 집합 상대적·Spotify 단일 플랫폼(국내 코어 미반영)·평결 아님. <6개국은 앵커 Top12 뷰(하위호환). 결정적. 최다 권역 tie-break 결정적(국가수→최고순위→권역순).
- [ ] **R. (v3.5 기획) 갭/화이트스페이스 = tunable 뷰**: 로스터 스코프에서 `개척 시장`(≥`market_min`팀 진입) 지표 + **`chart.type:"tunable"`**(전체 로스터×시장 행렬 + `market_min` knob) 방출. 대시보드가 **슬라이더로 임계 직접 입력 → client-side 재계산**(개척 시장·갭 갱신, static-first). 빈칸=미진입=greenfield(초록 강조), 진입=회색순위. 팀별 미개척 insight(기본 임계). 스코프 없으면 생략. 스키마 `tunable` enum + 대시보드 `Tunable` 컴포넌트 동시 갱신(§0). 결정적(행렬은 입력 순서 무관).
- [ ] **S. (v3.6 코호트) 데뷔·에이전시 + 신인 지리**: `enrich`가 `debut`(Wikidata P571)·`agency`(P264)를 **MB→wikidata 링크(검증 QID)에서만** 수집(동명이인 오염 방지, country 무회귀). 로스터 스코프에서 **신인 코호트**(데뷔 ≥ 스냅샷연도−`ROOKIE_YEARS`) 지리 지문 heatmap + `신인 최광역` 지표 + "무베이스도 닿는다" insight. 데뷔 미해석 팀은 제외(§4.2 한계). 결정적.

## 검증 로그 (2026-07-18, v1~v3.4)

- A/B/C ✅ smoke: base 200 엔트리, schema valid (진입곡 200·고유 117·1위 CORTIS-REDRED).
- D ✅ 빈/`<table></table>` 입력 → 0곡·0차트·schema valid·exit 0, insights에 "엔트리 없음" 명시.
- E ✅ 같은 입력 2회 → `generatedAt` 제외 산출 동일(v1·v2·v3 모두 `deterministic: True`).
- F ✅ insights에 "Kworb 집계값…참고용" + "단일 일자 스냅샷…" + 매칭·엔티티 한계 병기.
- G ✅ ruff `All checks passed` · pyright `0 errors`.
- H ✅ KR/Global/US/JP → heatmap(cols=[KR,GLOBAL,US,JP]) + 교차 시장 4·최광역 CORTIS(3개국). 신호: KR 히트가 JP·Global엔 닿고 US엔 대부분 미진입.
- I ✅ 합성 2일 스냅샷(임시, 미커밋) → line(x=2일, series 3곡) + 기간 최고 상승 검증.
- J ✅ `--entities`(50팀) → 원산지 bar + 국내(KR) 비중 지표 + 커버리지/출처/미해석 한계 명시. 미제공 v1/v2 하위호환 확인.
- K ✅ Wikidata 폴백으로 해석 **36→45/50**(MusicBrainz 36 · Wikidata 9). 원산지 KR 34·US 5·JP 4·CA 1·IT 1, 미해석 5팀(스타일라이즈드 표기) 명시. 결정적.
- L ✅ 헤더 파서: daily(200·Days 88)·weekly(200·Wks 13) 정확, daily 무회귀(4개국 리포트 동일).
- M ✅ 일간×주간 → 모멘텀 bar + 상승세 7/19곡, 최고 모멘텀 RESCENE-Runaway(+5). 3차트(bar·bar·bar).
- N ✅ `collect` → `<store>/2026-07-16.html` 적재. `analyze <store2>`(합성 2일) → line(TrackY 2→1). 디렉터리 glob 작동.
- O ✅ Apple KR 200곡 파싱(헤더 `</tr>`생략 견고화). Spotify×Apple → positioning heatmap(RESCENE-Pretty Girl: Spotify 4 vs Apple 127, 편중 +123), 양대 진입 13/20, 커버리지·MBID 한계 명시. 결정적.
- P ✅ 별칭 수집(CORTIS→'코르티스' 등). 하이브리드 매칭: 커버리지 13 무회귀(엔티티 유무 동일) + 엔티티 확인 11곡(코르티스↔CORTIS). HANRORO↔한로로(별칭無)도 제목으로 유지. 레코딩 MBID 실측=불발(0건) 기록.

## 검증 로그 (2026-07-19, v3.5 다국가 지리)

- **레일 실측**: Kworb Spotify **일간 76개국** + global/weekly 공개 확인(인덱스 HTTP 200). 32개국+global 수집→`tests/fixtures/geo/`.
- Q ✅ `--geo-scope KR` → `[KR 로스터]` 최광역 랭킹(15곡×33시장)·지리 지문(Top10 아티스트) heatmap + 조사 국가 32·최광역 BTS-SWIM(14개국)·BTS 최다 권역 중남미(4개국·29%). base=KR(1위 CORTIS-REDRED). 결정적(2회 동일).
- **명제 검증(핵심)**: K-pop 팀별 지리 footprint **상이** — LE SSERAFIM(EA+서구, PL#136·SG#10) vs BTS(**중남미** TH#1·CL#1·AR#17·BR#35) vs CORTIS(EA+SEA+MENA) vs aespa/ATEEZ(EA+SEA 역내) vs NMIXX/YENA(EA only). → 송곳 타겟팅 신호 성립.
- **스코프 발견**: 스코프 미지정(raw union)은 서구 팝 지배(Justin Bieber·Ariana 28개국) → K-pop 관점엔 로스터 스코프 필수. `_roster_canon`으로 entity-master country=KR + 별칭 필터(109 KR 트랙/4101).
- 대시보드 ✅ 33열 heatmap 가로스크롤 렌더(라이트/다크), 딥링크 `#chart-history`. 핵심 흐름 관통.
- 한계 병기 ✅ reach 상대성·Spotify 단일 플랫폼(Melon/Circle 미반영)·평결 아님.
- Q(tie-break) ✅ BTS 동아시아4·동남아4 동점 → 최고순위(동남아 TH#1) 우선으로 **동남아** 결정(임의성 제거). 결정적.
- R(화이트스페이스) ✅ `--geo-scope KR` → 개척 시장 **11개국**(EA 4·SEA 4·MENA 2·CL 1) + **tunable 차트**(행렬 34팀×32시장 + market_min knob). 팀별 갭: **LE SSERAFIM=TH·VN**(서구까지 가며 SEA 코어 공백)·CORTIS=CL(LATAM 無)·BTS=SA(거의 완비). market_min 2↔3 동일(분포 이봉형: 1팀 플루크 vs 3팀+ 진짜시장, 2팀 시장 없음)·≥4면 8개국(민감도 有). 결정적.
- R(tunable/대시보드) ✅ 스키마 `tunable` enum 추가(schema-valid 무회귀) + `Tunable.tsx`(슬라이더+client 재계산) + `ChartCard` 디스패치. dev·**정적 build/export 무회귀**(typecheck·lint·`out/index.html`에 slider·갭 51셀 구움). 슬라이더 SSR 초기값(market_min=2)이 Python 계산과 일치(개척 11·BTS 갭 1). 초록=미개척 강조·회색=진입순위.

## 검증 로그 (2026-07-19, v3.6 코호트·브레드스 · D-009)

- **엔티티 확장** ✅ `enrich`가 debut(P571)·agency(P264)를 MB→wikidata 링크로 수집. **Jimin=1955 오류 회피**(링크 없으면 미해석). country **무회귀**(신규 필드를 기존 맵에 병합 → 45/50 KR34 유지). 커버리지 debut 14·agency 25(그룹 P571 한정, 정직).
- **레이트리밋** ✅ 초기 aespa/ILLIT country 회귀(503) → WD 폴라이트 sleep + delay 1.5로 8/8·45/50 회복.
- S(신인 코호트) ✅ 데뷔 ≥2023 5팀(CORTIS 2025·Big Hit / RESCENE 2024·The Muze / ILLIT 2024 / Hearts2Hearts 2025 / KiiiKiii 2025) 지리 지문 + 신인 최광역 **CORTIS 13개국** + "무베이스도 닿는다" insight. 정직한 범위(CORTIS 13 ↔ RESCENE 1개국). 결정적.
- **브레드스** ✅ 32→**76개국** 수집·fixture(조사 국가 75). 넓은 뷰(최광역/지문)는 진입 시장만 열-필터(75→51/52) — 가독성 유지하며 브레드스 확보. 신인 지문 13열.
- 무회귀 ✅ 하위호환(4개국 앵커)·fandom-pulse(공유 스키마)·결정성·ruff·pyright 전부 통과.

## 실패 시 → [`../../WORKFLOW.md`](../../WORKFLOW.md) 리커버리

우회 금지. 원인 격리 → 최소 수정 → 재현 픽스처 추가.

## 검증 로그 (2026-07-19, v4 멀티플랫폼 차트 레일 · D-016)

- **소스 어댑터** ✅ `collect --platform`(메타 `platform:` 주석) + `collect-apple`(Apple 공식 RSS JSON → 기존 스토어 계약 facts-only 테이블 변환 — parse/signals/analyze 무변경 재사용) + 파서 `Track` 컬럼(Kworb YouTube 레이아웃). 실측: apple/kr 100곡(2026-07-19) · youtube/kr(2026-07-17) 수집 성공.
- **signals 플랫폼 차원** ✅ `chart/<platform>/<cc>/` 글롭(`*/*/*.html`) + 구 레이아웃 하위호환(메타 없으면 spotify). 라이브 3플랫폼 시리즈: 1828 아티스트 · 28시장 · 3플랫폼. act별 `platforms` 맵 + provenance `platformCount`·혼합 최고순위 경고 방출. **실측 효과: RESCENE #2·Hearts2Hearts #3·KiiiKiii #14 — Spotify 단일 렌즈에선 전부 '미진입'이던 워치리스트 팀이 Apple/YouTube 온셋으로 표면화.**
- **게이트** ✅ ruff·pyright 0 · 정본 회고 픽스처 재생성(platforms=["spotify"]·platformCount 1, 브리지 프로필 병기 생략 확인) · 결정성 · flagship(76개국) 스모크 schema valid · daily_collect.ps1 3플랫폼 루프 + 스토어 마이그레이션(chart/<cc>→chart/spotify/<cc>) PS 파스 OK.

## 검증 로그 (2026-07-19, v4 플랫폼 교차 분석 · D-016 후속)

- **analyze v4** ✅ `--latest`(leaf별 최신 스냅샷)·중첩 스토어 글롭·`--watchlist`(캐노니컬 병합+히트맵 우선 행). base 선정 = geo_scope 국가 + **spotify 우선**(v1 섹션 대표 = 최심 레일 홈 차트 — apple RSS URL이 title 오염되던 결함 수정).
- **플랫폼 교차 증강** ✅ (플랫폼 ≥2 감지 시) 지리 뷰=spotify 서브그룹 유지 + ① KPI `차트 플랫폼`·`Spotify 렌즈 밖` ② **아티스트×플랫폼 히트맵**(워치리스트 우선: CORTIS [1,1,1]·RESCENE [2,2,2]·H2H [3,6,9]·KiiiKiii [14,17,–]·MEOVV [41,162,–]) ③ **Spotify 렌즈 밖 표면화 bar**(화사 yt#3·QWER·희대의·한로로·검정치마…) ④ 워치리스트 사각 insight + **순위 절대비교 금지** 경고(§0).
- **라이브 실측** ✅ 30스냅샷(spotify 28시장 + apple/kr + youtube/kr) → Spotify 렌즈 밖 **24팀**. daily_collect §1.5에 일일 analyze 편입 → 대시보드 탭 라이브화(정본 재현 레시피는 fixtures/geo·fixtures/multiplatform).
- **픽스처** ✅ `tests/fixtures/multiplatform/<platform>/kr/`(실 3플랫폼 KR, facts-only) — 오프라인 스모크 schema valid · 결정성 2회 동일 · flagship(geo 76개국) 무회귀 · ruff/pyright 0 · ps1 파스 OK.

## 검증 로그 (2026-07-19, v4.1 플랫폼 수평 병렬 · 사용자 "YouTube 영향력·수평 표시")

- **수평 전환** ✅ 플랫폼 ≥2 감지 시 base(단일 스냅샷 v1 리포트) 개념 제거 → `_build_platform_parallel`: 플랫폼별 1위 KPI 나란히(캐노니컬 표기 통일) → **홈(KR) Top10 × 렌즈 히트맵**(트랙 키 = 캐노니컬 아티스트+제목 소문자 — 코르티스↔CORTIS 접힘, 제목 표기차는 행 분리 한계) → **렌즈 네이티브 수치 bar**(youtube 조회 1.24M/일 vs spotify 스트림 106k/일 — 혼합·환산 없음) → 교차 증강 → 지리(spotify 서브그룹 = 최심 레일, "위계 아님" insight 병기).
- **표시 순서** = `PLATFORM_ORDER ["youtube","spotify","apple"]` — 위계가 아니라 표시 순서, 값=도메인 소유자 판단(사용자 2026-07-19: "YouTube는 범접할 수 없는 영향력 — 단, 수평으로"). §2.1.
- **실측(3렌즈 KR)**: 1위 3렌즈 전원 CORTIS - REDRED · 합의/발산 히트맵에서 화사(youtube-온리)·Jimin(spotify-온리)·CORTIS ACAI(apple #10) 등 렌즈별 발산 가시화.
- **게이트** ✅ ruff·pyright 0 · 멀티플랫폼 픽스처 스모크 schema valid · 결정성 2회 동일 · flagship(geo 76개국, 단일 플랫폼 경로) 무회귀 · 라이브 리포트 재생성 · 대시보드 스크린샷.

## 검증 로그 (2026-07-19, 광역 확장 · 3렌즈 × ~50시장)

- **시장 확장** ✅ config 3플랫폼 각 ~50시장(전 권역: 아시아·중동/아프리카·유럽·미주·오세아니아) + `home_market`(kr) 공식화 → ps1 `--geo-scope` 배선. 실측 수집: **spotify 50/50 · apple 49/49 · youtube 48/49** — 유일 실패 youtube `gb`는 Kworb 표기가 `uk`라서(수정·수집 완료, REGIONS 유럽에 uk 추가). 최종 **148 스냅샷 · 조사 국가 49**.
- **광역 실측**: Spotify 렌즈 밖 **24→346팀** · 최광역 곡 26개국(BTS) · 신인 최광역 CORTIS 10개국 · 워치리스트 다시장 확인(CORTIS 12시장·BABYMONSTER 8·ILLIT 7 — 전부 3렌즈). ruff 0 · ps1 파스 OK · 대시보드 스크린샷.

## 검증 로그 (2026-07-19/20, D-016 ①② — 통합 진입 지도 · 렌즈 온셋)

- **① 3렌즈 통합 진입 지도** ✅ 수평 뷰에 tunable(view=whitespace) 추가 — KR 로스터 37팀 × 42시장, 셀=어느 렌즈든 최고순위(빈칸=3렌즈 전부 미진입). 실측: BTS 30시장·LE SSERAFIM 28·CORTIS 11. spotify-only 화이트스페이스와 병존(제목 구분). 대시보드 기존 Tunable 컴포넌트 재사용(무변경).
- **② 렌즈 온셋** ✅ signals `platformOnsets`(act×렌즈 첫 관측일) + provenance `platformFirstDates` 방출 → 브리지 `_lens_onset_insight` 집계(**좌측 절단 보정**: 렌즈별 수집 첫날 온셋 제외). 현 실측: 다렌즈 온셋 988팀 전원 절단 → "유효 표본 0 — 다일 축적 후 열림" 정직 보고(§0). 내일부터 유효 표본 축적 시작.
- **게이트** ✅ ruff·pyright 두 모듈 0 · 멀티플랫폼 픽스처 스모크 결정성 · schema valid(4탭) · 대시보드 렌더 확인(광역: BABYMONSTER youtube #5·KATSEYE spotify-온리 #70 표면화).

## 검증 로그 (2026-07-20, v4.2 멜론 4번째 렌즈 · D-017)

- **공식 Melon MCP 실측** ✅ `get_music_chart(DAILY)` 4콜 페이지네이션 → TOP100 완주(이용권 계정). 원본 응답 `data/live/melon_raw/` 보존.
- **convert-melon** ✅ 응답 파일 → 스토어 스냅샷(100 entries, `chart/melon/kr/`, meta `platform: melon`·`tos_class: official-mcp`). 파서: 응답이 파이썬 repr 유사 + 곡/앨범명 내부 따옴표('선녀외전' 등)로 literal_eval 불가 → **고정 키 앵커 정규식**(`','issue_date'`·`'}` 경계). 병기 표기 정리("RESCENE (리센느)"→RESCENE·"아일릿(ILLIT)"→아일릿 — 별칭 인덱스가 양표기 흡수, 파스 왕복 확인). 픽스처 `tests/fixtures/melon/mcp_page_sample.txt` 오프라인 스모크 + 결정성 2회 동일.
- **4렌즈 편입** ✅ PLATFORM_ORDER=[youtube, melon, spotify, apple] · 수평 뷰 4렌즈(1위 KPI 4개·subtitle 렌즈 수 동적) · 시리즈 3188 아티스트·platforms 맵에 melon 합류 · 브리지 프로필 `apple+melon+spotify+youtube` 병기. **실측 발산: melon 1위 RESCENE vs 타 3렌즈 1위 CORTIS.** ruff·pyright 0 · schema valid.
