import reportsJson from "@/data/reports.json";
import type { Report } from "@/lib/report";

// 기준 원장 — 이 시스템이 지금 가정하고 있는 값을 한자리에 모은다.
//
// 왜 이 화면이 있어야 하나: 이 저장소의 규율은 **임계값을 코드에 은닉하지 않는 것**이고,
// 기준의 형식은 엔지니어가, 값은 담당자가 소유한다. 그런데 지금까지 값들은 각 탭 안쪽
// 튜너에 흩어져 있어서 "이 시스템이 무엇을 가정하고 있나"를 한눈에 볼 자리가 없었다.
// 반박하려면 먼저 무엇을 반박할지 보여야 한다.
//
// 🔴 **저장 키를 화면에 찍지 않는다.** 노브의 `key`는 데이터 키(`min_posts` 같은 것)라
// 화면에 새면 안 된다. 표기는 리포트가 함께 실은 `label`이 들고 있다.
// 🔴 수치는 전부 리포트에서 온다. 값이 바뀌면 이 화면이 저절로 따라가고, 손으로 적어 넣은
// 값은 모듈이 기준을 조정한 날부터 조용히 거짓이 된다.

const reports = reportsJson as unknown as Report[];

export interface Criterion {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
}

export interface CriterionSet {
  /** 이 기준들이 무엇을 다시 계산하는가 */
  title: string;
  question?: string;
  definition?: string;
  criteria: Criterion[];
}

export interface CriteriaGroup {
  moduleId: string;
  moduleTitle: string;
  href: string;
  sets: CriterionSet[];
}

export interface CriteriaLedger {
  total: number;
  groups: CriteriaGroup[];
}

export function buildCriteriaLedger(): CriteriaLedger {
  const groups: CriteriaGroup[] = [];
  let total = 0;

  for (const r of reports) {
    const sets: CriterionSet[] = [];
    for (const c of r.charts) {
      if (c.type !== "tunable") continue;
      const knobs = c.data.knobs ?? [];
      if (knobs.length === 0) continue;
      total += knobs.length;
      sets.push({
        title: c.title ?? c.id ?? "",
        question: c.question,
        definition: c.definition,
        criteria: knobs.map((k) => ({
          label: k.label,
          value: k.default,
          min: k.min,
          max: k.max,
          step: k.step,
        })),
      });
    }
    if (sets.length === 0) continue;
    groups.push({
      moduleId: r.moduleId,
      moduleTitle: r.title,
      // 값을 실제로 돌릴 수 있는 자리는 리포트 안이다. 여기는 무엇이 있는지를 보이는 자리이며,
      // 보여 놓고 만질 곳으로 데려가지 않으면 원장이 아니라 목록이 된다.
      href: `/artist-intelligence#${r.moduleId}`,
      sets,
    });
  }

  return { total, groups };
}
