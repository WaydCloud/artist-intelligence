"use client";

import { useMemo, useState } from "react";
import {
  ADOPTION_MODE_KO,
  CASE_TYPE_KO,
  cellSortKey,
  isSurfaceable,
  type ChartFact,
  type Impulse,
  type LabsData,
  type TrajectoryCell,
} from "@/lib/labs";

/**
 * 임펄스 원장 뷰 (LABS).
 *
 * 🔴 이 화면은 **가설을 보여준다.** 채택 모듈 탭이 측정을 보여주는 것과 다르고,
 * 그래서 LABS로 갈라 둔다(DOMAIN §0 책임소재 불변식 — 도구는 증거에서 끝내고
 * 판단은 사람이 한다. 가설은 증거보다 한 칸 더 멀다).
 *
 * 규율 셋:
 *  ① **표면은 확실성 '중간' 이상만**(원장 스키마가 정한 것). 미만은 claim으로 올리지
 *     않되 **뺐다는 사실과 등급을 화면에 적는다** — 감추는 것과 안 싣는 것은 다르다.
 *  ② **등급은 항목마다 붙는다.** 페이지 상단 경고 하나로 뭉치면 링크로 특정 항목만
 *     공유될 때 경고가 따라가지 않는다.
 *  ③ **차트 사실과 서술 근거를 섞지 않는다.** 원장이 두 배열로 나눠 둔 이유가
 *     검증 방식이 다르기 때문이다. 링크된 것만 셀 아래에 붙이고 나머지는 따로 센다.
 */

/**
 * 🔴 **확실성을 색으로 그리지 않는다.** 처음엔 등급별로 색을 달리 줬는데 두 가지가
 * 어긋났다(DESIGN §7.5의 부류):
 *  ① 낮은 등급일수록 흐린 색이 되어 **가장 주의해야 할 항목이 가장 안 보였다.**
 *  ② '매우 높음'에 `--good`(초록)을 쓰니 확실성이 **좋음**으로 읽힌다. 확실성은
 *     좋고 나쁨이 아니라 이 문장을 얼마나 믿을 수 있는지다.
 * 등급은 낱말이 이미 말하므로 색을 얹지 않고, 전부 같은 가독 색으로 둔다.
 */
function CertaintyChip({ level, note }: { level: string; note?: string | null }) {
  return (
    <span className="inline-flex items-baseline gap-1 whitespace-nowrap text-[11px]">
      <span className="text-[var(--muted)]">확실성</span>
      <span className="text-[var(--ink-secondary)]">{level}</span>
      {note ? <span className="text-[var(--muted)]">({note})</span> : null}
    </span>
  );
}

/** 링크 글자가 어디로 가는지 말해야 한다. `출처 1`은 누른 뒤에야 알 수 있다(§6.1). */
function sourceLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function ChartFactLine({ fact }: { fact: ChartFact }) {
  // 차트 사실은 수치를 다툰다 — 그래서 수치를 다 보인다(순위·주차·진입일).
  const bits = [
    fact.entryDate ? `진입 ${fact.entryDate}` : null,
    fact.peakPosition ? `최고 ${fact.peakPosition}위` : null,
    fact.weeksOnChart ? `${fact.weeksOnChart}주` : null,
  ].filter(Boolean);
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs">
      <span className="text-[var(--ink-secondary)]">
        {fact.artist} - {fact.title}
      </span>
      <span className="tabular-nums text-[var(--muted)]">{bits.join(" · ")}</span>
      <span className="text-[11px] text-[var(--muted)]">{fact.chart}</span>
    </li>
  );
}

function Cell({ cell, facts }: { cell: TrajectoryCell; facts: ChartFact[] }) {
  const linked = facts.filter((f) => cell.chartEvidenceRefs.includes(f.ref));
  return (
    <li className="relative pl-6">
      <span
        aria-hidden
        className="absolute left-0 top-[0.45rem] h-1.5 w-1.5 rounded-full"
        style={{ background: "var(--baseline)" }}
      />
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-mono text-xs tabular-nums text-[var(--ink-secondary)]">{cell.date}</span>
        <span className="text-sm text-[var(--ink)]">{cell.cell}</span>
        <CertaintyChip level={cell.certainty} note={cell.certaintyNote} />
      </div>
      <p className="mt-1 text-sm leading-relaxed text-[var(--ink-secondary)]">{cell.evidence}</p>
      {linked.length > 0 ? (
        <div className="mt-2 border-l pl-3" style={{ borderColor: "var(--hairline)" }}>
          <div className="text-[11px] text-[var(--muted)]">붙어 있는 차트 사실</div>
          <ul className="mt-1 space-y-0.5">
            {linked.map((f) => (
              <ChartFactLine key={f.ref} fact={f} />
            ))}
          </ul>
        </div>
      ) : null}
      {cell.sources.length > 0 ? (
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
          {cell.sources.map((s) => (
            <a
              key={s}
              href={s}
              target="_blank"
              rel="noreferrer noopener"
              className="text-[11px] text-[var(--muted)] underline decoration-dotted underline-offset-2 transition-colors duration-200 ease-out hover:text-[var(--ink-secondary)]"
            >
              {sourceLabel(s)}
            </a>
          ))}
        </div>
      ) : null}
    </li>
  );
}

