import type { BarData } from "@/lib/report";

// Horizontal magnitude bars in plain HTML — naturally responsive, handles long
// (Korean) labels, single series → one hue (length carries magnitude, not color).
export function BarChart({ data }: { data: BarData }) {
  if (data.length === 0) return <p className="text-sm text-[var(--muted)]">데이터 없음</p>;
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="space-y-2.5">
      {data.map((d, i) => (
        <div key={i} title={`${d.name}: ${d.value.toLocaleString("en-US")}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="truncate text-xs text-[var(--ink-secondary)]">{d.name}</span>
            <span className="shrink-0 text-xs tabular-nums text-[var(--muted)]">
              {d.value.toLocaleString("en-US")}
            </span>
          </div>
          <div
            className="h-1.5 rounded-full"
            style={{ background: "color-mix(in srgb, var(--hairline) 55%, transparent)" }}
          >
            <div
              className="h-1.5 rounded-full transition-[width] duration-300 ease-out"
              style={{ width: `${Math.max(1, (d.value / max) * 100)}%`, background: "var(--series)" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
