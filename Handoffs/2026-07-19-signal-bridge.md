# Handoff 스냅샷 · 2026-07-19 · signal-bridge (소셜→차트 선행신호, D-011)

> D-010 "다일 collect가 본선"의 배선. 세 번째 세로 슬라이스 = **두 모듈을 시간축으로 조인**.

## 한 일

- **새 모듈 `signal-bridge`** (관통 3번째): fandom-pulse `social-buzz` × chart-history `chart-rank` 시계열을 공유 entity-master 캐노니컬로 조인 → **온셋·선행/지연(lead/lag)·분류** → 스키마 유효 report.json → **대시보드 자동 탭**(collect-reports가 수집, 스키마·대시보드 무변경).
- **두 소스 모듈에 `signals` 서브커맨드 추가** (자기 귀속 로직 재사용, 하위호환 신규 서브커맨드):
  - fandom-pulse `signals`: IG 스냅샷 → (일자×아티스트) 게시수 시계열. `build_signal_series`(report.py).
  - chart-history `signals`: 다일 스냅샷 store → (일자×아티스트) 최고순위 시계열. `build_chart_signal_series`(report.py). `tos_class:synthetic-fixture` 감지 → `provenance.synthetic=true` 전파.
- **공유 데이터 계약 `signal-series`** (정본: `modules/signal-bridge/SPEC.md`) — report-schema의 시간축 짝(D-007). 브리지는 두 모듈 코드 import 0 (데이터만 공유, D-010).
- **정직성(§0)**: 차트측 입력은 **합성 축적 fixture**(실 다일 collect 미확보) → 리포트 최상단 **"메커니즘 시연, 실증 아님"** 경고를 데이터-전파 플래그로 강제. 반례(chart-led)도 노출. `tests/fixtures/README.md`·chart_store meta에 SYNTHETIC 명시.
- **기준 원장(§2.1)**: θ_social·θ_rank CLI 노출(RULES §3). θ_rank 50→30 → ILLIT social-led→social-only 재분류(값이 판정을 바꿈, 실측).
- **대시보드 개선**: 범용 `LineChart`를 **다중 계열+범례+nice-tick**으로(계약 LineData.series 배열을 온전히 렌더). 단일 계열 하위호환(정수 눈금 8·6·4·2·0). `--series2/3` CSS 변수 3테마 추가.

## 실측 결과 (합성 차트 fixture 기준 — 시연값, 실증 아님)

- 추적 16팀 · 조인 4 · **소셜 선행 3**(ILLIT +6d·ATEEZ +4d·LE SSERAFIM +4d) · 중앙값 선행 4일 · **차트 선행(반례) 1**(YooA −1d) · **소셜-온리 관측대상 10**(izna·KATSEYE·i-dle·ENHYPEN·ITZY 등, D-010 pre-mainstream) · 차트-온리 2(aespa·The Weeknd).
- line 차트: ATEEZ 소셜 버즈(파랑, 07-14~17 선행) vs 차트 강도(주황, 07-18~24 후행) — 선행이 시각적으로 드러남.

## 게이트 (전부 그린, 로컬)

- ruff `All checks passed` · pyright 3모듈 `0 errors` · report-schema 3개 valid · 결정성 3단(social/chart/bridge) OK · 하위호환(chart-history 76개국 flagship·fandom-pulse) 무회귀 · 대시보드 tsc/eslint/prod build 통과 · 라이트+다크 스크린샷 확인.

## 파일

- 신규: `modules/signal-bridge/{SPEC,RULES,TESTS}.md` · `src/signal_bridge/{__init__,__main__,cli,bridge}.py` · `tests/fixtures/{social_series,chart_series}.json`·`chart_store/*.html`·`README.md` · `output/report.json`.
- 수정: `modules/fandom-pulse/src/fandom_pulse/{report,cli}.py` · `modules/chart-history/src/chart_history/{report,cli}.py` · `apps/dashboard/components/charts/LineChart.tsx` · `apps/dashboard/app/globals.css` · `apps/dashboard/data/reports.json` · `docs/DECISIONS.md`(D-011).

