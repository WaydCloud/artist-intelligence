// Build-time LABS collector: data/research/genre-impulse/impulses/*.json → data/labs.json
//
// 🔴 이것은 **리포트 계약이 아니다.** 채택 모듈은 `모듈 CLI → 스키마 유효 report.json →
// 대시보드`를 지나지만(AGENTS §0), 임펄스 원장은 **연구 산출물**이고 측정이 아니라
// **버전 매겨진 가설**이다. 억지로 report.schema.json에 넣으면 증거 레이어와 가설이
// 한 계약에 섞이므로, 별도 경로로 읽어 **LABS 표면에만** 싣는다.
//
// 그래서 이 파일이 하는 일은 옮겨 담기뿐이다 — 판단·집계·해석을 하지 않는다.
// 화면이 원장보다 더 많은 것을 말하기 시작하면 그 순간 원장이 정본이 아니게 된다.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..");
const impulsesDir = join(repoRoot, "data", "research", "genre-impulse", "impulses");
const outDir = join(here, "..", "data");

/** 차트 사실 한 줄의 참조 키 — scripts/impulse_trajectory_link.py의 `_ref`와 같은 형식. */
const refOf = (e) => `${e.chart ?? ""}|${e.artist ?? ""}|${e.title ?? ""}`;

const impulses = [];
if (existsSync(impulsesDir)) {
  for (const name of readdirSync(impulsesDir)) {
    if (!name.endsWith(".json")) continue;
    const p = join(impulsesDir, name);
    try {
      const d = JSON.parse(readFileSync(p, "utf-8"));
      impulses.push({
        id: d.id,
        nameKo: d.name_ko,
        nameEn: d.name_en ?? null,
        version: d.version,
        updated: d.updated,
        caseType: d.case_type,
        adoptionMode: d.adoption_mode ?? null,
        origin: d.origin ?? null,
        limits: d.limits ?? [],
        trajectory: (d.trajectory ?? []).map((c) => ({
          cell: c.cell,
          date: c.date,
          datePrecision: c.date_precision ?? null,
          evidence: c.evidence,
          sources: c.sources ?? [],
          certainty: c.certainty,
          certaintyNote: c.certainty_note ?? null,
          // 사람이 확정한 링크만 들어 있다. 비었다는 것은 "아직 대조되지 않았다"이지
          // "근거가 없다"가 아니다(§0 결측 ≠ 부재).
          chartEvidenceRefs: c.chart_evidence_refs ?? [],
        })),
        chartEvidence: (d.chart_evidence ?? []).map((e) => ({
          ref: refOf(e),
          chart: e.chart,
          artist: e.artist,
          title: e.title,
          role: e.role,
          charted: Boolean(e.charted),
          entryDate: e.entry_date ?? null,
          peakPosition: e.peak_position ?? null,
          weeksOnChart: e.weeks_on_chart ?? null,
          certainty: e.certainty ?? null,
          source: e.source,
        })),
      });
    } catch (e) {
      console.warn(`skip ${p}: ${e.message}`);
    }
  }
}
impulses.sort((a, b) => String(a.id).localeCompare(String(b.id)));

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "labs.json"), `${JSON.stringify({ impulses }, null, 2)}\n`);
const linked = impulses.reduce(
  (n, i) => n + i.trajectory.filter((c) => c.chartEvidenceRefs.length > 0).length,
  0,
);
console.log(`collected ${impulses.length} impulse(s) → data/labs.json (링크된 셀 ${linked}개)`);
