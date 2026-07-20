# fandom-pulse · RULES (불변식 · 기준 원장)

> 미시 판단(참여·모멘텀 기준)을 **정확히** 정의해 즉흥 산출을 막는다. §3이 이 모듈의 **기준 원장**([`../../AGENTS.md`](../../AGENTS.md) §2.1). 값 무결성은 [`TESTS.md`](TESTS.md)에서 검증.

## 1. 소스 · 수집 규칙 (§4 준수)

- 소스: **공개 IG 해시태그**(`apify/instagram-hashtag-scraper`, 로그아웃 공개 데이터). 매니지드 스크래퍼 = 리스크 이전 2차 레일, ToS 책임 사용자 귀속(DATA_SOURCES §4, D-002).
- **수집과 분석 분리**: `fetch`(라이브·Apify·종량) ↔ `analyze`(오프라인·결정적, 스모크 경로). 스모크는 네트워크를 타지 않는다.
- **facts-only만 저장**: 게시물당 `likes·comments·plays·type·timestamp·hashtags·music`만. **원문·PII 미저장** — `caption·ownerUsername·ownerId·url·mentions·taggedUsers·latestComments` 등은 fetch 단계에서 **즉시 폐기**(§4: 원문 최소저장·지표 중심·PII 제거).
- 비용: 종량제(PAY_PER_EVENT). fetch는 `--max-items`·`--max-usd` 캡 필수. 저빈도.
- **공유 엔티티 조인**(v2): `--entities`로 [`../../packages/entity-master/entities.json`](../../packages/entity-master/entities.json)(chart-history와 **동일 공유 데이터**, D-007)를 읽어 사운드→아티스트 귀속. 모듈 독립을 위해 chart-history 코드는 import하지 않고 **데이터만 공유**(`fandom_pulse/entities.py` 로컬 최소 매처).
- **워치리스트 병합**(v3·D-013): `--watchlist`로 [`../../packages/entity-master/watchlist.json`](../../packages/entity-master/watchlist.json)(**사용자 소유** 팔로우 목록)을 entities 위에 병합 — 팔로우 acts가 추적 유니버스에 합류(key·별칭), `overrides`가 enrich 오귀속을 마지막에 정정. 태그 목록은 해시태그 직접 귀속(§3)과 수집 타겟(config)의 단일 소스.

## 2. facts-only 레코드 (fetch 산출 = 저장 대상)

| 필드 | 의미 | 원본 → 매핑 |
|---|---|---|
| `likes` | 좋아요 수 | `likesCount` (int, 없으면 0) |
| `comments` | 댓글 수 | `commentsCount` (int, 없으면 0) |
| `plays` | 재생 수(릴스) | `videoPlayCount` (int\|null) |
| `type` | 형식 | `Video`→`reel`, 그 외→`post` |
| `timestamp` | 게시 시각(UTC ISO) | `timestamp` |
| `hashtags` | 공동 해시태그(소문자) | `hashtags` — **공개 태그, PII 아님** |
| `music` | 사운드 라벨 | `musicInfo`(artist+song) — **공개 트랙, PII 아님**; 없으면 null |

- 스냅샷 메타: `hashtag · resultsType · count · fetched_at · note(facts-only)`.

## 3. 기준 원장 (지표 정의 · 하중여부 · 도메인근거 · 한계)

> **소유 분리**(§2.1): *정의·도메인근거·테스트·한계* = 엔지니어. *임계값(튜닝 파라미터)* = **도메인 소유자**가 CLI 플래그로 조정 — 코드 은닉 금지.

