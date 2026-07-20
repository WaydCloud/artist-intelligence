# DATA_SOURCES.md — 데이터 접근 카탈로그

> K-pop 팬덤/A&R 인텔리전스 시스템의 데이터 접근 레일·워크플로우·소스 매핑·ToS 가이드.
> 기준일 2026-07-18 (9개 에이전트 리서치 합성). `[불확실]` = 배포 전 재확인 필요(가격·정책·버전·수치 유동).
> **모듈 약어**: **DD** dance-dynamics · **TB** trend-brand · **BH** brand-harness · **SM** song-match · **FD** fandom.
> 데이터 사용 규칙은 [`AGENTS.md`](AGENTS.md) §5 · [`docs/05-ethics-and-data.md`](docs/05-ethics-and-data.md)를 구속력으로 따른다(§4 참조).

---

## 1) 채택할 MCP 서버 (데이터 접근 레일)

원칙: **공식 API 기반 MCP를 1차**, 매니지드 스크래퍼 MCP는 리스크 이전용 2차, 로그인·자체 브라우저 자동화는 최후. 아래는 "레일(수도관)"이며, 실제 분석 로직은 §2 Agent Skills에 얹는다.

| MCP 서버 | 강점 | 주로 쓰는 소스 | 비용 | ToS |
|---|---|---|---|---|
| **naver-search-mcp** (isnow890) | 공식 Naver Open API 래핑(DataLab 트렌드 + 웹/뉴스/블로그/쇼핑) | 국내 검색 트렌드, 뉴스 | 무료(본인 Naver 키) | 낮음 |
| **YouTube MCP** (comments 지원본 선별) | 댓글·통계·트랜스크립트 도구화, 공식 Data API v3 소비 | YouTube MV 지표·댓글 | 무료(본인 GCP 쿼터 10k units/day) | 낮음 |
| **korean-data-mcp** (`get_melon_chart`) | 멜론 실시간/일간/주간 차트 MCP 네이티브 | 멜론(+Naver 등) | Apify 토큰, 무료 $5/월 | 중간 · **초기단계, 폴백 필수** `[불확실]` |
| **Trends MCP** (trendsmcp.ai) | 12+ 소스 통합 트렌드(구글/YT/TikTok/Reddit), 차단관리 위임 | 크로스플랫폼 트렌드 조기신호 | 무료 100 req/day~ | 중간 |
| **Firecrawl MCP** | 임의 웹 → LLM-ready 마크다운·스키마 추출 | 공식 사이트·보도자료·뉴스·위키·포럼 | 무료 1,000 크레딧/월 | 낮음 |
| **Exa MCP / Tavily MCP** | 에이전트 발견·검색 레이어(신인/이슈/담론 실시간 발굴) | 웹 디스커버리(수집 아님) | Exa 무료 20k/월, Tavily 무료 1k/월 | 낮음 |
| **Apify MCP** (mcp.apify.com) | 3,000+ Actor, 소셜/커머스 소스 폭 최대 | IG·TikTok·X·Reddit·Weibo·차트 | MCP 무료, Actor 종량(예 IG ~$1.5/1K) | **중간 · ToS 책임 사용자 귀속** |
| **Bright Data MCP** (Web MCP + 데이터셋 마켓) | 안티봇 우회(Web Unlocker)·SERP·사전수집 소셜 덤프 | 차단 강한 소스, 과거 대량 백필 | 무료 5,000 req/월, Unlocker ~$3/1K | **중간 · PIPA/GDPR 법무검토** |
| **mcp-server-weibo** | 热搜·슈퍼토픽·피드, API키 불필요 | 중화권 화력 | 무료(MIT) | 중간 · anti-bot 취약 |
| **Spotify MCP** | 검색·카탈로그·플레이리스트(대화형 조회) | Spotify 메타데이터 | 무료(본인 앱 쿼터) | 중간 · **대량수집 부적합** |
| **Playwright MCP** (microsoft, 표준) | 로그인·인터랙션 필요 소스에 유일 접근책 | 위버스·팬카페·투표사이트 | 무료(자체 컴퓨트) | **높음 · 인프라 중 법적 리스크 최상위** |

