"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import type { HeatmapData } from "@/lib/report";
import { seqColor, textOn } from "@/lib/palette";
import { ChartTooltip, useChartTooltip } from "./ChartTooltip";

// 격자 = (행 × 열)의 단일 눈금 값. 빈 칸(null)은 값이 없다는 뜻이며 0이 아니다.
//
// 값의 방향은 **리포트가 정한다**(`scale`): 순위는 작을수록 강하고, 백분위 같은 값은
// 클수록 강하다. 예전에는 순위만 있다고 가정해서, genre-impulse가 백분위를 실었을 때
// 낮은 값이 가장 진하게 칠해지고 범례가 그것을 "상위"라고 불렀다 — 같은 그림이 정반대로
// 읽히는 상태였다. 방향을 payload로 올려 그 가정을 없앤다.
//
// 🔴 칸의 인터랙션은 **툴팁**이고, 키보드·스크린리더는 **표 의미**로 닿는다(DESIGN §7).
//   - 칸에서 멀리 떨어진 머리글을 되짚지 않게 툴팁이 `행 · 열: 값`을 커서 옆에서 말한다.
//     32열 격자에서는 눈으로 열을 세는 것이 실제 비용이다.
//   - 칸마다 `tabIndex`를 붙이지 않는다. 12행 × 32열이면 탭 정지가 384개가 되어 키보드
//     사용자에게는 통과 불가능한 벽이 된다. 대신 행·열 머리글을 `<th scope>`로 선언해
//     스크린리더가 칸을 읽을 때 좌표를 같이 읽게 한다 — 이 격자는 이미 `<table>`이므로
//     추가 위젯이 아니라 **원래의 의미를 되돌려주는 것**이 맞는 답이다.
//   - 값은 칸 안에 이미 찍혀 있다. 툴팁은 값의 유일한 경로가 아니다(dataviz 비협상 항목).
export function Heatmap({ data, dark }: { data: HeatmapData; dark: boolean }) {
  const tip = useChartTooltip<{ row: string; col: string; text: string; missing: boolean }>();
  const byValue = data.scale === "value";
  const nums = data.cells.flat().filter((c): c is number => c != null);
  const max = Math.max(1, ...nums);
  const min = nums.length ? Math.min(...nums) : 0;

  // t: 0 = 가장 진한 끝(강함) → 1 = 옅은 끝. 방향만 여기서 갈린다.
  const t = (v: number) =>
    byValue ? (max === min ? 0 : 1 - (v - min) / (max - min)) : max <= 1 ? 0 : (v - 1) / (max - 1);
  const fill = (v: number) => seqColor(t(v), dark);
  const show = (v: number) => (byValue ? `${data.valuePrefix ?? ""}${v}` : `${v}위`);
  const emptyLabel = data.emptyLabel ?? "미진입";

  const legend = byValue
    ? [max, min + (max - min) * 0.66, min + (max - min) * 0.33, min].map((v) => Math.round(v))
    : [1, Math.round(max / 3), Math.round((2 * max) / 3), max];
  const ticks = legend.filter((v, i, a) => a.indexOf(v) === i);

  return (
    <div className="relative" ref={tip.containerRef}>
      <div className="overflow-x-auto">
        {/* `data-plot`은 인터랙션 게이트의 표식이다(`smoke-tabs.mjs`) — 칸 툴팁이 조용히
            빠지는 것을 세기 위해 "격자가 여기 있다"를 먼저 말해 둔다. */}
        <table data-plot="heatmap" className="border-separate" style={{ borderSpacing: 3 }}>
          <thead>
            <tr>
              <th />
              {data.cols.map((c) => (
                <th
                  key={c}
                  scope="col"
                  className="whitespace-nowrap px-2 pb-1 text-center text-xs font-light text-[var(--muted)]"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, ri) => (
              <tr key={ri}>
                <th scope="row" className="pr-3 text-left font-light">
                  <div className="max-w-[200px] truncate text-xs text-[var(--ink-secondary)]" title={row}>
                    {row}
                  </div>
                </th>
                {data.cells[ri].map((cell, ci) => {
                  const datum = {
                    row,
                    col: data.cols[ci],
                    text: cell == null ? emptyLabel : show(cell),
                    missing: cell == null,
                  };
                  const hover = {
                    onPointerMove: (e: ReactPointerEvent) => tip.show(e, datum),
                    onPointerLeave: tip.hide,
                  };
                  if (cell == null) {
                    return (
                      <td key={ci} style={{ width: 46, height: 28 }} {...hover}>
                        <div
                          className="h-7 rounded-md"
                          style={{ background: "color-mix(in srgb, var(--hairline) 45%, transparent)" }}
                        />
                      </td>
                    );
                  }
                  const bg = fill(cell);
                  return (
                    <td key={ci} style={{ width: 46, height: 28 }} {...hover}>
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
      </div>

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
          {data.weakLabel ?? "하위"} · 빈칸 = {emptyLabel}
        </span>
      </div>

      <ChartTooltip tip={tip}>
        {tip.datum && (
          <>
            <div
              className={`font-extrabold tabular-nums ${
                tip.datum.missing ? "text-[var(--muted)]" : "text-[var(--ink)]"
              }`}
            >
              {tip.datum.text}
            </div>
            <div className="mt-0.5 text-[var(--ink-secondary)]">{tip.datum.row}</div>
            <div className="text-[var(--muted)]">{tip.datum.col}</div>
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
