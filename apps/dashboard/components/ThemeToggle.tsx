"use client";

export function ThemeToggle({ theme, onToggle }: { theme: "light" | "dark"; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label="테마 전환"
      className="glass-card px-3 py-1.5 text-sm text-[var(--ink-secondary)] transition-colors duration-200 ease-out hover:text-[var(--ink)]"
    >
      {theme === "dark" ? "☀ Light" : "☾ Dark"}
    </button>
  );
}
