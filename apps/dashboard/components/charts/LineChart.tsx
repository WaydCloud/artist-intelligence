import type { LineData } from "@/lib/report";

// 시간에 따른 변화. 반응형 SVG(viewBox 스케일).
//
// 🔴 색 토큰은 3개이고 **순환하지 않는다**(dataviz 비협상 항목). 그래서 시리즈가 3개를
// 넘으면 색을 재사용하는 대신 **스몰 멀티플**로 접는다 — 2026-07-30 실측: 6시리즈 차트에서
// 토큰이 순환해 펄스 명료도와 스펙트럼 평탄도가 같은 보라색으로 그려졌고, 범례를 봐도
// 어느 선이 무엇인지 가릴 수 없었다. 4개 이상 수렴하는 선은 스몰 멀티플이 정답이다.
//
// 🔴 결측은 0이 아니다. `values`의 null에서 선을 **끊고** 축 계산에서도 뺀다(R6).
// 예전 코드는 null을 0으로 눕혀 관측이 없는 날 그래프가 바닥을 찍었다 — 리포트 스키마가
// "0은 관측값이라 그래프가 바닥을 찍는다"라고 명시해 둔 바로 그 실패였다.

const SLOT1 = "var(--series)";
const SERIES_COLORS = [SLOT1, "var(--series2)", "var(--series3)"];
// 이 수를 넘으면 색을 늘리지 않고 패널을 늘린다.
const TOKEN_CEILING = SERIES_COLORS.length;

type Series = { name: string; values: (number | null)[] };

function numeric(v: number | null): v is number {
  return typeof v === "number";
}

// 읽기 쉬운 눈금 라벨 — 정수는 그대로, 소수는 2자리 이하.
function fmtTick(v: number): string {
  return Number.isInteger(v) ? v.toLocaleString("en-US") : String(parseFloat(v.toFixed(2)));
}

// 눈금이 깔끔한 수에 떨어지게 하는 "nice" 간격. 정수 카운트(…,2,4,6,8)와
// 정규화된 0~1 데이터(0,0.25,0.5,…) 양쪽에서 5.25 / 3.5 같은 값을 피한다.
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

// 관측된 점의 **연속 구간**. 구간마다 따로 그리므로 결측이 있으면 선이 이어지지 않는다.
function runsOf(vals: (number | null)[]): number[][] {
  const runs: number[][] = [];
  let run: number[] = [];
  vals.forEach((v, i) => {
    if (numeric(v)) run.push(i);
    else if (run.length) {
      runs.push(run);
      run = [];
    }
  });
  if (run.length) runs.push(run);
  return runs;
}

function Plot({
  xs,
  series,
  top,
  tickVals,
  compact,
  colorOf,
}: {
  xs: string[];
  series: Series[];
  top: number;
  tickVals: number[];
  compact: boolean;
  colorOf: (i: number) => string;
}) {
  const W = compact ? 320 : 640;
  const H = compact ? 128 : 240;
  const padL = compact ? 30 : 44;
  const padR = compact ? 30 : 16;
  const padT = compact ? 10 : 16;
  const padB = compact ? 27 : 36;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const x = (i: number) => (xs.length === 1 ? padL + innerW / 2 : padL + (i / (xs.length - 1)) * innerW);
  const y = (v: number) => padT + innerH - (v / top) * innerH;
  const every = Math.max(1, Math.ceil(xs.length / (compact ? 3 : 8)));
  // 패널에서는 눈금을 위·아래 두 줄로 줄인다 — 작은 그림에 격자가 많으면 데이터보다 시끄럽다.
  const grid = compact ? [tickVals[0], tickVals[tickVals.length - 1]] : tickVals;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      style={{ height: "auto" }}
      role="img"
      aria-label={series.map((s) => s.name).join(", ")}
    >
      {grid.map((gv) => {
        const gy = y(gv);
        return (
          <g key={gv}>
            <line x1={padL} y1={gy} x2={W - padR} y2={gy} stroke="var(--hairline)" strokeWidth={1} />
            <text x={padL - 5} y={gy + 3} textAnchor="end" fontSize={compact ? 9 : 10} fill="var(--muted)">
              {fmtTick(gv)}
            </text>
          </g>
        );
      })}

      {series.map((s, si) => {
        const vals = s.values;
        const runs = runsOf(vals);
        const baseY = padT + innerH;
        const color = colorOf(si);
        const lastObserved = [...vals].reverse().findIndex(numeric);
        const lastIdx = lastObserved < 0 ? -1 : vals.length - 1 - lastObserved;
        return (
          <g key={s.name}>
            {/* 면은 **끊기지 않은 구간 안에서만** 채운다. 결측을 건너뛰고 채우면 없는
                관측을 있는 것처럼 보이게 한다. */}
            {series.length === 1 &&
              runs
                .filter((run) => run.length > 1)
                .map((run) => (
                  <polygon
                    key={`a-${run[0]}`}
                    points={
                      `${x(run[0])},${baseY} ` +
                      run.map((i) => `${x(i)},${y(vals[i] as number)}`).join(" ") +
                      ` ${x(run[run.length - 1])},${baseY}`
                    }
                    fill={color}
                    fillOpacity={0.07}
                  />
                ))}
            {runs
              .filter((run) => run.length > 1)
              .map((run) => (
                <polyline
                  key={`l-${run[0]}`}
                  points={run.map((i) => `${x(i)},${y(vals[i] as number)}`).join(" ")}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              ))}
            {vals.map((v, i) =>
              numeric(v) ? (
                <circle key={i} cx={x(i)} cy={y(v)} r={3} fill="var(--surface)" stroke={color} strokeWidth={1.5}>
                  <title>{`${s.name} · ${xs[i]}: ${fmtTick(v)}`}</title>
                </circle>
              ) : null,
            )}
            {/* 끝값 직접 라벨(패널에서만) — 축척을 공유해 작은 값이 눕는 패널에서도
                수준을 읽을 수 있게 한다. 모든 점에 숫자를 붙이지는 않는다. */}
            {compact &&
              lastIdx >= 0 &&
              (() => {
                // 라벨이 viewBox를 넘으면 **자르지 않고 안쪽으로 뒤집는다**. 클리핑은
                // 첫·끝 글자를 먹어 없는 값을 만든다(dataviz 안티패턴). 폭은 자릿수로
                // 어림한다 — SVG에서 렌더 폭을 미리 재려면 DOM 측정이 필요하고,
                // 그 비용을 들일 만큼 정밀할 필요는 없다(여유를 크게 잡으면 된다).
                const label = fmtTick(vals[lastIdx] as number);
                const est = label.length * 5.4;
                const outside = x(lastIdx) + 6 + est <= W;
                return (
                  <text
                    x={outside ? x(lastIdx) + 6 : x(lastIdx) - 6}
                    y={y(vals[lastIdx] as number) + 3}
                    fontSize={9}
                    textAnchor={outside ? "start" : "end"}
                    fill="var(--ink-secondary)"
                    stroke="var(--surface)"
                    strokeWidth={3}
                    paintOrder="stroke"
                  >
                    {label}
                  </text>
                );
              })()}
          </g>
        );
      })}

      {/* 결측 표시는 **축 아래 밴드**에 둔다. 플롯 안에 찍으면 그 자체가 값 위치로
          읽힌다 — 바닥(y=0)에 점을 놓았더니 실값이 0.01인 축에서 관측값과 구별되지
          않았다(2026-07-30 육안 검사). 축 밖의 마크는 값이 될 수 없다. */}
      {xs.map((lbl, i) => {
        const gone = series.filter((s) => !numeric(s.values[i]));
        if (gone.length === 0) return null;
        return (
          <g key={`m-${i}`}>
            <line
              x1={x(i)}
              y1={padT}
              x2={x(i)}
              y2={padT + innerH}
              stroke="var(--hairline)"
              strokeWidth={1}
            />
            <text
              x={x(i)}
              y={padT + innerH + 7}
              textAnchor="middle"
              fontSize={8}
              fill="var(--baseline)"
            >
              ×
              <title>{`${lbl}: 관측 없음 (${gone.map((s) => s.name).join(", ")})`}</title>
            </text>
          </g>
        );
      })}

      {xs.map((lbl, i) =>
        i % every === 0 || i === xs.length - 1 ? (
          <text
            key={i}
            x={x(i)}
            y={H - padB + (compact ? 18 : 20)}
            textAnchor="middle"
            fontSize={compact ? 9 : 10}
            fill="var(--muted)"
          >
            {lbl.length >= 10 ? lbl.slice(5) : lbl}
          </text>
        ) : null,
      )}
    </svg>
  );
}