**비채택/주의**: Puppeteer MCP는 2026년 deprecated → **신규 채택 금지**, Playwright로 표준화 `[불확실: 상태 재확인]`. Hanteo/theqoo/DC/Weverse **전용 MCP는 미존재** → 스크래퍼 래핑은 §4 리스크로 비권장.

---

## 2) 우리가 만들 Agent Skills (MCP 위 패키지드 워크플로우)

각 Skill = 여러 레일을 오케스트레이션 + 정규화 + 지표화. **원문 최소저장, 지표(볼륨·감성·순위) 중심 적재** 원칙(§4).

| Skill | 하는 일 | 사용 레일 | 산출물 | 모듈 |
|---|---|---|---|---|
| **팬덤 센티먼트 스윕** | 다국어 댓글·게시글을 컴백 단위로 수집→감성·언어권·멤버/곡 언급량 정량화 | YouTube MCP(1차 앵커)·Trends/Apify·Bright Data·Weibo | 컴백별 센티먼트 지수, 지역 팬덤 분포 | **FD**, TB |
| **차트 히스토리 수집** | 국내외 차트 주간 스냅샷 파이프라인·시계열 축적 | korean-data·Apify(circlechart)·Spotify/Apple/YT 공식 | 순위·변동·실물판매 시계열 | **TB**, SM, BH |
| **유사 그룹 벤치마크** | 유사 아티스트·태그·차트 위치·오디오 특성으로 피어 비교 | Last.fm·Spotify·ReccoBeats(오디오 대체)·차트 | 벤치마크 리포트, 포지셔닝 맵 | **SM**, BH |
| **댓글 패턴 마이너** | 답글트리·좋아요로 토픽/이상치/바이럴·**안무 언급** 추출 | YouTube MCP·Apify(IG/TikTok) | 토픽 클러스터, 안무/무대 반응 지표 | **DD**, FD |
| **바이럴 조기 감지** | 트렌딩 사운드·해시태그 + 검색 급상승으로 곡/챌린지 선행신호 | Trends MCP·TikTok Creative Center·Naver/Google Trends | 바이럴 후보 큐, 급상승 키워드 | **DD**, TB |
| **컴백 화력 KPI** | 초동·앨범판매·MV지표·팬플랫폼 매크로를 성과 대시보드로 | Hanteo B2B·Circle·YouTube·OpenDART | 컴백 성과 KPI(초동·화력) | **BH**, FD |
| **엔티티 마스터 빌더** | 아티스트/그룹/앨범 정규화·지식그래프 뼈대 | MusicBrainz/Wikidata·Firecrawl·나무위키(사실필드만) | 마스터 엔티티 그래프 | 공통(전 모듈) |
| **브랜드·평판 모니터** | 논란·평판·언론·브랜드 딜 신호 정량화 | BIGKINDS·Naver 뉴스 API·X 제3자·Exa/Tavily | 평판 타임라인, 리스크 알림 | **TB**, BH |

---

## 3) 데이터 소스 → 접근법 매핑

권장 접근 = 프로덕션 1차. ToS리스크: 낮음/중간/높음.

