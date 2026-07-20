import Link from "next/link";

const sections = [
  {
    href: "/artist-intelligence",
    title: "Artist Intelligence",
    description: "차트·팬덤·소셜 신호를 모은 리포트 대시보드",
  },
  {
    href: "/utilities",
    title: "Utilities",
    description: "보조 도구 모음 (준비 중)",
  },
];

// 브랜드 표면 (DESIGN.md §4) — 글로우·비네트·글래스·메탈릭 허용 구역.
export default function LandingPage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-6">
      <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: "var(--glow)" }} />
      <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: "var(--vignette)" }} />
      <div className="relative flex w-full max-w-2xl flex-col items-center gap-14">
        <div className="text-center">
          <h1
            className="bg-clip-text font-display text-4xl font-medium uppercase tracking-[0.35em] text-transparent sm:text-5xl"
            style={{ backgroundImage: "var(--metal)", paddingLeft: "0.35em" }}
          >
            WaydCloud
          </h1>
          <p className="mt-5 text-sm tracking-wide text-[var(--muted)]">
            데이터로 읽는 아티스트 신호 — 판단은 사람의 몫
          </p>
        </div>
        <div className="grid w-full gap-4 sm:grid-cols-2">
          {sections.map((s) => (
            <Link
              key={s.href}
              href={s.href}
              className="group rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-6 backdrop-blur-xl transition-colors duration-200 ease-out hover:border-[var(--baseline)]"
            >
              <div className="font-display text-base font-medium uppercase tracking-[0.12em] text-[var(--ink)]">
                {s.title}
              </div>
              <div className="mt-2 text-sm text-[var(--ink-secondary)]">{s.description}</div>
              <div className="mt-5 text-xs tracking-wide text-[var(--muted)] transition-colors duration-200 ease-out group-hover:text-[var(--ink-secondary)]">
                → 들어가기
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
