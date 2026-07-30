# DRAFT — 틱톡 워치리스트 v0 (D-035 ① · 초안 엔지니어 → **확정 A&R**)

> 작성 2026-07-30 · Apify 미실행(웹 검색만) · 수집 규격: `tiktok.com/music/<slug>-<clipId>`의 `userCount` 일별 시계열(사운드당 $0.003).
> **URL 검증 완료 10건 / url_pending 30건** — pending은 첫 수집 시 액터 검색 모드(제목+아티스트)로 clipId 자동 확정 → 이후 고정 수집.

## 사운드 (40건 / 50슬롯)

| # | 분류 | 곡 - 아티스트 | URL/clipId | 선정 근거 | 출처 |
|---|---|---|---|---|---|
| 1 | 임펄스(아마피아노) | Tshwala Bam - TitoM & Yuppe | `music/Tshwala-Bam-feat-SNE-EeQue-7325020516120529670` ✓ | 글로벌 바이럴 앵커(2.8M 크리에이트) — 곡선 상단 캘리브레이션 | Wikipedia |
| 2 | 임펄스(아마피아노) | PUSH 2 START - Tyla | `music/PUSH-2-START-7424363919676131344` ✓ | 1.5M 비디오·2025 VMA — Tyla 라인 현행 앵커 | Wikipedia |
| 3 | 임펄스(아마피아노) | CHANEL - Tyla | url_pending | 2026 신곡, 자체 안무 챌린지 진행 중 | Capital FM |
| 4 | 임펄스(아마피아노) | THAT GIRL - Tyla | url_pending | 신보 리드 싱글 — TikTok 인앱 프로모션(플랫폼 공식 푸시) | allAfrica |
| 5 | 임펄스(아마피아노) | Mnike - Tyler ICU 외 | url_pending | 2023 확산 1세대 앵커 — 성숙기 곡선 기준선 | OloriSuperGal |
| 6 | 임펄스(아마피아노) | Khanya Njalo - Kabza De Small | url_pending | Kabza 계열 2026 현행 | OkayAfrica |
| 7 | 임펄스(아마피아노) | Fada Xmas Akekho - Tyler ICU 외 | url_pending | 2026 발원지 히트 | OkayAfrica |
| 8 | 임펄스(아마피아노) | The Boy Is Mine - DBN GOGO | url_pending | 발원지 여성 DJ 라인 현행(Uncle Waffles 계열 대체) | OkayAfrica |
| 9 | 임펄스(저지클럽) | Players (DJ Smallz 732 Remix) - Coi Leray | `music/Players-DJ-Smallz-732-Jersey-Club-Remix-7174933863339952129` ✓ | 저지클럽 최대 바이럴 앵커(1.5M 크리에이트) | ABC Audio |
| 10 | 임펄스(저지클럽) | MOVE YA FEET (DJ Smallz 732 Remix) | `music/MOVE-YA-FEET-DJ-Smallz-732-Jersey-Club-Remix-7217197138160667438` ✓ | 리믹스류 현행 표본 | TikTok |
| 11 | 임펄스(저지클럽) | New Opp (DJ Smallz 732 Remix) - Sha Gz | `music/New-Opp-DJ-Smallz-732-Jersey-Club-Remix-7211528157675915265` ✓ | 드릴×저지클럽 크로스오버 — 요소 결합 감시 | TikTok |
| 12 | 임펄스(UKG) | Illegal - PinkPantheress | clipId `7502057134566525713` ✓ | 1M+ 비디오 핸드셰이크 트렌드 | Creative Center |
| 13 | 임펄스(UKG) | Girl Like Me - PinkPantheress | url_pending | Fancy That 싱글(2026-04) | Wikipedia |
| 14 | 임펄스(UKG) | The Bridge - Kelela & PinkPantheress | url_pending | 2026-07 퓨처 개러지/2-step — R&B 접합 확장 | Stereogum |
| 15 | 임펄스(정글/DnB) | Get Me Down - Nia Archives (feat. Jorja Smith) | url_pending | 신보(2026-07-17) — 정글 리바이벌 현행 선두 | DUBIKS |
| 16 | 임펄스(브라질 펑크) | Passo Bem Solto - ATLXS | url_pending | 브라질리언 폰크 글로벌 대표 | Wikipedia |
| 17 | 임펄스(브라질 펑크) | Montagem Na Mira | url_pending ⚠ | 몬타젬 현행 — 파생 클립 분산, 계측 규칙 필요 | TikTok |
| 18 | 임펄스(브라질 펑크) | Montagem Pegadora | url_pending ⚠ | 동상 | TikTok |
| 19 | 임펄스(아프로비츠) | Who's Dat Girl - Ayra Starr feat. Rema | url_pending | 2025-10, 복수 댄스 챌린지 파생 | Wikipedia |
| 20 | 임펄스(아프로비츠) | Where Do We Go - Ayra Starr | url_pending | 2026-03 현행 | Wikipedia |
| 21 | 부상(3-step) | Thukzin 대표 트랙(**곡 미확정**) | url_pending ⚠ | 아마피아노 후신 서브장르 선두 | Music Custodian |
| 22 | 부상(3-step) | MaWhoo 대표 트랙(**곡 미확정**) | url_pending ⚠ | 3-step 하이브리드 보컬 대표 | Zkhiphani |
| 23 | 부상(트랩홀) | WYFL - Skippa | url_pending | "Traphall" 웨이브 선두 | Caribbean E Mag |
| 24 | 부상(트랩홀) | Designa - Ayetian | url_pending | 트랩홀 국제 확산 | Caribbean E Mag |
| 25 | 부상(댄스홀) | Passport Princess (**아티스트 표기 상충** ⚠) | url_pending | 댄스홀 리바이벌 현행 | DancehallFlex |
| 26 | 부상(rage/opium) | Ken Carson Project X 대표 트랙(**곡 미확정**) | url_pending ⚠ | rage 계열 2026 신작 | Wikipedia |
| 27 | 부상(pluggnb) | pluggnb 대표 트랙(**곡 미확정**) | url_pending ⚠ | 부상 보도 — 곡 선정은 A&R와 | HypeNation |
| 28 | 부상(역방향) | Dracula (JENNIE Remix) - Tame Impala | url_pending | K-pop 아티스트가 서구 씬에 얹히는 역방향 표본 | HypeNation |
| 29 | K-pop 감시 | WDA - aespa feat. G-DRAGON | url_pending | 요소 차용 앵커(aespa) 최신 본진 | Soompi |
| 30 | K-pop 감시 | KISS N TELL - aespa | url_pending | 2026-07 일본 타이틀, 하우스 기반 — 요소 감시 | StarNews |
| 31 | K-pop 감시 | Supernova - aespa | `music/Supernova-7363576240010299408` ✓ | 115K+ 비디오 구곡 앵커 — 성숙 곡선 기준선 | TikTok |
| 32 | K-pop 감시 | Heavy Serenade - NMIXX | url_pending | 2026-05 타이틀 — genre-impulse 매치 곡 | allkpop |
| 33 | K-pop 감시 | 캐치 캐치 - YENA | url_pending | **모니터 첫 실행 1위 매치**·Circle 7위 — H4/H5 추적 직결 | CASEBOOK |
| 34 | K-pop 감시 | REDRED - CORTIS | `music/REDRED-7629278086664767505` ✓ | 워치 6팀·매치 곡(206K 비디오) | TikTok |
| 35 | K-pop 감시 | GO! - CORTIS | `music/GO-7535751648782829585` ✓ | 데뷔 타이틀(254.7K) — 신·구 곡선 비교쌍 | TikTok |
| 36 | K-pop 감시 | 404 (New Era) - KiiiKiii | url_pending | 매치 곡 | Wikipedia |
| 37 | K-pop 감시 | DDI RO RI - MEOVV | `music/DDI-RO-RI-7642754081773471760` ✓ | 2026-06 타이틀 | StarNews |
| 38 | K-pop 감시 | Lemon Tang - Hearts2Hearts | url_pending | 2026-06 타이틀, 댄스 트렌드 형성 보도 | Soompi |
| 39 | K-pop 감시 | Pretty Girl - RESCENE | url_pending | KARA 리메이크 — 2세대 소환 노선 감시 | allkpop |
| 40 | K-pop 감시 | OXY - Keyveatz | url_pending | AOMG 데뷔 타이틀 | Soompi |

