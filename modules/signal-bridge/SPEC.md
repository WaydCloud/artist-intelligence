# signal-bridge · SPEC (무엇을 만드나)

> 모듈 하네스의 "무엇을/UX/완료조건". 상세 규칙·**기준 원장**은 [`RULES.md`](RULES.md), 수용조건은 [`TESTS.md`](TESTS.md).
> 근거: [`../../docs/DECISIONS.md`](../../docs/DECISIONS.md) D-011(브리지)·D-010(소셜 선행)·D-007(공유 계약) · 바닥전제: [`../../DOMAIN.md`](../../DOMAIN.md) §0 · [`../../AGENTS.md`](../../AGENTS.md) §2.1·§5.

## 한 줄

두 모듈이 낸 **per-artist 신호 시계열**(fandom-pulse `social-buzz` × chart-history `chart-rank`)을 **공유 entity-master 캐노니컬로 조인**해, **소셜 버즈가 차트 진입을 선행하는가(temporal lead/lag)**를 `report.json`으로 낸다. **예측기가 아니라** 시간 순서 **신호 요약** — lead ≠ 인과(§0).

## 왜 (D-010 → D-011)

D-010에서 "무베이스 신인의 출발점 = 소셜"을 fandom-pulse 사운드→아티스트로 표면화했고, **진짜 선행(소셜 t → 차트 t+n)은 다일 collect가 본선**으로 남겨졌다. signal-bridge가 그 본선의 **배선·판정 로직**이다. 두 모듈은 서로의 **코드를 import하지 않고**, 공유 **데이터 계약**(signal-series)만 교환한다(D-007/D-010).

## 입력 / 출력

- **입력**: signal-series JSON 2개 — `--social`(fandom-pulse `signals`) · `--chart`(chart-history `signals`). 차트 시계열은 **두 모드**: (a) **전향** = 다일 store(시장 서브디렉터리 지원, D-013) → 실 per-day 시계열; (b) **회고(실증)** = 라이브 스냅샷(들)의 `Days` 필드로 진입일 역산(`--reconstruct-days N`, `provenance.reconstructed=true`, 다시장 병합). `--focus-social`은 버즈 있는 아티스트만(차트-온리 곡 제외) 선행 질문에 집중. `--watchlist`(D-013)는 **커버리지 지표 + 팀별 프로필**(누가·얼마나·왜·활용) + **신규 진입 알림**을 켠다. 스모크는 커밋 픽스처.
- **출력**: `output/report.json` (공유 report-schema 준수) → 대시보드가 **범용 렌더**로 자동 탭 생성(스키마·대시보드 변경 없음).

## signal-series 데이터 계약 (정본 — 두 이미터·브리지 공유)

각 소스 모듈의 `signals` 서브커맨드가 방출하고 브리지가 소비하는 **입력측 공유 계약**(report-schema의 시간축 짝, D-007 정신). **기계검증형은 [`packages/signal-series/signal-series.schema.json`](../../packages/signal-series/signal-series.schema.json)** — 검증은 `python scripts/validate_series.py <series.json>`, CI `data-contracts` 잡이 픽스처를 전수 검증한다. 이 서술과 스키마가 어긋나면 이 서술이 정본이고 스키마를 고친다:

```jsonc
{
  "moduleId": "fandom-pulse",          // 발신 모듈
  "signal": "social-buzz",             // "social-buzz" | "chart-rank" (브리지가 역할 검증)
  "unit": "posts/day",                 // 사람이 읽는 단위
  "higherIsStronger": true,            // 신호 방향 (social=true, chart-rank=false)
  "dates": ["2026-07-14", ...],        // 정렬된 ISO 일자 (이 모듈의 관측 창)
  "series": {                          // 캐노니컬 키 → dates에 정렬된 값
    "LE SSERAFIM": [0, 1, 2, ...],     //   social: 일간 게시수(0=무신호)
    "izna":        [1, 0, 0, ...]      //   chart : 일간 최고순위(null=차트 밖)
  },
  "roster": { "LE SSERAFIM": true, "izna": false },  // 캐노니컬 키가 추적 유니버스(entities+watchlist) 매치?
  "provenance": { "source", "generatedAt", "window", "synthetic"?, "reconstructed"?, "marketCount"?, "note" },
  // ---- 선택 필드 (D-013, 있으면 브리지가 '얼마나/왜/어디' 레이어에 사용) ----
  "engagement": { "izna": 527 },                     // social만: act별 likes+comments 합 (얼마나)
  "drivers":    { "izna": {"sounds": ["izna - DRIP"], "tags": ["#izna"]} },  // social만 (왜)
  "markets":    { "ILLIT": ["JP", "KR"] },           // chart만: act별 진입 시장 (어디)
  "platforms":  { "CORTIS": ["apple", "spotify"] },  // chart만(D-016): act별 진입 플랫폼 — 프로필 '어디' 병기. rank는 플랫폼 혼합 최고순위(진입 온셋용, 절대비교 금지)
  "platformOnsets": { "CORTIS": {"spotify": "2026-07-17"} }  // chart만(D-016 ②): 렌즈별 첫 관측일 — 브리지가 렌즈 시차 집계(provenance.platformFirstDates로 좌측 절단 보정 필수)
}
```

