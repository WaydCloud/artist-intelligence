"use client";

import { useMemo } from "react";
import type { LeadLagTunableData, TunableData, WhitespaceTunableData } from "@/lib/report";
import { scopeOf, useKnob } from "@/lib/knobs";
import { CriteriaActions, type CriteriaItem } from "./CriteriaActions";

// Interactive threshold views: the report ships raw data + knobs; we recompute the
// derived view client-side as the viewer turns each knob (static-first, no backend).
// 기준 원장 §2.1: 값=도메인 소유자 — 노출(슬라이더)·반박(재계산)·전달(CriteriaActions).
export function Tunable({ data, title }: { data: TunableData; title?: string }) {
  if (data.view === "leadlag") return <LeadLag data={data} title={title} />;
  return <Whitespace data={data} title={title} />;
}

// view=whitespace — a gap map: proven markets (≥threshold roster acts) × top acts,
// empty cell = greenfield the act hasn't reached.
function Whitespace({ data, title }: { data: WhitespaceTunableData; title?: string }) {
  const knob = data.knobs?.[0];
  const scope = scopeOf("whitespace", title);
  const [threshold, setThreshold] = useKnob(scope, knob?.key ?? "threshold", knob?.default ?? 2);
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

      <CriteriaActions
        title={title ?? "개척 시장"}
        items={[
          {
            label: knob?.label ?? "기준",
            from: String(knob?.default ?? 2),
            to: String(threshold),
            changed: threshold !== (knob?.default ?? 2),
          },
        ]}
        summary={`개척 시장 ${provenIdx.length}개국`}
      />
    </div>
  );
}

// view=leadlag — θ 슬라이더: 브리지 RULES §3 온셋 정의 그대로 클라이언트 재계산.
// 소셜 온셋 = 첫 게시수 ≥ θ_social · 차트 온셋 = 첫 순위 ≤ θ_rank · lead = 차트 − 소셜(일).
const DAY_MS = 86400000;

