# 실험 런북 — 전향(forward) 선행신호 실증

> **가설**: pre-mainstream(차트 밖) 소셜 활성이 **차트 진입을 선행**하는가?
> 회고(단일 스냅샷)는 이를 증명할 수 없다(D-012) — **소셜-온리 코호트 t → 차트 진입 t+n**을 실 데이터로 관측해야 한다. 이 실험이 그 관측을 자동 축적한다.

## 무엇을 검증하나

D-012 회고 실증은 established·차트인 아티스트에 대해 "소셜이 차트를 선행한다"를 **반증**했다(#kpopdance=이미 뜬 곡의 댄스 커버=후행). 남은 열린 질문은 **차트 밖 social-only 코호트**(현재 izna·i-dle·ENHYPEN·ITZY·KATSEYE·iKON·YooA)가 **나중에 차트에 진입하는가**다. 진입하면 그들의 (이미 지난) 소셜 온셋 대비 **양수 lead = 진짜 선행 신호**. 이것은 시간이 지나야만 관측된다.

## 자동 수집 (스케줄) — v2 광역 (D-013)

- **작업**: Windows Task Scheduler `AI-daily-collect` — 매일 **09:00**(golde 로그온 시) `scripts/daily_collect.ps1` 실행. 설정은 [`../config/collect.json`](../config/collect.json), 팔로우 대상은 [`../packages/entity-master/watchlist.json`](../packages/entity-master/watchlist.json)(**사용자 편집** — acts·별칭·해시태그·overrides).
- **매일 하는 일**: ① 무료 차트 collect **3플랫폼 × ~50시장**(D-016 광역: Kworb Spotify 50 + Apple 공식 RSS 49 + Kworb YouTube 49 — config `chart_markets`·`apple_markets`·`youtube_markets`, 홈 핀 `home_market: kr`) → `data/live/chart/<platform>/<cc>/` + **chart-history 라이브 리포트**(`analyze --latest` — 수평 병렬: 렌즈별 1위·Top10×렌즈·네이티브 수치·Spotify 렌즈 밖, 탭 매일 갱신). ② 유료 소셜 fetch **10태그**(장르 + 워치리스트 act 태그 자동 파생, 태그당 100건·$0.25 캡, **일 예산 $3 누적 강제**) → `data/live/social/<date>_<tag>.json` + **PII 게이트 즉시 실행**(REJECT→`quarantine/`). ②′ **무료 YT fetch**(공식 API ~12 units, D-014): 워치리스트 채널 최근작 조회·velocity → `data/live/yt/<date>.json` + 게이트 + yt-pulse report(4번째 탭). ③ forward signal-series 재생성 — 소셜 merge+dedup+**이중 귀속**(사운드+워치리스트 태그), 차트는 날짜 ≥2면 실 forward·1일이면 Days 역산 폴백(둘 다 다시장·markets 맵), YT velocity 시리즈. ④ signal-bridge(θ_rank=200, --focus-social, **--watchlist**, **--youtube**) → 커버리지(소셜/차트/YT)·팀별 프로필(YT 구독·velocity 병기)·**⚡ 신규 진입 알림** 포함 report.json. ⑤ 대시보드 갱신. ⑥ 요약 로그.
- **로그**: `data/live/logs/daily.log`. `SUMMARY joined=.. social-led=.. social-only=.. watch-cov=..`로 진행 추적.
- **산출물**: `data/live/`는 gitignore(재현 소스는 `tests/fixtures/`). 대시보드는 매 실행 후 **라이브 forward 결과**를 렌더.
- **워치리스트 편집**: `watchlist.json`에 act 추가/삭제(`key`·`aliases`·`hashtags`) → 다음 실행부터 수집 타겟·귀속·프로필에 자동 반영. 오귀속 발견 시 `overrides`에 정정.

## 스마트 태그 할당 (D-015) — 예산 배분 알고리즘

> 경계(§0): **워치리스트(누굴 팔로우)는 사용자 소유** — 알고리즘은 리스트를 편집하지 않고, 고정 일 예산 내에서 **오늘 어느 태그를 걷을지**(예산 배분)만 결정한다. 태그 수 ≤ 일 슬롯이면 사실상 전량 수집(현 10태그가 그 상태).

- **동작**: `scripts/tag_allocator.py plan`이 매 수집 직전 실행(daily_collect §2). 일 슬롯 = `daily_budget_usd ÷ per_tag_max_usd`(현 12). 선정 순서: ① **상시** — `genre_hashtags` + 워치리스트 `pin: true` acts의 태그(매일 무조건) → ② **강제** — 마지막 수집 후 `max_staleness_days`(K) 이상 경과(오래된 순, **기아 방지 보장**) → ③ **점수** — 남은 슬롯을 우선순위 점수순으로. 무료 신호만 소비(어제의 `chart_series`·`yt_series`·`social/` 파일명·직전 게시수) — 결정적, 네트워크 0. 실패 시 **전량-순서 폴백**(예산 가드가 뒤를 자름).
- **플랜 기록**: `data/live/plans/plan_<date>.json` — 선정 태그·사유(pin/stale/score)·점수 상세·스킵 목록. 로그에 `allocator: plan N/M tags | ...` 한 줄.
- **워치리스트 확장 문법**: `pin: true` = 매일 상시 수집 · `hashtags: []` = 유료 태그 없이 무료 레일(차트+YT)만으로 팔로우(비용 $0).

### 기준 원장 — 할당 점수 (값 = 사용자 소유, [`../config/collect.json`](../config/collect.json) `allocator` 노출)

| 성분 | 정의 | 하중? | 기본값 | 도메인 근거 | 한계/불확실성 |
|---|---|---|---|---|---|
| **K (max_staleness_days)** | K일 경과 태그는 점수 무관 강제 수집 | **하중** | 5 | 어떤 팀도 관측에서 굶지 않아야 커버리지 주장 가능(수집 유효성) | K가 곧 최악 온셋 오차(아래) |
| w_chart_entry | 차트 온셋이 최근 `chart_entry_window_days`(2) 내인 act의 태그 부스트 | **하중** | 3.0 | ⚡ 진입 직후가 소셜 반응이 가장 궁금한 순간('빠르게'의 핵심) | 차트 시계열은 어제 빌드(1일 지연) |
| w_yt_velocity | act YT velocity ÷ 워치리스트 최대 (0~1) | 튜닝 | 1.0 | 신작·캠페인 활성 = 소셜 파생 가능성 | velocity는 수명 평균 프록시(D-014 한계) |
| w_yield | 직전 수집 게시수 ÷ 캡 (0~1) | 튜닝 | 1.0 | 신호가 나오던 태그를 더 자주 | 과거 수율≠미래(모멘텀 가정) |
| w_new / w_stale | 미수집 태그 탐험 보너스 / 경과 비례(0~1) | 관습 | 2.0 / 1.0 | 신규 추가 팀 초기 관측 · 순환 압력 | — |

- **한계 정직(§0)**: 순환 수집에서 **안 걷은 날 ≠ 게시물 0인 날**. 수집일 증거 = `social/` 파일명 + `plans/` 기록. 비-pin 태그의 **소셜 온셋 해상도는 ±수집 간격**(K=5 보장, 시뮬레이션 실측 최대 4일)만큼 거칠어진다 — 정밀 온셋이 필요한 팀은 `pin`으로. 시리즈-레벨 결측 마스크 전파는 v2 과제.

## 결과 읽는 법 (무엇을 볼까)

- **핵심 지표**: `소셜 선행`(social-led) 카운트. **0 → 1+로 바뀌면** = social-only 코호트 중 하나가 차트에 진입했고 그 소셜 버즈가 앞섰다 = **선행 신호 후보 발견**(검증 대상, 예측 아님·§0).
- **`소셜-온리 관측대상`** 목록: 매일 갱신되는 pre-mainstream 후보. 특정 팀이 목록에서 사라지고 `선행/지연` bar에 양수로 나타나면 = 진입.
- **선행/지연 bar**: 회고에선 전부 음수(established 후행)였다. 전향에서 **양수 팀이 생기는지**가 관전 포인트.
- **한계(§0)**: 표본 극소·단일 시장(KR)·단일 해시태그·머신 오프 시 결측(차트 Days로 부분 복구). lead=시간 순서이지 인과 아님. **관측대상 신호이지 "뜰 팀" 평결 아님.**

## 비용 · 안전장치 (v2, 사용자 승인 $100/월 내)

- **비용**: 태그당 캡 $0.25, **일 예산 $3.00**(= 12슬롯) — 태그가 12개를 넘으면 **할당기(D-015, 위)가 예산 내 순환** 배분(초과 과금 없음), 스크립트의 누적 예산 가드가 백스톱. Apify가 run별 `maxTotalChargeUsd`로 하드 캡. `experiment_end = 2026-08-19`(config)까지 → 총 **≤ ~$93/월**(캡 기준 — 실 청구는 게시량 적은 태그일수록 낮음, Apify 콘솔에서 확인). 이후 유료 fetch 자동 중단(무료 차트만 계속).
- **일시정지**(무과금): `data/live/PAUSE` 파일 생성 → 유료 fetch 건너뜀(무료 차트는 계속). 재개: 파일 삭제.
- **완전 중단**: `schtasks /Delete /TN "AI-daily-collect" /F` (또는 작업 스케줄러에서 비활성화).
- **조정**: [`../config/collect.json`](../config/collect.json)의 `chart_markets`·`genre_hashtags`·`per_tag_max_items`·`per_tag_max_usd`·`daily_budget_usd`·`experiment_end` — 코드 수정 불필요.

## 수동 실행 / 테스트

```powershell
# 1회 실행(유료 fetch 포함):
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_collect.ps1
# 무과금 리허설(fetch 건너뜀, 파이프라인만):
$env:AI_DRYRUN="1"; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_collect.ps1; Remove-Item Env:\AI_DRYRUN
# 지금까지 축적 상태 요약:
python scripts\bridge_summary.py modules\signal-bridge\output\report.json
```

## 결과 확정 시 (실험 종료 후)

- social-led가 나타나면: 해당 팀·lead·소셜/차트 온셋을 `docs/DECISIONS.md`(D-013 등)에 기록, 대시보드 스냅샷 커밋. **여전히 관측대상 신호로 프레이밍**(§0).
- 나타나지 않으면(2주 내): 그것도 정직한 결과 — "이 표본·창에선 #kpopdance social-only가 KR 차트를 선행하지 않았다"(넓히기: 다중 시장·해시태그·더 긴 창·pre-mainstream 전용 소스).
