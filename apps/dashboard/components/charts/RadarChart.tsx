"use client";

import { useMemo } from "react";
import { Group } from "@visx/group";
import { LinePath } from "@visx/shape";
import { scaleLinear } from "@visx/scale";
import type { RadarData } from "@/lib/report";
import { ChartTooltip, useChartTooltip } from "./ChartTooltip";

// 요약 도형(R2) — 축 N개의 **비교 위치**를 한 폴리곤으로.
//
// 왜 이 형태인가: FM 데이터 허브가 고장 났을 때 유일하게 하중받던 요소가 맨 앞의 요약
// 도형 하나였다(REFERENCE §2, 독립 3근거). 그리고 이 도형은 두 기제를 동시에 만족한다 —
// 기준 링과의 거리가 **비교 위치**(기제 ①)이고, 어떤 축은 링 밖 어떤 축은 링 안인 그림이
// **불일치**(기제 ②)다. 값 자체를 읽는 도형이 아니다.
//
// 시리즈는 하나뿐이고 기준 링은 크롬이라 범례가 없다(dataviz: 단일 시리즈는 범례 없음 —
// 제목이 무엇을 그렸는지 이미 말한다).
//
// 🔴 결측 규율(R6): `value: null`인 축에서 폴리곤을 **잇지 않는다**. 0으로 이으면 도형이
// "이 축에서 분포 최하위"라고 거짓말한다. 관측된 축의 **연속 구간마다 열린 선**을 따로
// 그리고, 결측 축은 스포크만 남겨 라벨에 사유를 붙인다.

// 축 라벨은 **좌우로** 길고 위아래로는 한 줄이다. 정사각 viewBox에 같은 여백을 주면
// 위아래 공백만 커지고 폴리곤은 작아진다 — 가로 여백을 크게, 세로를 작게 잡는다.
const W = 340;
const H = 300;
const CX = W / 2;
const CY = H / 2;
const PAD_X = 62;
const PAD_Y = 30;
const R = Math.min(CX - PAD_X, CY - PAD_Y);

type Pt = { x: number; y: number };

