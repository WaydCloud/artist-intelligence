# ARCHITECTURE — 시스템 구성

> 하네스의 기술적 뼈대. 핵심 흐름과 불변식이 여기 정의된다. (기존 `docs/00-architecture.md`를 흡수·확장)

## 원칙 한 줄

> **통합의 실체는 "공유 백엔드"가 아니라 "공유 결과 규격(report contract)"이다.**
> 각 분석 모듈(Python)은 스키마 유효한 JSON 리포트 + 이미지를 뱉는다. 대시보드(정적 프론트)는 그걸 읽어 렌더한다.

## 핵심 흐름 (Core Flow) — 절대 불변식

```
모듈 CLI  ──▶  스키마 유효한 report.json  ──▶  대시보드 렌더
              (packages/report-schema)
```

이 흐름이 깨지면 **빌드하지 않는다.** CI가 강제한다([`WORKFLOW.md`](WORKFLOW.md), `.github/workflows/ci.yml`). 이것이 하네스의 심장이다.

## 왜 정적 우선(static-first)

- 청중(엔터 채용자)에겐 **링크 클릭 즉시·항상 동작**이 최우선. 죽은 데모 링크는 최악.
- 분석은 배치/오프라인 → 미리 계산 → 결과 커밋 → 정적 사이트 렌더. **라이브 백엔드 불필요.**
- 라이브 업로드 기능은 여력 될 때 옵션. 기본은 미리 계산된 데모.

## 폴더 구조

```
artist-intelligence/
├─ AGENTS.md · PRODUCT.md · DOMAIN.md · ARCHITECTURE.md · WORKFLOW.md   # 레포 하네스
├─ CLAUDE.md                     # AGENTS.md 임포트 (Claude Code 자동 로드)
├─ .github/workflows/ci.yml      # 게이트
├─ packages/report-schema/       # 공유 규격 (JSON Schema + TS 타입 + pydantic)
├─ apps/dashboard/               # Next.js 정적 (통합 허브 + 모듈 뷰)
└─ modules/
   └─ <module>/
      ├─ SPEC.md · RULES.md · TESTS.md   # 모듈 하네스
      ├─ src/                    # Python CLI
      ├─ data/                   # 입력 (대용량 → .gitignore)
      └─ output/report.json      # 산출물 (커밋 → 정적 렌더)
```

**규칙**: `apps/` = JS 세계, `modules/` = Python 세계. 억지로 합치지 말고 나란히.

## 공유 리포트 규격

- 정본은 `packages/report-schema/report.schema.json` (JSON Schema, draft 2020-12).
- TS 타입과 pydantic 모델이 이를 미러링. 모듈은 pydantic으로 검증 후 write, 대시보드는 TS 타입으로 read.
- 필드: `moduleId, title, subtitle?, generatedAt, metrics[], charts[], media[], insights[], recommendations[]`.
- **차트 페이로드도 제약된다**(D-036): `chart.type`이 `chart.data`의 형태를 결정한다(bar·line·heatmap·tunable 판별 분기). 2026-07-30까지 `"data": {}`로 무제약이었고, 그 틈으로 계약 이탈이 세 번 화면까지 나갔다. 읽는 쪽 정본은 `apps/dashboard/lib/report.ts`의 판별 유니온이며 **둘은 짝으로 갱신한다**.
- **계약은 두 층**이다: 스키마가 **형태**(키·타입·required)를, [`scripts/validate_report_data.py`](scripts/validate_report_data.py)가 **스키마로 표현할 수 없는 것**(교차 필드 길이, 렌더러가 아는 tunable `view`인지, 노브 기본값이 범위 안인지)을 본다. 분업이 성립하는지는 `--selftest`가 두 층을 한꺼번에 증명한다.
- **이 스키마를 어기는 변경은 금지**(핵심 흐름 계약). → [`AGENTS.md`](AGENTS.md)

## 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 대시보드 | Next.js(app router) + TS + Tailwind | 정적 export(`output: export`), Vercel 배포. **구현됨** |
| 차트 | 손수 만든 반응형 SVG/HTML (Recharts 미도입) | 정적 export 견고 · dataviz mark 규격 정밀 제어 · 의존성 최소 |
| 분석 | Python + uv | 모듈별 독립 CLI |
| 검증 | JSON Schema, pydantic, ajv | 스키마 게이트 |

**금지**: Nx·Turborepo·마이크로서비스·임의 라이브 백엔드·인증/DB(현 단계 불필요·과함).

## 데이터 · 자산

- 대용량 원본(영상·음원)은 커밋 금지(`.gitignore`). 저작물 재배포 금지. **파생 결과(JSON·작은 이미지)만 커밋.**
- 출처·라이선스는 각 모듈 SPEC에 명시. (윤리: [`AGENTS.md`](AGENTS.md))

## 빌드 규율: 세로 슬라이스

모듈 1개를 `분석 → 리포트 규격 → 대시보드 렌더`까지 완성형으로 관통시킨 뒤 복제. 어느 시점에 멈춰도 "예쁜 셸 + 완성 모듈"이 유지된다.

- **관통 완료**: `apps/dashboard`(범용 리포트 뷰)가 **chart-history·fandom-pulse**의 스키마 유효 report.json을 KPI + bar + line + heatmap으로 렌더 → **핵심 흐름 전체가 살아있음**(모듈 CLI → report.json → 대시보드). 빌드타임 수집(`scripts/collect-reports.mjs`) · 라이트/다크 · 딥링크 탭(`#moduleId`·`?theme=`).
- 다음 세로 슬라이스 후보: 플래그십 **dance-dynamics**(같은 계약으로 복제).
