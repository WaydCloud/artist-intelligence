# fandom-pulse · TESTS (수용조건 · 완료조건)

> 이 조건들이 통과해야 "완료"다. **로컬 검증이 게이트**(git/CI 미가동).

## 픽스처

- `tests/fixtures/ig_hashtag_kpopdance.json` — `#kpopdance` **facts-only 스냅샷**(원문·PII 제거, `fetch`가 생성해 커밋). 게시물당 `likes·comments·plays·type·timestamp·hashtags·music`만. **공개 태그·집계 지표만**(§4).
- `tests/fixtures/empty.json` — 0건 스냅샷(graceful 테스트용).

## 스모크 (핵심 흐름)

```bash
# 로컬(uv 미사용 시) PYTHONPATH 지정:
PYTHONPATH=modules/fandom-pulse/src python -m fandom_pulse analyze \
  modules/fandom-pulse/tests/fixtures/ig_hashtag_kpopdance.json \
  -o modules/fandom-pulse/output/
# 라이브 수집(종량·캡·facts-only): python -m fandom_pulse fetch --hashtag kpopdance \
#   --max-items 30 --max-usd 0.10 -o modules/fandom-pulse/tests/fixtures/ig_hashtag_kpopdance.json
# → output/report.json 생성 + report-schema 통과.
```

## 수용조건

- [ ] **A. 핵심 흐름**: 유효 스냅샷 → `output/report.json` 생성 + 스키마 유효.
- [ ] **B. 값 무결성**: `게시물 수` == 레코드 수, 모든 참여 `value ≥ 0`, 중앙값 number.
- [ ] **C. 필수 지표/차트**: `metrics`에 게시물 수·참여·중앙값, `charts`에 "공동 해시태그" bar.
- [ ] **D. graceful(0건)**: 빈 스냅샷 → 크래시 없이 유효 report + `insights` "게시물 없음".
- [ ] **E. 결정성**: 같은 입력 2회 → `generatedAt` 제외 동일.
- [ ] **F. 윤리**: "바이럴/히트 예측·인기·실력" 문구 없음. **표본·참여≠인기** 한계 병기.
- [ ] **G. 게이트**: `ruff check` · `pyright` 통과.
- [ ] **H. 기준 원장(튜닝)**: 하중 기준 임계값이 CLI 플래그로 노출(`--high-pct`·`--momentum-min-days`), 값 변경 시 지표 변화. RULES §3 원장과 일치.
- [ ] **I. facts-only**: fetch 산출/픽스처에 PII·원문 필드 부재(캡션·유저명·url 등).
- [ ] **J. (v2 선행신호) 사운드→아티스트 조인**: `--entities`(공유 entity-master) 제공 시 사운드 라벨→아티스트 귀속 → **진입 요약 도형**(`spread-artists`, v3.2부터 `charts`가 아니라 `summary`) + `곡 라벨로 잡힌 팀`·`아티스트 사전에 없는 팀` 지표 + "차트 로스터 밖 소셜 활성" 선행신호 insight. 'Original audio'(UGC) 제외. 미제공 시 확산 bar만(로스터 대조 생략, 하위호환). chart-history 코드 import 없음(데이터만 공유). **평결 아님**(§0). 결정적.

## 검증 로그 (2026-07-18, v1)

