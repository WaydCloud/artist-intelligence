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
- [ ] **J. (v2 선행신호) 사운드→아티스트 조인**: `--entities`(공유 entity-master) 제공 시 사운드 라벨→아티스트 귀속 `Top 아티스트 · 사운드 확산` bar + `사운드 확산 아티스트`·`로스터 밖 확산` 지표 + "차트 로스터 밖 소셜 활성" 선행신호 insight. 'Original audio'(UGC) 제외. 미제공 시 확산 bar만(로스터 대조 생략, 하위호환). chart-history 코드 import 없음(데이터만 공유). **평결 아님**(§0). 결정적.

## 검증 로그 (2026-07-18, v1)

- **A/B/C** ✅ smoke(실 픽스처 `#kpopdance` reels 30건) → schema valid. 게시물 30 · 총 참여 54,968 · 중앙값 좋아요 969/댓글 23 · 고참여 3(≥4443) · 릴스 100% · 게시 가속 +2.4/일. 차트 3종: 공동 해시태그 bar(#dance·#fyp·#ateez·#kpop) · 일별 게시량 line(6/29~7/17, 11일) · Top 사운드 bar(ATEEZ-BAD 등).
- **D** ✅ `empty.json`(0건) → 지표 1(게시물 수 0)·차트 0·schema valid·exit 0, insight "게시물 없음" 명시.
- **E** ✅ 같은 입력 2회 → `generatedAt` 제외 산출 동일(`deterministic: True`).
- **F** ✅ 금지 단정어(예측/히트/실력/인기총점) 부재 + "표본 편향·공식 지표 아님·인기·품질 단정 아님" 병기.
- **G** ✅ ruff `All checks passed` · pyright 6 files `0 errors`.
- **H** ✅ 기준 원장 튜닝: `--high-pct` 90→50 → 고참여 게시물 변화(합성 1→3). 임계값 CLI 노출(코드 은닉 없음), RULES §3 원장과 일치.
- **I** ✅ facts-only: 레코드 키 = `{likes, comments, plays, type, timestamp, hashtags, music}` 뿐. PII/원문 필드(캡션·유저명·url 등) **0건**. posts·reels 양쪽 확인.
- 비고: reels는 `plays·music` 존재 → 사운드/모멘텀 경로 실데이터 실증. posts 스냅샷은 music 결측·단일일자라 차트 1종으로 정직하게 축소(정상).

- [ ] **K. (v3 이중 귀속·D-013) 워치리스트**: `signals --watchlist` 제공 시 ① 워치리스트 acts가 추적 유니버스 합류(roster=true) ② 게시물 해시태그가 등록 태그와 일치하면 **해시태그 직접 귀속**(사운드와 합집합, 게시물당 1회) ③ `engagement`(참여 합)·`drivers`(top 사운드/태그) 필드 방출 ④ `overrides`가 엔티티 필드 정정. 미제공 시 v2 동작(사운드만, 하위호환). 결정적.

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