## 해시태그 (20건)

| # | 태그 | 분류 | 근거 |
|---|---|---|---|
| 1 | #amapiano | 장르(임펄스) | 표준 표기 |
| 2 | #jerseyclub | 장르(임펄스) | 검증 장르 리바운드 감시 |
| 3 | #ukgarage | 장르(임펄스) | #ukg는 일반어 충돌로 배제 |
| 4 | #dnb | 장르(임펄스) | 최대 유통 표기 |
| 5 | #jungle | 장르(임펄스) | ⚠ 일반어 중복 — #junglemusic 대안 검토 |
| 6 | #phonk | 장르(임펄스) | 폰크 상위 태그 |
| 7 | #brazilianphonk | 장르(임펄스) | phonk 하위 분화 분리 계측 |
| 8 | #brazilianfunk | 장르(임펄스) | 파벨라 펑크 영어권 표기 |
| 9 | #montagem | 장르(임펄스) | 파생 분산의 상위 수렴 태그 |
| 10 | #afrobeats | 장르(임펄스) | 표준 표기 |
| 11 | #afrohouse | 장르(부상) | 아마피아노 인접 확산 축 |
| 12 | #3step | 장르(부상) | ⚠ 실사용 여부 첫 수집 시 확인 |
| 13 | #dancehall | 장르(부상) | 리바이벌 상위 태그 |
| 14 | #traphall | 장르(부상) | ⚠ 저볼륨 가능 — 조기 신호 가치 |
| 15 | #pluggnb | 장르(부상) | 씬 내부 표기 |
| 16 | #hyperpop | 장르(감시) | 케이스 9 후속 재활성 감시 |
| 17 | #opiumcore | 장르+미학(부상) | rage/opium 실사용 태그 |
| 18 | #kpopdancechallenge | K-pop 표층 | 챌린지 수렴 태그 — 수용 표층 총량 |
| 19 | #randomplaydance | K-pop 고유 | 오프라인 문화의 틱톡 이식 — 기존 IG 은어와 미중복 |
| 20 | #meovvbody | 그룹 챌린지 | 워치 팀 챌린지 계측 표본 |

