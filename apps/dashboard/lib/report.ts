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
  // 원인분석 레이어 (signal-bridge RULES §3.1): 분류를 믿을지 판단할 근거.
  // censored = 차트 온셋이 수집 개시일과 같아 이전 진입을 배제하지 못하는 상태.
  evidence?: Record<string, { posts: number; days: number; censored: boolean }>;
  knobs: Knob[];
  note?: string;
}
// rhythm: sonic-profile — raw bar-kick profiles + the named template ledger; the client
// recomputes cosine match, the "no match" bucket and near-ties as the viewer drags.
// 값=A&R 소유(노출·반박). 배정 임계가 없으면 argmax가 늘 이름을 뱉어 음의 상관도 유형이 된다.
export interface RhythmTunableData {
  view: "rhythm";
  bins: number;
  templates: Record<string, number[]>;
  tracks: { name: string; profile: number[]; cohort?: string }[];
  noMatchLabel: string;
  knobs: Knob[];
  note?: string;
}
// tags: sonic-profile — per-track label probabilities + a detection threshold knob.
// `floor`/`truncated` carry the tagger's top-k cutoff so the client can count how many
// tracks the current threshold reads as a lower bound rather than a count (결측 ≠ 0).
export interface TagsTunableData {
  view: "tags";
  tracks: { name: string; labels: { label: string; p: number }[]; floor: number; truncated: boolean }[];
  topBuckets?: number;
  knobs: Knob[];
  note?: string;
}
export type TunableData =
  | WhitespaceTunableData
  | LeadLagTunableData
  | RhythmTunableData
  | TagsTunableData;

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
