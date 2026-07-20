"use client";

export function ThemeToggle({ theme, onToggle }: { theme: "light" | "dark"; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label="테마 전환"
      className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--ink-secondary)] transition-colors hover:text-[var(--ink)]"
    >
      {theme === "dark" ? "☀ Light" : "☾ Dark"}
    </button>
  );
}
