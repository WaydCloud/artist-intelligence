# CLAUDE.md

> Claude Code가 자동으로 로드하는 파일. 에이전트 규칙의 **정본은 [`AGENTS.md`](AGENTS.md)** 이며, 아래에서 임포트한다.

@AGENTS.md

## 작업 전 읽을 것 (맥락 로드 순서)

0. [`HANDOFF.md`](HANDOFF.md) — **먼저**: 지금 어디서 재개하는지(다음 행선지). 이력=`Handoffs/`, 결정=`docs/DECISIONS.md`
1. [`PRODUCT.md`](PRODUCT.md) — 무엇을/누구를 위해
2. [`DOMAIN.md`](DOMAIN.md) — 도메인 근거 (생성물의 바닥)
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — 핵심 흐름·규격·스택
4. [`WORKFLOW.md`](WORKFLOW.md) — 작업 순서·완료조건·리커버리
5. [`DESIGN.md`](DESIGN.md) — **클라이언트 대면 코드(UI·문구)를 만질 때 필수** (브랜드·토큰·표면 위계)
6. 해당 모듈의 `modules/<module>/SPEC.md · RULES.md · TESTS.md`

> 핵심 흐름: `모듈 CLI → 스키마 유효 report.json → 대시보드 렌더`. 이걸 깨면 빌드하지 않는다.
