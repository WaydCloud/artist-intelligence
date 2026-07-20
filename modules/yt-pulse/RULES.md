# yt-pulse · RULES (불변식 · 기준 원장)

> §3이 이 모듈의 **기준 원장**([`../../AGENTS.md`](../../AGENTS.md) §2.1). 값 무결성은 [`TESTS.md`](TESTS.md)에서 검증.

## 1. 소스 · 수집 규칙 (§4 준수)

- 소스: **YouTube Data API v3**(공식·무료 quota 10k units/day, ToS 최저 — D-002 1순위 레일). 키 `YOUTUBE_API_KEY`(User env).
- **쿼터 규율**(DATA_SOURCES §3): `search.list`(100 units)는 **`resolve`에서만**(1회성·명시적) → 커밋 캐시 `packages/entity-master/yt_channels.json`. 일일 `fetch`는 `channels.list`·`playlistItems.list`·`videos.list`(~1 unit)만 = **~12 units/일**(워치리스트 9팀 기준).
- **수집과 분석 분리**: `resolve`/`fetch`(라이브) ↔ `analyze`/`signals`(오프라인·결정적, 스모크). 스모크는 네트워크 금지.
- **facts-only만 저장**: 영상당 `artist(캐노니컬)·video_id·title·published_at·views·likes·comments·duration_s·type·subscribers`. **개인 데이터·댓글 원문·시청자 정보 없음** — 전부 공개 집계 지표(§4). 스냅샷은 snapshot-schema 계약 + PII 게이트.
- **채널 캐시 = 정정 가능**: `resolve`는 검색 top-1 채널을 기록(`channel_title` 병기) — **오매칭 가능성 명시**, 사람이 캐시 파일에서 `channel_id` 교체 가능(사용자 소유, watchlist와 같은 규율).

## 2. facts-only 레코드 (fetch 산출 = 저장 대상)

| 필드 | 의미 | 원본 → 매핑 |
|---|---|---|
| `artist` | 워치리스트 캐노니컬 key | (캐시 조인) |
| `video_id` | 공개 영상 ID | `id` — 공개 콘텐츠 식별자, PII 아님 |
| `title` | 영상 제목 | `snippet.title` — 사실 메타(드라이버 표시용) |
| `published_at` | 공개 시각(UTC ISO) | `snippet.publishedAt` |
| `views` / `likes` / `comments` | 공개 집계 지표 | `statistics.*` (int, 없으면 0) |
| `duration_s` | 길이(초) | `contentDetails.duration`(ISO8601) 파싱 |
| `type` | `short`(≤61s) / `video` | duration 파생 |
| `subscribers` | 채널 구독자(수집 시점) | `channels.statistics.subscriberCount` — act별 동일값 비정규화 |

## 3. 기준 원장 (지표 정의 · 하중여부 · 도메인근거 · 테스트 · 한계)

> **소유 분리**(§2.1): *정의·근거·테스트·한계* = 엔지니어. *임계값(튜닝)* = 도메인 소유자가 CLI로 조정.

| 지표/기준 | 정의 | 하중? | 임계값(튜닝) | 도메인 근거 | 테스트 | 한계/불확실성 |
|---|---|---|---|---|---|---|
| **평균 일 조회(velocity 프록시)** | `views ÷ max(1, 공개 후 경과일)` (영상별) | **하중** | — (파생) | 초기 조회 속도 = 화력의 속도 성분 — 단일 스냅샷에서 산출 가능한 근사 | TESTS B | **수명 평균이라 초동 과소평가**(오래된 영상일수록 하향) — 다일 축적 시 실측 증분으로 대체(v2) |
| **신작 감지** | `published_at ≥ 수집일 − RECENT_DAYS` | **하중** | `--recent-days` (기본 14) | 신작 업로드 = 캠페인 활성·컴백 신호(맥락 증거) | TESTS C | 공식 채널 업로드만(레이블 채널 MV 미포착 — v2) |
| **최근작 창** | 채널당 최근 업로드 `--per-channel`개 (기본 5) | 관습 | `--per-channel` | 최근 활동 표본 — 전체 카탈로그가 아니라 현재 화력 | TESTS B | 업로드 빈도 높은 채널은 창이 짧아짐 |
| **대표 velocity**(signals) | act별 최근작 중 **최대** 평균 일 조회 | 관습 | — | act의 '지금 가장 빠른 콘텐츠' = 시리즈 대표값 | TESTS D | 단일 대표값이라 분포 은닉 — 상세는 report/프로필 |
| **채널 화력 베이스** | 구독자 수(수집 시점) | 관습 | — | 도달 가능 규모의 공개 베이스라인 | TESTS B | 구독자≠활성 팬덤(§5) |

- **`charts[].data` 규약**: bar=`[{name,value}]` · line=`{x,series}` (공유 렌더 계약).
- **signal-series**(`signals`): `signal:"yt-velocity"` · `unit:"avg views/day"` · `higherIsStronger:true` · 날짜=스냅샷 수집일 · 선택 필드 `subscribers`(act→구독자)·`videos`(act→대표작 {title,views,avg_daily,published_at}) — 브리지 프로필 소비(SPEC의 signal-bridge 계약 준수).

## 4. 출력 규칙 (report.json)

- `moduleId = "yt-pulse"`. 공유 report-schema 준수. `generatedAt` 외 비결정 금지(정렬 고정).
- 채널 미해석/영상 0이어도 크래시 금지 — 유효 report + insight 명시.
- `insights` **반드시 병기**: (a) 공식 채널 한정(레이블 채널 MV 미포착), (b) velocity는 수명 평균 근사(다일 축적이 본선), (c) 조회수≠인기·실력 단정 아님(§0·§5).

## 5. 금지 (윤리 · 과대주장 — §0·§5)

- 조회수·velocity를 "히트 예측·인기 총점"으로 **단정 금지** — "이 축의 신호" 프레임만.
- 댓글 원문·시청자 개인 데이터 수집 금지(이 모듈 범위 아님 — 집계 지표만).
- 공식 API 쿼터 규율 위반 금지(search 남용 금지 — resolve 명시적 1회).
