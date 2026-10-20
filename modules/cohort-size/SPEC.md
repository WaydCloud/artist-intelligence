# cohort-size · SPEC (무엇을 만드나)

> 모듈 하네스의 "무엇을/UX/완료조건". 기준 원장은 [`RULES.md`](RULES.md), 수용조건은 [`TESTS.md`](TESTS.md).
> 근거: [`../../docs/DECISIONS.md`](../../docs/DECISIONS.md) **D-063**(척도 넷 · 창 3년 · 멜론 · 써클 예외) · 바닥전제: [`../../DOMAIN.md`](../../DOMAIN.md) §0.

## 한 줄

걸그룹의 **데뷔 인원 구간별 성공 비율**(k/n · 95% 신뢰구간)과 그 차이에 대한 **검정**을, 전체와 **데뷔 시기별로** 낸다. 답의 형식은 증거다: *"이 표본에서 인원과 성공 사이 관계를 찾지 못했다, 있더라도 크라메르 V ≤ x 수준"* 또는 *"관계 신호가 있다, V = x [구간]"*. "인원은 상관없다" 같은 평결은 내지 않는다.

## 왜

신인 걸그룹 기획에서 인원 수는 초기에 정하는 구조 결정이다. 업계 통념(5인조가 표준이다, 대인원이 유리하다 등)을 지난 데뷔 코호트의 실측으로 점검할 수 있게 한다. 판단은 A&R의 몫이다.

## 입력 / 출력

- **입력**: `data/research/cohort-size/facts.json`(커밋된 사실 픽스처). 그룹(데뷔 연도 · 제목 · 이름 · 한글 이름 · 데뷔 인원 또는 범위 · 판정 근거 · 유닛 여부)과 그룹별 성공 기록(음방 1위의 프로그램 · 연도, 멜론 · 써클의 연도 · 순위 · 표기, Spotify 순위)만 담는다.
  - 픽스처는 `build`가 기획 저장소의 RAW 캡처에서 한 번 만든다(손으로 돌림, CI 아님). 출처 id는 D-063과 [`../../DATA_SOURCES.md`](../../DATA_SOURCES.md) 끝 절.
- **출력**: `output/report.json`(공유 report-schema, 무변경) → 대시보드 탭. `output/analysis.json`(모든 표와 검정 값, 화면 수치를 되짚는 용도).

```
PYTHONPATH=modules/cohort-size/src python -m cohort_size build <기획저장소>/data/references --check-sizes <기획저장소>/docs/research/2026-10-18-debut-size/sizes.csv
PYTHONPATH=modules/cohort-size/src python -m cohort_size analyze -o modules/cohort-size/output/
PYTHONPATH=modules/cohort-size/src python -m cohort_size selftest
```

## 핵심 산출 (정의는 RULES §2 원장)

1. **구간별 성공 비율**: 척도(종합 · 음방 1위 · 멜론 · 써클)마다 인원 구간(기본 3명 이하 · 4 · 5 · 6 · 7명 이상)의 k/n · 비율 · 윌슨 95% 구간.
2. **검정**: 카이제곱 독립성(p는 표준 라이브러리로 구현한 카이제곱 생존함수) · 피셔-프리먼-홀턴 정확검정(몬테카를로) · 크라메르 V + 부트스트랩 구간 · 코크란-아미티지 추세. 기대 빈도 5 미만 칸 수를 함께 낸다.
3. **흐름**: ① 데뷔 시기(2012 ~ 14 · 2015 ~ 17 · 2018 ~ 20 · 2021 ~ 23, 2024는 창 미완으로 따로)별 같은 표와 검정 + 홀름 보정 ② 시기별 성공 팀과 전체 팀의 인원 분포(중앙값 · 5인조 비율).
4. **민감도**: 인원 미판정 팀을 상한(현재 + 전 멤버)으로 넣은 변형, 유닛 · 프로젝트 그룹을 넣은 변형. 결론이 움직이는지 화면에서 보인다.

## UX (대시보드 뷰) · 시각화 계약 채택 (D-041 · D-042 · D-043)

- **진입부**: 질문 4개(R1) · 답하지 않는 질문(R7) · 요약 도형 하나(R2) = `any-by-size`(종합 성공 비율, 구간별 막대, 이름에 k/n과 구간).
- **구획 3개**:

  | 구획 | 질문 | 차트 | 지표 |
  |---|---|---|---|
  | `size` 인원 | 인원에 따라 성공률이 다른가? | `measure-by-size` · `tests-by-population` · `spotify-by-size` | 분석한 팀 · 종합 성공 · 정확검정 p · 크라메르 V · 추세 p · 카이제곱 p |
  | `era` 시기 | 데뷔 시기마다 달랐나? | `era-by-size` · `era-tests` | 없음 |
  | `who` 성공한 팀 | 성공한 팀은 몇 명이었나? | `size-share` · `era-median` · `era-focus` | 성공한 팀 중앙 인원 · 전체 중앙 인원 |

- k/n은 막대 이름에 **텍스트로** 찍는다(길이만으로 말하지 않는다). 팀이 없는 구간은 줄을 뺀다(0 길이가 0%로 읽히지 않게).
- 시기별 검정은 종합 기준만 화면에 낸다. 척도별 시기 검정은 `analysis.json`에 있다(구획당 차트 상한 3).

## 완료 정의 (Definition of Done) · v0.1

- [x] 픽스처 → 스키마 유효 `report.json`(smoke)
- [x] 결정성: 같은 픽스처 → 같은 산출(`generatedAt` 제외). 난수는 고정 시드
- [x] 기준 원장: 하중 기준 전부 RULES §2 + CLI 노출
- [x] 정직성(§0): 평결 어휘 0 · 표본 · 결측 · 3차 출처 · 창 미완 · 생존 편향을 신뢰도 라인과 인사이트에 병기
- [x] `lint`(ruff) · `typecheck`(pyright) · `selftest` · `validate_report_data.py` 통과
- [ ] 사용자 E2E: 탭을 직접 열어 판정(이 세션에서 미검증)

## 범위 밖

- 인과("인원이 성공을 만든다") · 성공 예측 · 기획사 규모 등 교란 통제 · 보이그룹 · 솔로.
- 일일 수집 · 발행 스크립트 편입(정적 1회 분석이다).
- 별칭(인포박스 `other` · `formerly`) 대조: 기본 꺼짐이며 v0.1에 구현하지 않았다(RULES §2.4 한계).
