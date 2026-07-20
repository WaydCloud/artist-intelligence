# 2026-07-18 · Firecrawl 실측 검증 (나무위키 ✅ / 써클차트 🚩)

> Handoffs/ 아카이브 — 이 시점 스냅샷. (다음 행선지는 루트 `HANDOFF.md`)

## 이 구간에 한 일

- **Firecrawl 데이터 레일 실측 검증**(HANDOFF 작업 2). 직접 v2 API 사용(유효 키, User scope).
- **나무위키 사실 추출 검증 ✅** — `includeTags:["table"]`(인포박스 한정) + 사실 스키마로 aespa 메타 정확 추출(데뷔 2020-11-17·SM·유통 카카오·팬덤 MY·멤버 4인). 전체 217k자 naive 추출은 `null`.
- **써클차트 검증 🚩** — 랭킹은 JS/내부엔드포인트 로드라 정적 스크랩 미포착. **푸터에 "AI/ML 학습·TDM 무단이용 금지" 명시** 확인 → 스크랩 부적합, 정식 제휴/문화빅데이터포털 경로만.
- **MCP 툴 무효 토큰 원인 규명** — 프로세스가 `setx` 이후 env를 상속 못 받음(Process scope 없음 / User scope 정상). VSCode 재시작으로 해결.
- `DATA_SOURCES.md` 갱신: 써클차트 행 + §4 하드룰 + "Firecrawl 실측 검증(2026-07-18)" 메모.

## 배운 것 (재사용)

- **엔티티 마스터 빌더 패턴**: 대용량 위키 페이지는 `includeTags:["table"]`로 인포박스만 좁혀 사실 스키마 추출. NC 라이선스라 사실 필드만 적재.
- **Firecrawl v2 API**: JSON 추출 = `formats:[{type:"json",schema,prompt}]`(구 `jsonOptions` 최상위는 400). URL 발견 = `/v2/map`.
- **MCP env**: `.mcp.json`의 `${VAR}`는 부모 프로세스 env에서 확장 → `setx` 후엔 앱 재시작 필수.

## 다음 세션 진입점

→ 루트 [`HANDOFF.md`](../HANDOFF.md)