function LeadLag({ data, title }: { data: LeadLagTunableData; title?: string }) {
  const kS = data.knobs.find((k) => k.key === "theta_social");
  const kR = data.knobs.find((k) => k.key === "theta_rank");
  const kP = data.knobs.find((k) => k.key === "min_posts");
  const kC = data.knobs.find((k) => k.key === "exclude_censored");
  const scope = scopeOf("leadlag", title);
  const [thetaS, setThetaS] = useKnob(scope, "theta_social", kS?.default ?? 1);
  const [thetaR, setThetaR] = useKnob(scope, "theta_rank", kR?.default ?? 200);
  const [minPosts, setMinPosts] = useKnob(scope, "min_posts", kP?.default ?? 1);
  const [censoredFlag, setCensoredFlag] = useKnob(scope, "exclude_censored", kC?.default ? 1 : 0);
  const hideCensored = censoredFlag === 1;

  const rows = useMemo(() => {
    const out: {
      key: string;
      klass: string;
      lead: number | null;
      posts: number;
      censored: boolean;
      weak: boolean;
    }[] = [];
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
      const ev = data.evidence?.[key];
      const posts = ev?.posts ?? 0;
      // 좌측 절단은 차트 온셋이 기본 기준일 때만 유효한 판정 — θ_rank를 조이면 온셋이 뒤로 밀린다
      const censored = Boolean(ev?.censored) && thetaR >= (kR?.default ?? thetaR);
      const weak = Boolean(data.evidence) && posts < minPosts;
      if (hideCensored && censored) continue;
      if (sOnset && cOnset) {
        const lead = Math.round((Date.parse(cOnset) - Date.parse(sOnset)) / DAY_MS);
        out.push({
          key,
          klass: lead > 0 ? "social-led" : lead < 0 ? "chart-led" : "coincident",
          lead,
          posts,
          censored,
          weak,
        });
      } else {
        out.push({ key, klass: sOnset ? "social-only" : "chart-only", lead: null, posts, censored, weak });
      }
    }
    return out;
  }, [data, thetaS, thetaR, minPosts, hideCensored, kR]);

  const count = (c: string) => rows.filter((r) => r.klass === c).length;
  // 판정 가능 = 표본 하한 통과 + 비검열. 나머지는 지우지 않고 흐리게 표시(RULES §3.1: 행 삭제 금지)
  const decidable = rows.filter((r) => r.klass === "social-led" && !r.weak && !r.censored).length;
  const joined = rows
    .filter((r) => r.lead != null)
    .sort((a, b) => (b.lead ?? 0) - (a.lead ?? 0) || a.key.localeCompare(b.key));
  const maxAbs = Math.max(1, ...joined.map((r) => Math.abs(r.lead ?? 0)));

  const onOff = (v: number) => (v === 1 ? "켜기" : "끄기");
  const criteriaItems: CriteriaItem[] = [
    kS && { label: kS.label, from: String(kS.default), to: String(thetaS), changed: thetaS !== kS.default },
    kR && { label: kR.label, from: String(kR.default), to: String(thetaR), changed: thetaR !== kR.default },
    kP && data.evidence
      ? { label: kP.label, from: String(kP.default), to: String(minPosts), changed: minPosts !== kP.default }
      : null,
    kC && data.evidence
      ? {
          label: kC.label,
          from: onOff(kC.default ? 1 : 0),
          to: onOff(censoredFlag),
          changed: censoredFlag !== (kC.default ? 1 : 0),
        }
      : null,
  ].filter(Boolean) as CriteriaItem[];

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
        {kP && data.evidence && <Slider knob={kP} value={minPosts} onChange={setMinPosts} />}
        {kC && data.evidence && (
          <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
            <input
              type="checkbox"
              checked={hideCensored}
              onChange={(e) => setCensoredFlag(e.target.checked ? 1 : 0)}
              className="accent-[var(--series)]"
            />
            <span>{kC.label}</span>
          </label>
        )}
      </div>
      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-[var(--ink-secondary)]">
        <span>소셜 선행 <b className="text-[var(--ink)]">{count("social-led")}</b></span>
        {data.evidence && (
          <span title="표본 하한 통과 + 차트 온셋 비검열">
            그중 판정 가능 <b className="text-[var(--ink)]">{decidable}</b>
          </span>
        )}
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
            // 판정 근거가 약한 행은 지우지 않고 흐리게 — 도구가 대신 결론내지 않는다
            const held = r.weak || r.censored;
            const why = [
              r.weak ? `표본 ${r.posts}건 < ${minPosts}건` : null,
              r.censored ? "차트 온셋 좌측절단(수집 개시일과 동일)" : null,
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <div
                key={r.key}
                className={`flex items-center gap-2 text-xs ${held ? "opacity-45" : ""}`}
                title={`${r.key}: ${lead > 0 ? "+" : ""}${lead}일${why ? ` — 판단 보류: ${why}` : ""}`}
              >
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
                <div className="w-4 text-center text-[var(--muted)]" aria-hidden={!held}>
                  {held ? "ⓘ" : ""}
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
        {data.evidence && <span className="ml-2">ⓘ 흐린 행 = 판단 보류(표본 부족 또는 좌측 절단) · 마우스를 올리면 사유</span>}
      </div>
      {data.note && <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>}

      <CriteriaActions
        title={title ?? "선행 판별"}
        items={criteriaItems}
        summary={
          `소셜 선행 ${count("social-led")}` +
          (data.evidence ? ` · 그중 판정 가능 ${decidable}` : "") +
          ` · 동시 ${count("coincident")} · 차트 선행 ${count("chart-led")}` +
          ` · 소셜-온리 ${count("social-only")} · 차트-온리 ${count("chart-only")}`
        }
      />
    </div>
  );
}
