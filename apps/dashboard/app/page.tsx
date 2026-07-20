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

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 p-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-[var(--ink)]">WaydCloud</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">이동할 영역을 선택하세요</p>
      </div>
      <div className="grid w-full max-w-2xl gap-4 sm:grid-cols-2">
        {sections.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="group rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 transition-colors hover:border-[var(--series)]"
          >
            <div className="text-lg font-semibold tracking-tight text-[var(--ink)] group-hover:text-[var(--series)]">
              {s.title}
            </div>
            <div className="mt-1.5 text-sm text-[var(--ink-secondary)]">{s.description}</div>
            <div className="mt-4 text-xs text-[var(--muted)]">→ 들어가기</div>
          </Link>
        ))}
      </div>
    </main>
  );
}
