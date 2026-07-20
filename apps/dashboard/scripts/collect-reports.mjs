// Build-time report collector: modules/*/output/report.json → data/reports.json.
// Keeps the static export self-contained (핵심 흐름: report.json → 대시보드 렌더).
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // apps/dashboard/scripts
const repoRoot = join(here, "..", "..", ".."); // repo root
const modulesDir = join(repoRoot, "modules");
const outDir = join(here, "..", "data");

const reports = [];
if (existsSync(modulesDir)) {
  for (const name of readdirSync(modulesDir)) {
    const p = join(modulesDir, name, "output", "report.json");
    if (!existsSync(p)) continue;
    try {
      reports.push(JSON.parse(readFileSync(p, "utf-8")));
    } catch (e) {
      console.warn(`skip ${p}: ${e.message}`);
    }
  }
}
reports.sort((a, b) => String(a.moduleId).localeCompare(String(b.moduleId)));

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "reports.json"), `${JSON.stringify(reports, null, 2)}\n`);
console.log(`collected ${reports.length} report(s) → data/reports.json`);
