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
// impulse-rules: genre-impulse — per-track cohort percentiles + the rule's shape, so the
// client can recompute which tracks match as the two percentile cuts move.
// 곡별 백분위를 실어야 임계를 낮췄을 때 **새 곡이 나타날 수 있다** — 분포만 보내면
// 컷 선은 움직여도 매치 목록은 얼어붙는다(2026-07-30 실측 결함).
export interface ImpulseRulesTunableData {
  view: "impulse-rules";
  lowPct: number;
  highPct: number;
  axes: string[];
  pools: Record<string, number[]>;
  rules: { id: string; impulseId: string; lowAll: string[]; highAny: string[] }[];
  tracks: { name: string; watch?: boolean; pcts: Record<string, number> }[];
  knobs: Knob[];
  note?: string;
}
export type TunableData =
  | WhitespaceTunableData
  | LeadLagTunableData
  | RhythmTunableData
  | TagsTunableData
  | ImpulseRulesTunableData;

// `type`이 `data`의 형태를 결정한다 — 판별 유니온이라 `as BarData` 같은 캐스트가 필요 없고,
// 분기를 빼먹으면 컴파일러가 잡는다. 예전엔 `data: ... | unknown`이라 캐스트가 검사를 무력화했고,
// 그래서 2026-07-30에 bar 키 오용(`label`)이 타입체크·스키마 양쪽을 통과해 화면까지 나갔다.
// **쓰는 쪽 정본은 packages/report-schema/report.schema.json이며 둘은 짝으로 갱신한다**(AGENTS §0).
export type Chart =
  | { type: "bar"; title?: string; data: BarData }
  | { type: "line"; title?: string; data: LineData }
  | { type: "heatmap"; title?: string; data: HeatmapData }
  | { type: "tunable"; title?: string; data: TunableData }
  // radar는 아직 렌더러가 없다(카드가 "미지원"을 표시한다). 스키마도 같은 이유로 무제약이며,
  // 구현할 때 스키마 분기와 여기 형태를 함께 정한다.
  | { type: "radar"; title?: string; data: unknown };

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
