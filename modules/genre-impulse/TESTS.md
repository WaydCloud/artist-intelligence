# genre-impulse · TESTS (수용 조건)

> smoke는 네트워크 0, 커밋 픽스처만. `PYTHONPATH=modules/genre-impulse/src python -m genre_impulse selftest`.

## §1. 핵심 흐름

1. **스키마 유효**: 픽스처(합성 sonic 스냅샷 + 원장 픽스처 2건 — 규칙 있는 것 1·없는 것 1) → `report.json`이 report-schema 검증 통과.
2. **결정성**: 같은 픽스처 2회 실행 → `generatedAt` 제외 동일 산출.
3. **빈 입력 graceful**: 코호트 0곡 / 원장 0건 / 규칙 0건 각각에서 죽지 않고 insights에 명시.

## §2. 원장 로드

4. 스키마 위반 임펄스 레코드 → 스킵 + insights 보고(조용한 무시 금지).
5. 확실성 등급 병기: 리포트에 인용된 원장 사실에 등급 문자열이 붙는다. **중간 미만 등급은 표면에 없다.**

## §3. 검출 규칙 (hyperpop-texture)

6. **양성**: organic_ratio 최하위 + spectral_flatness 최상위인 합성 트랙을 코호트에 심으면 매치된다.
7. **음성**: 전 축 중앙인 트랙은 매치되지 않는다.
8. **임계 재계산**: `--low-pct 1 --high-pct 99`로 좁히면 매치 0이 된다(튜너 배선 검증).
9. **백분위 정의 고정**: n=1 코호트에서 백분위 계산이 죽지 않는다. 동값(tie)은 `이하 비율` 정의로 결정적.
10. **falsy 함정**: `organic_ratio == 0.0`인 트랙이 "값 없음"으로 오분류되지 않는다(D-032가 기록한 `0.0 or 기본값` 함정 회귀).

## §4. 정직성

11. 단정 어휘 가드: report.json 직렬화 문자열에 "차트인할" · "뜰 것" · "데뷔감" 이 없다.
12. 커버리지 KPI: metrics에 `규칙 확정 n/원장 전체 N`이 존재한다.
13. 유사≠도달: insights 최상단에 비교 모집단 근사·유사≠도달 병기가 존재한다.
