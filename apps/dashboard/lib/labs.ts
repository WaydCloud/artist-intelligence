// LABS 읽기 타입 — data/research/genre-impulse/impulse.schema.json의 읽기 쪽 거울.
//
// 🔴 **리포트 계약이 아니다.** 채택 모듈은 report.schema.json을 지나지만 임펄스 원장은
// 연구 산출물이고 측정이 아니라 **버전 매겨진 가설**이다. 두 계약을 섞지 않으려고
// 타입도 lib/report.ts와 분리해 둔다.

/** 원장의 6등급(D-033 보완⑥). 스키마가 "표면은 중간 이상만, 등급 병기"라고 정했다. */
export type Certainty = "매우 높음" | "높음" | "중간" | "낮음" | "매우 낮음" | "불가능한 수준";

/** 표면에 claim으로 올릴 수 있는 등급. 미만은 뺀 사실을 화면에 적는다(결측 ≠ 부재). */
export const SURFACE_MIN: Certainty[] = ["매우 높음", "높음", "중간"];

export const isSurfaceable = (c: Certainty): boolean => SURFACE_MIN.includes(c);

export interface TrajectoryCell {
  cell: string;
  date: string;
  datePrecision: string | null;
  evidence: string;
  sources: string[];
  certainty: Certainty;
  certaintyNote: string | null;
  /** 사람이 확정한 링크만. 비었다면 "아직 대조되지 않았다"이지 "근거가 없다"가 아니다. */
  chartEvidenceRefs: string[];
}

export interface ChartFact {
  ref: string;
  chart: string;
  artist: string;
  title: string;
  role: string;
  charted: boolean;
  entryDate: string | null;
  peakPosition: number | null;
  weeksOnChart: number | null;
  certainty: Certainty | null;
  source: string;
}

export interface Impulse {
  id: string;
  nameKo: string;
  nameEn: string | null;
  version: string;
  updated: string;
  caseType: string;
  adoptionMode: { mode: string; notes?: string } | null;
  origin: { region?: string; scene?: string } | null;
  limits: string[];
  trajectory: TrajectoryCell[];
  chartEvidence: ChartFact[];
}

export interface LabsData {
  impulses: Impulse[];
}

/** 확산 경로 유형을 사람 말로. 값은 스키마 enum이 정본이다. */
export const CASE_TYPE_KO: Record<string, string> = {
  import: "해외 유입",
  endogenous: "내생",
  "hybrid-endogenous": "혼합 내생",
  revival: "부활",
  "continuity-revival": "연속 부활",
  "algorithmic-excavation": "알고리즘 발굴",
};

/** 한국 도달 판정 3모드(+진행 중). 이진이 아니라는 것이 이 표의 요점이다. */
export const ADOPTION_MODE_KO: Record<string, string> = {
  full: "전면 수용",
  element: "요소만 수용",
  blocked: "막힘",
  "in-progress": "진행 중",
};

/**
 * 셀 날짜 표기를 정렬 키로. "YYYY-MM" · "YYYY" · "YYYY~YYYY" · "미도달"이 섞여 있다.
 * 해석 불가와 미도달은 뒤로 보낸다 — 순서를 지어 주되 없는 날짜를 만들지 않는다.
 */
export function cellSortKey(date: string): number {
  const m = /(\d{4})(?:-(\d{2}))?/.exec(date ?? "");
  if (!m) return Number.MAX_SAFE_INTEGER;
  return Number(m[1]) * 12 + (m[2] ? Number(m[2]) : 1);
}