## A&R 확정 시 검토 포인트 (8건)

1. **곡 미확정 5건**(#21·22·25·26·27) — 장르 대표성 근거는 있으나 곡 선정은 도메인 판단.
2. **Uncle Waffles 현행 트랙 부재** — 발원지 로컬 소스(Fakaza·Zkhiphani)로 보강 또는 #8로 대체 유지.
3. **몬타젬 파생 분산** — 계측 클립 규칙 필요(제안: 검색 결과 userCount 최대 클립).
4. **KiiiKiii 8월 컴백** — 발매 즉시 타이틀 추가 권고(발매 직후가 성장률 계측 최적).
5. **구곡 앵커 3건**(#1·31·35) 슬롯 유지 여부 — 곡선 기준선 가치로 유지 권고(50슬롯 중 40 사용).
6. **sped-up 파생** 별도 슬롯 여부.
7. **저볼륨 태그**(#3step·#traphall) 실측 0이면 교체 후보: #junglemusic·#baltimoreclub·#gqom.
8. url_pending 30건은 첫 수집 시 액터 검색 모드로 자동 해소.

## 한계

- URL 검증 10/40 — 틱톡 music 페이지의 검색 노출이 낮음. K-pop 신곡은 "공식 음원 vs original sound" 분산 주의.
- **지리 편향**: 검색이 미국 중심 — 발원지(남아공·브라질·자메이카) 최심부는 얕음(근원 소스 깊이 원칙 기준 보강 여지).
- 부상 후보 장르는 보도 1건 수준 — 케이스북 규율상 `미검증`, 교차 검증 전 하중 금지.
- 스니펫 사용량 수치는 캡처 시점 불명 — 기준선은 액터 첫 실측으로 재설정.
- 6~7월 신곡의 초기 userCount 0~수백은 정상(성장률 계측엔 적기).
