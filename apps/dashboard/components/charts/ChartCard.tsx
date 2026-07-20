import type { BarData, Chart, HeatmapData, LineData, TunableData } from "@/lib/report";
import { BarChart } from "./BarChart";
import { LineChart } from "./LineChart";
import { Heatmap } from "./Heatmap";
import { Tunable } from "./Tunable";

export function ChartCard({ chart, dark }: { chart: Chart; dark: boolean }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
      {chart.title && <h2 className="mb-4 text-sm font-medium">{chart.title}</h2>}
      {chart.type === "bar" && <BarChart data={chart.data as BarData} />}
      {chart.type === "line" && <LineChart data={chart.data as LineData} />}
      {chart.type === "heatmap" && <Heatmap data={chart.data as HeatmapData} dark={dark} />}
      {chart.type === "tunable" && <Tunable data={chart.data as TunableData} />}
      {chart.type === "radar" && <p className="text-sm text-[var(--muted)]">radar 렌더는 아직 미지원</p>}
    </section>
  );
}
