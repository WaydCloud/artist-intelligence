"use client";

import { useEffect, useState } from "react";
import type { Report } from "@/lib/report";
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
    <div className="min-h-screen">
      <header className="border-b border-[var(--hairline)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="text-sm font-medium tracking-tight">Artist Intelligence</div>
            <div className="text-xs text-[var(--muted)]">리포트 대시보드 · 모듈 CLI → report.json → 렌더</div>
          </div>
          <ThemeToggle theme={theme} onToggle={() => setTheme(dark ? "light" : "dark")} />
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-5">
        <nav className="flex gap-1 pt-4" role="tablist" aria-label="모듈">
          {reports.map((r, i) => (
            <button
              key={r.moduleId}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => select(i)}
              className={
                i === active
                  ? "rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--ink)]"
                  : "rounded-md px-3 py-1.5 text-sm text-[var(--muted)] transition-colors hover:text-[var(--ink-secondary)]"
              }
            >
              {r.moduleId}
            </button>
          ))}
        </nav>
      </div>

      {report ? (
        <ReportView
          report={report}
          dark={dark}
          moduleIds={reports.map((r) => r.moduleId)}
          onSelectModule={(id) => {
            const idx = reports.findIndex((r) => r.moduleId === id);
            if (idx >= 0) select(idx);
          }}
        />
      ) : (
        <div className="mx-auto max-w-5xl px-5 py-16 text-[var(--muted)]">리포트가 없습니다.</div>
      )}

      <footer className="mx-auto max-w-5xl px-5 py-10 text-xs leading-relaxed text-[var(--muted)]">
        정적 렌더 · 이 대시보드는 <strong className="font-medium">스키마 유효 report.json</strong>만 읽습니다(핵심 흐름 계약).
        지표는 <strong className="font-medium">근거 있는 신호</strong>이며 예측·단정이 아닙니다.
      </footer>
    </div>
  );
}
