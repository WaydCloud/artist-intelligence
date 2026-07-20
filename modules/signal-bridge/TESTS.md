# signal-bridge · TESTS (수용조건 · 완료조건)

> 이 조건들이 통과해야 "완료"다. **로컬 검증이 게이트**(git/CI 미가동).

## 픽스처

- `tests/fixtures/social_series.json` — **실 데이터** social-buzz 시계열. fandom-pulse `signals`가 커밋된 `#kpopdance` facts-only 스냅샷에서 생성(14팀 × 5일). 재생성:
  `python -m fandom_pulse signals modules/fandom-pulse/tests/fixtures/ig_hashtag_kpopdance.json --entities packages/entity-master/entities.json -o modules/signal-bridge/tests/fixtures/social_series.json`
- `tests/fixtures/chart_store/*.html` — **합성** 다일 차트 스냅샷(6일, Kworb Spotify daily 형태). `tos_class: synthetic-fixture`로 라벨 — 실 데이터 아님, 브리지 시연용(§0). 상세: `tests/fixtures/README.md`.
- `tests/fixtures/chart_series.json` — chart-rank 시계열. chart-history `signals`가 위 store에서 생성(6팀 × 6일, `provenance.synthetic=true`). 재생성:
  `python -m chart_history signals modules/signal-bridge/tests/fixtures/chart_store --entities packages/entity-master/entities.json -o modules/signal-bridge/tests/fixtures/chart_series.json`
- **`tests/fixtures/chart_live_kr/2026-07-17.html`** — **실 데이터**(실증). 라이브 Kworb KR daily 스냅샷(facts-only 차트 테이블, D-005/D-007 패턴). `collect`로 재수집(라이브): `python -m chart_history collect --url https://kworb.net/spotify/country/kr_daily.html --store data/live/chart_kr --country KR`.
- **`tests/fixtures/chart_kr_series.json`** — 실 chart-rank 시계열(회고). chart-history `signals --reconstruct-days 21`이 위 실 스냅샷의 **Days 필드로 진입일 역산**해 생성(`provenance.reconstructed=true`). 재생성:
  `python -m chart_history signals modules/signal-bridge/tests/fixtures/chart_live_kr --entities packages/entity-master/entities.json --reconstruct-days 21 -o modules/signal-bridge/tests/fixtures/chart_kr_series.json`

## 스모크 (핵심 흐름)

```bash
# 정본(실증·회고) — 대시보드 커밋 산출물. 실 소셜 × 실 KR 차트(Days 역산):
PYTHONPATH=modules/signal-bridge/src python -m signal_bridge analyze \
  --social modules/signal-bridge/tests/fixtures/social_series.json \
  --chart  modules/signal-bridge/tests/fixtures/chart_kr_series.json \
  --theta-rank 200 --focus-social \
  -o modules/signal-bridge/output/
# 메커니즘 테스트(합성 fixture, 헤르메틱) — 배선·판정 로직 검증:
#   analyze --social …/social_series.json --chart …/chart_series.json -o <tmp>
# → output/report.json 생성 + report-schema 통과 → 대시보드 자동 탭.
```

## 수용조건

- [ ] **A. 핵심 흐름**: 두 signal-series → `output/report.json` 생성 + 스키마 유효.
- [ ] **B. 값 무결성**: 조인 수 = 양측 온셋 존재 팀 수, `중앙값 선행` = social-led lead 중앙값, 모든 지표 정합.
- [ ] **C. 조인·분류**: 로스터 팀은 캐노니컬(ATEEZ/ILLIT/LE SSERAFIM), 미매치는 원 라벨(YooA)로 조인. social-led/chart-led/social-only/chart-only 정확 분류.
- [ ] **D. graceful**: 잘못된 signal 역할(social↔chart)·빈 조인 → 크래시 없이 실패 메시지 또는 유효 report.
- [ ] **E. 결정성**: 같은 입력 2회 → `generatedAt` 제외 동일(두 이미터 + 브리지 3단 모두).
- [ ] **F. 정직성(§0)**: 합성 입력이면 **메커니즘 시연 경고**가 최상단 insight · lead≠인과·표본 극소 병기 · **반례(chart-led) 노출**.
- [ ] **G. 게이트**: `ruff check` · `pyright` 통과 + **기존 두 모듈 스모크 무회귀**.
- [ ] **H. 기준 원장(튜닝)**: θ_social·θ_rank가 CLI 노출(`--theta-social`·`--theta-rank`), 값 변경 시 분류 변화. RULES §3 원장과 일치.
- [ ] **I. 모듈 독립**: 브리지가 fandom-pulse·chart-history 코드 import 없음(데이터=signal-series만 공유).

## 검증 로그 (2026-07-19, v1 · D-011)

