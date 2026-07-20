"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Report } from "@/lib/report";
import { BrandBackdrop } from "@/components/BrandBackdrop";
import { ReportView } from "@/components/ReportView";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Dashboard({ reports }: { reports: Report[] }) {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [active, setActive] = useState(0);

  useEffect(() => {
    const forced = new URLSearchParams(window.location.search).get("theme");
    const stored = localStorage.getItem("theme");
    const initial =
      forced === "dark" || forced === "light"
        ? forced
        : stored === "dark" || stored === "light"
          ? stored
          : window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
    setTheme(initial);

    // deep-link a report by moduleId in the hash (#fandom-pulse) — shareable links
    const hash = decodeURIComponent(window.location.hash.replace("#", ""));
    const idx = reports.findIndex((r) => r.moduleId === hash);
    if (idx >= 0) setActive(idx);
  }, [reports]);

  function select(i: number) {
    setActive(i);
    window.history.replaceState(null, "", `#${reports[i].moduleId}`);
  }

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const report = reports[active];
  const dark = theme === "dark";

  return (
    <div className="relative min-h-screen">
      <BrandBackdrop vignette={false} />
      <header className="sticky top-0 z-20 border-b border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-3">
          <div>
            <Link
              href="/"
              className="metal-text font-display text-[10px] font-medium uppercase tracking-[0.3em]"
            >
              WaydCloud
            </Link>
            <div className="font-display text-sm font-medium tracking-wide text-[var(--ink)]">
              Artist Intelligence
              <span className="ml-2 text-xs font-normal tracking-normal text-[var(--muted)]">리포트 대시보드</span>
            </div>
          </div>
          <ThemeToggle theme={theme} onToggle={() => setTheme(dark ? "light" : "dark")} />
        </div>
      </header>

      <div className="relative mx-auto max-w-5xl px-5">
        <nav className="flex flex-wrap gap-1.5 pt-4" role="tablist" aria-label="모듈">
          {reports.map((r, i) => (
            <button
              key={r.moduleId}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => select(i)}
              className={
                i === active
                  ? "glass-card px-3 py-1.5 text-sm text-[var(--ink)]"
                  : "rounded-2xl px-3 py-1.5 text-sm text-[var(--muted)] transition-colors duration-200 ease-out hover:text-[var(--ink-secondary)]"
              }
            >
              {r.moduleId}
            </button>
          ))}
        </nav>
      </div>

      {report ? (
        <div className="relative">
          <ReportView
            report={report}
            dark={dark}
            moduleIds={reports.map((r) => r.moduleId)}
            onSelectModule={(id) => {
              const idx = reports.findIndex((r) => r.moduleId === id);
              if (idx >= 0) select(idx);
            }}
          />
        </div>
      ) : (
        <div className="relative mx-auto max-w-5xl px-5 py-16 text-[var(--muted)]">표시할 리포트 없음</div>
      )}

      <footer className="relative mx-auto max-w-5xl border-t border-[var(--hairline)] px-5 py-10 text-xs leading-relaxed text-[var(--muted)]">
        모든 지표는 <strong className="font-medium">참고용 신호</strong>. 예측이나 단정이 아니며, 판단은 사람의 몫.
      </footer>
    </div>
  );
}
