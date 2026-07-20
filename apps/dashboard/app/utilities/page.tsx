import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Utilities",
};

export default function UtilitiesPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold tracking-tight text-[var(--ink)]">Utilities</h1>
      <p className="text-sm text-[var(--muted)]">준비 중입니다.</p>
      <Link
        href="/"
        className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm text-[var(--ink-secondary)] transition-colors hover:border-[var(--baseline)]"
      >
        ← 처음으로
      </Link>
    </main>
  );
}