### 차트 · 판매
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| Circle Chart | 국가 공식차트·실물판매 A&R 표준 | **정식 제휴가 유일한 클린 경로**: circlechart.kr 푸터 '차트제휴신청'(운영: 한국대중음악산업협회 — 구 음콘협, 2026-04 명칭 변경, kpia.or.kr. 비용·자격 비공개=문의 기반, 2026-07-20 조사). ~~문화빅데이터포털~~ 재조사 결과 **국내 차트 미보유**(해외 아이튠즈 K-POP 순위 2020 스냅샷뿐 — 공공데이터포털 동일) → 공공데이터 경로 배제. 랭킹은 JS 로드 + **TDM 금지 명시**(2026-07-18 실측) → 직접 스크랩·Apify **부적합** | 중간→**높음**(DB권 + 명시적 TDM 금지) |
| Hanteo(초동) | 초동·팬덤 화력 업계표준 | **Hanteo Global B2B 정식계약(유일 합법)**. 스크래핑·비공식 라이브러리 = **부적합** | 높음(스크래핑)/낮음(B2B) |
| 멜론 | 국내 대중성 벤치마크 | **공식 Melon MCP 서버**(카카오엔터, `mcp.melon.com/mcp` · OAuth 2.0 · `get_music_chart`로 공식 TOP100/일간/주간 — 유일한 공식 프로그래매틱 경로, 2026-07 베타) — 자동 수집 허용 범위·화이트리스트는 `melon_info@kakaoent.com` 사전 문의 필수(2026-07-20 조사). 비공식(korean-data-mcp/melon-chart.py/Apify)은 ToS 리스크로 차선 | **낮음(공식 MCP, 문의 전제)**/중간(스크랩) |
| 지니·벅스 | 코어 팬덤 스트리밍 화력(멜론과 교차) | genie/bugs-chart.py, korea-music-chart-api | 중간 |
| **추가 권장** | 미·글로벌·일본 핵심 · 무료 프록시 | **Luminate/Billboard(Hot100·Global200·K-pop100), Oricon·Billboard Japan·LINE Music, Kworb·K-pop Radar·iChart, YT/Spotify Charts·iTunes RSS** `[소스화 필요]` | 상이 |

### 스트리밍
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| Spotify | 글로벌·popularity·플레이리스트 | **Client Credentials로 카탈로그/popularity/팔로워/플레이리스트만**. 오디오피처 신규앱 불가 → ReccoBeats/Cyanite 대체 | 낮음(공식)/높음(스크래핑) |
| Apple Music | 미·일 국가/도시 차트, ISRC | MusicKit developer token(JWT), $99/년 | 낮음 |
| YouTube Data v3 | MV지표·**댓글(밀도 최고)** | videos.list·commentThreads.list(~1 unit), search.list(100) 회피, 강한 캐싱 | 낮음 |
| Last.fm | 서구 취향그래프·유사아티스트·태그 | pylast(공식). **상업 시 별도 라이선스** | 중간 |
| **추가 권장** | 라이선스 애그리게이터(개별 스크래핑 합법 대체) | **Chartmetric·Soundcharts·Viberate·Songstats** `[핵심 — 소스화 필요]` | 낮음 |

### 소셜
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| YouTube 댓글 | 최대 공개 팬텍스트, **센티먼트 1순위 앵커** | 공식 Data API v3 → 병목 시 정식 상향, 대량백필만 Apify 한시 | 낮음 |
| Instagram | 비주얼 팬덤·브랜드 반응 | **자사=Graph API**. 공개=Bright Data/Apify로 **로그아웃 공개 데이터만** | 낮음(자사)/높음(스크래핑) |
| TikTok | 챌린지·사운드 바이럴 선행 | 상업 Research API **부적합** → EnsembleData/ScrapeCreators | 낮음(불가)/높음(스크래핑) |
| X(Twitter) | 실시간 화력·총공·조기감지 | 하이브리드: 감사=공식, 대량=제3자(공급사 이중화) | 낮음(공식)/높음(제3자) |
| Reddit | 서구 롱폼 담론·이유 | 실시간=공식 API(상업 유료), 백필=Arctic Shift/Academic Torrents 덤프 | 낮음/중간 |
| **추가 권장** | 서구 코어 실시간 · 연구용 | **Discord, Meta Content Library(학술)** `[누락]` | 상이 |

### 국내 커뮤니티 · 중화권
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| 나무위키 | 한국어 마스터 데이터 표준 | 과거 덤프(HF) + extractor로 **사실필드만**, 최신분만 소량 | 중간 · **NC 라이선스(상업 시 법무 필수)** |
| theqoo | 여성팬덤 여론·이슈 조기경보 | 저빈도 헤드리스 / 대행, **지표만 적재** | 높음 |
| DCInside | 최대 익명 화력/논란 진앙 | dcinside-python3-api / robots 준수 | 높음(명예훼손·PIPA) |
| 네이트판 | 팬덤 밖 대중여론 확산 | 경량 requests/BS4, 식별정보 제거 | 중간 |
| 웨이보 | 중화권 화력·热搜 | mcp-server-weibo / TikHub·Apify, **지표 중심** | 중간 |
| **추가 권장** | 이슈확산·조직인프라·중국 | **인스티즈·FMKorea, 네이버/다음 팬카페, Douyin·QQ Music·NetEase·Bilibili** `[누락]` | 높음 |

