# DRAFT · alt z 정답지와 사전 등록 (D-065) · **A&R 확정 대기**

> 이 문서와 `modules/genre-impulse/RULES.md` §2.1.5는 **측정보다 먼저** 커밋된다. 커밋 시점이 증거다
> (`DRAFT-dreamcore-answer-sheet.md` · `DRAFT-jersey-club-answer-sheet.md` §2 선례).
> 기계용 목록: [`../data/research/genre-impulse/altz/answer_sheet.json`](../data/research/genre-impulse/altz/answer_sheet.json).
>
> dreamcore(D-064)와 다른 점 하나: dreamcore는 출처가 말하는 소리를 축으로 번역해 규칙을 먼저 정했다. alt z는 **소리를 정의한 1차 출처가 없다**(§1). 그래서 축을 번역하지 않고, 양성을 둘로 나눠 한쪽(탐색)에서 축을 고르고 다른 쪽(홀드아웃)에서 판정한다. 고르는 규칙과 판정 기준은 이 커밋에서 고정한다.

## 0. 날짜별 기록

| 날짜 | 단계 | 무엇 |
|---|---|---|
| 2026-10-24 | 1 정답지 | 기획 저장소 조사 노트(1차 조사 2026-10-24)에서 양성 28 · 음성 12 확정 |
| 2026-10-24 | 2 사전 등록 | 분할 · 탐색 규칙 · 판정 기준 고정, RULES §2.1.5 사전 등록 · 이 커밋 |
| 2026-10-24 | 3 실측 · 탐색 | 40곡 중 38곡 해석 · 탐색 14/14 측정 · §6 |
| 2026-10-24 | 4 축 고정 | `silence_ratio` 상위 1축 고정 · 홀드아웃 전에 이 커밋 |
| | 5 판정 | (홀드아웃 · H-map · 코호트 베이스라인) |

## 1. 무엇을 alt z라고 부르나 (측정 전에 정함)

**Spotify 장르 분류 체계의 장르 태그다.** 이름을 붙인 사람은 Glenn McDonald(당시 Spotify)다. 분류 단위는 곡이 아니라 **아티스트**이고, 기준은 소리가 아니라 **청취자 공유 클러스터**다. 도구로 청취자가 겹치는 아티스트 묶음을 찾고 사람이 들어 본 뒤 인정했다. 등급 `매우 높음`.

