# 2026-07-18 · Apify 레일 (소셜 폭, D-002 3번)

> Handoffs/ 아카이브 — 이 시점 스냅샷. (다음 행선지는 루트 `HANDOFF.md`)

## 이 구간에 한 일

- **레일 배선** (Firecrawl → YouTube → **Apify** → Bright Data 중 3번):
  - `.mcp.json`: `apify` 원격 MCP 서버(`https://mcp.apify.com`, Streamable HTTP, `Authorization: Bearer ${APIFY_TOKEN}`, `?tools=actors,docs`). SSE는 2026-04 deprecated → streamable HTTP.
  - `.env.example`: `APIFY_TOKEN` 활성화(발급 `console.apify.com/settings/integrations`, `setx`→MCP는 VSCode 재시작). ToS/비용/지표만 원칙 병기.
  - `scripts/apify_probe.py`: 표준 라이브러리 probe. **무료 기본**(`GET /v2/users/me`), 유료 Actor는 `--run` + 비용 캡(`maxItems`/`maxTotalChargeUsd`) 뒤, 결과는 **지표만**(숫자 필드 집계 + PII 키 값 미출력).
- **실측 검증**(사용자 토큰 발급, plan STARTER):
  - 무료 whoami: 토큰 VALID. **오프라인 probe는 재시작 불필요** — User scope 값을 그 호출에만 주입(토큰 미노출).
  - 유료 end-to-end: `apify~instagram-hashtag-scraper` · `#kpopdance` 20건 · `run-sync-get-dataset-items` · `$0.10` 캡 내. 지표만(likesCount mean 11.9/max 56·commentsCount mean 1.15/max 12·미디어 치수·필드 존재율), PII(ownerUsername·caption·url 등) redact 실증.
- DATA_SOURCES.md에 "Apify 실측 검증 (2026-07-18)" 섹션 추가.

## 검증 (로컬 = 게이트)

- ruff · pyright(0 errors) · `--help` · no-token graceful(exit 2) · free whoami · paid 실측. 전부 통과.
- Windows cp949 콘솔 크래시 수정: probe 출력 문자를 ASCII로(`—·§` → `-|`). 소스 한글 주석은 인쇄 안 되므로 무관.

## 배운 것 / 한계

- **매니지드 스크래퍼 = 리스크 이전 2차 레일**(§4): 종량제 + ToS 책임 사용자 귀속 → probe를 "무료 기본·유료 opt-in·비용 캡·지표만"으로 설계.
- `#kpopdance` 최근글은 소규모 계정 위주라 engagement 낮음 — **레일은 정상**, A&R 신호엔 그룹/공식계정·챌린지 해시태그 타깃 필요.
- MCP 서버(대화형 Actor 탐색)는 setx 후 **VSCode 재시작** 필요(프로세스 env 상속). 오프라인 probe/수집은 무관.
- TikTok 상업 스크래핑은 회피(§4) — IG 공개(로그아웃)가 sanctioned 경로.

## 세션 로테이션 진입점

→ 루트 [`HANDOFF.md`](../HANDOFF.md)(Apify 레일 인계점으로 갱신됨) — 후보: 대시보드 / 케이스 스터디 컨셉(우선 논의) / **Apify 스킬화**(팬덤 센티먼트·댓글 패턴 마이너 → report.json) / 댄스 v1 / v3.5(ISRC) / Bright Data.