### 트렌드
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| Google Trends | 글로벌 검색 관심도(상대값) | 공식 v1alpha 신청 `[승인제]` → SerpApi(캐시)/DataForSEO. **pytrends 직접 비권장** | 낮음/높음(pytrends) |
| Naver DataLab | 국내 검색 표준(상대값) | **Naver Developers Open API 1차**(무료 1k/day). NCloud 'Search Trend' **종료 임박** `[재확인]` | 낮음 |
| SerpAPI 계층 | 차단 없는 다중신호 수급 | SerpApi(캐시)/DataForSEO/Bright Data 이중화 | 낮음 |
| TikTok Creative Center | 트렌딩 사운드·해시태그 진앙 | 수동 저빈도 / 자동은 Apify·라이선스 벤더 | 중간(자동 스캔=위반) |
| **추가 권장** | 음방 순위 · 채널 애널리틱스 | **인기가요/뮤뱅/엠카 1위·점수, Social Blade·HypeAuditor** `[누락]` | 상이 |

### 팬 플랫폼
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| Weverse | 팬덤 규모·참여 최상위 신호 | **공개 표기값 + Similarweb/Sensor Tower 매크로 + IR**. 원문은 파트너십 외 합법경로 없음 | 낮음(매크로)/높음(비공식) |
| DearU 버블 | 유료 코어팬·직접매출 신호 | **OpenDART 공시/IR(매크로)** + Sensor Tower. 메시지 원문 **금지** | 낮음(공시)/높음(원문) |
| Fromm | 버블 밖 커버리지 보완 | OpenDART(노머스)+앱 애널리틱스 매크로만 `[불확실]` | 낮음/높음(원문) |
| **추가 권장** | 컴백 화력·코어팬 직접신호 | **최애돌·Fanplus·Idol Champ·Mnet Plus·Starplay** `[누락]` | 상이 |

### 마스터 · 메타 · 기타 (갭 반영)
| 소스 | 가치 | 권장 접근 | ToS |
|---|---|---|---|
| **MusicBrainz·Wikidata·Discogs·dbkpop** | **상업이용 가능 오픈 엔티티**(나무위키 NC 회피) | 오픈 덤프/공식 API + 교차검증 | 낮음 |
| **BIGKINDS·Naver 뉴스 API** | 논란·평판 정량분석 합법소스 | 공식 API | 낮음 |
| **Genius·Musixmatch** | 가사·작곡/작사 크레딧(ISRC 보강) | 가사 API | 낮음 |
| **Setlist.fm·Bandsintown·Songkick + 국내 티켓** | 오프라인 수요·지역 팬덤 분포 | 공식 API/공개 | 낮음 |
| **IFPI Global Music Report** | 글로벌 산업통계 매크로 | 공식 연간 리포트(공개) 인용 | 낮음 |

---

## 4) ToS · 법적 · 윤리 가이드 (구속력)

> [`AGENTS.md`](AGENTS.md) §5 · [`docs/05-ethics-and-data.md`](docs/05-ethics-and-data.md)와 연동. 위반 소지가 있으면 **진행 전 중단·질문**.

**접근 우선순위 (위→아래로만 내려간다):**
1. 공식 API (낮은 리스크)
2. 라이선스 애그리게이터 (Chartmetric·Soundcharts 등 — 개별 스크래핑의 합법 대체)
3. 매니지드 스크래퍼 MCP (Apify·Bright Data — 리스크 이전, ToS 책임은 여전히 우리)
4. 자체 브라우저 자동화 (Playwright — 최후, 법적 리스크 최상위)