export function LineChart({ data }: { data: LineData }) {
  const xs = data.x;
  const series: Series[] = data.series ?? [];
  if (series.length === 0 || xs.length === 0)
    return <p className="text-sm text-[var(--muted)]">데이터 없음</p>;

  const maxV = Math.max(...series.flatMap((s) => s.values.filter(numeric)), 0);
  const { top, values: tickVals } = niceTicks(maxV, 4);
  const nMissing = series.reduce((a, s) => a + s.values.filter((v) => !numeric(v)).length, 0);
  const faceted = series.length > TOKEN_CEILING;

  return (
    <div>
      {/* 범례는 2계열 이상에서 항상. 스몰 멀티플에서는 패널 제목이 그 일을 하므로 없다
          (패널당 시리즈 1개 = 색이 하나 = 범례가 제목을 반복할 뿐). */}
      {!faceted && series.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1">
          {series.map((s, si) => (
            <span key={s.name} className="flex items-center gap-1.5 text-xs text-[var(--ink-secondary)]">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: SERIES_COLORS[si] }}
              />
              {s.name}
            </span>
          ))}
        </div>
      )}

      {faceted ? (
        <>
          <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            {series.map((s) => (
              <div key={s.name}>
                <div className="mb-1 truncate text-xs text-[var(--ink-secondary)]" title={s.name}>
                  {s.name}
                </div>
                <Plot
                  xs={xs}
                  series={[s]}
                  top={top}
                  tickVals={tickVals}
                  compact
                  colorOf={() => SLOT1}
                />
              </div>
            ))}
          </div>
          {/* 축척을 공유한다는 사실이 없으면 패널끼리 비교해도 되는지 알 수 없다. */}
          <p className="mt-3 text-xs text-[var(--muted)]">
            {series.length}개 축을 같은 축척(0~{fmtTick(top)})으로 나란히 놓음 · 끝값을 직접 표시
          </p>
        </>
      ) : (
        <Plot
          xs={xs}
          series={series}
          top={top}
          tickVals={tickVals}
          compact={false}
          colorOf={(i) => SERIES_COLORS[i]}
        />
      )}

      {/* 결측이 있다는 사실을 화면이 스스로 말한다 — 끊긴 선만으로는 "왜 끊겼나"를
          못 전달하고, 눈치채지 못하면 결측이 0으로 읽히던 예전 상태로 돌아간다. */}
      {nMissing > 0 && (
        <p className="mt-1 text-xs text-[var(--muted)]">
          관측 없는 지점 {nMissing}개 · 선을 잇지 않음 (0으로 그리지 않음)
        </p>
      )}
    </div>
  );
}
