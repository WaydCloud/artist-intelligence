import type { Chart, Inference, Reliability } from "@/lib/report";
import { mergeReliability } from "@/lib/report";
import { BarChart } from "./BarChart";
import { LineChart } from "./LineChart";
import { Heatmap } from "./Heatmap";
import { RadarChart } from "./RadarChart";
import { Tunable } from "./Tunable";
import { ChartBoundary } from "./ChartBoundary";
import { ReliabilityLine } from "@/components/ReliabilityLine";
import { Definition } from "@/components/Definition";
import { InferenceBlock } from "@/components/InferenceBlock";

// 카드 안의 순서가 곧 규율이다:
//   제목 → 질문(R3) → 정의 펼침(R5) → 신뢰도(R8) → 플롯 → 추론(R4)
//
// 신뢰도가 플롯 **위**에 오는 것이 핵심이다. 아래로 내리면 각주가 되고 각주는 안 읽힌다.
// 추론이 플롯 **아래**에 오는 것도 규약이다(DESIGN §6.2 배치) — 관측 위에 해석을 얹으면
// 읽는 사람이 둘을 구별하지 못한다.

export function ChartCard({
  chart,
  dark,
  baseReliability,
  inferences = [],
}: {
  chart: Chart;
  dark: boolean;
  baseReliability?: Reliability;
  inferences?: Inference[];
}) {
  const rel = mergeReliability(baseReliability, chart.reliability);
  return (
    <section
      id={chart.id}
      // 앵커로 도착했을 때 잠깐 표시된다(TabQuestions.goTo가 data-landed를 붙인다).
      className="glass-card scroll-mt-24 p-5 transition-[border-color] duration-300 ease-out data-[landed=true]:border-[var(--series)]"
    >
      {/* 제목은 바운더리 밖에 둔다 — 플롯이 죽어도 어느 카드가 비었는지는 보여야 한다. */}
      {chart.title && <h2 className="font-display text-sm font-extrabold tracking-wide">{chart.title}</h2>}

      {/* R3 — 이 차트로 답할 수 있는 질문. 답할 질문이 없으면 차트를 뺀다(계약이 강제). */}
      {chart.question && (
        <p className="mb-3 mt-1 max-w-[68ch] text-xs leading-relaxed text-[var(--ink-secondary)]">
          <span className="text-[var(--muted)]">답할 수 있는 질문 </span>
          {chart.question}
        </p>
      )}

      <Definition text={chart.definition} />
      <ReliabilityLine r={rel} />

      <ChartBoundary label={chart.title ?? chart.type}>
        {chart.type === "bar" && <BarChart data={chart.data} />}
        {chart.type === "line" && <LineChart data={chart.data} />}
        {chart.type === "heatmap" && <Heatmap data={chart.data} dark={dark} />}
        {chart.type === "radar" && <RadarChart data={chart.data} />}
        {chart.type === "tunable" && <Tunable data={chart.data} title={chart.title} />}
      </ChartBoundary>

      {inferences.length > 0 && <InferenceBlock items={inferences} nested />}
    </section>
  );
}
