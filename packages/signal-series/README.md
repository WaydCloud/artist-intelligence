# signal-series — 모듈 간 시계열 공유 규격

> **정본 서술**: [`modules/signal-bridge/SPEC.md`](../../modules/signal-bridge/SPEC.md) §"signal-series 데이터 계약".
> 이 패키지는 그 계약의 **기계검증형**(JSON Schema)이다. 여태 문서 관례로만 존재해
> series 픽스처가 어떤 계약으로도 검증되지 않던 구멍(D-030 잔여)을 메운다.

## 세 계약의 자리

| 계약 | 대상 | 검증 |
|---|---|---|
| `snapshot-schema` | 수집물(fetch/collect 산출) | `scripts/validate_snapshot.py` (+PII 게이트) |
| **`signal-series`** | **모듈 간 시계열(`signals` 산출)** | **`scripts/validate_series.py`** |
| `report-schema` | 대시보드 입력(report.json) | CI schema-validate 잡 |

방출: chart-history · fandom-pulse · yt-pulse · sonic-profile의 `signals` 서브커맨드.
소비: signal-bridge(`--social`·`--chart`·`--youtube`).

## 검증

```bash
python scripts/validate_series.py modules/signal-bridge/tests/fixtures/social_series.json
```

스키마가 못 잡는 일관성은 검증기가 마저 검사한다:

- **길이**: 모든 `series` 배열 길이 = `dates` 길이 (어긋나면 조인이 조용히 어긋난다)
- **정렬**: `dates`가 엄격 오름차순
- **키 짝**: `roster`가 `series`의 모든 키를 갖는가

CI `data-contracts` 잡이 `modules/**/tests/fixtures/`의 series 문서(구조로 식별:
`dates`+`series`+`roster`+`provenance`, `records` 없음)를 전수 검증하며, **대상 0건이면 실패**한다
(조용한 통과 방지 — D-030의 교훈).

## 계약 변경 규율

- 새 선택 필드(모듈별 부가 레이어)는 **스키마에 명시적으로 추가**한 뒤 방출한다 —
  최상위 `additionalProperties: false`라 스키마에 없는 필드는 게이트가 막는다.
  이는 의도된 마찰이다: 공유 규격의 변경은 승인 대상(AGENTS §0·§1).
- `provenance`는 핵심 3필드(`source`·`generatedAt`·`window`)만 강제하고 부가 맥락은 자유 —
  출처 설명이 풍부해지는 것은 막을 이유가 없다(DOMAIN §0 추궁 가능성).
