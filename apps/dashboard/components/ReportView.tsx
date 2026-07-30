"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Chart, Metric, Report } from "@/lib/report";
import { KpiTile } from "@/components/KpiTile";
import { ChartCard } from "@/components/charts/ChartCard";
import { ProfileCards, isProfileLine } from "@/components/ProfileCards";
import { TabQuestions } from "@/components/TabQuestions";
import { InferenceBlock } from "@/components/InferenceBlock";
import { SectionNav } from "@/components/SectionNav";

// ISO 타임스탬프를 그대로 찍으면 화면에 기계 문자열이 남는다. 초·타임존 표기는
// 읽는 사람의 판단을 바꾸지 않으므로 분 단위까지만 보인다.
function fmtStamp(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]} UTC` : iso;
}

// 모듈이 내는 문구에는 `**강조**` 표기가 섞여 있는데, 그동안 화면에 **별표 그대로**
// 찍히고 있었다. 표기를 강조로 살리고 별표는 지운다. 마크업이 아니라 텍스트 노드만
// 만들므로 문구가 HTML을 주입할 수 없다(라벨은 신뢰하지 않는 데이터다).
function emphasize(text: string) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-medium text-[var(--ink)]">
        {part}
      </strong>
    ) : (
      part
    ),
  );
}

function List({ title, items, marker }: { title: string; items: string[]; marker: string }) {
  return (
    <div>
      <h2 className="mb-2 font-display text-sm font-medium tracking-wide">{title}</h2>
      <ul className="space-y-2">
        {items.map((t, i) => (
          <li key={i} className="flex gap-2 text-sm leading-relaxed text-[var(--ink-secondary)]">
            <span className="select-none text-[var(--series)]">{marker}</span>
            <span className="max-w-[68ch]">{emphasize(t)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReportView({
  report,
  dark,
  moduleIds = [],
  onSelectModule,
}: {
  report: Report;
  dark: boolean;
  moduleIds?: string[];
  onSelectModule?: (id: string) => void;
}) {
  const sections = report.sections ?? [];
  const [active, setActive] = useState(sections[0]?.id ?? "");
  const still = useReducedMotion();

  // 프로필 라인(RULES §4.1 규약)은 카드 섹션으로 분리, 나머지는 기존 인사이트 리스트.
  const profileLines = report.insights.filter(isProfileLine);
  const insights = report.insights.filter((l) => !isProfileLine(l));
  // 교차 링크: subtitle/insight 본문에 등장하는 다른 모듈 id → 탭 링크 칩 (범용 감지)
  const haystack = [report.subtitle ?? "", ...report.insights].join("\n");
  const related = moduleIds.filter((id) => id !== report.moduleId && haystack.includes(id));

  // R4 배치 — 추론은 딛고 선 관측 **아래**로 내려간다. chartId가 없는 추론만 맨 끝에 모인다.
  const infs = report.inferences ?? [];
  const infOf = (id?: string) => (id ? infs.filter((i) => i.chartId === id) : []);
  const knownIds = new Set(
    [report.summary, ...report.charts].map((c) => c?.id).filter((v): v is string => !!v),
  );
  const orphanInfs = infs.filter((i) => !i.chartId || !knownIds.has(i.chartId));

  // 앵커로 이동할 때 **그 차트가 있는 구획을 먼저 연다**. 구획을 전환하지 않으면
  // 질문을 눌러도 대상이 DOM에 없어 아무 일도 일어나지 않는다.
  const sectionOfChart = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of report.charts) if (c.id && c.section) m.set(c.id, c.section);
    return m;
  }, [report.charts]);

  const activeSection = sections.find((s) => s.id === active) ?? sections[0];
  const inSection = (c: Chart | Metric) =>
    sections.length === 0 || (c as { section?: string }).section === activeSection?.id;

  const shownCharts = sections.length === 0 ? report.charts : report.charts.filter((c) => inSection(c));
  const shownMetrics =
    sections.length === 0 ? report.metrics : report.metrics.filter((m) => inSection(m));

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-5 py-6">
      <section>
        <h1 className="font-display text-xl font-semibold tracking-wide">{report.title}</h1>
        {report.subtitle && <p className="mt-1 break-words text-sm text-[var(--ink-secondary)]">{report.subtitle}</p>}
        <p className="mt-0.5 text-xs tabular-nums text-[var(--muted)]">{fmtStamp(report.generatedAt)} 생성</p>
        {related.length > 0 && onSelectModule && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[var(--muted)]">소스 모듈:</span>
            {related.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onSelectModule(id)}
                className="rounded border border-[var(--border)] px-2 py-0.5 text-[var(--ink-secondary)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--ink)]"
              >
                {id} ↗
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ── 진입부 (R1 + R2 + R7) ──
          첫 화면에 놓이는 것은 **질문 목록 하나와 요약 도형 하나**뿐이다. 검증된 사실:
          하중을 받는 것은 수백 개 그래프가 아니라 맨 앞의 작은 요약 도형 하나이고
          (독립 3근거 · REFERENCE §2), 나머지는 그 요약이 던진 질문에 답하러 갈 곳이다. */}
      {(report.summary || report.questions?.length || report.notAnswered?.length) && (
        <>
          {/* 왼쪽은 본문 텍스트(카드 아님), 오른쪽만 카드. 표면당 강조 하나라는 규칙이
              배치를 정한다 — 같은 상자 둘을 나란히 놓으면 무엇이 중심인지 사라진다. */}
          <div className="grid items-start gap-x-8 gap-y-5 lg:grid-cols-[1fr_minmax(0,25rem)]">
            <TabQuestions
              questions={report.questions}
              notAnswered={report.notAnswered}
              onBeforeJump={(chartId) => {
                const sid = sectionOfChart.get(chartId);
                if (sid) setActive(sid);
              }}
            />
            {report.summary && (
              <ChartCard chart={report.summary} dark={dark} baseReliability={report.reliability} />
            )}
          </div>
          {/* 요약에 붙은 해석은 카드 밖 전폭으로 내린다. 카드 안에 두면 요약 카드만
              길어져 위 두 칸의 균형이 깨지고, 배치가 곧 짜침이 된다.
              여전히 관측 **아래**이므로 §6.2 배치 규약을 지킨다. */}
          {report.summary && infOf(report.summary.id).length > 0 && (
            <InferenceBlock items={infOf(report.summary.id)} />
          )}
        </>
      )}

      {sections.length > 0 && (
        <div className="border-b border-[var(--hairline)] pt-4">
          <SectionNav sections={sections} active={activeSection?.id ?? ""} onSelect={setActive} />
        </div>
      )}

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeSection?.id ?? "all"}
          initial={still ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={still ? { opacity: 0 } : { opacity: 0, y: -6 }}
          transition={{ duration: still ? 0 : 0.22, ease: "easeOut" }}
          className="space-y-6"
        >
          {/* 구획의 머리글은 라벨이 아니라 **질문**이다. 읽는 사람이 지금 무엇을
              보고 있는지는 이름이 아니라 답하려는 질문으로 정해진다. */}
          {activeSection?.question && (
            <header className="pt-3">
              <h2 className="max-w-[24ch] font-display text-2xl font-semibold leading-snug tracking-tight text-[var(--ink)] sm:text-[1.75rem]">
                {activeSection.question}
              </h2>
              {activeSection.note && (
                <p className="mt-2.5 max-w-[68ch] text-sm leading-relaxed text-[var(--muted)]">
                  {activeSection.note}
                </p>
              )}
            </header>
          )}

          {shownMetrics.length > 0 && (
            <section>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {shownMetrics.map((m, i) => (
                  <KpiTile key={i} m={m} />
                ))}
              </div>
              {/* R5 — 정의는 화면에서 열린다. 다만 **행에 하나**다: 타일마다 펼침 장치를
                  달면 같은 모양이 6번 반복되고, 반복된 장식은 정보가 아니라 잡음이 된다.
                  (2026-07-30 육안 검사에서 실제로 그렇게 보였다.) */}
              {shownMetrics.some((m) => m.definition) && (
                <details className="group mt-3 text-xs">
                  <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[var(--muted)] transition-colors duration-150 ease-out hover:text-[var(--ink-secondary)]">
                    <span
                      aria-hidden
                      className="inline-block transition-transform duration-200 ease-out group-open:rotate-90"
                    >
                      ›
                    </span>
                    지표가 무엇을 재는가
                  </summary>
                  <dl className="mt-2 grid gap-x-6 gap-y-2 border-l border-[var(--hairline)] pl-3 sm:grid-cols-2">
                    {shownMetrics
                      .filter((m) => m.definition)
                      .map((m, i) => (
                        <div key={i}>
                          <dt className="text-[var(--ink-secondary)]">{m.label}</dt>
                          <dd className="max-w-[68ch] leading-relaxed text-[var(--muted)]">{m.definition}</dd>
                        </div>
                      ))}
                  </dl>
                </details>
              )}
            </section>
          )}

          {shownCharts.map((c, i) => (
            <ChartCard
              key={c.id ?? i}
              chart={c}
              dark={dark}
              baseReliability={report.reliability}
              inferences={infOf(c.id)}
            />
          ))}
        </motion.div>
      </AnimatePresence>

      {profileLines.length > 0 && <ProfileCards lines={profileLines} />}

      {/* 어느 관측에도 매이지 않은 추론만 여기 모인다 — 나머지는 각자의 카드 아래 있다. */}
      {orphanInfs.length > 0 && <InferenceBlock items={orphanInfs} />}

      {(insights.length > 0 || report.recommendations.length > 0) && (
        <section className="grid gap-6 border-t border-[var(--hairline)] pt-6 md:grid-cols-2">
          {insights.length > 0 && <List title="인사이트" items={insights} marker="·" />}
          {report.recommendations.length > 0 && <List title="추천" items={report.recommendations} marker="→" />}
        </section>
      )}
    </main>
  );
}
