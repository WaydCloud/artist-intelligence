// Mirrors packages/report-schema/report.schema.json (read side).

export interface Metric {
  label: string;
  value: number | string;
  unit?: string;
  delta?: number;
  benchmark?: number;
  hint?: string;
  // R5 — 이 지표가 무엇을 재는가. 화면에서 인라인으로 펼쳐진다(원장 링크가 아니다).
  definition?: string;
  section?: string;
}

// D-043 — 탭을 질문 단위로 가르는 구획. 대시보드는 한 번에 한 구획만 보여준다.
// 구획의 머리글은 라벨이 아니라 **질문**이다: 읽는 사람이 어디로 갈지 정하려면
// "플랫폼"이 아니라 "네 곳이 같은 곡을 올렸나"가 필요하다.
export interface Section {
  id: string;
  label: string;
  question?: string;
  note?: string;
}

// R8 — "이 화면을 어디까지 믿을지"를 도구가 먼저 말하는 자리. 카드의 1급 요소로 렌더된다.
// 리포트 최상위 값과 차트별 값을 **필드 단위로 병합**해 쓴다(mergeReliability).
export interface Reliability {
  sample?: string;
  accuracy?: string;
  missing?: string;
  engine?: string;
}

// 최상위 기본값 위에 차트별 값을 덮는다. 엔진 버전처럼 모듈 공통인 것은 최상위에
// 한 번만 실리므로, 병합하지 않으면 차트 카드의 신뢰도 라인에서 엔진이 사라진다.
export function mergeReliability(
  base: Reliability | undefined,
  over: Reliability | undefined,
): Reliability | undefined {
  if (!base && !over) return undefined;
  return { ...base, ...over };
}

// R4 · D-039 — 태그된 자동 추론. `insights: string[]`과 분리된 객체인 이유는
// 동반 4종(basis·sample·confidence·limits)을 문자열에 실을 자리가 없기 때문이다.
export interface Inference {
  text: string;
  basis: string;
  sample: string;
  confidence: "low" | "medium" | "high";
  limits: string;
  chartId?: string;
}

// R1 — 이 탭에서 답할 수 있는 질문. chartId는 같은 리포트의 차트 id를 가리킨다.
export interface TabQuestion {
  q: string;
  chartId: string;
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

// radar: 요약 도형(R2). 절대값이 아니라 **비교 위치**를 그린다 — 스케일이 다른 축을
// 한 폴리곤에 얹으면 그림이 값이 아니라 스케일을 보여주기 때문에, value는 공통 스케일
// (백분위 등)이고 무엇으로 정규화했는지는 scaleNote가 들고 있다.
// `value: null`은 **관측 없음**이며 0이 아니다(R6) — 0은 "분포 최하위"라는 관측값이라
// 결측을 0으로 그리면 도형이 "이 축에서 꼴찌"라고 거짓말한다.
export interface RadarAxis {
  name: string;
  value: number | null;
  definition?: string;
  missingReason?: string;
  sample?: number;
  raw?: number;
  rawUnit?: string;
}
export interface RadarData {
  axes: RadarAxis[];
  max?: number;
  // 기준 링 — 비교 대상이 도형 안에 그려진다. 시리즈가 아니라 크롬이라 범례를 요구하지 않는다.
  baseline?: number;
  baselineLabel?: string;
  scaleNote?: string;
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

// 차트 카드의 공통 메타 — 어느 type이든 같은 자리에서 읽는다.
//   id          앵커 대상(questions[].chartId · inferences[].chartId · DOM #id).
//               제목 문자열로 앵커를 잡으면 문구를 다듬는 순간 링크가 조용히 끊긴다.
//   question    R3 — 이 차트로 답할 수 있는 질문. 답할 질문이 없으면 차트를 뺀다.
//   definition  R5 — 축·지표가 무엇을 재는가.
//   reliability R8 — 최상위 값을 필드 단위로 덮는다(mergeReliability).
//   section     D-043 — 어느 구획에 속하는가. 구획당 차트 수에는 상한이 있다.
interface ChartMeta {
  id?: string;
  title?: string;
  question?: string;
  definition?: string;
  reliability?: Reliability;
  section?: string;
}

// `type`이 `data`의 형태를 결정한다 — 판별 유니온이라 `as BarData` 같은 캐스트가 필요 없고,
// 분기를 빼먹으면 컴파일러가 잡는다. 예전엔 `data: ... | unknown`이라 캐스트가 검사를 무력화했고,
// 그래서 2026-07-30에 bar 키 오용(`label`)이 타입체크·스키마 양쪽을 통과해 화면까지 나갔다.
// **쓰는 쪽 정본은 packages/report-schema/report.schema.json이며 둘은 짝으로 갱신한다**(AGENTS §0).
export type Chart =
  | ({ type: "bar"; data: BarData } & ChartMeta)
  | ({ type: "line"; data: LineData } & ChartMeta)
  | ({ type: "heatmap"; data: HeatmapData } & ChartMeta)
  | ({ type: "tunable"; data: TunableData } & ChartMeta)
  | ({ type: "radar"; data: RadarData } & ChartMeta);

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
  // R2 — 진입 요약 하나. 배열이 아니라 단일 객체라 첫 화면에 도형 두 개가 놓일 수 없다.
  // 여기 실린 차트는 `charts`에 중복해 싣지 않는다.
  summary?: Chart;
  questions?: TabQuestion[]; // R1
  notAnswered?: string[]; // R7
  sections?: Section[]; // D-043
  reliability?: Reliability; // R8 기본값 (차트별 값이 덮는다)
  inferences?: Inference[]; // R4 · D-039
}
