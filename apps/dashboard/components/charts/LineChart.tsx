"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import type { LineData } from "@/lib/report";
import { ChartTooltip, useChartTooltip } from "./ChartTooltip";

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
//
// 🔴 인터랙션은 **크로스헤어 + 통합 툴팁**이다(DESIGN §7 "선·면에 크로스헤어+툴팁").
//   - 히트 타깃은 플롯 **전면**이고 가장 가까운 x로 스냅한다. 점마다 `<title>`을 달던
//     예전 방식은 히트 타깃이 6px이라 104점 차트(signal-bridge)에서는 조준해야 잡혔다.
//   - 시리즈별로 툴팁을 따로 띄우지 않는다. 같은 x의 값을 **한 툴팁에 모아야** 두 선을
//     비교할 수 있고, 그것이 이 차트가 답하는 질문이다.
//   - 결측도 같은 툴팁에서 "관측 없음"으로 말한다. 빠진 줄로 두면 0으로 읽힌다.
//   - **키보드로 같은 곳에 닿는다**(좌우 화살표·Home·End). `<title>` 속성은 포인터
//     전용이라 키보드로는 값에 닿을 방법이 아예 없었다.
//   - 툴팁이 값의 유일한 경로가 아니게 표 뷰를 함께 낸다(dataviz 비협상 항목).

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

// 한 x에 모인 전 시리즈의 값 — 통합 툴팁이 그리는 것.
type Column = {
  label: string;
  rows: { name: string; color: string; text: string; missing: boolean }[];
};

