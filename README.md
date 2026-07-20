# 아티스트 인텔리전스 시스템 (Artist Intelligence System)

> A&R · 기획을 위한 데이터/AI 의사결정 **지원** 플랫폼
> *"AI는 감(感)을 대체하지 않는다. 잡무를 걷어내고 놓치기 쉬운 신호를 표면화한다."*

---

## 이게 뭔가

K-pop 신인 기획부터 캐스팅·트레이닝, 레퍼토리(곡) 선정까지 — A&R/기획의 판단을 **대체하지 않고 증폭**하는 분석 도구 모음. 여러 개의 독립 분석 모듈이 하나의 통합 대시보드 아래 묶여, 신인 걸그룹을 기획·육성·데뷔시키는 전 과정을 데이터로 뒷받침한다.

이 저장소는 **채용 포트폴리오**다. 목표는 엔지니어링 실력 과시가 아니라, **A&R/기획의 판단(taste)과 직무 이해**를 증명하는 것. 각 도구는 하나의 A&R 의사결정을 뒷받침하는 *증거*로 존재한다.

---

## Thesis (왜 이 접근인가)

- **증폭 > 대체.** 업계는 "감"과 예술성을 방어적으로 지킨다. 이 시스템은 그걸 위협하지 않는다. 반복 노동을 걷어내고, 사람이 놓치는 신호를 눈에 보이게 만든다.
- **판단을 증명한다.** 트렌드 대시보드 하나로는 약하다. 그 데이터로 *실제 기획 결정을 내리고 근거를 대는 것*이 핵심. 도구는 증거, 논지가 주인공.
- **실데이터로.** 초동(Hanteo)·Circle Chart·Spotify/YouTube·브랜드평판 등 실제 지표를 쓴다. 토이 데이터는 신뢰를 못 준다.

---

## 포트폴리오 전략 (심사자를 위한 메모)

1. **케이스 스터디 척추** — 가상의 신인 걸그룹 1팀(또는 정체된 실제 그룹의 리포지셔닝)을 데뷔/재기시키는 서사 위에 도구를 얹는다. "이런 판단을 했고, 이 도구가 그 판단을 뒷받침했다."
2. **깊이 > 넓이** — 완성된 1~2개가 반쪽 5개를 이긴다. **댄스 다이내믹**을 먼저 "와우" 수준까지 완성한다.
3. **정적 우선(static-first)** — 미리 계산된 결과를 렌더하는 정적 사이트로 배포(Vercel). 링크 클릭 시 **즉시·항상** 동작해야 한다.
4. **증폭 프레이밍 유지** — 모든 리포트는 "정답"이 아니라 **근거 있는 옵션/피드백**을 제시한다.

---

## 모듈 지도 (A&R 라이프사이클에 매핑)

| A&R 단계 | 모듈 | 폴더 | 상태 |
|---|---|---|---|
| 캐스팅 & 트레이닝 | **댄스 다이내믹 분석** (히어로) | `modules/dance-dynamics` | 🚧 개발 중 (v1) |
| 기획 & 방향성 | **트렌드 & 브랜드 애널리시스** (데이터 레이어) | `modules/trend-brand` | 📄 스펙 |
| 기획 추론 | **브랜드 하니스** (기획 에이전트, 추론 레이어) | `modules/brand-harness` | 📄 스펙 |
| 레퍼토리 (A&R 본진) | **곡–아티스트 매칭** (데모 스크리닝) | `modules/song-match` | 📄 스펙 |
| 운영 & 팬덤 | 팬덤/오디언스 퍼널 | `modules/fandom` | 💭 예정 |
| 공통 (거버넌스) | **윤리·데이터 원칙** | [`AGENTS.md`](AGENTS.md) §5 · [`docs/05`](docs/05-ethics-and-data.md) | ✅ |

> 이 지도를 대시보드 첫 화면에 그려두면 "이 사람은 A&R 전체 흐름을 안다"가 한눈에 전달된다.

---

## 하네스 문서

**레포 공유 하네스** (모든 모듈이 준수):
- [`PRODUCT.md`](PRODUCT.md) — 무엇을 / 누구를 위해 / 왜
- [`DOMAIN.md`](DOMAIN.md) — 케이팝·팬덤 도메인 지식 (모든 생성물의 grounding)
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 핵심 흐름·리포트 규격·정적우선·스택
- [`AGENTS.md`](AGENTS.md) ↔ [`CLAUDE.md`](CLAUDE.md) — 에이전트 규칙·하드 게이트
- [`WORKFLOW.md`](WORKFLOW.md) — 작업 순서·완료조건·리커버리

**게이트**:
- [`packages/report-schema/report.schema.json`](packages/report-schema/report.schema.json) — 핵심 흐름 계약(스키마)
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — lint · typecheck · smoke · schema · security

**모듈 하네스**:
- [`modules/dance-dynamics/`](modules/dance-dynamics/) — `SPEC` · `RULES` · `TESTS` ✅ (템플릿 완성)
- 스테이징 스펙(모듈화 예정): [`docs/02-trend-brand.md`](docs/02-trend-brand.md) · [`docs/03-brand-harness.md`](docs/03-brand-harness.md) · [`docs/04-song-match.md`](docs/04-song-match.md)
- 윤리 정책: [`docs/05-ethics-and-data.md`](docs/05-ethics-and-data.md) (규칙 강제는 [`AGENTS.md`](AGENTS.md) §5)

---

## 로드맵 (세로 슬라이스 / walking skeleton)

가로(모든 백엔드 먼저)가 아니라 **세로**로 간다. 어느 시점에 멈춰도 "예쁜 셸 + 완성된 모듈"이 되도록.

1. **[진행]** 댄스 다이내믹 모듈 → 리포트 규격 → 대시보드 렌더까지 **한 줄로 관통** (완성형 1개)
2. 트렌드 & 브랜드 데이터 레이어 추가
3. 곡–아티스트 매칭 추가
4. 브랜드 하니스(에이전트)로 추론 레이어 얹기
5. 팬덤/오디언스, 보컬 분석 등 확장

---

## 스택 요약

- **대시보드**: Next.js + TypeScript + Tailwind + shadcn/ui (정적 export, Vercel)
- **분석 모듈**: Python + uv, 각 모듈은 독립 CLI
- **통합**: 공유 리포트 규격(JSON) — 모듈이 결과물을 뱉고, 대시보드가 렌더
- **원칙**: Nx/Turborepo 같은 무거운 모노레포 툴 **미사용** (지금 규모엔 과함)