## 실증(회고) — D-012 (같은 세션 후반)

- **라이브 레일 검증**: `chart-history collect` → 실 Kworb KR/GLOBAL daily(무료·저ToS, D-005). snapshot_date 07-17(Spotify 일간 1~2일 지연). 실 KR 스냅샷을 facts-only **재현 fixture 커밋**(`tests/fixtures/chart_live_kr/`).
- **회고 실증 모드**: chart-history `signals --reconstruct-days N` — 단일 라이브 스냅샷의 **Days(차트인 일수)로 진입일 역산**(`entry=snapshot−(Days−1)`, 실 온셋). 브리지 `--focus-social`(버즈 있는 팀만) + chart-led exemplar + `reconstructed` insight.
- **결과(§0 정직)**: 실 소셜 × 실 KR 차트 → **소셜 선행 0 · 차트 선행 7팀**(ATEEZ −14d·IVE −13d·ILLIT −19d·LE SSERAFIM −19d·BOYNEXTDOOR −20d·BABYMONSTER −19d·YEONJUN −3d) · **소셜-온리 7팀**(izna·i-dle·ENHYPEN·ITZY·KATSEYE·iKON·YooA). → **"소셜이 차트를 선행한다" 순진한 가설 반증** — #kpopdance=이미 뜬 곡의 댄스 커버=후행(D-009 인컴번트 렌즈 실증). 선행 후보=social-only 코호트.
- **대시보드 정본 = 실 회고 결과**(합성 데모 대체; 합성은 헤르메틱 메커니즘 테스트로 잔존). line 예시(LE SSERAFIM): 차트 강도 플랫-고 + 소셜 급등 → "차트 먼저, 소셜 나중" 시각화.
- 게이트: ruff·pyright 0·schema·결정성(recon+bridge)·하위호환·라이트/다크 스크린샷 모두 그린. `data/live/` gitignore 추가.

## 광역 수집 체계 — D-013 (같은 세션 최후반, 사용자 "$100/월·압도적 개선")