function CaseView({ imp }: { imp: Impulse }) {
  const shown = useMemo(
    () =>
      imp.trajectory
        .filter((c) => isSurfaceable(c.certainty))
        .slice()
        .sort((a, b) => cellSortKey(a.date) - cellSortKey(b.date)),
    [imp],
  );
  const withheld = imp.trajectory.filter((c) => !isSurfaceable(c.certainty));
  const charted = imp.chartEvidence.filter((f) => f.charted);
  const linkedRefs = new Set(imp.trajectory.flatMap((c) => c.chartEvidenceRefs));
  const unlinked = charted.filter((f) => !linkedRefs.has(f.ref));

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="font-display text-lg font-extrabold tracking-[0.06em] text-[var(--ink)]">
            {imp.nameKo}
          </h2>
          {imp.nameEn ? <span className="text-sm text-[var(--muted)]">{imp.nameEn}</span> : null}
        </div>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[var(--ink-secondary)]">
          <div className="flex gap-1.5">
            <dt className="text-[var(--muted)]">확산 경로</dt>
            <dd>{CASE_TYPE_KO[imp.caseType] ?? imp.caseType}</dd>
          </div>
          {imp.origin?.region ? (
            <div className="flex gap-1.5">
              <dt className="text-[var(--muted)]">발원</dt>
              <dd>
                {imp.origin.region}
                {imp.origin.scene ? ` · ${imp.origin.scene}` : ""}
              </dd>
            </div>
          ) : null}
          {imp.adoptionMode ? (
            <div className="flex gap-1.5">
              <dt className="text-[var(--muted)]">한국 도달</dt>
              <dd>{ADOPTION_MODE_KO[imp.adoptionMode.mode] ?? imp.adoptionMode.mode}</dd>
            </div>
          ) : null}
          <div className="flex gap-1.5">
            <dt className="text-[var(--muted)]">가설 버전</dt>
            <dd className="tabular-nums">
              {imp.version} · {imp.updated} 갱신
            </dd>
          </div>
        </dl>
      </header>

      <section aria-labelledby={`traj-${imp.id}`}>
        <h3 id={`traj-${imp.id}`} className="text-sm text-[var(--ink)]">
          이 장르는 어떤 경로로 왔나
        </h3>
        <ol
          className="mt-3 space-y-5 border-l pl-3"
          style={{ borderColor: "var(--hairline)" }}
        >
          {shown.map((c) => (
            <Cell key={`${c.cell}-${c.date}`} cell={c} facts={imp.chartEvidence} />
          ))}
        </ol>
        {withheld.length > 0 ? (
          <p className="mt-4 text-xs leading-relaxed text-[var(--muted)]">
            확실성이 &lsquo;중간&rsquo;에 못 미치는 {withheld.length}건은 위 목록에서 뺐습니다. 원장에는 그대로
            있습니다: {withheld.map((c) => `${c.cell}(${c.certainty})`).join(" · ")}
          </p>
        ) : null}
      </section>

      <section aria-labelledby={`chart-${imp.id}`}>
        <h3 id={`chart-${imp.id}`} className="text-sm text-[var(--ink)]">
          아직 어느 셀에도 붙지 않은 차트 사실
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
          차트인은 &lsquo;그 시장에 도달했다&rsquo;는 사실이지 궤적의 어느 칸인지를 뜻하지 않습니다. 어느 셀에
          붙일지는 사람이 정합니다. 비어 있다는 것은 아직 대조되지 않았다는 뜻이지 근거가 없다는 뜻이
          아닙니다.
        </p>
        {unlinked.length > 0 ? (
          <ul className="mt-2 space-y-0.5">
            {unlinked.map((f) => (
              <ChartFactLine key={f.ref} fact={f} />
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-[var(--muted)]">
            {charted.length > 0 ? "차트 사실이 모두 셀에 붙었습니다." : "이 케이스에는 차트인 사실이 없습니다."}
          </p>
        )}
      </section>

      {imp.limits.length > 0 ? (
        <section aria-labelledby={`limits-${imp.id}`}>
          <h3 id={`limits-${imp.id}`} className="text-sm text-[var(--ink)]">
            이 가설의 한계
          </h3>
          {/* 한 줄씩 세로 규칙으로 가른다. 구분이 없으면 여러 한계가 한 문단으로 뭉쳐
              어디서 끊기는지 알 수 없다(실측). */}
          <ul className="mt-2 space-y-2">
            {imp.limits.map((l) => (
              <li
                key={l}
                className="border-l pl-3 text-xs leading-relaxed text-[var(--ink-secondary)]"
                style={{ borderColor: "var(--hairline)" }}
              >
                {l}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

export function ImpulseLedger({ data }: { data: LabsData }) {
  const [active, setActive] = useState(0);
  const impulses = data.impulses;
  if (impulses.length === 0) {
    return <p className="text-sm text-[var(--muted)]">원장 레코드가 없습니다.</p>;
  }
  const imp = impulses[Math.min(active, impulses.length - 1)];
  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap gap-1.5" role="tablist" aria-label="임펄스 케이스">
        {impulses.map((m, i) => (
          <button
            key={m.id}
            type="button"
            role="tab"
            id={`labs-tab-${m.id}`}
            aria-selected={i === active}
            aria-controls="labs-panel"
            onClick={() => setActive(i)}
            className="rounded-full border px-3 py-1 text-xs transition-colors duration-200 ease-out"
            style={{
              borderColor: i === active ? "var(--baseline)" : "var(--border)",
              color: i === active ? "var(--ink)" : "var(--muted)",
            }}
          >
            {m.nameKo}
          </button>
        ))}
      </nav>
      {/* role="tab"만 두고 패널이 없으면 보조기술이 무엇이 바뀌었는지 알 수 없다. */}
      <div id="labs-panel" role="tabpanel" aria-labelledby={`labs-tab-${imp.id}`}>
        <CaseView imp={imp} />
      </div>
    </div>
  );
}
