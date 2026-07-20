"use client";

import { useMemo, useState } from "react";
import type { LeadLagTunableData, TunableData, WhitespaceTunableData } from "@/lib/report";

// Interactive threshold views: the report ships raw data + knobs; we recompute the
// derived view client-side as the viewer turns each knob (static-first, no backend).
// 기준 원장 §2.1: 값=도메인 소유자.
export function Tunable({ data }: { data: TunableData }) {
  if (data.view === "leadlag") return <LeadLag data={data} />;
  return <Whitespace data={data} />;
}

// view=whitespace — a gap map: proven markets (≥threshold roster acts) × top acts,
// empty cell = greenfield the act hasn't reached.
function Whitespace({ data }: { data: WhitespaceTunableData }) {
  const knob = data.knobs?.[0];
  const [threshold, setThreshold] = useState<number>(knob?.default ?? 2);
  const { matrix } = data;
  const topRows = data.topRows ?? 10;

  const { provenIdx, rowIdx } = useMemo(() => {
    const nCols = matrix.cols.length;
    // 시장 강도 = 열별 진입 팀 수(전체 로스터) → 개척 시장 = 강도 ≥ 임계
    const strength = Array.from({ length: nCols }, (_, j) =>
      matrix.cells.reduce((n, row) => n + (row[j] != null ? 1 : 0), 0),
    );
    const proven = Array.from({ length: nCols }, (_, j) => j).filter(
      (j) => strength[j] >= threshold,
    );
    // reach = 행별 진입 시장 수 → 상위 팀 선택(표시)
    const reach = matrix.rows.map((_, i) =>
      matrix.cols.reduce((n, _c, j) => n + (matrix.cells[i][j] != null ? 1 : 0), 0),
    );
    const rows = matrix.rows
      .map((_, i) => i)
      .sort((a, b) => reach[b] - reach[a] || matrix.rows[a].localeCompare(matrix.rows[b]))
      .slice(0, topRows);
    return { provenIdx: proven, rowIdx: rows };
  }, [matrix, threshold, topRows]);

  const topGap = rowIdx.length
    ? provenIdx.filter((j) => matrix.cells[rowIdx[0]][j] == null).length
    : 0;
  const gapBox = {
    background: "color-mix(in srgb, var(--good) 16%, transparent)",
    border: "1px solid var(--good)",
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs">
        <label htmlFor="tunable-knob" className="text-[var(--ink-secondary)]">
          {knob?.label ?? "기준"}
        </label>
        <input
          id="tunable-knob"
          type="range"
          min={knob?.min ?? 1}
          max={knob?.max ?? 6}
          step={knob?.step ?? 1}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          className="accent-[var(--series)]"
          aria-label={knob?.label ?? "기준"}
        />
        <span className="tabular-nums font-medium">{threshold}팀+</span>
        <span className="text-[var(--muted)]">
          개척 시장 <b className="tabular-nums text-[var(--ink)]">{provenIdx.length}</b>개국
          {rowIdx.length ? ` · ${matrix.rows[rowIdx[0]]} 미개척 ${topGap}개국` : ""}
        </span>
      </div>

      {provenIdx.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">이 기준에서는 개척 시장 없음. 슬라이더를 낮추면 후보 표시</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="border-separate" style={{ borderSpacing: 2 }}>
            <thead>
              <tr>
                <th />
                {provenIdx.map((j) => (
                  <th
                    key={j}
                    className="px-2 pb-1 text-center text-xs font-normal text-[var(--muted)]"
                  >
                    {matrix.cols[j]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowIdx.map((i) => (
                <tr key={i}>
                  <td className="pr-3">
                    <div
                      className="max-w-[160px] truncate text-xs text-[var(--ink-secondary)]"
                      title={matrix.rows[i]}
                    >
                      {matrix.rows[i]}
                    </div>
                  </td>
                  {provenIdx.map((j) => {
                    const v = matrix.cells[i][j];
                    const label = `${matrix.rows[i]} · ${matrix.cols[j]}`;
                    return v == null ? (
                      <td key={j} style={{ width: 40, height: 26 }} title={`${label}: 미개척`}>
                        <div className="h-6 rounded" style={gapBox} />
                      </td>
                    ) : (
                      <td key={j} style={{ width: 40, height: 26 }} title={`${label}: ${v}위`}>
                        <div
                          className="flex h-6 items-center justify-center rounded text-xs tabular-nums text-[var(--muted)]"
                          style={{ background: "var(--hairline)" }}
                        >
                          {v}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted)]">
        <span className="inline-block h-3 w-3 rounded" style={gapBox} />
        <span>미개척</span>
        <span
          className="ml-2 inline-block h-3 w-3 rounded"
          style={{ background: "var(--hairline)" }}
        />
        <span>진입(숫자=순위)</span>
      </div>

      {data.note && (
        <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>
      )}
    </div>
  );
}

// view=leadlag — θ 슬라이더: 브리지 RULES §3 온셋 정의 그대로 클라이언트 재계산.
// 소셜 온셋 = 첫 게시수 ≥ θ_social · 차트 온셋 = 첫 순위 ≤ θ_rank · lead = 차트 − 소셜(일).
const DAY_MS = 86400000;

function LeadLag({ data }: { data: LeadLagTunableData }) {
  const kS = data.knobs.find((k) => k.key === "theta_social");
  const kR = data.knobs.find((k) => k.key === "theta_rank");
  const [thetaS, setThetaS] = useState<number>(kS?.default ?? 1);
  const [thetaR, setThetaR] = useState<number>(kR?.default ?? 200);

  const rows = useMemo(() => {
    const out: { key: string; klass: string; lead: number | null }[] = [];
    for (const [key, s] of Object.entries(data.series)) {
      let sOnset: string | null = null;
      if (s.social)
        for (let i = 0; i < data.socialDates.length; i++)
          if ((s.social[i] ?? 0) >= thetaS) {
            sOnset = data.socialDates[i];
            break;
          }
      let cOnset: string | null = null;
      if (s.chart)
        for (let i = 0; i < data.chartDates.length; i++) {
          const v = s.chart[i];
          if (v != null && v <= thetaR) {
            cOnset = data.chartDates[i];
            break;
          }
        }
      if (!sOnset && !cOnset) continue;
      if (sOnset && cOnset) {
        const lead = Math.round((Date.parse(cOnset) - Date.parse(sOnset)) / DAY_MS);
        out.push({ key, klass: lead > 0 ? "social-led" : lead < 0 ? "chart-led" : "coincident", lead });
      } else {
        out.push({ key, klass: sOnset ? "social-only" : "chart-only", lead: null });
      }
    }
    return out;
  }, [data, thetaS, thetaR]);

  const count = (c: string) => rows.filter((r) => r.klass === c).length;
  const joined = rows
    .filter((r) => r.lead != null)
    .sort((a, b) => (b.lead ?? 0) - (a.lead ?? 0) || a.key.localeCompare(b.key));
  const maxAbs = Math.max(1, ...joined.map((r) => Math.abs(r.lead ?? 0)));

  function Slider({
    knob,
    value,
    onChange,
  }: {
    knob: typeof kS;
    value: number;
    onChange: (v: number) => void;
  }) {
    return (
      <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
        <span>{knob?.label ?? "기준"}</span>
        <input
          type="range"
          min={knob?.min ?? 1}
          max={knob?.max ?? 200}
          step={knob?.step ?? 1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="accent-[var(--series)]"
          aria-label={knob?.label ?? "기준"}
        />
        <b className="w-8 tabular-nums text-[var(--ink)]">{value}</b>
      </label>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Slider knob={kS} value={thetaS} onChange={setThetaS} />
        <Slider knob={kR} value={thetaR} onChange={setThetaR} />
      </div>
      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-[var(--ink-secondary)]">
        <span>소셜 선행 <b className="text-[var(--ink)]">{count("social-led")}</b></span>
        <span>동시 <b className="text-[var(--ink)]">{count("coincident")}</b></span>
        <span>차트 선행 <b className="text-[var(--ink)]">{count("chart-led")}</b></span>
        <span>소셜-온리 <b className="text-[var(--ink)]">{count("social-only")}</b></span>
        <span>차트-온리 <b className="text-[var(--ink)]">{count("chart-only")}</b></span>
      </div>

      {joined.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">이 기준에서는 소셜·차트 상승 시작이 모두 잡힌 팀 없음</p>
      ) : (
        <div className="space-y-1">
          {joined.map((r) => {
            const lead = r.lead ?? 0;
            const w = (Math.abs(lead) / maxAbs) * 50;
            return (
              <div key={r.key} className="flex items-center gap-2 text-xs" title={`${r.key}: ${lead > 0 ? "+" : ""}${lead}일`}>
                <div className="w-28 truncate text-right text-[var(--ink-secondary)]" title={r.key}>
                  {r.key}
                </div>
                <div className="relative h-4 flex-1">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--baseline)]" />
                  <div
                    className="absolute inset-y-0.5 rounded-sm"
                    style={
                      lead >= 0
                        ? { left: "50%", width: `${w}%`, background: "var(--series)" }
                        : { right: "50%", width: `${w}%`, background: "var(--series2)" }
                    }
                  />
                </div>
                <div className="w-10 tabular-nums text-[var(--muted)]">
                  {lead > 0 ? "+" : ""}
                  {lead}일
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted)]">
        <span className="inline-block h-3 w-3 rounded" style={{ background: "var(--series)" }} />
        <span>양수 = 소셜이 먼저</span>
        <span className="ml-2 inline-block h-3 w-3 rounded" style={{ background: "var(--series2)" }} />
        <span>음수 = 차트가 먼저</span>
      </div>
      {data.note && <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>}
    </div>
  );
}