// 통합 툴팁의 내용 — 같은 x의 값을 한 자리에 모은다. 시리즈마다 따로 띄우면 두 선을
// 비교할 수 없고, 비교가 이 차트의 질문이다. 결측도 같은 목록에서 말한다(빠진 줄로
// 두면 0으로 읽힌다).
function ColumnBody({ col }: { col: Column }) {
  const swatch = col.rows.length > 1;
  return (
    <>
      <div className="text-[var(--muted)]">{col.label}</div>
      {col.rows.map((r) => (
        <div key={r.name} className="mt-0.5 flex items-baseline gap-2">
          {swatch && (
            <span
              aria-hidden
              className="inline-block h-2 w-2 shrink-0 rounded-sm"
              style={{ background: r.color, opacity: r.missing ? 0.3 : 1 }}
            />
          )}
          <span className="min-w-0 flex-1 truncate text-[var(--ink-secondary)]">{r.name}</span>
          <span
            className={`shrink-0 tabular-nums ${
              r.missing ? "text-[var(--muted)]" : "font-medium text-[var(--ink)]"
            }`}
          >
            {r.text}
          </span>
        </div>
      ))}
    </>
  );
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
  const tip = useChartTooltip<Column>();
  const svgRef = useRef<SVGSVGElement | null>(null);
  // 크로스헤어가 선 x. 포인터와 키보드가 같은 상태를 공유한다.
  const [active, setActive] = useState<number | null>(null);

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
  // 결측 안내선은 결측이 소수일 때만 의미가 있다(아래 결측 블록의 주석 참고).
  const missingCols = xs.filter((_, i) => series.some((s) => !numeric(s.values[i]))).length;
  const guides = missingCols * 4 <= xs.length;

  const columnAt = (i: number): Column => ({
    label: xs[i],
    rows: series.map((s, si) => {
      const v = s.values[i];
      return {
        name: s.name,
        color: colorOf(si),
        text: numeric(v) ? fmtTick(v) : "관측 없음",
        missing: !numeric(v),
      };
    }),
  });
  const speak = (i: number) =>
    `${xs[i]} · ${columnAt(i)
      .rows.map((r) => `${r.name} ${r.text}`)
      .join(", ")}`;

  // viewBox 사용자 단위 → 컨테이너 기준 px. 툴팁은 DOM에 뜨므로 배율을 넘어와야 한다.
  const project = (ux: number, uy: number) => {
    const svg = svgRef.current;
    const box = tip.containerRef.current;
    if (!svg || !box) return null;
    const r = svg.getBoundingClientRect();
    const b = box.getBoundingClientRect();
    if (!r.width) return null;
    const k = r.width / W;
    return { left: r.left - b.left + ux * k, top: r.top - b.top + uy * k, k, rect: r, boxRect: b };
  };

  // 포인터 y는 그대로 쓰고(자연스럽다), 키보드에는 그 x에서 **가장 위 관측값**을 준다.
  const openAt = (i: number, clientY?: number) => {
    const p = project(x(i), 0);
    if (!p) return;
    setActive(i);
    let topPx: number;
    if (typeof clientY === "number") {
      topPx = clientY - p.boxRect.top;
    } else {
      const highest = Math.min(...series.map((s) => (numeric(s.values[i]) ? y(s.values[i] as number) : Infinity)));
      topPx = p.rect.top - p.boxRect.top + (Number.isFinite(highest) ? highest : padT) * p.k;
    }
    tip.showAt(p.left, topPx, columnAt(i));
  };

  const close = () => {
    setActive(null);
    tip.hide();
  };

  const nearest = (clientX: number): number | null => {
    const p = project(0, 0);
    if (!p) return null;
    if (xs.length === 1) return 0;
    const ux = (clientX - p.rect.left) / p.k;
    const step = innerW / (xs.length - 1);
    return Math.min(xs.length - 1, Math.max(0, Math.round((ux - padL) / step)));
  };

  const onKey = (e: KeyboardEvent) => {
    const cur = active ?? 0;
    const go = (i: number) => {
      e.preventDefault();
      openAt(Math.min(xs.length - 1, Math.max(0, i)));
    };
    if (e.key === "ArrowRight") go(cur + 1);
    else if (e.key === "ArrowLeft") go(cur - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(xs.length - 1);
    else if (e.key === "Escape") close();
  };

  return (
    <div className="relative" ref={tip.containerRef}>
      <svg
        ref={svgRef}
        // 인터랙션 게이트(`smoke-tabs.mjs`)가 "선 차트인데 크로스헤어가 없다"를 세는 표식.
        // 히트 타깃 자체로 세면 없는 것을 셀 수 없어서 순환이 된다.
        data-plot="line"
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ height: "auto", display: "block" }}
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
              {/* 점은 마크일 뿐이고 히트 타깃이 아니다 — 값은 크로스헤어 툴팁이 낸다.
                  예전에는 여기 `<title>`을 달았는데, 6px 원이 히트 타깃이라 104점 차트에서는
                  조준해야 잡혔고 키보드로는 닿을 방법이 없었다. */}
              {vals.map((v, i) =>
                numeric(v) ? (
                  <circle key={i} cx={x(i)} cy={y(v)} r={3} fill="var(--surface)" stroke={color} strokeWidth={1.5} />
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
            않았다(2026-07-30 육안 검사). 축 밖의 마크는 값이 될 수 없다.

            🔴 안내선은 **결측이 예외일 때만** 그린다. 안내선의 일은 축 아래 ×를 자기 열과
            잇는 것인데, 결측이 다수가 되면 세로선이 플롯을 덮어 배경 해치가 된다 — 104점
            중 91점이 결측인 차트에서 실제로 그랬고, 증거 레이어 위에 텍스처를 얹지 않는다는
            DESIGN §4에 걸린다. 게다가 크로스헤어가 같은 시각 언어(세로선)를 쓰기 때문에
            선이 많아지면 **지금 읽고 있는 열이 어느 것인지** 구별되지 않는다.
            결측 자체는 침묵하지 않는다: ×는 전부 남고 개수는 아래 문장이 말한다. */}
        {xs.map((lbl, i) => {
          const gone = series.filter((s) => !numeric(s.values[i]));
          if (gone.length === 0) return null;
          return (
            <g key={`m-${i}`}>
              {guides && (
                <line
                  x1={x(i)}
                  y1={padT}
                  x2={x(i)}
                  y2={padT + innerH}
                  stroke="var(--hairline)"
                  strokeWidth={1}
                />
              )}
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

        {/* 크로스헤어 — 크롬이므로 시리즈 색을 쓰지 않고 격자보다 한 단계 진한 토큰을 쓴다
            (격자와 같은 색이면 어느 선이 지금 읽히는 선인지 구별되지 않는다).
            강조 점은 마크 위에 덮어 그린다: 어느 값을 읽고 있는지가 툴팁 밖에서도 보여야
            한다(키보드 포커스의 시각 표시도 이것이 겸한다). */}
        {active !== null && (
          <g pointerEvents="none">
            <line
              x1={x(active)}
              y1={padT}
              x2={x(active)}
              y2={padT + innerH}
              stroke="var(--baseline)"
              strokeWidth={1}
            />
            {series.map((s, si) =>
              numeric(s.values[active]) ? (
                <circle
                  key={s.name}
                  cx={x(active)}
                  cy={y(s.values[active] as number)}
                  r={4.5}
                  fill={colorOf(si)}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
              ) : null,
            )}
          </g>
        )}

        {/* 히트 타깃은 플롯 전면이다. 마크(6px)가 아니라 이 면이 받아서 가장 가까운 x로
            스냅한다 — 그래서 점이 촘촘해도 조준할 필요가 없다(DESIGN §7 "히트 타깃은
            마크보다 크게"). 키보드는 좌우 화살표로 같은 자리를 지난다. */}
        <rect
          x={padL}
          y={padT}
          width={innerW}
          height={innerH}
          fill="transparent"
          tabIndex={0}
          role="slider"
          aria-orientation="horizontal"
          aria-label="지점별 값 보기 (좌우 화살표로 이동)"
          aria-valuemin={0}
          aria-valuemax={Math.max(0, xs.length - 1)}
          aria-valuenow={active ?? 0}
          aria-valuetext={speak(active ?? 0)}
          style={{ cursor: "crosshair", outline: "none" }}
          onPointerMove={(e) => {
            const i = nearest(e.clientX);
            if (i !== null) openAt(i, e.clientY);
          }}
          onPointerLeave={close}
          onFocus={() => openAt(active ?? 0)}
          onBlur={close}
          onKeyDown={onKey}
        />
      </svg>

      {/* 통합 툴팁 — 같은 x의 값을 한 자리에 모은다. 시리즈마다 따로 띄우면 두 선을
          비교할 수 없고, 비교가 이 차트의 질문이다. 결측도 같은 목록에서 말한다. */}
      <ChartTooltip tip={tip}>{tip.datum ? <ColumnBody col={tip.datum} /> : null}</ChartTooltip>
    </div>
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

      {/* 표 뷰 — 툴팁이 값의 유일한 경로가 되지 않게(dataviz 비협상 항목).
          크로스헤어가 붙기 전에는 값에 닿는 길이 점 위의 `<title>` 하나뿐이었다. */}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-[var(--muted)] transition-colors duration-150 ease-out hover:text-[var(--ink-secondary)]">
          표로 보기
        </summary>
        <div className="mt-2 max-h-72 overflow-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--hairline)] text-[var(--muted)]">
                <th scope="col" className="py-1 pr-3 font-medium">
                  지점
                </th>
                {series.map((s) => (
                  <th key={s.name} scope="col" className="py-1 pr-3 text-right font-medium">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {xs.map((lbl, i) => (
                <tr key={lbl} className="border-b border-[var(--hairline)]">
                  <th scope="row" className="py-1 pr-3 font-normal text-[var(--ink-secondary)]">
                    {lbl}
                  </th>
                  {series.map((s) => {
                    const v = s.values[i];
                    return (
                      <td
                        key={s.name}
                        className={`py-1 pr-3 text-right tabular-nums ${
                          numeric(v) ? "text-[var(--ink)]" : "text-[var(--muted)]"
                        }`}
                      >
                        {numeric(v) ? fmtTick(v) : "관측 없음"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
