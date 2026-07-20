# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 현재 위치 (세션 로테이션 인계점, 2026-07-20)

- 프로젝트: `C:\Projects\artist-intelligence`.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식/도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 4종 관통** (핵심 흐름 `모듈 CLI → 스키마 유효 report.json → 대시보드` 전체):
  1. **chart-history v4.2** — 차트 **4렌즈**(D-016/D-017: Kworb Spotify 50시장 + Apple 공식 RSS 49 + Kworb YouTube 49 + **멜론 공식 MCP** KR) · **플랫폼 수평 병렬 리포트**(1위 KPI 나란히·Top10×렌즈 합의/발산·네이티브 수치 bar·`PLATFORM_ORDER=[youtube, melon, spotify, apple]` — 값=도메인 소유자) · **3렌즈 통합 진입 지도**(로스터×시장 whitespace tunable) · 지리 리프레임(spotify 서브그룹=최심 레일, 위계 아님 명시) · **렌즈 온셋 시차**(platformOnsets → 브리지 좌측 절단 보정 — 다일 축적 후 유효 표본) · daily `analyze --latest`로 탭 라이브화.
  2. **fandom-pulse v3.1** — IG 해시태그 화력·참여·모멘텀·사운드 + 이중 귀속(사운드+태그) + **`tag_aliases` 귀속 전용 은어 태그**(11팀 웹 조사 반영, 인덱스 12→51태그 · 모호 태그 배제 기준 RULES §3).
  3. **signal-bridge v1.3** — 3소스 조인·분류·판단-지원(커버리지·**프로필 카드**(RULES §4.1 라인 규약→`ProfileCards.tsx`)·⚡알림·**θ 튜너**(tunable leadlag, 패리티 검증)·교차 링크·렌즈 온셋 insight). 정직성 플래그 전파(§0).
  4. **yt-pulse v1** — 워치리스트 공식 채널 velocity·신작(무료 ~12u/일, D-014).
- **공유 계약 3층**: `snapshot-schema` · `signal-series`(선택 필드: engagement/drivers/markets/**platforms**/**platformOnsets**) · `report-schema`(무변경 유지). + PII 게이트 + `packages/entity-master`(entities+watchlist).
- 로컬 툴: Python 3.14 · Node 24 · **git 아님**(로컬 검증이 게이트). `jsonschema`·`ruff`·`pyright`. Edge 헤드리스 스크린샷. dev+build 충돌은 prebuild 가드 차단(`check-dev-off.mjs`, 우회 `AI_ALLOW_BUILD=1`).
- 키: `FIRECRAWL_API_KEY`·`YOUTUBE_API_KEY`·`APIFY_TOKEN` User scope. **Melon MCP**: `.mcp.json` 등록(OAuth — 토큰 단기 만료, 세션에서 `/mcp` 재연결 필요할 수 있음).

## 🔴 가동 중: 전향 실증 자동 수집 (매일 09:00, 사용자 승인 $100/월)

- **Task Scheduler `AI-daily-collect`** → `scripts/daily_collect.ps1`(ASCII-only, config 주도).
- 매일: 무료 차트 **3플랫폼 × ~50시장**(spotify/apple/youtube — 멜론은 아래 세션-보조) + chart-history 수평 뷰 갱신 + **유료 소셜**(D-015 **태그 할당기**: 상시 pin+genre → K=5일 강제 → 점수(⚡차트진입 w3·YT velocity·수율·탐험), 예산 $3/일 강제, 플랜 `data/live/plans/`) + 무료 YT + PII 게이트 → series 3종 → bridge → 대시보드 4탭. 로그 `data/live/logs/daily.log`.
- **워치리스트 11팀**(`watchlist.json`, 사용자 소유): pin 7(MEOVV·KiiiKiii·ILLIT·RESCENE·CORTIS·KISS OF LIFE·KEYVEATZ) + 비-pin 4(izna·KATSEYE·BABYMONSTER·Hearts2Hearts). 12태그=12슬롯이라 아직 전량 매일(순환은 확장 시 발동). 문법: `pin: true`(상시)·`hashtags: []`(무료 레일만)·`tag_aliases`(귀속 전용 은어).
- **멜론(D-017) = 세션-보조 수집**: 세션에서 "멜론 수집" → MCP `get_music_chart(DAILY)` 4콜 → `data/live/melon_raw/` → `convert-melon` → `chart/melon/kr/` → 분석 자동 합류. 화이트리스트 회신 오면 자체 수집기(OAuth 리프레시)로 스케줄 편입.
- **관전 포인트**: `소셜 선행`(현재 4팀 — 창 비대칭 유의) · ⚡신규 진입 · 커버리지 · **렌즈 온셋 유효 표본**(현재 0 — 좌측 절단, 다일 축적 후 열림) · D-015 순환 동작. 확인: `python scripts/bridge_summary.py`.
- **가드**: PAUSE 파일 · `experiment_end=2026-08-19` · `AI_DRYRUN=1`. 중단: `schtasks /Delete /TN "AI-daily-collect" /F`. 런북: [`docs/EXPERIMENT-forward-leading.md`](docs/EXPERIMENT-forward-leading.md).
- ⚠ 커밋 `output/report.json`은 스케줄 실행 시마다 라이브로 덮어씀(재현 레시피는 TESTS·아래 메모).

## 방금 끝낸 것 (2026-07-19~20 아크 요약 — 상세: [`Handoffs/2026-07-19-signal-bridge.md`](Handoffs/2026-07-19-signal-bridge.md))

