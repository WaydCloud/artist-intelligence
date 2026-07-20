// Mirrors packages/report-schema/report.schema.json (read side).

export interface Metric {
  label: string;
  value: number | string;
  unit?: string;
  delta?: number;
  benchmark?: number;
  hint?: string;
}

export type BarData = { name: string; value: number }[];
export interface LineData {
  x: string[];
  series: { name: string; values: (number | null)[] }[];
}
export interface HeatmapData {
  rows: string[];
  cols: string[];
  cells: (number | null)[][];
}

// tunable: a chart carrying its raw matrix + threshold knobs; the dashboard
// recomputes a derived `view` client-side as the viewer turns each knob.
// Generic — any module can emit one (기준 원장 §2.1: 값=도메인 소유자, 노출).
export interface Knob {
  key: string;
  label: string;
  default: number;
  min: number;
  max: number;
  step: number;
}
export interface WhitespaceTunableData {
  view: "whitespace";
  matrix: HeatmapData;
  knobs: Knob[];
  topRows?: number;
  note?: string;
}
// leadlag: signal-bridge RULES §2 — raw social/chart series + θ knobs; the client
// recomputes onsets/classification as the viewer drags (기준 원장 §2.1: 값=A&R 소유).
export interface LeadLagTunableData {
  view: "leadlag";
  socialDates: string[];
  chartDates: string[];
  series: Record<string, { social?: number[]; chart?: (number | null)[] }>;
  knobs: Knob[];
  note?: string;
}
export type TunableData = WhitespaceTunableData | LeadLagTunableData;

export interface Chart {
  type: "line" | "bar" | "heatmap" | "radar" | "tunable";
  title?: string;
  data: BarData | LineData | HeatmapData | TunableData | unknown;
}

export interface Media {
  type: "image" | "video";
  src: string;
  caption?: string;
}

export interface Report {
  moduleId: string;
  title: string;
  subtitle?: string;
  generatedAt: string;
  metrics: Metric[];
  charts: Chart[];
  media: Media[];
  insights: string[];
  recommendations: string[];
}
