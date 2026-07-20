# 2026-07-18 · chart-history v3 (엔티티 마스터 조인)

> Handoffs/ 아카이브 — 이 시점 스냅샷. (다음 행선지는 루트 `HANDOFF.md`)

## 이 구간에 한 일

- **firecrawl MCP 정상화 확인** — VSCode 재시작으로 키 상속(scrape 200). 직접 API도 병행 가능.
- **chart-history v3 빌드** — 엔티티 마스터 조인.
  - `normalize.py`: 표준 아티스트/곡 키(협업·feat·버전 접미 정규화) → 교차 매칭 견고화.
  - `entities.py` + `enrich` 커맨드: **MusicBrainz(CC0)** 아티스트 검색(rate-limit 1.1s, UA) → 커밋 가능한 엔티티 맵(mbid·name·country·type).
  - `analyze --entities`(오프라인): **아티스트 원산지 분포** bar + 국내(KR) 비중 지표 + 커버리지/미해석 한계 insight.
- MusicBrainz를 엔티티 마스터로 채택(DATA_SOURCES "MusicBrainz 실측 검증" 메모).

## 검증 (로컬 = 게이트)

- v3 smoke(4개국 + entities): base 200 · entities 50 · schema valid. 국내 78%(해석 36/50), 원산지 KR 28·US 4·JP 2·CA 1·IT 1, 미해석 14팀 명시.
- 결정성(v1/v2/v3) True · 하위호환(v1 단일·v2 --entities 생략) · ruff · pyright · schema-validate · live fetch · live enrich. 전부 통과.

## 배운 것 / 한계

- MusicBrainz 커버리지 우수(신생 그룹 포함)하나 **로마자·표기 변형 미해석**(임영웅·JANNABI 등) → v3.1 위키 보강 대상.
- 원산지는 **기술적 사실 서술**로만(국적 기반 가치판단 금지, RULES §5).
- 수집(enrich/fetch, 라이브)과 분석(analyze, 오프라인·결정적) 분리로 스모크 결정성 유지.

## v3.1 (같은 세션 이어서) — Wikidata 폴백

- `entities.py`에 **Wikidata 폴백** 추가(`wbsearchentities`→`wbgetentities`, P495/P27 국가, P297 ISO 코드, QID 캐시). `enrich`가 MB 미해석분을 Wikidata로 보강(`--no-wiki`로 off).
- **해석 36→45/50**(MusicBrainz 36 + Wikidata 9). 원산지 KR 34·US 5·JP 4·CA 1·IT 1. 임영웅·JANNABI·성시경·Kenshi Yonezu 등 로마자 표기 해소.
- 리포트 insight에 **출처(MB·Wikidata)** 병기. 잔여 미해석 5팀(스타일라이즈드·혼종 표기) 명시. 결정성·게이트 전부 재확인.
- 남은 v3.2: 다일 자동 축적 파이프라인 + 크로스소스(멜론/iTunes) + firecrawl→나무위키 사실 보강.

## v3.2 (같은 세션 이어서) — 헤더 파서 · 크로스뷰 모멘텀 · 축적

- **헤더 기반 파서**: 고정 인덱스 → 라벨 매핑. daily(`Days`)·weekly(`Wks`) 등 변형 견고, daily 무회귀.
- **크로스뷰 모멘텀**: 같은 국가·날짜, 다른 뷰(일간×주간) → 모멘텀 = 주간순위−일간순위(+상승세). RESCENE-Runaway +5, 상승세 7/19.
- **축적 파이프라인**: `collect`→`data/snapshots/<store>/<date>.html`(gitignore), `analyze <dir>`→디렉터리 glob→날짜 라인.
- weekly 픽스처 커밋. 게이트·결정성·하위호환 전부 재확인. 커밋 리포트는 4개국+엔티티 유지.
- 남은 v3.3: 크로스소스(Apple KR=한글명 ↔ Spotify=Latin → 크로스언어 매칭) + 잔여 5팀 수기 + 실데이터 다일 라인.

## v3.3 (같은 세션 이어서) — 크로스소스 positioning

- **크로스소스**: chart 라벨→서비스(Spotify/Apple) 도출, 같은 국가·다른 서비스 = 크로스소스 차원. **제목 기준 매칭**(아티스트 한글↔Latin이라 제목으로 조인).
- 신호: RESCENE-Pretty Girl Spotify 4위 vs Apple 127위(편중 +123, 스트리밍 강세). 양대 진입 13/20. heatmap(곡×[Spotify,Apple]).
- 파서 견고화: **암묵적 행종료**(Apple thead가 `</tr>` 생략) → Apple 200곡 파싱. Apple 픽스처 커밋.
- 한계 정직: 제목 언어 갈리는 곡(만찬가↔Bansanka) 미매칭 ~35% → 레코딩 MBID 매칭은 v3.4.
- 게이트·결정성·하위호환 전부 재확인. 커밋 리포트는 4개국+엔티티 유지.

## v3.4 (같은 세션 이어서) — 엔티티 별칭 크로스언어 매칭

- **레코딩 MBID 매칭 실측 → 불발**: MB 레코딩 검색이 신곡·크로스언어(아이오아이/갑자기, 태연/만찬가)에서 0건. 무료 구조화 데이터로 제목-언어 갭 해결 불가 확인.
- **전환**: MB 별칭(`inc=aliases`)에 한글 변형 존재(코르티스·에스파·리센느·아이오아이) 확인 → `enrich`가 별칭 수집, `alias_index`로 크로스언어 아티스트 인식.
- **하이브리드 크로스소스**: 제목 매칭(커버리지 유지) + **엔티티 콜리전 가드**(양쪽이 다른 엔티티면 거부). 커버리지 13 무회귀 + 엔티티 확인 11곡. HANRORO↔한로로(별칭無)도 제목으로 유지.
- 한계 정직: 제목-언어 갭은 **유료 ISRC 애그리게이터**(Chartmetric 등) 과제로 문서화(v3.5).
- entities.json 별칭 포함 재생성. 게이트·결정성·무회귀 전부 재확인.

## 세션 로테이션 진입점

→ 루트 [`HANDOFF.md`](../HANDOFF.md)(v3.4 인계점으로 갱신됨) — 후보: 대시보드(보류·언제든) / **케이스 스터디 컨셉(우선 논의 권장)** / 댄스 v1 / v3.5(ISRC) / Apify.