| 지표 | 정의 | 하중? | 임계값(튜닝) | 도메인 근거 | 한계 |
|---|---|---|---|---|---|
| **참여(engagement)** | `likes + comments` (게시물당) | — | — | 좋아요·댓글 = 공개 반응 화력의 대리지표(DOMAIN §3 핵심행동) | 알고리즘·계정규모 편향; 인기·품질 아님(§5) |
| **화력(게시물 수)** | facts-only 레코드 수 | 관습 | — | 태그 사용량 = 참여 폭 | 스크랩 표본(첫 페이지 등) 한정 |
| **중앙값 참여** | `median(engagement)` (좋아요·댓글 각) | 관습 | — | 평균은 바이럴 1건에 왜곡 → 중앙값이 대표 | 표본 작으면 불안정 |
| **고참여 게시물** | `engagement ≥ 스냅샷 상위 P분위` | **하중** | `--high-pct` (기본 90) | **상대 분위** = 계정규모 절대편향 회피 | 임계값은 가설 — 도메인이 조정 |
| **릴스 비중** | `reel / (post+reel)` | 관습 | — | 형식 믹스 = 챌린지/댄스 신호(DD) | type 매핑 근사 |
| **게시 가속(모멘텀)** | `(최근 절반 게시/일) − (이전 절반)` | **하중** | `--momentum-min-days` (기본 2) | 케이던스 가속 = 조기 확산 신호 | 단일 fetch는 window 짧음 — 다일 collect가 본선 |
| **Top 공동 해시태그** | 질의 태그 제외 co-occurrence 상위 N | 관습 | `--top-tags` (기본 10) | 공동 태그 = 확산·맥락 도달 | 봇·스팸 태그 혼입 가능 |
| **Top 사운드** | `music` 라벨 상위 N | 관습 | `--top-sounds` (기본 8) | 트렌딩 사운드 = 챌린지 선행(DD) | music 메타 결측 많음 |
| **사운드→아티스트 확산** (v2·선행신호) | 사운드 라벨 'Artist - Song'의 공식 아티스트별 게시물 수 | 관습 | `--entities` (공유 맵) | 소셜 사운드 확산 = 차트 **선행** 신호(무베이스 신인의 실제 출발점) | 'Original audio'(UGC)·협업·표기차로 귀속 누락 |
| **로스터 밖 확산** (선행 후보) | 사운드 확산 아티스트 中 **entity-master(차트 로스터)에 없는** 팀 | — | (같은 `--entities`) | 차트(top-200)로 안 잡히는 소셜 활성 = pre-mainstream 조사 대상 | 로스터=추적한 top-50이라 '미차트' 아님(established 혼입 가능) — **평결 아님**(§0) |
| **해시태그 직접 귀속** (v3·D-013, `signals` 전용) | 게시물 해시태그가 **워치리스트 act의 등록 태그**(`watchlist.json` artists[].`hashtags` **+ `tag_aliases`**)와 일치 → 그 act에 귀속. 사운드 귀속과 **합집합**(게시물당 act 1회) | 관습 | `--watchlist` (태그=사용자 소유) | UGC('Original audio') 사운드라 사운드 귀속이 못 잡는 pre-mainstream 게시물을 **자기 태그로** 포착 — 두 번째 증거 경로. `tag_aliases` = **귀속 전용**(은어·밈·팬덤명 태그 — 수집 타겟 아님·과금 없음): 팬은 공식명이 아니라 은어로 태그한다(예: #키키·#키오라·#영크크) | 팬덤 태그 스팸/무관 게시물 혼입 가능(태그≠공식) · 태그 미등록 act는 사운드 경로만 · **모호 태그 배제 기준**: 일반어와 겹치는 라틴 은어(예: kiki)는 오귀속 위험으로 등록하지 않고 한글형만 등록 |
| **참여량·드라이버** (v3, `signals` 전용) | act별 귀속 게시물의 `likes+comments` 합(engagement) + 상위 사운드·태그(drivers) | 관습 | — | '얼마나(magnitude)·왜(어떤 사운드/태그가 끄는가)' 증거 레이어(D-013) | 스크랩 표본 한정 · 참여≠인기 단정(§5) |

- **차원 자동감지**: 스냅샷 timestamp가 **`--momentum-min-days`일 이상 걸치면** 게시 가속·일별 라인 산출, 아니면 **pulse(단일 창)**로 insight에 명시.
- **`charts[].data` 규약**(대시보드 렌더 계약): bar = `[{name, value}]` · line = `{x:[label], series:[{name, values:[num|null]}]}` (chart-history RULES §4.1과 동일).

## 4. 출력 규칙 (report.json)

- `moduleId = "fandom-pulse"`. 필수 상위 필드는 공유 스키마 준수([`../../packages/report-schema/report.schema.json`](../../packages/report-schema/report.schema.json)).
- `generatedAt` = 실행 시각(UTC ISO). 지표·차트는 facts-only 입력에서 **결정적** 도출(시각 외 비결정 금지).
- **게시물 0**: 크래시 금지. 유효 report + `insights`에 "게시물 없음" 명시.
- `insights`에 **반드시 병기**: (a) 공개 IG 표본 한계(첫 페이지/스크랩 편향), (b) 참여 = 신호일 뿐 **인기·품질 단정 아님**, (c) 단일 fetch면 모멘텀은 짧은 창.

## 5. 금지 (윤리 · 과대주장 — [`../../AGENTS.md`](../../AGENTS.md) §5, 바닥전제 §0)

- 참여·화력을 "바이럴/히트 예측"·"인기 총점"·"실력"으로 **단정 금지**. → "이 축에서 이런 신호"로만. (평결 = 결정 레이어 침범 — §0.)
- IG 스크랩 지표를 **공식 지표로 등치 금지**(표본값 명시).
- 다루는 것은 **공개 집계 지표**. 팬 개인(닉네임·계정·댓글 원문 등)은 이 모듈 범위 아님 — fetch가 폐기.
- 미성년·초상·개인정보 주의. **특정 개인 타깃 분석 금지**(집계만).