- **조인 키 = entity-master 최상위 캐노니컬 키.** fandom-pulse는 사운드→아티스트를 `entities.match`(→`["key"]`)로, chart-history는 차트 아티스트를 `alias_index`(→primary key)로 **동일 키**에 수렴. 미매치 팀은 **원 라벨 유지**(roster=false) — 소셜-온리/차트-온리로 조인에서 살아남아 pre-mainstream 관측대상이 된다.
- **`synthetic`**(선택): 소스 스냅샷 `tos_class == synthetic-fixture`면 chart-history 이미터가 `true`로 실어 보낸다 → 브리지가 **메커니즘 시연 경고**를 방출(정직성이 데이터를 따라 흐름, §0).

## 핵심 산출 (정의는 RULES §3 기준 원장)

1. **온셋**: 소셜 온셋 = 첫 `게시수 ≥ θ_social` 일자 · 차트 온셋 = 첫 `순위 ≤ θ_rank` 일자.
2. **선행 일수(lead)** = 차트 온셋 − 소셜 온셋 (양수 = 소셜이 먼저).
3. **분류**: `social-led`(lead>0) · `coincident`(0) · `chart-led`(lead<0) · `social-only`(차트 온셋 없음, 관측대상) · `chart-only`.
4. **차트**: (line) 예시 아티스트 소셜 버즈 vs 차트 강도(정규화) · (bar) 팀별 선행/지연 일수 · (bar) 소셜-온리 관측대상.

## UX (대시보드 뷰) — 시각화 계약 채택 (D-041·D-042·D-043)

> 형식 정본은 [`../../DESIGN.md`](../../DESIGN.md) §7.1~§7.4. 이 모듈은 계약을 **채택**했으므로 R1~R8이 `scripts/validate_report_data.py`에서 하드 게이트다.

- **진입부**: 답하는 질문 4개(R1) + 답하지 않는 질문(R7) + **요약 도형 하나**(R2) = `class-mix`(bar 3행: 소셜이 먼저 / 차트가 먼저 / 같은 날). 이 탭에서 가장 오해받기 쉬운 한 줄이 "소셜이 먼저다"라, **반례를 같은 눈금 위에** 놓는 것이 첫 화면의 일이다.
- **구획 4개**(D-043):

  | 구획 | 질문 | 차트 | 지표 |
  |---|---|---|---|
  | `leadlag` 선행·지연 | 소셜과 차트 중 어느 쪽이 먼저 움직였나? | `lead-days` · `lag-days` | 두 신호가 다 있는 팀 · 소셜 선행 · 판정 가능 선행 · 중앙값 선행 |
  | `example` 한 팀 보기 | 한 팀에서 두 신호는 실제로 어떻게 겹치나? | `lead-example` | — |
  | `pre` 차트 밖 | 차트에 아직 없는데 소셜에서 도는 팀은? | `social-only` | 추적 아티스트 · 차트 밖에서 도는 팀 · 소셜 신호가 없는 팀 · 워치리스트 커버리지 |
  | `tuner` 기준 | 기준을 움직이면 분류가 어떻게 달라지나? | `leadlag-tuner` | — |

- 구획 아래: **워치리스트 프로필 카드**(`--watchlist` 시 — `[프로필]` insight를 [RULES §4.1](RULES.md) 라인 규약으로 대시보드가 구조화 렌더, 파싱 실패 시 평문 폴백) → 인사이트(정직성 경고 최상단)/추천.
- 모듈 탭 간 **교차 링크**: 대시보드가 subtitle/insight의 모듈 id를 감지해 탭 링크를 만든다 — **부제에서 모듈 id를 빼면 이 링크가 사라진다.**

## 완료 정의 (Definition of Done)

- [ ] 두 signal-series → **스키마 유효 `report.json`** (smoke 통과)
- [ ] 조인 키 일치(양 모듈 캐노니컬 동일) — 로스터 팀은 캐노니컬, 미매치는 원 라벨로 조인
- [ ] 결정성: 같은 입력 → 같은 산출(`generatedAt` 제외)
- [ ] **기준 원장**: θ_social·θ_rank가 RULES §3 원장 + **CLI 노출**(`--theta-social`·`--theta-rank`, §2.1)
- [ ] **정직성(§0)**: 합성 입력이면 **메커니즘 시연 경고**를 최상단 insight로 · lead≠인과·표본 극소 병기 · 반례(chart-led) 노출
- [ ] `lint`(ruff)·`typecheck`(pyright) 통과, 기존 두 모듈 스모크 무회귀

## 빌드 단계

- **v1** (D-011): 두 signal-series 조인 → 온셋·선행/지연·분류 → report.json. 배선·판정 로직 완성(합성 픽스처로 메커니즘 검증).
- **v1.1 실증(회고)** (D-012): **실 데이터**로 검증 — 실 #kpopdance 소셜 × 실 Kworb KR 차트(Days 역산). **결과: "소셜이 차트를 선행한다" 순진한 가설 반증**(소셜 선행 0·차트 선행 7팀 — #kpopdance는 이미 뜬 곡의 댄스 커버=후행). 선행 후보는 social-only 코호트. **대시보드 정본 = 이 실 회고 결과.**
- (예정) **v2 실증(전향)** — **본선**: 라이브 다일 collect로 `소셜-온리 t → 차트 진입 t+n`을 관측(회고 단일 스냅샷으로 증명 불가한 선행 방향). 소셜↔차트 오버레이 뷰 · θ tunable 슬라이더 · 다중 시장·해시태그.
