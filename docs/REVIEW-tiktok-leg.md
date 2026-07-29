# REVIEW — 틱톡/숏폼 레그 검토 보고 (D-034 ④ · 승인 전 검토 · 2026-07-30)

> 지출·계정 생성·API 신청 없이 조사만 수행. 가격은 Apify BRONZE 티어 표시가 기준 **추정**(±50%). 채택 여부·비용 상한·ToS 수용은 도메인 소유자 건별 확인 대상(§건별 확인).

## 핵심 발견 2건

1. **Billboard TikTok Top 50은 2025-03-07자로 중단**(18개월 운영 후) — 신호 ③(미국 바이럴 차트)의 1순위 후보가 라이브 소스로는 소멸. 소급 아카이브(위키)로만 유효 ([Wikipedia](https://en.wikipedia.org/wiki/TikTok_Billboard_Top_50)).
2. **TikTok Research API는 상업 사용 금지 + 지역 요건**(미국·EEA·영국·스위스·브라질의 학술/비영리) — 한국 상업 A&R은 이중 부적격 ([자격](https://developers.tiktok.com/products/research-api/), [ToS](https://www.tiktok.com/legal/page/global/terms-of-service-research-api/en)).

## 경로 비교표

| 경로 | 얻는 신호 | 비용/월(추정) | ToS 위험 | 안정성 | 판정 |
|---|---|---|---|---|---|
| A. TikTok Research API | 원데이터 | $0 | 없음 | — | **탈락**(상업 금지+지역) |
| B. Billboard TikTok Top 50 | 미국 바이럴 주간 | $0 | 낮음(위키 아카이브) | — | **소급 전용**(2023-09~2025-03 리드타임 검증용) |
| C. Creative Center 수동 확인 | 국가별 트렌딩 사운드·해시태그 | $0(인건 주1회) | 없음 | 사람 의존 | **보조 채택**(시계열 축적 불가) |
| D. Creative Center 스크랩 (Apify [burbn](https://apify.com/burbn/tiktok-trending-sounds)·[akash9078](https://apify.com/akash9078/tiktok-trending-hashtags-scraper)·[clockworks/ads](https://apify.com/clockworks/tiktok-ads-scraper), $0.005/결과) | 신호 ②·③ 대체(24+개국) | 주간 ~$2 / 일간 ~$30 | 중간(비로그인 공개·수치만) | 99%+ | 1안 후보 |
| E. 사운드 사용량 스크랩 (Apify [apidojo](https://apify.com/apidojo/tiktok-music-scraper) $0.003/쿼리 ★4.78·338명 / [khadinakbar](https://apify.com/khadinakbar/tiktok-sound-scraper) 17명뿐) | **신호 ①: 사운드별 사용 동영상 수 시계열** | 50개 일1회 ~$4.5 | 중간 | 88~98%·규모 작음 | 1안 후보 — **스모크 선행 필수** |
| F. 해시태그 스크랩 (Apify [clockworks](https://apify.com/clockworks/tiktok-hashtag-scraper) ★4.88·15,737명) | 신호 ②: 해시태그 누적 조회수 성장률 | 20태그 일1회 ~$1.2 | 중간 | 99.8% | 1안 후보(최대 규모 개발사) |
| G. 무료 대리 신호 (B 소급+C 수동+기존 YouTube 레일) | ③소급+②주간+KR 후행 | $0 | 낮음 | 사람 의존 | 2안 |

**비용 종합(추정)**: 1안(E+F+D 주간) = **월 $8~12** ≈ 현 소셜 레그(월 ~$90)의 1/8~1/11.

## 권고안

- **1안 — Apify 3액터 최소 구성(월 $8~12, 권고)**: 사운드 워치리스트 50개 일 1회(E) + 장르 해시태그 20개 일 1회(F) + Creative Center US·KR 주 1회(D) + 위키 아카이브 소급(B). 기존 Apify 레일 재사용, 오디오/영상 미수집·수치 메타데이터만. **포기**: TikTok ToS(자동 수집 서면 허가 필요 조항) 잔류 위험 수용 — 비로그인 공개·수치 한정이라 실질 위험은 차단/불안정 쪽이라 판단하나, **수용 여부는 도메인 소유자 몫**.
- **2안 — 무지출(월 $0)**: 위키 소급 + Creative Center 수동 주간. **포기**: 핵심 신호 ①(사운드 사용량 시계열) 전부 — 이중 기준선의 권고 목표(바이럴 층 12~34개월 선행) 달성 불가.

## 건별 확인 필요 (도메인 소유자)

1. **비용 상한** — 제안: 월 $15(현 소셜 레그와 별도 계상), 초과 시 밀도 하향(일→주) 규칙.
2. **ToS 수용** — TikTok 자동 수집 금지 조항 인지 하에 "비로그인 공개·수치 메타데이터 한정" 수용 여부. (써클차트 배제와의 차이: 써클은 TDM 금지 명시 국내 사업자 — 관할·실질 위험 상이)
3. **계정** — 기존 Apify 계정 재사용 vs 분리.
4. **워치리스트 소유** — 사운드 50·해시태그 20의 선정·갱신 주체(근원 소스 깊이 원칙: 팬덤 은어 포함 여부).
5. **소액 스모크** — E 액터 출력 스키마 실검증용 ~$1 미만 지출 승인.

## ✅ 스모크 결과 (2026-07-30 · D-035 ① 승인분 · 총 ~$0.01)

- **`khadinakbar/tiktok-sound-scraper` 채택 확정 근거 확보**: 출력 스키마에 `userCount` 실재, 대형 사운드 실측 — Kendrick Lamar "luther" 음원 페이지 → **userCount 1,427,352** 반환(3.8초). 검색 경로("jersey club" 쿼리)도 작동(무명 사운드 2건, userCount 10 — 실제값). 부가 필드: `isCommerceMusic`·`createdAt`·`themeTags`.
- **설계 함의**: ① 워치리스트는 **music URL/clipId 기반**으로 구축(검색 경로는 발견용) ② `outputMode=sounds`+`maxVideosPerSound=0`이면 사운드당 $0.003 — 50개 일 1회 = **월 ~$4.5**(추정 유지) ③ apidojo 액터는 출력이 포스트 단위뿐이라 신호 ①에는 **부적합 확정**(스키마 실측) — 후보에서 제외.
- ⚠ 소규모 액터(사용자 17명) 중단 위험은 잔존 — 수집 스크립트에 액터 교체 가능한 구조로.

## 한계·불확실성

- ~~신호 ① 추정~~ → ✅ 위 스모크로 실증됨.
- Apify 가격 수시 변경(±50%) · TikTok 스크랩 방지 능동 강화 중 — 성공률은 과거치.
- 한국 저작권법 TDM 면책 부재(계류) — 수치 메타데이터는 사실 정보라 쟁점이 얇다고 보나 **법률 자문 아님**.
- Creative Center 순위 산식 불투명(광고주용 큐레이션) · burbn 액터의 KR 포함 여부 미확인.
