# 2026-07-29~30 · 장르 임펄스: 기획(D-033) → 조사(Phase A) → 원장(Phase B) → 모니터 v1(Phase C) 관통

> 한 세션에서 신규 지시가 기획 → 조사 80% → 정형화 → 가동 중인 모듈까지 갔다. 결정 D-033(+보완⑤⑥)·D-034·D-035. [PR #5](https://github.com/WaydCloud/artist-intelligence/pull/5) 커밋 23개.

## 무엇을 했나 (시간순)

1. **기획(D-033)**: 프레임 4결정을 ASK로 받음 — 이중 축 매트릭스(지리×확산) · 임펄스=특질 벡터+장르 라벨 · 기준선=과거 사례 도출 · 미국 외 경로 포함. `docs/PLAN-genre-impulse.md`. "조사 80%"의 운영 정의 = 케이스북 ≥6건(음성 ≥2) 전 구현 금지.
2. **Phase A1 — 케이스북 10건**(`docs/CASEBOOK-genre-impulse.md`): 병렬 리서치 에이전트 9기로 하루에 1차 완료. 종합: **글로벌 차트 확정→한국 주류 시차가 12개월(2016)→2~6개월(2023)로 압축·병렬화**(빌보드는 확증 신호지 조기 신호 아님), 조기 신호 1순위=발원지 숏폼 바이럴 파도(12~34개월 선행), 한국 선행 사례 3건(양방향 관측 필요), 수용 창 13~15개월.
3. **교차 검증**: 약출처 18건 재확인 — 반증 3(AtHeart 귀속 오류 · '이지리스닝' 명명=어도어 2022-07 소개문 기점 · 트로피컬 첫 수용=f(x) 4 Walls 2015-10), 격상 5, 확정 5, 강등 1(EK/수퍼비 근거 사용 금지).
4. **D-033 보완⑤ — 수용 3모드**: 도메인 소유자가 하이퍼팝·드릴을 "요소 차용 모드"로 재정의 — *"요소를 빌린다 → 새 사운드로 정체성 강화"가 명시적 목표 산출물*. 요소 차용 타임라인 조사: 하이퍼팝→Savage(가온 2위)→**aespa '쇠맛' 정체성화**(요소→팬덤 은어→언론 표제화 2024-05), 드릴→**ENHYPEN "Future Perfect"(2022-07) 명시 드릴 타이틀 실존**(1차 "미발견" 뒤집힘)·정체성화 미발생. 가설 H1~H5(H4=요소×세계관 결합, H5=은어의 언론 공식화가 정체성화 지표→fandom-pulse 직결).
5. **D-033 보완⑥ — 확실성 6등급**: 매우 높음~불가능한 수준, 표면은 중간 이상만·등급 병기. 케이스북 전체 재표기(47건). '불가능한 수준' 2건은 전부 부재 증명 — 해제 조건 병기(멜론/가온 원자료).
6. **A2.1 검출 실험**: 정답지(Savage 계보·Future Perfect) 89곡 실측 — **하이퍼팝 텍스처 = organic_ratio↓+flatness↑+over_unity↑ 조합으로 부분 검출 가능**(Savage organic P2.2·Whiplash over_unity P100), brightness는 예측 실패(사전 등록 덕에 정직 기록), **드릴 = 5축 전부 중앙 — 리듬 축 공백 실증**(스템 분리의 정량 근거). 커버리지 공백 6곡(iTunes/Deezer에 원곡 부재 — 커버/노래방만).
7. **Phase B**: `impulse.schema.json` + 임펄스 레코드 10건(`data/research/genre-impulse/impulses/`) 전건 검증 통과. 모드 분포 full 6 · element 3 · in-progress 1.
8. **D-034(ASK 4승인)**: Phase C 착수+PR · 이중 기준선(운영=최소선, 숏폼 승인 시 바이럴 층 상향) · 스템 분리(Demucs) 승인 · 수집망 3종(해외 이력·크레딧 무료, 틱톡 유료 검토).
9. **Phase C v1 — `modules/genre-impulse/`**: SPEC·RULES(검출 규칙 원장 — `hyperpop-texture` 1건, 임계 CLI 노출)·TESTS 먼저 → CLI(analyze·selftest). **selftest 13/13 · ruff·pyright 0 · report-schema 유효. 실데이터 첫 실행 11곡 매치 — 1위 최예나 '캐치 캐치'(케이스북 독립 확인 곡, sanity 통과)**.
10. **D-035(ASK 4확정)**: 틱톡 1안(월 상한 $15·ToS 수용) · 빌보드 GitHub 데이터셋 채택 · **daily_collect 3.7 단계 편입**(파스 검증) · 워치 소유=초안 엔지니어/확정 A&R.
11. **틱톡 스모크(~$0.01)**: `khadinakbar/tiktok-sound-scraper` **userCount 실증**("luther" 1,427,352) — 신호 ① 가용 확정. apidojo는 포스트 단위뿐이라 부적합 확정. 검토 보고 2건: `docs/REVIEW-tiktok-leg.md`(Billboard TikTok 50은 **2025-03 중단** 발견) · `docs/REVIEW-chart-history-sources.md`(Kworb에 빌보드 없음·써클 TDM 금지 유지 실측).
12. **워치리스트 초안 v0**: `docs/DRAFT-tiktok-watchlist-v0.md` — 사운드 40·태그 20, A&R 검토 포인트 8건.

## 함정·교훈 (다음에 밟지 말 것)

- **🔴 av/Smart App Control 사건**: 21:01까지 정상이던 `import av`가 23:29 시스템 전역 차단(App Control, Defender 탐지 없음) → 다음날 새벽 자연 해소(SAC 클라우드 판정 갱신 추정, **원인 미확정 — 재발 감시**). 대응 원칙을 지켰다: 보안 설정 해제·우회 설치·av 버전 교체를 하지 않고 격리·기록·보고. 재발 시 HANDOFF의 보존 기록(해소 선택지 3안) 참조.
- **iTunes 오매칭**: 커버/노래방/일본어판이 조용히 잡힌다(가시나→ALNU, 보라빛 밤→노래방 반주). **query vs resolved 대조 스캔을 fetch 후 반드시 돌릴 것.** 한글 제목 재시도로 5건 구제, 6곡은 원곡 자체가 스토어에 없음.
- **에이전트 조사물의 아티스트 귀속 오류**(AtHeart 사건) — 교차 검증 없이는 하중 금지 규율이 실제로 작동했다.
- **PR #5는 PR #3 위에 스택** — #3 squash 머지 시 리베이스 필요할 수 있음.
- **D-007 한시 예외**: genre-impulse가 `sonic_profile.derived`를 import(RULES §3 문서화) — packages/ 승격은 별도 승인.

## 미결 (다음 세션 재개점은 HANDOFF.md)

- 워치리스트 A&R 확정(검토 포인트 8건) → 틱톡 수집 스크립트(액터 교체 가능 구조·월 상한 $15 가드)
- 빌보드 이력 파이프라인(3자 대조 스모크 → 케이스 궤적·US 코호트 소급)
- 스템 분리 구현(sonic-profile RULES 정의 먼저) · A2 본편 · 동시대 KR 코호트(Wayback 멜론)
- "2021 저지클럽 관측" 실체 인터뷰 · 크레딧 레지스트리 설계 · 다음 sonic 레그 av 재발 확인
