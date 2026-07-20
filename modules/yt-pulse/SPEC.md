# yt-pulse · SPEC (무엇을 만드나)

> 모듈 하네스의 "무엇을/UX/완료조건". 상세 규칙·**기준 원장**은 [`RULES.md`](RULES.md), 수용조건은 [`TESTS.md`](TESTS.md).
> 근거: [`../../DATA_SOURCES.md`](../../DATA_SOURCES.md) §3(YouTube Data v3 — videos.list ~1 unit·search.list 100 회피·강한 캐싱, quota 10k/day) · D-002(YouTube=1순위 공식 레일) · D-013(워치리스트) · 바닥전제 [`../../DOMAIN.md`](../../DOMAIN.md) §0.

## 한 줄

**워치리스트 acts의 공식 YouTube 채널** 최근 업로드(MV·Shorts)의 **조회·참여·업로드 케이던스**를 facts-only 지표로 수집해 `report.json`(대시보드 4번째 탭)과 **yt-velocity signal-series**(브리지 '얼마나' 레이어)로 낸다. 히트 **예측기가 아니라** 공식 채널 **화력·속도 신호 요약**(§0).

## 왜 (D-013의 '얼마나' 3번째 소스)

소셜(IG 게시량·참여)·차트(순위·시장)에 이어 **YouTube 조회수 = K-pop에서 가장 큰 공개 '얼마나' 지표**(무료 공식 API, ToS 최저). 특히 **신곡 업로드 감지 + 초기 조회 속도(velocity)**는 캠페인 시작·화력의 조기 증거 — 소셜 버즈·차트 진입의 **맥락(왜 지금?)**을 제공한다.

## 입력 / 출력

- **`resolve`** (라이브, 1회성·명시적): watchlist.json → 채널 검색(search.list, 100 units/act) → **커밋 캐시** [`../../packages/entity-master/yt_channels.json`](../../packages/entity-master/yt_channels.json). 이후 fetch는 캐시만 사용(쿼터 절약, DATA_SOURCES "search 회피"). 오매칭은 캐시 파일에서 **수동 정정**(사용자 소유).
- **`fetch`** (라이브, 일일·저쿼터 ~12 units): 캐시 채널들 → 채널 통계(구독자) + 최근 업로드 N개 → 영상 통계(조회·좋아요·댓글·길이) → **facts-only 스냅샷**(snapshot-schema 계약: provenance+quality+records).
- **`analyze`** (오프라인·결정적, 스모크): 스냅샷(들) → **스키마 유효 `report.json`** → 대시보드 자동 탭.
- **`signals`** (오프라인): 스냅샷(들) → **`yt-velocity` signal-series** — act별 대표 최근작의 **평균 일 조회**(views/일, 단일 스냅샷에서도 산출 가능한 속도 프록시). 브리지가 `--youtube`로 소비(프로필·커버리지).

## 핵심 산출 (정의는 RULES §3 기준 원장)

1. **구독자·최근작 조회 합** — 채널 화력 베이스라인 (KPI)
2. **평균 일 조회(velocity 프록시)** = views ÷ 공개 후 경과일 — 단일 스냅샷에서의 속도
3. **신작 감지** — 최근 K일 내 업로드 = 캠페인 활성 신호
4. (bar) act별 최근작 조회 · (bar) act별 velocity · (line) 다일 축적 시 조회 증분

## UX (대시보드 뷰)

- KPI(추적 acts·해석 채널·총 최근작 조회·최고 velocity) → act별 조회 bar → velocity bar → 인사이트(신작·한계)/추천.

## 완료 정의 (Definition of Done)

- [ ] `resolve` → 커밋 캐시(채널 ID·제목 — 사람이 검증·정정 가능)
- [ ] `fetch` → snapshot-schema 유효 + **PII 게이트 CLEAN**(공개 집계 지표만)
- [ ] `analyze` → **스키마 유효 report.json**(커밋 픽스처로 오프라인 스모크) → 대시보드 자동 탭
- [ ] `signals` → yt-velocity signal-series(공유 계약) — 브리지 `--youtube` 소비
- [ ] 결정성: 같은 입력 → 같은 산출(`generatedAt` 제외)
- [ ] 기준 원장: velocity·신작 창 등 하중 기준 RULES §3 + CLI 노출
- [ ] `lint`·`typecheck` 통과, 기존 모듈 무회귀

## 빌드 단계

- **v1** (이번, D-014): 채널 resolve 캐시 + 일일 fetch + analyze/signals + 브리지 프로필 통합 + daily_collect 무료 스텝.
- (예정) **v2**: 다일 축적 → **실측 일별 조회 증분**(velocity 프록시 대체) · 레이블 채널 영상 레지스트리(HYBE LABELS 등에 올라가는 MV 포착) · 댓글 밀도(센티먼트 앵커, DATA_SOURCES).