export function RadarChart({ data }: { data: RadarData }) {
  const axes = data.axes ?? [];
  const max = data.max ?? 100;
  const tip = useChartTooltip<{ name: string; body: string[] }>();

  const geo = useMemo(() => {
    const r = scaleLinear<number>({ domain: [0, max], range: [0, R] });
    // 12시에서 시작해 시계방향. 축 순서는 리포트가 정한 순서를 그대로 쓴다(재정렬 금지 —
    // 도형의 모양이 곧 지문이므로 순서가 바뀌면 같은 데이터가 다른 그림이 된다).
    const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(1, axes.length);
    const at = (i: number, radius: number): Pt => ({
      x: Math.cos(angle(i)) * radius,
      y: Math.sin(angle(i)) * radius,
    });
    return { r, angle, at };
  }, [axes.length, max]);

  if (axes.length < 3) return <p className="text-sm text-[var(--muted)]">축 3개 미만은 요약 도형을 만들 수 없음</p>;

  const observed = axes.filter((a) => typeof a.value === "number");
  if (observed.length === 0)
    return (
      <p className="text-sm text-[var(--ink-secondary)]">
        관측 없음 · 이 요약이 딛고 설 축이 아직 채워지지 않음
      </p>
    );

  // 관측된 축의 **연속 구간**(원형이므로 마지막→첫 축도 이어질 수 있다)
  const runs: number[][] = [];
  {
    let run: number[] = [];
    for (let i = 0; i < axes.length; i++) {
      if (typeof axes[i].value === "number") run.push(i);
      else {
        if (run.length) runs.push(run);
        run = [];
      }
    }
    if (run.length) runs.push(run);
    // 전 축 관측 → 닫힌 폴리곤. 첫·마지막 구간이 맞닿으면 하나로 합친다.
    if (runs.length > 1 && runs[0][0] === 0 && runs[runs.length - 1].at(-1) === axes.length - 1) {
      const last = runs.pop()!;
      runs[0] = [...last, ...runs[0]];
    }
  }
  const closed = runs.length === 1 && runs[0].length === axes.length;

  const baseline = typeof data.baseline === "number" ? data.baseline : null;
  // 기준 링과 겹치는 격자 링은 그리지 않는다. 겹치면 **기준선이 격자처럼 읽혀** 이 도형의
  // 핵심(비교 위치)이 사라진다 — 실측된 결함이다(2026-07-30 육안 검사).
  const ringVals = [0.25, 0.5, 0.75, 1]
    .map((f) => f * max)
    .filter((v) => baseline === null || Math.abs(v - baseline) > max * 0.02);

  const fmt = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

  return (
    <div className="relative" ref={tip.containerRef}>
      <svg
        // 인터랙션 게이트(`smoke-tabs.mjs`)의 표식 — 마크 툴팁이 빠졌는지 센다.
        data-plot="radar"
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ height: "auto", maxWidth: 440, margin: "0 auto", display: "block", overflow: "visible" }}
        role="img"
        aria-label={`요약 도형 · ${axes.map((a) => a.name).join(", ")}`}
      >
        <Group left={CX} top={CY}>
          {/* 격자 — 실선 헤어라인, 배경 쪽으로 물러난다 (점선 금지) */}
          {ringVals.map((rv) => (
            <polygon
              key={rv}
              points={axes.map((_, i) => { const p = geo.at(i, geo.r(rv)); return `${p.x},${p.y}`; }).join(" ")}
              fill="none"
              stroke="var(--hairline)"
              strokeWidth={1}
            />
          ))}
          {axes.map((_, i) => {
            const p = geo.at(i, R);
            return <line key={i} x1={0} y1={0} x2={p.x} y2={p.y} stroke="var(--hairline)" strokeWidth={1} />;
          })}

          {/* 기준 링 — 비교 대상(코호트 중앙값). 시리즈가 아니라 크롬이라 색을 쓰지 않는다.
              🔴 **직접 라벨을 붙인다.** 캡션에만 설명을 두면 링이 격자 중 하나로 읽히고,
              그러면 "선 밖이 코호트보다 높은 쪽"이라는 이 도형의 유일한 판독 규칙이 사라진다.
              (dataviz: 직접 라벨이 격자보다 먼저다.) */}
          {/* 눈금 라벨 — 축 **사이** 방향, 그중 폴리곤이 가장 안쪽으로 들어온 틈에 적는다.
              축 위에 적으면 꼭짓점·축 라벨과 부딪히고, 고정된 방향에 적으면 데이터에 따라
              선 위에 얹힌다(실측 결함). 그래도 겹칠 수 있으니 표면색 헤일로를 두른다 —
              마크의 표면 링과 같은 기제이고, 증거 가독성이 최우선이다(DESIGN §4). */}
          {(() => {
            const rOf = (i: number) => (typeof axes[i].value === "number" ? (axes[i].value as number) : 0);
            let gap = 0;
            for (let i = 1; i < axes.length; i++) {
              const cur = rOf(i) + rOf((i + 1) % axes.length);
              if (cur < rOf(gap) + rOf((gap + 1) % axes.length)) gap = i;
            }
            const a = geo.angle(gap) + Math.PI / axes.length;
            const ticks: [number, string][] = [[max, fmt(max)]];
            if (baseline !== null) ticks.push([baseline, `기준 ${fmt(baseline)}`]);
            return ticks.map(([v, label]) => (
              <text
                key={label}
                x={Math.cos(a) * geo.r(v)}
                y={Math.sin(a) * geo.r(v)}
                dy={-3}
                fontSize={9}
                fill="var(--muted)"
                stroke="var(--surface)"
                strokeWidth={3}
                paintOrder="stroke"
                textAnchor="middle"
              >
                {label}
              </text>
            ));
          })()}

          {/* 면 — 닫힌 폴리곤일 때만 채운다. 결측이 있으면 면적이 거짓이 되므로 선만 그린다. */}
          {closed && (
            <polygon
              points={runs[0].map((i) => { const p = geo.at(i, geo.r(axes[i].value as number)); return `${p.x},${p.y}`; }).join(" ")}
              fill="var(--series)"
              fillOpacity={0.1}
            />
          )}

          {/* 기준 링은 면 **위**에 그린다 — 아래로 내리면 10% 워시에 덮여 흐려지고,
              그러면 "선 밖이 코호트보다 높은 쪽"이라는 판독 규칙이 사라진다.
              시리즈가 아니라 크롬이므로 색을 쓰지 않는다(범례를 요구하지 않는 이유). */}
          {baseline !== null && (
            <polygon
              points={axes.map((_, i) => { const p = geo.at(i, geo.r(baseline)); return `${p.x},${p.y}`; }).join(" ")}
              fill="none"
              stroke="var(--baseline)"
              strokeWidth={2}
            />
          )}

          {runs.map((run, ri) => (
            <LinePath<number>
              key={ri}
              data={closed ? [...run, run[0]] : run}
              x={(i) => geo.at(i, geo.r(axes[i].value as number)).x}
              y={(i) => geo.at(i, geo.r(axes[i].value as number)).y}
              stroke="var(--series)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              fill="none"
            />
          ))}

          {/* 마크 + 히트 타깃. 점은 표면색 링을 둘러 격자 위에서도 읽힌다. */}
          {axes.map((a, i) => {
            if (typeof a.value !== "number") return null;
            const p = geo.at(i, geo.r(a.value));
            const body = [
              `${data.scaleNote ?? "값"} ${fmt(a.value)}`,
              ...(typeof a.raw === "number" ? [`원값 ${fmt(a.raw)}${a.rawUnit ? ` ${a.rawUnit}` : ""}`] : []),
              ...(typeof a.sample === "number" ? [`표본 ${a.sample}곡`] : []),
              ...(baseline !== null ? [`기준 ${fmt(baseline)}${data.baselineLabel ? ` (${data.baselineLabel})` : ""}`] : []),
            ];
            return (
              <Group key={a.name} left={p.x} top={p.y}>
                <circle r={4.5} fill="var(--series)" stroke="var(--surface)" strokeWidth={2} />
                {/* 투명 히트 영역 — 마크보다 크게(pinpoint 금지) */}
                <circle
                  r={13}
                  fill="transparent"
                  tabIndex={0}
                  role="button"
                  aria-label={`${a.name}: ${body.join(", ")}`}
                  onPointerMove={(e) => tip.show(e, { name: a.name, body })}
                  onPointerLeave={tip.hide}
                  onFocus={(e) => tip.show(e, { name: a.name, body })}
                  onBlur={tip.hide}
                  style={{ cursor: "pointer", outline: "none" }}
                />
              </Group>
            );
          })}

          {/* 축 라벨. 텍스트는 시리즈 색을 입지 않는다(dataviz: text wears text tokens). */}
          {axes.map((a, i) => {
            const p = geo.at(i, R + 15);
            const anchor = p.x > 6 ? "start" : p.x < -6 ? "end" : "middle";
            const gone = typeof a.value !== "number";
            return (
              <g key={`l-${a.name}`}>
                <text
                  x={p.x}
                  y={p.y}
                  textAnchor={anchor}
                  dominantBaseline="middle"
                  fontSize={10}
                  fill={gone ? "var(--muted)" : "var(--ink-secondary)"}
                >
                  {a.name}
                </text>
                {/* 결측은 침묵하지 않는다 — 축 라벨 자리에서 바로 말한다(R6) */}
                {gone && (
                  <text
                    x={p.x}
                    y={p.y + 11}
                    textAnchor={anchor}
                    dominantBaseline="middle"
                    fontSize={9}
                    fill="var(--muted)"
                  >
                    관측 없음
                  </text>
                )}
              </g>
            );
          })}
        </Group>
      </svg>

      <ChartTooltip tip={tip}>
        {tip.datum && (
          <>
            {/* 값이 앞, 라벨이 뒤 — 읽는 사람은 축을 이미 알고 숫자를 원한다 */}
            <div className="font-medium tabular-nums text-[var(--ink)]">{tip.datum.body[0]}</div>
            <div className="mt-0.5 text-[var(--ink-secondary)]">{tip.datum.name}</div>
            {tip.datum.body.slice(1).map((l) => (
              <div key={l} className="tabular-nums text-[var(--muted)]">
                {l}
              </div>
            ))}
          </>
        )}
      </ChartTooltip>

      {/* 스케일 설명은 도형의 필수 동반자다. 없으면 폴리곤은 판독 불가다. */}
      {(data.scaleNote || data.baselineLabel) && (
        <p className="mt-3 text-center text-xs leading-relaxed text-[var(--muted)]">
          {data.scaleNote}
          {baseline !== null && data.baselineLabel && ` · 기준선 ${fmt(baseline)} = ${data.baselineLabel}`}
        </p>
      )}

      {/* 표 뷰 — 툴팁이 값의 유일한 경로가 되지 않게(dataviz 비협상 항목) */}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-[var(--muted)] transition-colors duration-150 ease-out hover:text-[var(--ink-secondary)]">
          표로 보기
        </summary>
        <table className="mt-2 w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--hairline)] text-[var(--muted)]">
              <th className="py-1 pr-3 font-medium">축</th>
              <th className="py-1 pr-3 text-right font-medium">값</th>
              <th className="py-1 pr-3 text-right font-medium">원값</th>
              <th className="py-1 text-right font-medium">표본</th>
            </tr>
          </thead>
          <tbody>
            {axes.map((a) => (
              <tr key={`t-${a.name}`} className="border-b border-[var(--hairline)]">
                <td className="py-1 pr-3 text-[var(--ink-secondary)]">
                  {a.name}
                  {a.definition && <span className="block text-[var(--muted)]">{a.definition}</span>}
                </td>
                <td className="py-1 pr-3 text-right tabular-nums text-[var(--ink)]">
                  {typeof a.value === "number" ? fmt(a.value) : "관측 없음"}
                </td>
                <td className="py-1 pr-3 text-right tabular-nums text-[var(--ink-secondary)]">
                  {typeof a.raw === "number" ? `${fmt(a.raw)}${a.rawUnit ? ` ${a.rawUnit}` : ""}` : "·"}
                </td>
                <td className="py-1 text-right tabular-nums text-[var(--muted)]">
                  {typeof a.sample === "number" ? a.sample : "·"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {axes.some((a) => a.missingReason) && (
          <ul className="mt-2 space-y-1 text-[var(--muted)]">
            {axes
              .filter((a) => a.missingReason)
              .map((a) => (
                <li key={`m-${a.name}`}>
                  {a.name}: {a.missingReason}
                </li>
              ))}
          </ul>
        )}
      </details>
    </div>
  );
}