McDonald 본인 발언 (Chris Dalla Riva 인터뷰, 2024-05-26, <https://www.cantgetmuchhigher.com/p/spotifys-former-data-guru-sets-the>). 인용은 이 두 줄뿐이다.

- "That's one I actually did name."
- "For “Alt Z”, it was artists that fell into the “Indie Pop” category. But “Indie Pop” is way too broad, so I had to make something up. I could have called the genre “Generation Z” because most of the listeners were young. That felt boring, though. What struck me is that the music felt alternative and Gen Z-ish. I also liked the idea that the keyboard shortcut for undo was Control + Z."

🔴 **같은 페이지의 굵은 글씨 두 줄은 질문자의 말이다.** "I guess I picked well [laughs]." · "When you listen to the artists..., the name makes sense." 를 McDonald의 말로 인용하지 않는다.

노출: Every Noise at Once 장르 지도 <https://everynoise.com/engenremap-altz.html> · 자동 플레이리스트 「The Sound of Alt Z」(소유자 The Sounds of Spotify). 첫 등장(Wayback): 전체 지도 2021-03-14 22:54 UTC 캡처에 없음 → 2021-03-16 01:19 UTC 캡처에 있음(`높음`). 장르 페이지 첫 캡처 2021-04-29, 플레이리스트 첫 캡처 2021-07-21(640곡 · 좋아요 906).

### 1.1 출처가 말하는 소리

| 요소 | 근거 | 등급 |
|---|---|---|
| 「felt alternative and Gen Z-ish」 | McDonald 인터뷰 | 매우 높음 |
| 청취자 대부분이 젊다 | 같은 인터뷰 | 매우 높음 |
| 지도 좌표: 세로 6,258개 장르 중 위에서 42%(pop · k-pop · hyperpop · electropop 15~17%보다 organic 쪽, bedroom pop 50% · indie pop 61% · gen z singer-songwriter 69%보다 mechanical 쪽), 가로 63%(약간 spikier and bouncier) | Every Noise 지도. 축 문구 "down is more organic, up is more mechanical and electric; left is denser and more atmospheric, right is spikier and bouncier". 명명자 "The calibration is fuzzy". 순위 환산은 조사자 계산 | 중간 |
| "Alt pop with story-full lyrics that theatre kids are likely to love" | The Tab 2차 인용, Spotify 원문 미확인 | 낮음 |
| 기타 · 로파이 · 베드룸 프로덕션 · 템포 · 보컬 · 장르 혼합 | 1차 출처 없음 | 근거 없음 |

- 🔺 **소리 요소를 정의한 1차 출처가 없다.** 지도 좌표(`중간`)만 소리 축 하나(organic ↔ mechanical)에 위치를 준다. 이 좌표는 규칙에 쓰지 않고 예측 H-map(§3.5)으로만 쓴다.
- 트레이드 프레스(Billboard · Rolling Stone · Pitchfork · NME · The FADER · MBW)의 정의는 찾지 못했다(§5).

## 2. 정답지

### 2.1 양성 28곡 (전부 해외 곡 · 한국 발매 0곡)

등급 `높음`의 근거: 명명자의 체계가 **아티스트 단위로** alt z에 넣었고, 곡은 그 체계의 예시곡(S1) 또는 플레이리스트 항목(S2)이다. 곡 단위로 alt z라고 부른 출처는 아니다.

- S1 = Every Noise alt z 페이지의 아티스트별 예시곡("e.g.", 데이터 2023-11-19).
- S2 = 「The Sound of Alt Z」 2021-07-21 Wayback 캡처의 순번(PL #n).

| # | 아티스트 | 곡 | 출처 | 등급 | 분할 |
|---|---|---|---|---|---|
| 1 | Alec Benjamin | Let Me Down Slowly | S1 | 높음 | 탐색 |
| 2 | Ashe | Moral of the Story | S1 | 높음 | 홀드아웃 |
| 3 | Ashnikko | Daisy | S1 | 높음 | 탐색 |
| 4 | Au/Ra | Panic Room | S1 · S2 PL #21 | 높음 | 홀드아웃 |
| 5 | Bea Miller | feel something | S2 PL #5 | 높음 | 탐색 |
| 6 | BENEE | Supalonely | S1 | 높음 | 홀드아웃 |
| 7 | Charlotte Lawrence | Joke's On You | S2 PL #4 | 높음 | 탐색 |
| 8 | Em Beihold | Numb Little Bug | S1 | 높음 | 홀드아웃 |
| 9 | FINNEAS | Let's Fall in Love for the Night | S1 | 높음 | 탐색 |
| 10 | FLETCHER | Bitter | S1 · S2 PL #2 | 높음 | 홀드아웃 |
| 11 | gnash | i hate u, i love u | S1 | 높음 | 탐색 |
| 12 | Gracie Abrams | I miss you, I'm sorry | S1 | 높음 | 홀드아웃 |
| 13 | Holly Humberstone | Paint My Bedroom Black | S1 | 높음 | 탐색 |
| 14 | Jeremy Zucker | comethru | S1 | 높음 | 홀드아웃 |
| 15 | Lauren Spencer Smith | Fingers Crossed | S1 | 높음 | 탐색 |
| 16 | Lizzy McAlpine | ceilings | S1 | 높음 | 홀드아웃 |
| 17 | Maggie Lindemann | Pretty Girl (Cheat Codes X CADE Remix) | S1 · S2 PL #6 | 높음 | 탐색 |
| 18 | Maisie Peters | Psycho | S2 PL #26 | 높음 | 홀드아웃 |
| 19 | Melanie Martinez | Pacify Her | S1 | 높음 | 탐색 |
| 20 | mxmtoon | prom dress | S1 | 높음 | 홀드아웃 |
| 21 | Olivia O'Brien | hate u love u | S2 PL #1 | 높음 | 탐색 |
| 22 | Penelope Scott | Rät | S1 | 높음 | 홀드아웃 |
| 23 | Rosa Linn | SNAP | S1 | 높음 | 탐색 |
| 24 | Sasha Sloan | Dancing With Your Ghost | S1 · S2 PL #29 | 높음 | 홀드아웃 |
| 25 | Sody, Cavetown | is your bedroom ceiling bored? | S2 PL #13 | 높음 | 탐색 |
| 26 | Tate McRae | greedy | S1 | 높음 | 홀드아웃 |
| 27 | UPSAHL | Drugs | S2 PL #11 | 높음 | 탐색 |
| 28 | Zolita | Shut Up and Cry | S2 PL #24 | 높음 | 홀드아웃 |

- 고르지 않았다: 조사 노트 (a)의 28곡을 **전부** 넣었다.
- Maggie Lindemann은 리믹스다. 버전은 다른 녹음이라(`DRAFT-answer-sheet-corpus.md` §4) 이 리믹스만 센다.

### 2.2 음성 12곡 (등급 `중간`)

선정 기준(조사 노트 (b)): 이웃 장르 지도의 예시곡이고, alt z 지도 248명과의 겹침으로 거른다. 곡이 alt z가 아니라는 것은 출처가 말한 것이 아니라 아티스트 집합에서 추론한 것이라 `중간`이다.

| # | 아티스트 | 곡 | 이웃 장르 | 이유 | H-map 묶음 |
|---|---|---|---|---|---|
| 1 | NewJeans | Super Shy | k-pop | k-pop 지도 382명과 alt z 248명의 겹침 0 | 아래 |
| 2 | Jung Kook | Seven | k-pop | 같은 겹침 0/382 | 아래 |
| 3 | Dua Lipa | Dance The Night | dance pop | dance pop과 겹침 0 | 아래 |
| 4 | Doja Cat | Paint The Town Red | dance pop | 같은 겹침 0 | 아래 |
| 5 | Future | WAIT FOR U | trap | trap과 겹침 0 | 아래 |
| 6 | Lil Peep | Star Shopping | emo rap | emo rap과 겹침 0 | 쓰지 않음 |
| 7 | blink-182 | All The Small Things | pop punk | pop punk와 겹침 0 | 쓰지 않음 |
| 8 | Olivia Rodrigo | vampire | pop | 아티스트가 alt z 248명에 없다 | 쓰지 않음 |
| 9 | Conan Gray | Heather | bedroom pop 경계 | 2021-05 캡처에는 alt z, 2023 데이터에는 없다 | 위 |
| 10 | girl in red | we fell in love in october | bedroom pop / indie pop | bedroom pop 겹침 4/142 · indie pop 겹침 9/110 | 위 |
| 11 | Clairo | Sofia | bedroom pop / indie pop | 같은 장르 겹침 | 위 |
| 12 | Isabel LaRosa | older | hyperpop | hyperpop 겹침 1/211 | 아래 |

- 🔺 **Conan Gray는 경계 사례다.** 명명자의 체계가 2021-05에는 이 아티스트를 alt z에 넣었다. 음성으로 쓰되, 매치되면 그 사실을 따로 적는다(판정 수는 그대로 센다).
- 🔺 girl in red · Clairo가 겹침 4명 · 9명 안에 드는지는 조사 노트에 없다. 이 둘은 「alt z 아님」의 근거가 가장 약하다.

### 2.3 분할 (측정 전에 고정)

규칙: 양성 28곡을 (아티스트 casefold, 곡명 casefold)로 정렬한다. 홀수 번째(1, 3, 5, ...)는 **탐색**, 짝수 번째는 **홀드아웃**이다. 음성 12곡은 전부 홀드아웃에만 쓴다.

- **탐색 14곡**: Alec Benjamin 「Let Me Down Slowly」 · Ashnikko 「Daisy」 · Bea Miller 「feel something」 · Charlotte Lawrence 「Joke's On You」 · FINNEAS 「Let's Fall in Love for the Night」 · gnash 「i hate u, i love u」 · Holly Humberstone 「Paint My Bedroom Black」 · Lauren Spencer Smith 「Fingers Crossed」 · Maggie Lindemann 「Pretty Girl (Cheat Codes X CADE Remix)」 · Melanie Martinez 「Pacify Her」 · Olivia O'Brien 「hate u love u」 · Rosa Linn 「SNAP」 · Sody, Cavetown 「is your bedroom ceiling bored?」 · UPSAHL 「Drugs」
- **홀드아웃 양성 14곡**: Ashe 「Moral of the Story」 · Au/Ra 「Panic Room」 · BENEE 「Supalonely」 · Em Beihold 「Numb Little Bug」 · FLETCHER 「Bitter」 · Gracie Abrams 「I miss you, I'm sorry」 · Jeremy Zucker 「comethru」 · Lizzy McAlpine 「ceilings」 · Maisie Peters 「Psycho」 · mxmtoon 「prom dress」 · Penelope Scott 「Rät」 · Sasha Sloan 「Dancing With Your Ghost」 · Tate McRae 「greedy」 · Zolita 「Shut Up and Cry」
- **홀드아웃 음성 12곡**: §2.2 전부.

## 3. 사전 등록 (⚠ **측정 전에 고정** · 값은 A&R 조정 가능)

### 3.1 기준 분포

dreamcore(D-064 §3)와 같다. 정답지 곡의 백분위는 `data/live/sonic` 일일 스냅샷 2026-07-28 ~ 최신의 **KR 차트 코호트 녹음 전체**(`source:track_id`로 중복 제거, 가장 최근 관측값)를 모집단으로 잰다. 「최신」은 탐색 단계를 실행할 때 있는 마지막 스냅샷이고, 홀드아웃 단계도 **같은 창**을 쓴다(창 끝 날짜는 `discover.json`에 적는다). 일일 베이스라인(기준 ③)은 모듈과 같이 **그날 코호트 안 백분위**로 재고, 해석된 차트 곡이 **30곡 미만인 날은 제외**한다. 백분위 정의는 모듈의 `_percentile`(이하 비율)이다. `organic_ratio`는 스냅샷에 없어 sonic-profile `derive_all`로 다시 계산한다(RULES §3).

### 3.2 후보 축 (이 커밋의 `cli.py` `AXIS_LABELS` 9축, 이 순서)

| 순서 | 축 | 화면 표기 |
|---|---|---|
| 1 | `organic_ratio` | 유기음 비율 |
| 2 | `spectral_flatness` | 스펙트럼 평탄도 |
| 3 | `over_unity_ratio` | 인터샘플 피크 비율 |
| 4 | `onset_rate_high` | 고역 온셋 밀도 |
| 5 | `silence_ratio` | 무음 비율 |
| 6 | `swing_ratio` | 스윙 비율 |
| 7 | `tempo_bpm` | 템포 |
| 8 | `brightness_hz` | 음색 밝기 |
| 9 | `spectral_contrast_mean` | 스펙트럼 대비 |

이 9축 밖의 특질(타격감 · 온셋 밀도 등)은 이번에 보지 않는다. 더 넓게 고르면 14곡에서 우연히 걸리는 축이 늘어난다.

### 3.3 탐색 규칙 (탐색 14곡에만 적용)

1. 축마다 측정된 탐색 양성의 백분위를 잰다. 하위 꼬리 = 백분위 ≤ 20, 상위 꼬리 = 백분위 ≥ 80 (공유 P_low · P_high 기본값).
2. **같은 꼬리에 측정된 탐색 양성이 10곡 이상**이면 그 축은 자격이 있고, 방향은 그 꼬리다. 10은 절대 수다. 측정된 탐색 양성이 10곡 미만이면 어떤 축도 자격이 없다.
3. 자격 있는 축이 3개를 넘으면 같은 꼬리 곡 수가 많은 3개만 남긴다. 동수는 §3.2의 순서가 앞선 축을 남긴다.
4. **후보 규칙**: 남긴 축마다 그 축의 꼬리에 있는 곡(축마다 자기 방향, 전부 AND).
5. 자격 있는 축이 없으면 결과는 **「판별 축 없음」**이다. 이것도 유효한 결과다. 뜻은 「alt z는 청취자가 정의한 묶음이고, 이 9축에서 소리 서명으로 드러나지 않는다」이다. 이때는 홀드아웃 규칙 검정을 하지 않는다(H-map과 코호트 기록은 한다).
6. 고른 축은 **홀드아웃을 재기 전에** 이 문서 §6과 RULES §2.1.5에 적어 따로 커밋한다.

### 3.4 홀드아웃 판정 기준 (dreamcore D-064 §3과 같은 넷)

넷 다 통과해야 등재다.

| # | 기준 | 정의 | 기본값 |
|---|---|---|---|
| ① | 적중률 | 측정된 홀드아웃 양성 중 후보 규칙 매치 비율 | **≥ 60%**, 측정 홀드아웃 양성 **≥ 10곡** |
| ② | 오탐률 | 측정된 음성 중 매치 비율 | **≤ 10%**, 측정 음성 **≥ 10곡** |
| ③ | 코호트 베이스라인 | KR 일일 코호트에서 매치된 곡-일 / 평가된 곡-일 (그날 코호트 안 백분위, §3.1) | **≤ 15%** |
| ④ | 출처 등급 | 등급 `중간` 이상인 **측정** 홀드아웃 양성 수 | **≥ 10곡** |

- 양성은 전부 `높음`이라 ④는 「측정된 홀드아웃 양성 ≥ 10곡」과 같다. 즉 홀드아웃 양성 14곡 중 측정 실패가 5곡 이상이면 ①과 ④가 함께 실패한다.
- 측정 실패(프리뷰 없음 · 검증 실패)는 **결측**이다. 0으로 세지 않는다.
- 기준을 결과를 보고 옮기지 않는다. 미달이면 미달이다.

### 3.5 출처 지도 예측 H-map (보고만 · 규칙에 쓰지 않음)

근거: Every Noise 지도의 세로축 문구 "down is more organic, up is more mechanical and electric"와 alt z의 세로 위치(위에서 42%, pop · k-pop · hyperpop · electropop보다 organic 쪽, bedroom pop · indie pop · gen z singer-songwriter보다 mechanical 쪽). 명명자 단서 "The calibration is fuzzy". 등급 `중간`.

예측 (둘 다 맞아야 「지지」):

1. 측정된 양성 **28곡 전체**의 `organic_ratio` 중앙값 **>** 측정된 음성 「아래」 묶음(NewJeans · Jung Kook · Dua Lipa · Doja Cat · Future · Isabel LaRosa)의 중앙값.
2. 같은 양성 중앙값 **<** 측정된 음성 「위」 묶음(girl in red · Clairo · Conan Gray)의 중앙값.

- 값은 `organic_ratio` 원값의 `statistics.median`이다. 기준 분포 백분위는 함께 적기만 한다.
- 어느 묶음이든 측정된 곡이 0이면 그 비교는 「판정 불가」다.
- 지도 축은 Every Noise 자체 특질로 만든 좌표이고 `organic_ratio`는 이 저장소 태거의 악기 질량 비율이다. 같은 낱말이 같은 양을 재는지는 모른다. H-map이 틀려도 지도가 틀렸다는 뜻이 아니다.

### 3.6 보조 기록 (판정에 쓰지 않음)

- 양성의 발매연도(측정 메타데이터 `release_date`, Apple만 있음)를 기록한다. 연도가 몰려 있으면 녹음 시대가 축 값에 섞일 수 있다(dreamcore §7 관측 2).
- 탐색에서 자격을 얻지 못한 축도 9축 전부의 꼬리 곡 수를 `discover.json`에 남긴다.

## 4. 측정 절차 (sonic-profile RULES §1 준수 · dreamcore와 같음)

- 도구: [`../scripts/dreamcore_sheet_fetch.py`](../scripts/dreamcore_sheet_fetch.py)를 정답지 폴더를 받도록 일반화해 쓴다. sonic-profile의 `_apple`(스토어프런트 KR → US → GB) · `_deezer`(Deezer 폴백) · `features_from_preview`를 그대로 불러 쓴다. 새 측정 코드는 없다.
- 검증: **아티스트 별칭 일치 AND 곡명 핵심 일치** 둘 다, 그리고 시트에 없는 괄호 한정어가 있으면 다른 녹음으로 본다(D-064에서 더한 조건). 별칭은 시트 줄에 적힌 이름과 한국 두 팀의 한글 이름뿐이다.
- 저빈도(요청 간 1초) · 오디오 무보관 · 최대 40곡(이번 40곡).
- 산출: `data/research/genre-impulse/altz/`(`sheet_features.json` · `discover.json` · `verify.json`). `data/live`에는 쓰지 않는다.

## 5. 출처 수집 기록 · 조사 한계

- 출처: 기획 저장소 세션의 1차 조사 노트(2026-10-24). 원문은 기획 세션 스크래치에만 두고 이 저장소에 재배포하지 않는다(AGENTS §5).
- archive.org는 curl CDX로 조회했다. Every Noise `lookup.cgi`는 403. 2023-12 이후 플레이리스트 캡처는 빈 셸이다.
- **읽지 못한 것**: Billboard(robots로 조회 안 함) · Pitchfork · Guardian · NYT · Vulture(검색 차단) · Rolling Stone(tollbit) · MBW(403) · NME · FADER(0건). McDonald 책 원문 미확인.
- 지도 순서 · 플레이리스트 순서의 기준은 확인하지 못했다. 겹침 수 · 좌표 순위는 조사자 계산이다.
- Wrapped 노출은 인터뷰어 증언 1건(`중간`)뿐이다.

## 6. 탐색 결과 (2026-10-24 · 홀드아웃 백분위를 계산하기 전에 고정)

수치 원본: [`../data/research/genre-impulse/altz/discover.json`](../data/research/genre-impulse/altz/discover.json) · 특질: `sheet_features.json` (같은 폴더).

**해석 38/40.** Apple US 33 · Deezer 5(Ashnikko 「Daisy」 · FINNEAS 「Let's Fall in Love for the Night」 · Penelope Scott 「Rät」 · Zolita 「Shut Up and Cry」 · Lil Peep 「Star Shopping」) · Apple KR 0. **측정 실패 2곡**: Sasha Sloan 「Dancing With Your Ghost」(홀드아웃 양성) · Jung Kook 「Seven」(음성). 둘 다 「아티스트 별칭 AND 곡명 핵심 · 괄호 한정어」 검증을 통과한 프리뷰가 없었다. 결측으로 두고 0으로 세지 않는다. 그래서 홀드아웃 양성은 측정 13곡, 음성은 측정 11곡이 상한이다.

**정체성 주의 1건 (판정 전 기록, 교정하지 않음)**: Ashe 「Moral of the Story」가 Apple 「Moral of the Story (feat. Niall Horan)」으로 풀렸다. 검증은 feat 표기를 한정어로 보지 않으므로(gnash · BENEE · Future도 feat 표기로 풀렸다) 규칙상 통과다. Every Noise 예시곡이 어느 녹음을 가리켰는지는 조사 노트에 없어 바꾸지 않는다. 홀드아웃 결과에서 이 곡을 따로 적는다.

**기준 분포**: 스냅샷 86개(2026-07-28 ~ 2026-10-23)의 KR 차트 녹음 **239개**(중복 제거). 홀드아웃 단계도 이 창을 쓴다.

**탐색 14/14 측정.** 축별 같은 꼬리 곡 수 (자격 = 10곡 이상):

| 순서 | 축 | 하위 ≤ 20 | 상위 ≥ 80 | 중앙 백분위 | 자격 |
|---|---|---|---|---|---|
| 1 | `organic_ratio` | 0 | 3 | 63.8 | ✗ |
| 2 | `spectral_flatness` | 9 | 1 | 12.7 | ✗ |
| 3 | `over_unity_ratio` | 7 | 0 | 20.7 | ✗ |
| 4 | `onset_rate_high` | 7 | 1 | 19.9 | ✗ |
| 5 | `silence_ratio` | 0 | **14** | 95.4 | **✓ 상위** |
| 6 | `swing_ratio` | 1 | 5 | 51.7 | ✗ |
| 7 | `tempo_bpm` | 3 | 2 | 39.8 | ✗ |
| 8 | `brightness_hz` | 9 | 1 | 14.6 | ✗ |
| 9 | `spectral_contrast_mean` | 1 | 4 | 70.1 | ✗ |

**고정한 후보 규칙**: `silence_ratio` 백분위 ≥ **P_high**(80). 1축이다. 홀드아웃은 이 규칙으로만 판정한다(§3.4).

🔺 **판정 전에 적어 두는 관측 (해석은 A&R 몫)**: 기준 분포에서 `silence_ratio`가 값을 가진 237곡 중 0인 곡이 95.4%다(최대 0.0386). 백분위 정의가 「이하 비율」이라 값이 0인 곡은 모두 **P95.4**를 받는다. 탐색 양성 14곡 중 11곡이 정확히 P95.4(값 0)이고, 0보다 큰 3곡(Ashnikko P96.6 · FINNEAS P96.2 · Rosa Linn P97.9)도 상위 꼬리다. 같은 연구 경로로 잰 dreamcore 음성(K-pop 11곡)도 이 기준 분포에 넣으면 11곡 모두 P95.4 이상이다. 즉 이 축의 상위 꼬리는 「무음이 많다」가 아니라 「무음이 없다」를 담고 있을 수 있다. 규칙은 사전 등록대로 고정하고, 오탐률(②)과 코호트 베이스라인(③)이 이 동값 문제를 판정한다. 탐색 규칙이나 백분위 정의를 지금 바꾸지 않는다.

탐색 양성의 발매연도(Apple 12곡): 2015 1 · 2016 3 · 2018 1 · 2019 2 · 2020 2 · 2022 2 · 2023 1. Deezer 2곡은 발매일이 없다.

## 7. 홀드아웃 결과와 판정

(측정 후 채운다)
