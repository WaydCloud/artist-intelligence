import type { HeatmapData } from "@/lib/report";
import { rankColor, textOn } from "@/lib/palette";

// Rank-by-market grid. rank = sequential magnitude (1 = strongest). Empty cell
// (null) = not charting. Theme-aware ramp; per-cell contrast-safe ink.
export function Heatmap({ data, dark }: { data: HeatmapData; dark: boolean }) {
  const ranks = data.cells.flat().filter((c): c is number => c != null);
  const maxRank = Math.max(1, ...ranks);
  const legend = [1, Math.round(maxRank / 3), Math.round((2 * maxRank) / 3), maxRank].filter(
    (v, i, a) => v >= 1 && a.indexOf(v) === i,
  );

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr>
            <th />
            {data.cols.map((c) => (
              <th key={c} className="px-2 pb-1 text-center text-xs font-normal text-[var(--muted)]">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, ri) => (
            <tr key={ri}>
              <td className="pr-3">
                <div className="max-w-[200px] truncate text-xs text-[var(--ink-secondary)]" title={row}>
                  {row}
                </div>
              </td>
              {data.cells[ri].map((cell, ci) => {
                if (cell == null) {
                  return (
                    <td key={ci} style={{ width: 46, height: 28 }}>
                      <div
                        className="h-7 rounded-md"
                        style={{ background: "color-mix(in srgb, var(--hairline) 45%, transparent)" }}
                      />
                    </td>
                  );
                }
                const bg = rankColor(cell, maxRank, dark);
                return (
                  <td key={ci} style={{ width: 46, height: 28 }} title={`${row} · ${data.cols[ci]}: ${cell}위`}>
                    <div
                      className="flex h-7 items-center justify-center rounded-md text-xs tabular-nums"
                      style={{ background: bg, color: textOn(bg) }}
                    >
                      {cell}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted)]">
        <span>상위</span>
        {legend.map((r, i) => {
          const bg = rankColor(r, maxRank, dark);
          return (
            <span key={i} className="rounded-md px-1.5 py-0.5 tabular-nums" style={{ background: bg, color: textOn(bg) }}>
              {r}
            </span>
          );
        })}
        <span>하위 · 빈칸 = 미진입</span>
      </div>
    </div>
  );
}
