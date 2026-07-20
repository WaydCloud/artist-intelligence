# entity-master — 공유 캐노니컬 엔티티 레이어

> 모듈 공통 **캐노니컬 차원(dimension)**: 아티스트/그룹 → 표준 엔티티(원산지·MBID·별칭).
> 정본 스키마 [`entity.schema.json`](entity.schema.json), 데이터 [`entities.json`](entities.json) (CC0 사실만).

## 왜 공유 레이어인가

지금까지 엔티티 맵은 chart-history 로컬이었다. 여러 모듈이 **같은 아티스트 축**으로 조인해야 "관리 체계"가 성립한다 — 하나의 캐노니컬 차원, 여러 모듈. (관리 체계 backbone, [`../../DATA_SOURCES.md`](../../DATA_SOURCES.md) §5.)

## 데이터 (CC0 사실만)

- 출처: **MusicBrainz 1차** + **Wikidata 폴백**(다국어·로마자). `source` 병기.
- 각 엔티티: `source · id(MBID/QID) · name · country(ISO2) · type · score · aliases[]`.
- **추측 금지**: 국가 미상은 `{"resolved": false}` — 원산지 집계에서 제외(0으로 왜곡 금지).
- `country`/`type`은 커뮤니티 편집 기반 → **불완전 가능(참고)**. 국적 기반 가치판단 금지(AGENTS §5).

## 생성 · 검증

- 생성(라이브): `chart-history enrich <snapshot> --top 50 -o packages/entity-master/entities.json` (MusicBrainz+Wikidata, rate-limit 1.1s, UA 명시).
- 검증: `entities.json`이 `entity.schema.json` 준수 (jsonschema).

## 조인 패턴 (모듈이 이 차원에 붙는 법)

- **chart-history**: `analyze --entities packages/entity-master/entities.json` → `normalize.primary_artist` 키로 조인 → 아티스트 원산지 분포.
- **fandom-pulse** (예정): 스냅샷의 `music`(사운드=아티스트+곡) / 그룹 해시태그 → **별칭 인덱스**로 아티스트 엔티티 인식(코르티스↔CORTIS) → 사운드/챌린지를 아티스트 차원에 귀속.
- **별칭 크로스언어**: `aliases[]`가 한글↔로마자↔다국어를 잇는다 → 크로스소스/크로스플랫폼 매칭의 콜리전 방지·언어 견고화.