- **A** ✅ social(14×5) × chart(6×6) → `output/report.json` schema valid. 차트 3종: 선행 예시 line(ATEEZ) · 선행/지연 bar · 소셜-온리 관측대상 bar.
- **B/C** ✅ 추적 16 · 조인 4 · 소셜 선행 3 · 중앙값 선행 4일 · 소셜-온리 10 · 차트-온리 2. social-led=ILLIT(+6d)·ATEEZ(+4d)·LE SSERAFIM(+4d), chart-led=YooA(−1d, 반례), chart-only=aespa·The Weeknd, social-only=izna·KATSEYE·i-dle·ENHYPEN·ITZY 등 10팀(D-010 pre-mainstream). 조인 키 = 공유 entity-master 캐노니컬(로스터 ATEEZ/ILLIT/LE SSERAFIM + 미매치 원 라벨 YooA).
- **E** ✅ chart-series·social-series·bridge-report 3단 모두 `generatedAt` 제외 2회 산출 동일(DETERMINISTIC).
- **F** ✅ 최상단 insight = "⚠ 메커니즘 시연 — 차트측 입력이 합성 축적 fixture … 실증 아니라 … 배선·판정 로직 시연 … 라이브 다일 collect가 본선(§0)". lead≠인과·표본 극소·**chart-led 반례(YooA)** 병기. `provenance.synthetic=true`가 데이터 계약을 따라 전파(chart-history 이미터 → 브리지).
- **G** ✅ ruff `All checks passed` · pyright signal-bridge `0 errors`. 무회귀: chart-history flagship(76개국) · fandom-pulse(#kpopdance) 스모크 both schema valid.
- **H** ✅ θ_rank 50→30: ATEEZ/LE SSERAFIM 선행 4→**6일**, ILLIT 차트 온셋(min rank 38 > 30) 소멸 → **social-led→social-only 재분류**(소셜선행 3→2, 소셜온리 10→11). 임계값 CLI 노출(코드 은닉 없음), 분류가 값에 반응(§2.1 값=A&R 소유).
- **I** ✅ `signal_bridge/bridge.py`·`cli.py` — `chart_history`·`fandom_pulse` import 0. 공유는 signal-series JSON(데이터)뿐(D-007/D-010).
- 한계 정직: 차트측 **합성**(실증 아님) · 소셜 표본=단일 해시태그 스크랩 · 조인 N=4(극소) · top-200 천장 · lead=시간 순서(인과 아님). **실증 본선 = 라이브 다일 collect**(v2).

- [ ] **J. (v1.2 광역·D-013) 워치리스트 판단-지원**: `--watchlist` 제공 시 ① **커버리지 지표**(팔로우 N 중 소셜 X·차트 Y·양측 Z) ② **팀별 프로필 insight**(`[프로필] key — class · 소셜 N건·참여 E · 드라이버 · 차트 최고#R·시장 → 활용 옵션(§0)`) ③ **⚡ 신규 진입 알림**(차트 온셋이 창 최근 2일 + 소셜 신호 보유). 차트 시계열의 `markets`·소셜의 `engagement`/`drivers` 선택 필드 소비. 미제공 시 기존 산출(하위호환). 결정적.

## 검증 로그 (2026-07-19, v1.2 광역·워치리스트 · D-013)

- **J** ✅ `--watchlist`(9 acts) → 커버리지 `4/9 소셜 · 차트 6/9 · 양측 2` 지표 + 프로필 4건(izna: `social-only · 소셜 1건·참여 527 · 드라이버 izna - DRIP, #izna · 차트 미진입 → 조사·모니터 우선순위 후보`) + subtitle 시장 수 표기. 다시장 차트 시계열(`markets` 맵·28시장 실측 수집 28/28 성공) 소비 확인. 하위호환(미제공·합성 메커니즘·flagship 스모크) 무회귀. 결정적(3단 x2). ruff·pyright 0. 변수 섀도잉 버그(`watch`) pyright가 포착 → `only_rows`로 해소.

- [ ] **K. (UX·D-013) 프로필 카드 규약**: 프로필 insight가 RULES §4.1 라인 문법을 만족(자유텍스트의 구분자 시퀀스는 이미터 `_seg`가 무공백형으로 접음) → 대시보드 `ProfileCards`가 구조화 카드 렌더, 문법 위반 라인은 평문 폴백. **스키마 무변경**(프로필은 여전히 평문 insight).

## 검증 로그 (2026-07-19, 프로필 카드 뷰 · D-013 UX)

- **K** ✅ `_seg` 새니타이즈(`" — "`·`" · "`·`" → "` → 무공백 접기: 키·드라이버·YT 제목) 후 정본 재생성 — 프로필 9/9 라인이 대시보드와 동일 문법 파서 통과. `apps/dashboard/components/ProfileCards.tsx`: `[프로필]` insight 분리 → 카드 그리드(분류 배지 = 시리즈 색 점+텍스트 라벨 — good/bad 토큰 미사용, 평결로 안 읽히게 §0) · 파싱 실패 시 평문 폴백 · 기존 인사이트 리스트에서 프로필 제외.
- **게이트** ✅ ruff 0 · pyright 0 · schema valid · 결정성(2회 `generatedAt` 제외 동일) · 대시보드 typecheck/lint/build(static export) 통과 · signal-bridge 탭 라이트/다크 스크린샷 — 9카드 3열 그리드·배지·폴백 없음 확인.

- [ ] **L. (UX·v1.3) θ 튜너 + 교차 링크**: `tunable(view=leadlag)` 차트가 원자료 시계열+knobs를 싣고(RULES §2), 대시보드 재계산 규칙이 §3 온셋 정의와 **동일**(패리티: 기본 θ 재계산 = 리포트 지표). 대시보드가 subtitle/insight의 모듈 id를 감지해 소스 모듈 탭 링크 렌더.

## 검증 로그 (2026-07-19, θ 튜너·교차 링크 · v1.3)

- **L** ✅ `_tunable_leadlag`: 분석 유니버스 rows의 소셜/차트 원시계열 + θ knobs(social 1..10 · rank 10..200) 방출 — 4번째 차트, schema valid(스키마 enum의 기존 `tunable` 사용, 무변경). **패리티 검증**: tunable data에서 기본 θ(1/200)로 §3 규칙 재계산 → social-led 0·조인 7·social-only 7·chart-only 0 = 리포트 지표와 일치(PARITY OK). 대시보드 `Tunable`이 view로 디스패치(whitespace 무회귀), `LeadLag` 듀얼 슬라이더 → 분류 카운트 + 발산 바(양수=--series·음수=--series2) 실시간 재계산.
- **교차 링크** ✅ subtitle에 YT 소스 병기(`× YT(yt-pulse)`, --youtube 시) → 대시보드가 subtitle/insight 본문의 다른 모듈 id 감지 → `소스 모듈: chart-history ↗ fandom-pulse ↗ yt-pulse ↗` 탭 전환 칩(범용 — 모든 모듈에 적용).
- **게이트** ✅ ruff·pyright 0 · 합성 스모크(워치리스트 미제공) 4차트 schema valid · 대시보드 typecheck/lint/build · 라이트/다크 스크린샷(튜너 슬라이더·칩 확인).

## 검증 로그 (2026-07-19, 실증·회고 · D-012)

- **라이브 레일** ✅ `chart-history collect` → 실 Kworb KR/GLOBAL daily 스냅샷(snapshot_date 07-17, Spotify 일간 1~2일 지연이라 최신 완성일). 무료·저ToS(D-005). fixture 커밋(facts-only).
- **회고 실증** ✅ 실 소셜(social_series) × 실 KR 차트(`--reconstruct-days 21`, Days 역산) → **소셜 선행 0 · 차트 선행(소셜 지연) 7팀**: ATEEZ −14d·IVE −13d·ILLIT −19d·LE SSERAFIM −19d·BOYNEXTDOOR −20d·BABYMONSTER −19d·YEONJUN −3d. **소셜-온리 관측대상 7팀**(izna·i-dle·ENHYPEN·ITZY·KATSEYE·iKON·YooA). 버즈 없는 차트곡 112 제외(--focus-social).
- **정직 결론**(§0) ✅ "소셜이 차트를 선행한다"는 순진한 가설 **반증** — #kpopdance는 이미 뜬 곡의 댄스 커버라 established엔 **후행**. 선행 후보는 social-only 코호트(전향 검증 필요). line 예시(LE SSERAFIM): 차트 강도 플랫-고 + 소셜 07-15 급등 = "차트 먼저, 소셜 나중" 시각화.
- **재구성 정직성** ✅ `provenance.reconstructed=true` 전파 → 브리지 최상단 insight "진입일은 실제, 중간 순위 근사, 재진입 시 Days 리셋". synthetic 경고 아님(실 데이터).
- **결정성** ✅ recon-series·real-bridge 2회 `generatedAt` 제외 동일.
- **게이트** ✅ ruff `All checks passed` · pyright 3모듈 `0 errors` · schema valid · **하위호환**(합성 메커니즘 스모크 3차트·chart-history flagship·fandom-pulse) 무회귀 · 대시보드 build/screenshot(라이트+다크).
- **한계 정직**: 단일 시장(KR)·단일 해시태그 · Days 재진입 리셋 · 중간 순위 근사 · **회고 단일 스냅샷이라 선행 방향(social-only→차트) 증명 불가 → 전향 다일 collect가 본선(다음)**.

## 실패 시 → [`../../WORKFLOW.md`](../../WORKFLOW.md) 리커버리

우회 금지. 원인 격리 → 최소 수정 → 재현 픽스처 추가.