- **A/B/C** ✅ smoke(실 픽스처 `#kpopdance` reels 30건) → schema valid. 게시물 30 · 총 참여 54,968 · 중앙값 좋아요 969/댓글 23 · 고참여 3(≥4443) · 릴스 100% · 게시 가속 +2.4/일. 차트 3종: 공동 해시태그 bar(#dance·#fyp·#ateez·#kpop) · 일별 게시량 line(6/29~7/17, 11일) · Top 사운드 bar(ATEEZ-BAD 등).
  - ⚠ 이 줄의 게시 가속(+2.4)과 라인 길이(11일)는 **v3.2에서 바뀌었다**(달력 날짜 19일 · +2.8). 아래 2026-07-30 로그를 정본으로 본다.
- **D** ✅ `empty.json`(0건) → 지표 1(게시물 수 0)·차트 0·schema valid·exit 0, insight "게시물 없음" 명시.
- **E** ✅ 같은 입력 2회 → `generatedAt` 제외 산출 동일(`deterministic: True`).
- **F** ✅ 금지 단정어(예측/히트/실력/인기총점) 부재 + "표본 편향·공식 지표 아님·인기·품질 단정 아님" 병기.
- **G** ✅ ruff `All checks passed` · pyright 6 files `0 errors`.
- **H** ✅ 기준 원장 튜닝: `--high-pct` 90→50 → 고참여 게시물 변화(합성 1→3). 임계값 CLI 노출(코드 은닉 없음), RULES §3 원장과 일치.
- **I** ✅ facts-only: 레코드 키 = `{likes, comments, plays, type, timestamp, hashtags, music}` 뿐. PII/원문 필드(캡션·유저명·url 등) **0건**. posts·reels 양쪽 확인.
- 비고: reels는 `plays·music` 존재 → 사운드/모멘텀 경로 실데이터 실증. posts 스냅샷은 music 결측·단일일자라 차트 1종으로 정직하게 축소(정상).

- [ ] **L. (v3.2) 시각화 계약 + 구획**: `scripts/validate_report_data.py`가 이 모듈을 **채택 모듈**로 검사(R1~R8 하드 게이트) 통과 · 구획 3개에 차트 1개씩(상한 3) · 지표가 전부 구획에 배정됨 · 요약 도형은 `charts`에 중복되지 않음 · 0건 스냅샷도 계약 유지(구획 미선언).
- [ ] **M. (v3.2) 계정명 비게재**: 산출 `report.json` 어디에도 UGC 사운드 라벨(`… - Original audio`)이 없다. 제외 건수는 `top-sounds`의 신뢰도 라인에 표기(RULES §3·§5).
- [ ] **N. (v3.2) 일별 라인의 빈 날**: `daily-posts`의 `x`가 창의 달력 날짜 전부이고, 게시물이 없는 날의 값이 `0`이다(관측된 날만 세우지 않는다).
- [ ] **K. (v3 이중 귀속·D-013) 워치리스트**: `signals --watchlist` 제공 시 ① 워치리스트 acts가 추적 유니버스 합류(roster=true) ② 게시물 해시태그가 등록 태그와 일치하면 **해시태그 직접 귀속**(사운드와 합집합, 게시물당 1회) ③ `engagement`(참여 합)·`drivers`(top 사운드/태그) 필드 방출 ④ `overrides`가 엔티티 필드 정정. 미제공 시 v2 동작(사운드만, 하위호환). 결정적.

## 검증 로그 (2026-07-30, v3.2 시각화 계약 + 구획 · D-041·D-042·D-043)

- **L** ✅ `ADOPTED_MODULES`에 `fandom-pulse` 추가 → 검사기 CLEAN(전수 6리포트). 구획 3(게시 흐름 1 · 사운드 1 · 게시물 1) · 지표 9개 전부 배정 · 요약(`spread-artists`)은 `charts`에 없음 · 질문 4개 앵커 정상. 0건 스냅샷: 차트 0 · 구획 미선언 · 요약(빈 막대) + 질문 3개 유지 → CLEAN.
- **M** ✅ 산출 `report.json`에 `… - Original audio` 라벨 **0건**(남은 것은 설명 문구뿐). 이전 산출에는 계정명 4개(`megatdream`·`qianyihere`·`oakids_maggie`·`glxefanaccount`)가 막대로 그려지고 있었다 — 정적 게이트 4종·탭 스모크를 **전부 통과한 상태**였고 **육안 검사에서만** 잡혔다. `top-sounds` 신뢰도 라인이 제외 14건을 표기.
- **N** ✅ `daily-posts` x축 = 2026-06-29~07-17 **19일**(관측 11일), 값 `[1,0,0,0,0,0,0,0,0,1,3,…]`. 이전에는 관측된 11일만 세워 6/29→7/9의 **열흘이 한 칸으로 접혀** 선이 그 위를 곧게 지나가고 있었다. 창 정의가 바뀌며 게시 가속 +2.4 → **+2.8/일**(RULES §3 분모 = 달력 날짜).
- **육안**(라이트/다크 × 구획 3) ✅ 부제에서 액터 id·초 단위 타임스탬프 제거(정확한 출처는 신뢰도 `engine`이 유지) · `게시 가속` 힌트 잘림 해소(창 표기를 정의로 이동) · `게시물 수`를 게시 흐름 구획으로 옮겨 타일 1개짜리 행 해소.
- **게이트** ✅ ruff · pyright 0 · schema valid · `validate_report_data.py`(+`--selftest` 79/79) · `smoke:tabs` 6탭 × 2테마 PASS(구획마다) · 결정성 True.

## 검증 로그 (2026-07-19, v3 이중 귀속·워치리스트 · D-013)

- **K** ✅ `--watchlist`(9 acts) → izna 게시물이 **#izna 태그로 귀속**(drivers: `izna - DRIP`, `#izna`) · engagement 방출(izna 527) · roster=true 합류 · overrides(Jin→KR·BTS agency→Big Hit) 적용 확인. 하위호환: watchlist 미제공 시 v2 산출 동일. 결정적(3단 x2 동일). ruff·pyright 0.

## 검증 로그 (2026-07-19, v2 사운드→아티스트 선행신호 · D-010)

- **J** ✅ `--entities`(공유 entity-master 50팀) → `Top 아티스트 · 사운드 확산` bar(ATEEZ 4·LE SSERAFIM 2·ILLIT·KATSEYE·izna·i-dle…) + 사운드 확산 **14팀** · **로스터 밖 10팀**(KATSEYE·izna(2024 신인)·i-dle·ENHYPEN·ITZY…). 선행신호 insight: "차트(top-200)로 안 잡히는 소셜 활성(신인·pre-mainstream 포함)". 결정적(True). schema valid.
- 하위호환 ✅ `--entities` 없이 → 확산 bar만, 로스터 대조 생략(엔티티 없음). PII 게이트 CLEAN 무회귀. ruff·pyright 통과.
- 모듈 독립 ✅ `fandom_pulse/entities.py` 로컬 최소 매처(chart-history import 없음), 공유는 **데이터**(entities.json)뿐(D-007).
- 한계 정직: 로스터=추적 top-50이라 '로스터 밖'에 established(IVE·ITZY) 혼입 — '미차트' 단정 아님, 조사 대상 신호. UGC·협업·표기차로 귀속 누락.

## 검증 로그 (2026-07-19, tag_aliases 귀속 전용 태그 · D-013 확장)

- **귀속 인덱스 확장** ✅ watchlist `tag_aliases`(은어·밈·팬덤명, 수집 타겟 아님·과금 없음)가 `load_hashtag_index`에 합류(충돌 시 `hashtags` 우선) — 인덱스 12→**51태그**(11 acts). 프로브: #키키→KiiiKiii · #키오라→KISS OF LIFE · #영크크→CORTIS · #베몬/#monstiez→BABYMONSTER · #안원잘부→RESCENE · #s2u→Hearts2Hearts 전부 정확. 유료 수집 태그(daily_collect가 읽는 `hashtags`)는 12개 불변.
- **모호 태그 배제 기준**(RULES §3 원장): 일반어 충돌 라틴/한글 배제 실사례 — izna 팬덤명 '나야'(일반어)·KISSY(kissy face)·MEOVV '폼폼'(폼폼푸린)·H2H(head-to-head)·CORTIS '코어'(~코어 밈, coer만 등록). 배제 사유는 watchlist note에 기록.
- **게이트** ✅ ruff·pyright 0 · analyze 스모크 schema valid · 정본 3종(social/chart series·bridge) 재생성 — 커버리지 4/11·프로필 11건(신규 KISS OF LIFE·KEYVEATZ 포함).

## 실패 시 → [`../../WORKFLOW.md`](../../WORKFLOW.md) 리커버리

우회 금지. 원인 격리 → 최소 수정 → 재현 픽스처 추가.
