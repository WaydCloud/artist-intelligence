import type { Metric } from "@/lib/report";

function fmt(v: number | string): string {
  return typeof v === "number" ? v.toLocaleString("en-US") : v;
}

export function KpiTile({ m }: { m: Metric }) {
  const up = typeof m.delta === "number" && m.delta > 0;
  const down = typeof m.delta === "number" && m.delta < 0;
  return (
    <div className="glass-card p-4 transition-colors duration-200 ease-out hover:border-[var(--baseline)]">
      <div className="text-xs text-[var(--muted)]">{m.label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="truncate text-2xl font-semibold tracking-tight text-[var(--ink)]">{fmt(m.value)}</span>
        {m.unit && <span className="shrink-0 text-xs text-[var(--ink-secondary)]">{m.unit}</span>}
      </div>
      {typeof m.delta === "number" && (
        <div
          className="mt-0.5 text-xs tabular-nums"
          style={{ color: up ? "var(--good)" : down ? "var(--bad)" : "var(--muted)" }}
        >
          {up ? "▲" : down ? "▼" : "→"} {Math.abs(m.delta).toLocaleString("en-US")}
        </div>
      )}
      {m.hint && (
        <div className="mt-1 truncate text-xs text-[var(--muted)]" title={m.hint}>
          {m.hint}
        </div>
      )}
    </div>
  );
}