- **프로필 카드 뷰**(RULES §4.1) → **D-015 태그 할당기**($3 고정 예산 순환, 36태그 시뮬 검증) → **pin 7팀+신규 2팀**(KISS OF LIFE·KEYVEATZ, YT resolve) → **은어 심층 귀속**(`tag_aliases`, 3 병렬 에이전트 조사, 12→51태그) → **θ 튜너+교차 링크** → **D-016 멀티플랫폼**(Apple RSS+YouTube, 3×~50시장 광역, 수평 병렬 리포트, 통합 진입 지도, 렌즈 온셋 메커니즘) → **D-017 멜론 4번째 렌즈**(공식 MCP·convert-melon·세션-보조).
- **실측 하이라이트**: Spotify 렌즈 밖 346팀 · **멜론 1위 RESCENE vs 타 3렌즈 1위 CORTIS**(1위 레벨 렌즈 발산) · 워치리스트 5팀 멜론 TOP100 내 · RESCENE 프로필 `#1·apple+melon+spotify+youtube`.
- 게이트 전부 그린(ruff·pyright 4모듈 0 · schema · 결정성 · 하위호환 · 스크린샷). dev+build 크래시 1회 → prebuild 가드 신설.

## 바로 다음 (재개 첫 액션) — 사용자 "다음 단계로 진행" 선언됨

1. **yt-pulse v2** ← 직전 세션에서 다음 후보로 지목 — **레이블 채널 영상 레지스트리**(HYBE LABELS 등 레이블 채널에 올라오는 워치리스트 MV 포착 — 공식 채널-온리 사각 해소) · **댓글 밀도**(센티먼트 1순위 앵커, DATA_SOURCES). 기준 원장 필수.
2. **실험 모니터/확정** — 며칠 축적 후: 소셜 선행·⚡진입·렌즈 온셋 유효 표본·D-015 순환 확인 → D-018로 기록.
3. **멜론 화이트리스트 회신 처리** — 회신 오면 자체 수집기(OAuth 리프레시 + MCP HTTP) 구현 → daily 편입. (아래 '대기' 참조)
4. **결측≠무신호 시리즈 전파**(D-015 v2) — 태그 순환 발동 전 정합성 기반. 워치리스트 확장 시 필요.
5. **댄스 모듈 v1(DD 플래그십)** — 문서만 있음. 지표 엔진(순수 numpy) 선행 가능.
6. 케이스 스터디(사용자 주도) · Vercel 배포 · 써클차트 제휴 신청.

## 열린 결정 / 대기

- **멜론 화이트리스트 문의 발신 완료(2026-07-20, 사용자)** → `melon_info@kakaoent.com` 회신 대기. 회신 내용 공유되면 자체 클라이언트 구현. **이용권 필요 여부 미확정**(차트 조회는 불필요 추정 — 확정은 이용권 만료 후 재실측, 또는 회신에서 확인).
- 써클차트 '차트제휴신청'(kpia.or.kr, 한국대중음악산업협회) — 열린 경로. 공공데이터 경로는 국내 차트 미보유로 배제 확정(D-017 조사).
- 케이스 스터디 컨셉 미정 · DOMAIN.md 인사이더 보강(Q2·Q3) 대기 · 배포 static-first(D-003).

## 로컬 실행 메모

```bash
# ── 멜론 세션-보조 수집(D-017): 세션에서 MCP get_music_chart(DAILY) 4콜(start=1,31,61,91) →
#    원본을 data/live/melon_raw/<date>_pN.txt 로 저장 후:
PYTHONPATH=modules/chart-history/src python -m chart_history convert-melon \
  data/live/melon_raw/<date>_p*.txt --store data/live/chart/melon/kr --date <date>

# ── 라이브 재생성(수집 후 전체 관통):
PYTHONPATH=modules/chart-history/src python -m chart_history signals data/live/chart \
  --entities packages/entity-master/entities.json --watchlist packages/entity-master/watchlist.json \
  -o data/live/chart_series.json
PYTHONPATH=modules/signal-bridge/src python -m signal_bridge analyze \
  --social data/live/social_series.json --chart data/live/chart_series.json \
  --youtube data/live/yt_series.json --theta-rank 200 --focus-social \
  --watchlist packages/entity-master/watchlist.json -o modules/signal-bridge/output/
PYTHONPATH=modules/chart-history/src python -m chart_history analyze data/live/chart --latest \
  --entities packages/entity-master/entities.json --watchlist packages/entity-master/watchlist.json \
  --geo-scope KR -o modules/chart-history/output/
node apps/dashboard/scripts/collect-reports.mjs

# ── 회고 정본(커밋 fixture) 재생성: modules/*/TESTS.md 레시피 참조 (bridge: social/chart_kr/yt series → analyze)
# ── 멀티플랫폼 오프라인 스모크: analyze modules/chart-history/tests/fixtures/multiplatform --latest --entities … --watchlist … --geo-scope KR
# ── 멜론 변환 스모크: convert-melon modules/chart-history/tests/fixtures/melon/mcp_page_sample.txt --store <tmp> --date 2026-07-20
# ── 광역 수집 수동 1회: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_collect.ps1  (리허설 AI_DRYRUN=1)
# ── yt 채널 재해석(워치리스트 변경 시): PYTHONPATH=modules/yt-pulse/src python -m yt_pulse resolve --watchlist packages/entity-master/watchlist.json -o packages/entity-master/yt_channels.json
# ── 게이트: python -m ruff check modules/ scripts/ · python -m pyright modules/<m> · <m> validate output/report.json
# ── 대시보드: cd apps/dashboard && npm run dev  (build는 dev 끈 뒤 — prebuild 가드가 막아줌)
```
