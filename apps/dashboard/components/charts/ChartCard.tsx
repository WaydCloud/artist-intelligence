import type { Chart } from "@/lib/report";
import { BarChart } from "./BarChart";
import { LineChart } from "./LineChart";
import { Heatmap } from "./Heatmap";
import { Tunable } from "./Tunable";
import { ChartBoundary } from "./ChartBoundary";

export function ChartCard({ chart, dark }: { chart: Chart; dark: boolean }) {
  // 제목은 바운더리 밖에 둔다 -- 플롯이 죽어도 어느 카드가 비었는지는 보여야 한다.
  return (
    <section className="glass-card p-5">
      {chart.title && <h2 className="mb-4 font-display text-sm font-medium tracking-wide">{chart.title}</h2>}
      <ChartBoundary label={chart.title ?? chart.type}>
        {chart.type === "bar" && <BarChart data={chart.data} />}
        {chart.type === "line" && <LineChart data={chart.data} />}
        {chart.type === "heatmap" && <Heatmap data={chart.data} dark={dark} />}
        {chart.type === "tunable" && <Tunable data={chart.data} title={chart.title} />}
        {chart.type === "radar" && <p className="text-sm text-[var(--muted)]">radar 차트는 아직 미지원</p>}
      </ChartBoundary>
    </section>
  );
}
