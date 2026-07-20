# signal-bridge fixtures

## ⚠ `chart_store/*.html` — 합성 데이터 (SYNTHETIC)

`chart_store/`의 6개 다일 스냅샷은 **합성(synthetic) 픽스처**다 — **실제 차트 데이터가 아니다.**

- **목적**: 브리지 배선·판정 로직(온셋·선행/지연·분류)을 **시연**하기 위해, 소셜 버즈보다 며칠 늦게 차트에 진입하는 타임라인을 인위적으로 인코딩했다.
- **정직성(§0)**: 이 픽스처가 만든 "소셜 선행" 결과는 **"소셜이 차트를 선행한다"는 실증이 아니다.** 실증은 **라이브 다일 collect**(fandom-pulse `fetch` + chart-history `collect`를 N일 축적)로만 가능하다.
- 각 파일 `<!-- ... tos_class: synthetic-fixture ... -->` 메타로 라벨되며, chart-history `signals` 이미터가 이를 감지해 signal-series `provenance.synthetic=true`로 전파 → 브리지가 리포트 최상단에 **메커니즘 시연 경고**를 낸다.
- Kworb Spotify daily 테이블 형태라 chart-history의 실 파서가 그대로 읽는다(파서 우회 없음).
- 재생성: `scratchpad/gen_chart_store.py`(생성 스크립트, 커밋 아님)의 `TIMELINE` 딕셔너리가 원본. 타임라인(실측 소셜 온셋 대비 합성 차트 온셋): ATEEZ +4d · LE SSERAFIM +4d · ILLIT +6d(social-led) · YooA −1d(chart-led 반례) · aespa·The Weeknd(chart-only).

## `social_series.json` · `chart_series.json`

두 모듈의 `signals` 서브커맨드가 생성한 signal-series(재생성 명령은 [`../../TESTS.md`](../../TESTS.md)). `social_series.json`은 **실 데이터**(`#kpopdance` facts-only 스냅샷 유래), `chart_series.json`은 위 **합성** store 유래.
