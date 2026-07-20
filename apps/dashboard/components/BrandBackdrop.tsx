// 브랜드 표면 배경 레이어 — 글로우·비네트·필름 그레인 (DESIGN.md §1 시네마틱, §3).
// 데이터 표면(대시보드·차트·리포트 본문)에서 사용 금지 (DESIGN.md §4).
export function BrandBackdrop({ vignette = true }: { vignette?: boolean }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <div className="absolute inset-0" style={{ background: "var(--glow)" }} />
      {vignette && <div className="absolute inset-0" style={{ background: "var(--vignette)" }} />}
      <div
        className="absolute inset-0"
        style={{ backgroundImage: "var(--grain)", opacity: "var(--grain-opacity)" }}
      />
    </div>
  );
}