**저장·처리 원칙:**
- **원문 최소 저장, 지표 중심 적재** (볼륨·감성·순위·언급량). 개인식별정보(닉네임·계정 등) 제거·해시.
- MV/음원 등 **저작물 원본 재배포 금지** — 파생 지표만.
- 미성년 관련 데이터 주의, 명예훼손·PIPA/GDPR 소지 콘텐츠는 지표화 후 원문 폐기.
- **시행(게이트, D-007)**: JSON 수집물은 [`packages/snapshot-schema`](packages/snapshot-schema)(provenance+quality+records) 준수 + [`scripts/validate_snapshot.py`](scripts/validate_snapshot.py) **PII 게이트**로 검증(records에 유저명·id·url·caption·댓글원문 등 있으면 REJECT) → §4가 관습이 아니라 **검증 가능한 계약**. 공유 엔티티 차원 = [`packages/entity-master`](packages/entity-master). CI가 강제.

**소스별 하드 룰:**
- **Hanteo 초동** → B2B 정식계약만 합법. 스크래핑 금지.
- **Circle Chart** → 페이지 푸터에 **"No unauthorized use for AI/ML training or text and data mining (TDM)"** 명시(2026-07-18 실측 확인). 랭킹은 JS/내부 엔드포인트 로드 → 직접 스크랩·Apify actor **부적합**. **정식 제휴(음콘협)/문화빅데이터포털 경로만.**
- **나무위키** → NC 라이선스. 상업 이용 시 법무 검토. 원문 재배포 금지, 사실 필드만. 상업 대체 = MusicBrainz/Wikidata/Discogs/dbkpop.
- **커뮤니티(theqoo·DC·네이트판)** → 저빈도·robots 준수·지표만·식별정보 제거.
- **소셜** → 자사 계정은 Graph API. 공개 데이터만. TikTok 상업 스크래핑 위반 주의.
- **팬 플랫폼(Weverse·Bubble)** → 원문 합법경로 없음 → 공시(OpenDART)·앱 애널리틱스 **매크로만**.
- **키 관리** → 모든 API 키는 환경변수. 커밋 금지(CI gitleaks가 차단).

---

## 5) 모듈별 우선 소스·스킬 매핑

| 모듈 | 1차 소스 | 핵심 Skill | 주 MCP 레일 |
|---|---|---|---|
| **DD** dance-dynamics | YouTube(안무영상·댓글), TikTok 챌린지 | 댓글 패턴 마이너 · 바이럴 조기 감지 | YouTube MCP · Trends · Apify |
| **TB** trend-brand | 차트(Circle/Hanteo/멜론), 트렌드, 뉴스 | 차트 히스토리 · 브랜드·평판 모니터 · 센티먼트 스윕 | korean-data/Apify · naver-search · Trends · Firecrawl |
| **BH** brand-harness | 평판·뉴스·공시, 컴백 성과 | 브랜드·평판 모니터 · 컴백 화력 KPI | Firecrawl · naver-search · Exa/Tavily |
| **SM** song-match | Spotify/Apple/Last.fm 오디오·태그, 차트 | 유사 그룹 벤치마크 · 차트 히스토리 | Spotify MCP · (ReccoBeats) · 차트 |
| **FD** fandom | 소셜 댓글, 커뮤니티, 팬플랫폼 매크로 | 센티먼트 스윕 · 컴백 화력 KPI · 댓글 패턴 마이너 | YouTube · Apify · Bright Data · Weibo |
| 공통 | 엔티티/메타 | 엔티티 마스터 빌더 | MusicBrainz/Wikidata · Firecrawl |

---

## 적용 메모 — 현재 MCP 셋업 순서 검증

리서치가 우리 순서(**Firecrawl → Apify → Bright Data**)를 뒷받침한다:
- **Firecrawl** = 공식 사이트·위키·뉴스·보도자료 (ToS 낮음) → **안전한 첫 타자**, 리스크 없이 파이프라인 검증.
- **Apify** = 소셜(IG/TikTok/X/Reddit) 폭 최대 (ToS 책임 사용자 귀속 — §4 준수).
- **Bright Data** = 차단 강한 소스·대량 백필 (PIPA/GDPR 법무 검토 후).
- 단, **YouTube 댓글은 공식 Data API가 1순위 앵커** — Apify보다 먼저 붙일 가치가 큼(센티먼트 코어, ToS 낮음).

---

## Firecrawl 실측 검증 (2026-07-18)

