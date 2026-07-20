# 2026-07-18 · 대시보드 (핵심 흐름 우반부 관통)

> Handoffs/ 아카이브 — 이 시점 스냅샷. (다음 행선지는 루트 `HANDOFF.md`)

## 이 구간에 한 일

- **`apps/dashboard`** 구현 — 스키마 유효 report.json을 렌더하는 **범용 리포트 뷰**. Next.js(app router) · TS · Tailwind · **정적 export**(`output: export`, Vercel용).
  - 컴포넌트: KPI 타일(label·value·unit·delta·hint·문자열지표) · **bar**(HTML 수평 magnitude) · **line**(SVG 시계열, 마커·그리드) · **heatmap**(CSS grid, 순위=sequential blue, 빈칸=미진입, 대비-안전 텍스트) · 인사이트/추천.
  - 빌드타임 수집 `scripts/collect-reports.mjs`: `modules/*/output/report.json → data/reports.json`(커밋, CI typecheck용).
  - 라이트/다크(검증된 dataviz 레퍼런스 팔레트, CSS 토큰) · 딥링크 탭 `#moduleId` · 테마 링크 `?theme=`.
- **설계 결정**: Recharts 대신 **손수 만든 반응형 SVG/HTML 차트** — 정적 export 견고·dataviz mark 규격 정밀 제어·의존성 최소. ARCHITECTURE 스택 문서 갱신.
- dataviz 스킬 로드 → form heuristic·검증된 팔레트·mark specs 준수(대부분 단일 시리즈라 blue sequential + 뉴트럴, 새 categorical 없음 → 검증기 불필요).

## 검증 (로컬 = 게이트)

- `npm run lint`(✔ ESLint 0) · `npm run typecheck`(✔ tsc) · `npm run build`(✓ 정적 export). Next 보안 패치 `^14.2.35`.
- **실제 렌더 스크린샷**(Edge 헤드리스, out/ 서빙):
  - chart-history — KPI 10 + bar×3 + heatmap(KR/GLOBAL/US/JP × 12곡) + 인사이트 → **라이트·다크 둘 다** 정상.
  - fandom-pulse — KPI 7 + 공동해시태그 bar + **line**(일별 게시량 06-29~07-17, 07-14 스파이크) + Top 사운드(ATEEZ-BAD) → 정상.
- prerender된 정적 HTML(41KB)에 두 리포트 데이터 구움 · `package-lock` 커밋(CI `dashboard` 잡 대비) · `next-env.d.ts`·`*.tsbuildinfo` gitignore.

## 배운 것 / 한계

- 핵심 흐름 `모듈 CLI → report.json → 대시보드` **전체 살아있음** — 이후 모듈은 같은 계약으로 대시보드가 자동 렌더(dance-dynamics 등).
- Windows: 백그라운드 http.server가 `out/`을 잠가 재빌드 EBUSY → 서버 멈추고 클린 재빌드. Edge 헤드리스는 OS 다크를 감지(라이트는 `?theme=light`).
- 남은: 필터/시계열/미디어 렌더 · dance-dynamics 뷰 · **Vercel 배포**(링크 하나 데모, PRODUCT 성공기준).

## 세션 로테이션 진입점

→ 루트 [`HANDOFF.md`](../HANDOFF.md) — **재개 첫 액션: 대시보드를 로컬 서버로 눈으로 확인**(`cd apps/dashboard && npm run dev`). 그 다음 후보: 케이스 스터디 컨셉 / 댄스 v1 / Vercel 배포 / fandom-pulse v2.
