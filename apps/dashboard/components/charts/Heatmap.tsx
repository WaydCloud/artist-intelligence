import type { HeatmapData } from "@/lib/report";
import { seqColor, textOn } from "@/lib/palette";

// 격자 = (행 × 열)의 단일 눈금 값. 빈 칸(null)은 값이 없다는 뜻이며 0이 아니다.
//
// 값의 방향은 **리포트가 정한다**(`scale`): 순위는 작을수록 강하고, 백분위 같은 값은
// 클수록 강하다. 예전에는 순위만 있다고 가정해서, genre-impulse가 백분위를 실었을 때
// 낮은 값이 가장 진하게 칠해지고 범례가 그것을 "상위"라고 불렀다 — 같은 그림이 정반대로
// 읽히는 상태였다. 방향을 payload로 올려 그 가정을 없앤다.
export function Heatmap({ data, dark }: { data: HeatmapData; dark: boolean }) {
  const byValue = data.scale === "value";
  const nums = data.cells.flat().filter((c): c is number => c != null);
  const max = Math.max(1, ...nums);
  const min = nums.length ? Math.min(...nums) : 0;

  // t: 0 = 가장 진한 끝(강함) → 1 = 옅은 끝. 방향만 여기서 갈린다.
  const t = (v: number) =>
    byValue ? (max === min ? 0 : 1 - (v - min) / (max - min)) : max <= 1 ? 0 : (v - 1) / (max - 1);
  const fill = (v: number) => seqColor(t(v), dark);
  const show = (v: number) => (byValue ? `${data.valuePrefix ?? ""}${v}` : `${v}위`);

  const legend = byValue
    ? [max, min + (max - min) * 0.66, min + (max - min) * 0.33, min].map((v) => Math.round(v))
    : [1, Math.round(max / 3), Math.round((2 * max) / 3), max];
  const ticks = legend.filter((v, i, a) => a.indexOf(v) === i);

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr>
            <th />
            {data.cols.map((c) => (
              <th
                key={c}
                className="whitespace-nowrap px-2 pb-1 text-center text-xs font-normal text-[var(--muted)]"
              >
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
                const bg = fill(cell);
                return (
                  <td
                    key={ci}
                    style={{ width: 46, height: 28 }}
                    title={`${row} · ${data.cols[ci]}: ${show(cell)}`}
                  >
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
        <span>{data.strongLabel ?? "상위"}</span>
        {ticks.map((v, i) => {
          const bg = fill(v);
          return (
            <span
              key={i}
              className="rounded-md px-1.5 py-0.5 tabular-nums"
              style={{ background: bg, color: textOn(bg) }}
            >
              {v}
            </span>
          );
        })}
        <span>
          {data.weakLabel ?? "하위"} · 빈칸 = {data.emptyLabel ?? "미진입"}
        </span>
      </div>
    </div>
  );
}