레일 자체는 검증 완료(직접 v2 API + 유효 키, 잔여 크레딧 정상). **MCP 툴은 이 세션에서 무효 토큰** — Claude Code/VSCode 프로세스가 `setx` **이후**의 `FIRECRAWL_API_KEY`를 상속 못 받음(User scope엔 정상 존재, Process scope엔 없음). → **VSCode 재시작**하면 `.mcp.json`의 `${FIRECRAWL_API_KEY}`가 정상 확장돼 MCP 툴 사용 가능. (오프라인 Python 수집은 애초에 env 키 직접 읽으므로 무관 — D-003.)

- ✅ **나무위키 사실 추출**: 전체 페이지(217k자) naive JSON 추출은 `null`. **`includeTags:["table"]`로 인포박스만 좁히면 정확 추출** — aespa: 데뷔 2020-11-17 · 소속 SM · 유통 카카오 · 팬덤 MY · 멤버 4인, 전부 검증됨. → **엔티티 마스터 빌더는 "인포박스 테이블 한정 + 사실 스키마" 패턴** 채택(NC 라이선스: 사실 필드만, 원문 미저장).
- 🚩 **써클차트**: 랭킹이 JS/내부엔드포인트 로드라 정적 스크랩 미포착(마크다운 516자=헤더/푸터뿐, 빈 테이블 → LLM이 "Album Title 1" 환각). **푸터에 AI/ML·TDM 무단이용 금지 명시** → §3·§4 하드룰 반영. 스크랩 대신 **정식 제휴/문화빅데이터포털**. → 차트 히스토리 레일은 **Kworb 등 오픈 애그리게이터로 전환**(D-005).
- ✅ **Kworb 차트 추출**(써클차트 대체): `spotify/country/kr_daily.html` 정적 테이블에서 순위·아티스트·곡·스트림 정확 추출(환각 없음). 정적 HTML·anti-bot 없음·저ToS → **차트 히스토리 수집 스킬의 1차 소스**. Billboard/iTunes/Apple·국가별 다수 차트 커버.
- **v2 API 주의**: JSON 추출은 `formats:[{"type":"json","schema":…,"prompt":…}]` 형태. 구 `jsonOptions` 최상위 키는 400(Unrecognized key). URL 발견은 `/v2/map`(`search` 파라미터)로.

## YouTube Data API v3 실측 검증 (2026-07-18)

키 유효(User scope, 직접 REST 호출 — MCP 아님, 재시작 불필요). **댓글=센티먼트 1순위 앵커** 확인.

- ✅ **videos.list** (`part=statistics,snippet`, ~1 unit): MV 조회수·좋아요·댓글수 지표 확보(스모크: Gangnam Style 60억 조회).
- ✅ **commentThreads.list** (`part=snippet`, `order=relevance`, `maxResults`, `nextPageToken`, ~1 unit): 댓글 텍스트+좋아요+답글수, **다국어(영/한/스페인어) 혼재** → 언어권·감성 분포 산출 가능. **작성자명(PII) 미적재**(§4).
- 원칙: 원문은 감성/언급량 **지표로 집계 후 폐기**, PII 제거, 강한 캐싱. `search.list`(100 units) 회피 — 대상은 **video ID로 직접 지정**. 기본 쿼터 10k units/day.

## 엔티티 마스터(MusicBrainz + Wikidata) 실측 검증 (2026-07-18)

`chart-history` v3/v3.1 엔티티 조인에 채택(둘 다 CC0·상업이용 가능·구조화, 직접 REST·UA 명시).

- ✅ **MusicBrainz**(`/ws/2/artist/`, 1req/1.1s): 신생 K-pop(CORTIS·RESCENE·Hearts2Hearts)까지 `country·type·MBID` 확보. KR 상위 50팀 중 **36팀 해석**.
- ✅ **Wikidata 폴백**(v3.1, `wbsearchentities`→`wbgetentities`, P495/P27 국가, P297 ISO): MB가 놓친 **로마자·native-name 변형**(임영웅·JANNABI·성시경·Kenshi Yonezu 등) 해소 → 총 **45/50**(MB 36 + Wikidata 9).
- 🚩 잔여 한계: 스타일라이즈드·혼종 표기(예 "데이먼스 이어 Damons year", "LEE CHANHYUK") 5팀 미해석 → 수기/추가 소스. `country`는 커뮤니티 편집 기반 → 불완전 가능(참고).
- 패턴: **enrich(라이브)→커밋 엔티티 맵(사실만·source 병기)→analyze(오프라인 조인)** 로 스모크 결정성 유지.

