import Link from "next/link";
import type { Metadata } from "next";
import { BrandBackdrop } from "@/components/BrandBackdrop";

export const metadata: Metadata = {
  title: "Utilities",
};

// 브랜드 표면 (DESIGN.md §4).
export default function UtilitiesPage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-6">
      <BrandBackdrop vignette={false} />
      <div className="relative flex flex-col items-center gap-4 rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-10 py-8 backdrop-blur-xl">
        <h1 className="font-display text-xl font-medium uppercase tracking-[0.12em] text-[var(--ink)]">Utilities</h1>
        <p className="text-sm text-[var(--muted)]">준비 중</p>
        <Link
          href="/"
          className="mt-2 text-sm text-[var(--ink-secondary)] transition-colors duration-200 ease-out hover:text-[var(--ink)]"
        >
          ← 처음으로
        </Link>
      </div>
    </main>
  );
}