- **워치리스트 1급 데이터**(`packages/entity-master/watchlist.json`, 사용자 소유): 팔로우 acts 9팀 시드(key·별칭·해시태그) + `overrides` 정정 계층(Jin=MC Jin 오귀속→BTS 진·BTS agency Avex→Big Hit). 모든 모듈 로더가 entities 위에 병합. entities.json mojibake 키 정정.
- **config 주도 수집**(`config/collect.json`): 차트 **28시장/일**(Kworb 무료, 실측 28/28 성공) · 소셜 **10태그/일**(#kpopdance + act 태그 자동 파생, 태그당 100건·$0.25 캡, 일 예산 $3 누적 강제 → 월 ≤~$93). daily_collect v2: PII 게이트 즉시 실행+격리, 시장 서브디렉터리 store(`data/live/chart/<cc>/`), 마이그레이션 자동.
- **이중 귀속**(fandom-pulse v3): 사운드 + **워치리스트 해시태그 직접 귀속**(UGC 사운드 사각 해소) + engagement·drivers. **다시장 차트 시계열**: 전 시장 최저 rank + markets 맵(역산 모드도 다시장).
- **브리지 판단-지원**: `--watchlist` → 커버리지 지표(4/9 소셜·6/9 차트) + **팀별 프로필**(누가·얼마나·왜·활용 옵션, §0) + **⚡ 신규 차트 진입 알림**. pyright가 변수 섀도잉 버그 포착(`watch`→`only_rows`).
- 게이트: ruff·pyright 0 · 결정성 3단 · 하위호환(flagship·v2·합성) 무회귀 · 실전 광역 1회차 수집 실행.

## YouTube 레일 — D-014 (같은 세션 종반, 사용자 "유튜브 레일은 필수")

- **신규 모듈 `yt-pulse`**(4번째 관통): `resolve`(search 1회성→커밋 캐시 `yt_channels.json`, 비-Topic 우선 — KATSEYE 'Topic' 오매칭 실사례 포착·해결) → `fetch`(일일 ~12 units 무료, snapshot-schema+PII CLEAN) → `analyze`(대시보드 4탭 자동) → `signals`(`yt-velocity` + `subscribers`·`videos` 선택 필드).
- **velocity 프록시** = views÷경과일(수명 평균 근사, 한계 원장 명시 — 다일 축적 시 실측 증분 대체). **신작 감지**(`--recent-days` 14) = 캠페인 활성.
- 실측: 9/9 채널 · 45영상 · 구독 12.7M(BABYMONSTER)~507k(KiiiKiii) · 최고 velocity 1.31M/일(KATSEYE) · 최근작 조회 합 25.2M.
- **브리지 3-소스화**: `--youtube` → 프로필에 `YT 구독 788k·'…' +427.3k/일` 병기 + 커버리지 `YT 9/9` + **창 비대칭 경고**(태그 소급 소셜 창 vs 차트 창 — 회고 lead 과신 방지). no-signal 클래스(무신호도 정보).
- daily_collect에 무료 YT 스텝 편입(게이트 포함). 통합 드라이런 완주. 게이트: ruff·pyright 4모듈 0 · schema 4 valid · 결정성 · 4탭 스크린샷.

## 남은 것 (다음)

- **전향 관측**: 스케줄이 매일 3-소스 광역 수집 — `소셜 선행` 0→1+·⚡알림·커버리지 추이 확인(며칠). 결과 → D-015. 다일 축적 시 YT 실측 증분·소셜 실측 모멘텀 열림.
- 워치리스트 큐레이션(사용자) · θ tunable 슬라이더 · 프로필 카드 뷰 · yt-pulse v2(레이블 채널 레지스트리·댓글 밀도) · 댄스 모듈 v1.

## 프로필 카드 뷰 — D-013 UX (같은 날 후속 세션)

- **RULES §4.1 프로필 라인 표시 규약** 신설: `[프로필] <key> — <class>[(±Nd)] · 소셜 … · 드라이버: … · <차트요약>[ · YT …] → <활용>(§0)`. 구분자는 `" — "`·`" · "`·`" → "` 3종뿐 — 자유텍스트(키·드라이버·YT 제목)에 등장하면 이미터 `_seg`가 무공백형으로 접어 문법 보존(브리지 `bridge.py`).
- **대시보드 `ProfileCards.tsx`**: `[프로필]` insight를 인사이트 리스트에서 분리 → 3열 카드 그리드(소셜/드라이버/차트/YT 행 + 활용 푸터). 분류 배지 = 시리즈 색 점+텍스트 라벨(good/bad 토큰 미사용 — 평결로 안 읽히게 §0). **파싱 실패 라인은 평문 폴백**(규약=표시 향상, 계약 파괴 아님). **report-schema 무변경.**
- 검증(TESTS K): 정본 재생성 후 프로필 9/9 문법 통과 · ruff/pyright 0 · schema valid · 결정성 · 대시보드 typecheck/lint/build · 라이트/다크 스크린샷. 잔여: θ tunable 슬라이더 · 두 모듈 교차 링크.

## 스마트 태그 할당 — D-015 (같은 날, 사용자 워치리스트 확장 질의에서)

- **맥락**: 워치리스트 20~30팀 확장 시 전량 매일 수집 = $225~300/월 캡(승인 $100/월 초과), 기존 예산 가드는 뒷순서 태그 영구 스킵(기아). 사용자 선택: **$3/일 유지 + pin 직접 지정**.
- **구현**: `scripts/tag_allocator.py plan`(stdlib·결정적·무료 신호만) — 상시(genre+`pin: true`) → 강제(K=5일 경과·기아 방지) → 점수(⚡차트 신규 진입 w3 · YT velocity · 직전 수율 · 탐험/staleness). 수집 이력=`social/` 파일명 도출(상태 파일 없음). 플랜·사유 `data/live/plans/plan_<date>.json`. daily_collect.ps1 §2에 통합(실패 시 전량 폴백, 예산 가드 백스톱, ASCII 유지 — 한글은 .py에).
- **경계(§0)**: 워치리스트는 사용자 소유 — 알고리즘은 편집하지 않고 예산 배분만. 가중치·K = config `allocator` 노출(값=사용자 소유). 원장·한계(비-pin 온셋 해상도 ±수집 간격) = EXPERIMENT 런북.
- **검증**: 실 데이터 plan 10/10(12슬롯 내 전량·KATSEYE YT 부스트 확인) · 36태그 6일 시뮬(전 태그 수집·pin 4 매일·최대 간격 4일≤K5) · 결정성 2회 동일 · ruff/pyright 0 · PS5.1 통합 블록 실행 + ps1 전체 파스 OK.
- **워치리스트 문법 확장**: `pin: true`(매일 상시) · `hashtags: []`(무료 레일만 팔로우 $0) — watchlist.json $comment에 문서화(데이터 무변경).

## 워치리스트 심층화 — pin 지정 + 은어 귀속 (같은 날, 사용자 큐레이션)

- **pin 7팀**(사용자 지정): MEOVV·KiiiKiii·ILLIT·RESCENE·CORTIS + 신규 **KISS OF LIFE**(S2, 2023)·**KEYVEATZ**(키비츠, AOMG 첫 걸 크루 2026-06-30 데뷔, 웹 검증). YT resolve 2/2(비-Topic 공식 채널). 11팀=12태그=12슬롯 → 아직 전량 매일 수집.
- **사용자 피드백**: "watchlist가 근원소스인데 얕으면 다음 데이터가 전부 부족" — 은어(키키·키오라·영크크 등)를 제대로 매칭해야 함. → 메모리 저장(root-source-depth).
- **`tag_aliases` 필드 신설**(fandom-pulse entities.py): 귀속 전용 해시태그(수집 타겟 아님·과금 없음) — hashtags와 합쳐 hashtag_index 구성(충돌 시 hashtags 우선). RULES §3 원장 갱신 + **모호 태그 배제 기준**(일반어 충돌 라틴/한글 배제: 나야·KISSY·폼폼·H2H·코어).
- **11팀 웹 조사**(3 병렬 에이전트, 교차 확인·단일 소스는 low/미등록): 키키=공식 표기(키이키이 폐기)·티키(팬덤 TiiiKiii) / 키오프(공식 푸시)+키오라(통용) / 영크크(YOUNG CREATOR CREW 밈, 나무위키 단독 문서)·coer·redred / 베몬·baemon·monstiez / 글릿 / 리마인·안원잘부(원이 100만 채널 밈)·러브어택(역주행) / 하투하·s2u / eyekons+멤버 6태그 / keybeats / 이즈나. 귀속 인덱스 **12→51태그**.
- 게이트: ruff·pyright 0 · 정본 3종 재생성(커버리지 4/11·프로필 11건) · fandom-pulse 스모크 schema valid · 유료 태그 12개 불변. 검증 로그: fandom-pulse TESTS.

## θ 튜너 + 교차 링크 — 브리지 대시보드 심화 완결 (같은 날)

- **tunable(view=leadlag)** (RULES §2 신설): 브리지가 분석 유니버스의 소셜/차트 원시계열 + θ knobs를 4번째 차트로 방출(스키마 무변경 — enum 기존 tunable) → 대시보드 `LeadLag` 컴포넌트가 듀얼 슬라이더(θ_social 1..10 · θ_rank 10..200)로 온셋·분류·lead를 클라이언트 재계산(static-first). §2.1 완성형: A&R이 임계값을 대시보드에서 직접 돌려봄. **패리티 검증**: 기본 θ 재계산 = 리포트 지표 일치(TESTS L). Tunable은 view 디스패치로 분리(whitespace 무회귀).
- **교차 링크**: 대시보드가 subtitle/insight 본문의 다른 모듈 id를 감지해 `소스 모듈: … ↗` 탭 전환 칩 렌더(범용). 브리지 subtitle에 `× YT(yt-pulse)` 병기(--youtube 시)로 3소스 전부 링크.
- 게이트: ruff·pyright 0 · schema valid(4차트) · 합성 스모크 무회귀 · 대시보드 typecheck/lint/build · 라이트/다크 스크린샷.

## 멀티플랫폼 차트 레일 — D-016 (같은 날, 사용자 "Spotify 한정" 지적)

- **3플랫폼**: Kworb Spotify(기존 28시장) + **Apple 공식 RSS**(27 storefront, `collect-apple`이 JSON→facts-only 테이블 변환 — 파이프라인 무변경 재사용, ToS 최저) + **Kworb YouTube**(27시장, 파서 `Track` 컬럼 추가). 스토어 `chart/<platform>/<cc>/` + 자동 마이그레이션 + 구 스냅샷 spotify 호환.
- **signals**: 플랫폼 혼합 최고순위(진입 온셋용·절대비교 금지 경고) + act별 `platforms` 맵 → 브리지 프로필 `·apple+spotify+youtube` 병기(단일 spotify 생략). signal-series 계약에 선택 필드 `platforms` 추가(signal-bridge SPEC).
- **도입 당일 실측**: Apple KR top-5 = 코르티스 #1·리센느 #2/#5·H2H #3 · YouTube KR #1-2 = CORTIS·RESCENE. 3플랫폼 조인: **RESCENE #2·Hearts2Hearts #3·KiiiKiii #14** — Spotify 렌즈에선 전부 '미진입'이던 팀. 실 소셜 축적과 겹치며 워치리스트 4팀 social-led 분류 시작(창 비대칭 유의).
- 멜론(국내 정본, ToS 중간)은 **사용자 결정 대기로 보류**. 게이트: ruff·pyright 0 · 정본 재생성·결정성·flagship 무회귀 · ps1 3플랫폼 루프 파스 OK. 상세: chart-history TESTS v4 로그.

## chart-history v4 — 플랫폼 교차 분석 (같은 날, 사용자 "chart-history를 멀티플랫폼에 맞게 압도적 개선")

- **analyze v4**: `--latest`(leaf별 최신)·중첩 스토어 글롭·`--watchlist` → daily_collect §1.5가 매일 라이브 3플랫폼 스토어를 분석 — **chart-history 탭이 커밋 픽스처 정적 뷰에서 매일 갱신되는 라이브 교차 뷰로 전환**(지리 플래그십은 spotify 서브그룹 위에서 유지, base=spotify 홈 차트).
- **플랫폼 교차 증강**: KPI(차트 플랫폼·Spotify 렌즈 밖) + 아티스트×플랫폼 히트맵(워치리스트 우선) + Spotify 렌즈 밖 표면화 bar + 사각 insight. 순위 절대비교 금지 경고(§0) 병기.
- **실측**: Spotify 렌즈 밖 24팀 — 워치리스트(RESCENE·H2H·KiiiKiii는 다플랫폼 히트맵 행) + 국내 대중성 프록시(화사 yt#3·QWER·한로로·검정치마 = apple/youtube-온리, 멜론 없이도 국내 신호 일부 흡수).
- 픽스처 `tests/fixtures/multiplatform/` 커밋(오프라인 스모크·결정성). 게이트 전부 그린. SPEC v4·TESTS 로그.

## chart-history v4.1 — 플랫폼 수평 병렬 (같은 날, 사용자 "YouTube 영향력, 수평으로")

- 사용자 피드백: Spotify를 본편으로 두고 나머지를 부록화하지 말 것 — apple·youtube도 메인 메트릭, 특히 YouTube. 단 수평 표시.
- **재설계**: 멀티플랫폼 감지 시 base 리포트 제거 → 수평 병렬 조립(플랫폼별 1위 KPI 나란히 · 홈 Top10×렌즈 합의/발산 히트맵 · 렌즈 네이티브 수치 bar(환산 금지) · 교차 증강 · 지리=spotify 서브그룹은 "깊이 문제, 위계 아님" 명시). 표시 순서 `PLATFORM_ORDER=[youtube, spotify, apple]`(값=도메인 소유자, §2.1).
- 실측: 3렌즈 1위 전원 CORTIS - REDRED · youtube 조회 1.24M/일 vs spotify 106k/일(영향력 차이가 네이티브 수치로 노출) · 화사 youtube-온리 등 발산 가시화. 게이트 전부 그린(TESTS v4.1 로그).

## 광역 확장 — 3렌즈 × ~50시장 (같은 날, 사용자 "KR 핀 + 20~30개국, 집대성")

- config 3플랫폼 시장 각 ~50국(전 권역) + `home_market: kr` 공식화(ps1 --geo-scope 배선). **즉시 전량 수집**: spotify 50/50 · apple 49/49 · youtube 49/49(gb→uk 표기 수정) = 148 스냅샷.
- 결과: 조사 국가 49 · **Spotify 렌즈 밖 346팀** · 워치리스트 다시장·다렌즈(CORTIS 12시장) · 수평 뷰 subtitle "youtube 49시장 · spotify 50시장 · apple 49시장". 내일부터 스케줄이 이 폭으로 매일 자동.

## D-016 ①② — 통합 진입 지도 · 렌즈 온셋 시차 (2026-07-19/20 경계, 사용자 "바로 진행")

- **① 3렌즈 통합 진입 지도**: 수평 뷰에 KR 로스터 × 42시장 whitespace tunable(셀=어느 렌즈든 최고순위, 빈칸=진짜 공백). 화이트스페이스 질문의 정답을 플랫폼 불문 진입으로 승격.
- **② 렌즈 온셋 시차 메커니즘**: signals `platformOnsets`+`platformFirstDates` → 브리지 렌즈 선행 집계 insight(좌측 절단 보정 — 수집 첫날 온셋 제외). 현재 유효 표본 0(정직 보고), 다일 축적부터 "어느 플랫폼이 먼저 반응하나"가 열림. 계약: signal-bridge SPEC 선택 필드 · chart-history RULES §1 원장.
- 게이트 그린(두 모듈 ruff/pyright 0·결정성·schema). 멜론 레일은 여전히 사용자 ToS 결정 대기.

## 멜론 4번째 렌즈 — D-017 (2026-07-20, 공식 Melon MCP)

- 정식 경로 조사(사용자 선택) → **공식 Melon MCP 발견**(카카오엔터, OAuth) → 사용자 이용권 구매 → `.mcp.json` 등록·인증 → DAILY TOP100 실측(4콜) → `convert-melon`(정규식 앵커 파서·병기 표기 정리) → `chart/melon/kr/` 편입.
- 4렌즈 수평 뷰 가동: **melon 1위 RESCENE vs 타 렌즈 1위 CORTIS**(1위 레벨 렌즈 발산 실측). 워치리스트 5팀 멜론 TOP100 내. PLATFORM_ORDER=[youtube, melon, spotify, apple].
- **운영**: 세션-보조 수집(스케줄 미편입 — MCP는 대화형 OAuth. 세션에서 "멜론 수집" 요청 시 fetch→convert, 스냅샷 있으면 분석 자동 합류). 상시 자동화 필요 시 화이트리스트 문의(melon_info@kakaoent.com). D-017·TESTS v4.2 로그.

## 세션 종료 (2026-07-20 로테이션)

- 사용자: 멜론 화이트리스트 문의 메일 **발신 완료**(melon_info@kakaoent.com) — 회신 대기. 이용권은 일단 유지(차트 조회의 이용권 필요 여부는 미확정 — 만료 후 재실측 or 회신으로 확정).
- OAuth 관찰: Melon MCP 토큰 단기 만료(수 시간) + 자동 리프레시 없음 → 세션-보조 수집 확정, 자동화는 화이트리스트 경로.
- 다음 세션 1순위 후보: **yt-pulse v2**(레이블 채널 레지스트리·댓글 밀도). HANDOFF 재작성 완료.
