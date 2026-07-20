# snapshot-schema — 수집물(입력측) 공유 규격

> `report-schema`(출력측)의 **짝**. 모든 JSON 수집 산출(`fetch`/`collect`)이 준수하는 **facts-only 스냅샷** 계약.
> 정본: [`snapshot.schema.json`](snapshot.schema.json) (JSON Schema draft 2020-12). 게이트: [`../../scripts/validate_snapshot.py`](../../scripts/validate_snapshot.py).

## 왜

핵심 흐름은 `모듈 CLI → report.json → 대시보드`다. 그 **입력측**(수집물)은 지금까지 계약이 없어 모듈마다 제각각이었다. 이 규격은 **거버넌스 메타데이터를 표준화**해 정제·관리 체계를 형식화한다:

- **provenance** — 출처·도구·버전·라이선스·ToS 등급·수집 파라미터. *추궁 가능성의 전제*(책임소재 불변식, [`../../DOMAIN.md`](../../DOMAIN.md) §0).
- **quality** — 정제 품질 지표(records·raw·dropped·coverage). *정제 각 단계의 품질을 측정·명시*(기준 원장, [`../../AGENTS.md`](../../AGENTS.md) §2.1).
- **records** — facts-only 레코드(모듈 형태). **PII·원문 필드 금지** — 게이트가 검증(§4).

## 형태

```jsonc
{
  "provenance": {
    "source": "Instagram / Apify apify~instagram-hashtag-scraper",
    "tool": "fandom-pulse.fetch",
    "tool_version": "0.1.0",
    "fetched_at": "2026-07-18T11:36:59Z",
    "license": "public-metrics",
    "tos_class": "managed-scraper",     // official-api | licensed-aggregator | open-aggregator | managed-scraper | first-party | synthetic
    "params": { "hashtag": "kpopdance", "resultsType": "reels", "maxItems": 30 },
    "pii_policy": "facts-only: PII·원문 fetch 단계 폐기(§4)"
  },
  "quality": { "records": 30, "raw": 30, "dropped": 0, "notes": [] },
  "records": [ { "likes": 969, "comments": 23, "type": "reel", "timestamp": "…", "hashtags": ["…"], "music": "…" } ]
}
```

## 게이트

```bash
python scripts/validate_snapshot.py <snapshot.json>
```

- **스키마 검증**: 위 계약 준수.
- **PII 게이트(§4)**: `records`에 금지 필드(유저명·id·url·caption·mentions·댓글 원문 등)가 있으면 **REJECT**. §4를 관습→게이트로.
- **신선도**: `fetched_at`이 오래되면 경고(선택).
- 품질 요약(records/raw/dropped, tos_class) 출력.

## 적용 범위

- **JSON 수집 산출**(fandom-pulse 등, 향후 소셜/API 모듈): 이 규격 준수 + 게이트 통과.
- **chart-history**: 원 스냅샷이 **HTML 표**(Kworb 차트 사실)라 별도 형태. provenance는 **헤더 주석**으로 편입하고, 차트 사실이라 PII 게이트는 N/A(D-007).
