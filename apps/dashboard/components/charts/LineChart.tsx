import type { LineData } from "@/lib/report";

// Change-over-time as a responsive SVG line (viewBox-scaled). Renders every series
// in data.series (schema allows N); a legend appears only when there is more than
// one (single-series keeps its title-only read). Per-point <title> gives the hover.
const SERIES_COLORS = ["var(--series)", "var(--series2)", "var(--series3)"];

// Trim to a readable tick label — integers as-is, fractions to ≤2 decimals.
function fmtTick(v: number): string {
  return Number.isInteger(v) ? v.toLocaleString("en-US") : String(parseFloat(v.toFixed(2)));
}

// A "nice" round step so gridlines land on clean numbers for both integer counts
// (…,2,4,6,8) and normalized 0–1 data (0,0.25,0.5,…), not 5.25 / 3.5.
function niceStep(raw: number): number {
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return nice * mag;
}

function niceTicks(max: number, count: number): { top: number; values: number[] } {
  if (!(max > 0)) return { top: 1, values: [0, 1] };
  const step = niceStep(max / count);
  const top = Math.ceil(max / step) * step;
  const values: number[] = [];
  for (let v = top; v >= -1e-9; v -= step) values.push(parseFloat(v.toFixed(6)));
  return { top, values };
}

export function LineChart({ data }: { data: LineData }) {
  const W = 640;
  const H = 240;
  const padL = 44;
  const padR = 16;
  const padT = 16;
  const padB = 34;
  const xs = data.x;
  const series = data.series ?? [];
  if (series.length === 0 || xs.length === 0)
    return <p className="text-sm text-[var(--muted)]">데이터 없음</p>;

  const valsOf = (s: (typeof series)[number]) => s.values.map((v) => (v == null ? 0 : v));
  const maxV = Math.max(...series.flatMap((s) => valsOf(s)), 0);
  const { top, values: tickVals } = niceTicks(maxV, 4);
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const x = (i: number) => (xs.length === 1 ? padL + innerW / 2 : padL + (i / (xs.length - 1)) * innerW);
  const y = (v: number) => padT + innerH - (v / top) * innerH;
  const every = Math.max(1, Math.ceil(xs.length / 8));
  const color = (i: number) => SERIES_COLORS[i % SERIES_COLORS.length];

  return (
    <div>
      {series.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1">
          {series.map((s, si) => (
            <span key={s.name} className="flex items-center gap-1.5 text-xs text-[var(--ink-secondary)]">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: color(si) }}
              />
              {s.name}
            </span>
          ))}
        </div>
      )}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ height: "auto" }}
        role="img"
        aria-label={series.map((s) => s.name).join(", ")}
      >
        {tickVals.map((gv) => {
          const gy = y(gv);
          return (
            <g key={gv}>
              <line x1={padL} y1={gy} x2={W - padR} y2={gy} stroke="var(--hairline)" strokeWidth={1} />
              <text x={padL - 6} y={gy + 3} textAnchor="end" fontSize={10} fill="var(--muted)">
                {fmtTick(gv)}
              </text>
            </g>
          );
        })}

        {series.map((s, si) => {
          const vals = valsOf(s);
          return (
            <g key={s.name}>
              <polyline
                points={vals.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
                fill="none"
                stroke={color(si)}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {vals.map((v, i) => (
                <circle
                  key={i}
                  cx={x(i)}
                  cy={y(v)}
                  r={4}
                  fill="var(--surface)"
                  stroke={color(si)}
                  strokeWidth={2}
                >
                  <title>{`${s.name} · ${xs[i]}: ${fmtTick(v)}`}</title>
                </circle>
              ))}
            </g>
          );
        })}

        {xs.map((lbl, i) =>
          i % every === 0 || i === xs.length - 1 ? (
            <text key={i} x={x(i)} y={H - padB + 16} textAnchor="middle" fontSize={10} fill="var(--muted)">
              {lbl.length >= 10 ? lbl.slice(5) : lbl}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}