## Apify 실측 검증 (2026-07-18)

레일 순서 D-002의 3번(소셜 폭). **매니지드 스크래퍼 = 리스크 이전 2차 레일**(§4): 종량제 + ToS 책임 사용자 귀속 → **무료 기본·유료 opt-in·비용 캡·지표만** 원칙으로 배선.

- **배선**: [`.mcp.json`](.mcp.json) `apify` 원격 서버(`https://mcp.apify.com`, Streamable HTTP, `Bearer ${APIFY_TOKEN}`, `?tools=actors,docs`) · [`.env.example`](.env.example) `APIFY_TOKEN`(setx→MCP는 VSCode 재시작) · [`scripts/apify_probe.py`](scripts/apify_probe.py) 안전 probe.
- ✅ **토큰/플랜**(무료 `GET /v2/users/me`, Actor 0·비용 0): VALID · plan STARTER. **오프라인 probe는 재시작 불필요** — setx가 쓴 User scope 값을 그 호출에만 주입(토큰 미노출).
- ✅ **고도화 실측**(유료 `POST /v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items`): `#kpopdance` 공개글 20건, `maxItems=20`·`maxTotalChargeUsd=$0.10` 캡 내. **지표만 추출** — `likesCount`(mean 11.9/max 56)·`commentsCount`(mean 1.15/max 12)·미디어 치수 분포·필드 존재율. **PII 필드**(`ownerUsername`·`ownerFullName`·`ownerId`·`caption`·`url`·`displayUrl`·`id`)는 probe가 **값 미출력 redact**, 비-숫자 필드(`latestComments`·`mentions`·`taggedUsers`)도 존재 카운트만 → §4 "원문 최소저장·지표 중심" 실증.
- ✅ **MCP 대화형**(VSCode 재시작 후): `fetch-actor-details` Bearer 인증 정상 응답 → `.mcp.json` 배선 대화형 확인. 툴: `search-actors`·`fetch-actor-details`·`call-actor`·`get-dataset-items`·`get-actor-run` 등. `call-actor`는 `fetch-actor-details`로 입력 스키마 먼저 확인 후 호출.
- **비용(확정)**: `apify/instagram-hashtag-scraper` = **PAY_PER_EVENT $0.0023/result**(BRONZE tier) → 20건 실측 ≈ **$0.046**. Actor마다 종량 모델 상이 → 호출 전 `fetch-actor-details`의 `pricing` 확인 + `maxTotalChargeUsd` 캡 필수.
- **패턴**: `run-sync-get-dataset-items → 지표 요약(PII redact) → 원문 미저장`. Actor ID는 `username~actorname`(경로에 `/` 불가). Bearer 헤더 인증(URL 토큰 회피).
- 🚩 **한계/주의**: (a) `#kpopdance` 최근글은 소규모 계정 위주라 engagement 낮음 — **레일은 정상**, A&R 신호엔 그룹/공식계정·챌린지 해시태그 타깃 필요. (b) 공개(로그아웃) 데이터·지표만·종량제 비용 **사용자 귀속**(§4). (c) MCP 서버(대화형 Actor 탐색)는 **VSCode 재시작 후** 사용(프로세스 env 상속). (d) TikTok 상업 스크래핑은 여전히 회피(§4) — IG 공개가 sanctioned 경로.
- **→ 스킬화 완료**: 이 레일 위 첫 스킬 모듈 [`modules/fandom-pulse`](modules/fandom-pulse) 빌드·스모크 통과 — IG 해시태그 **화력·참여·모멘텀·사운드**를 facts-only로 산출(`fetch`가 PII 즉시 폐기 → `analyze` 결정적 → 스키마 유효 report.json). 하중 기준(고참여·모멘텀)은 **기준 원장**(AGENTS §2.1)으로 튜닝 노출. reels 실측: 트렌딩 사운드(ATEEZ-BAD 등)·게시 가속 +2.4/일.
