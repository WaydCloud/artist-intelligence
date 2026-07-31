"use client";

import type { StageFocus, StoryGroup } from "@/lib/story";

// 좁혀지는 무대 (DESIGN.md §7.8).
//
// 칸 하나가 팀 하나이고 **자리에는 뜻이 없다** — 그래서 자리를 옮기지 않는다. 단계가 바뀔 때
// 움직이는 것은 색과 흐림뿐이고, 마크가 자리를 바꾸면 §7.7의 행 재정렬과 같은 결함이 된다
// (겹치는 동안 무엇이 무엇인지 사라진다). 무대는 증거 레이어(§4)라 dataviz 토큰만 쓰고
// 글래스·그라디언트를 얹지 않는다.
//
// 색은 카테고리 토큰 3개까지이고 순환하지 않는다(§7.3). 여기 카테고리는 정확히 3개다.

const CATEGORY_COLOR: Record<StoryGroup["key"], string> = {
  social: "var(--series)",
  chart: "var(--series2)",
  same: "var(--series3)",
};

// 모집단만 보여주는 단계에서는 카테고리를 주장하지 않는다 — 중립 크롬 색으로 둔다.
const NEUTRAL = "var(--baseline)";
// 걸러진 칸(한때 범위 안이었다)과 범위 밖 칸을 가르는 것은 **불투명도가 아니라 색**이다.
// 처음엔 같은 색에 흐림만 달리 줬는데 라이트 모드에서 둘 다 흰 배경으로 씻겨 구별되지
// 않았다(§7.3의 색 순환과 같은 부류: 그림이 말하려던 구분이 그림에 없다).
const FILTERED = "var(--baseline)";
const OUTSIDE = "var(--hairline)";

const COLS = 18;

interface Dot {
  color: string;
}

/**
 * 아직 살아 있는 칸들이 놓일 자리. **가운데를 중심으로** 계산한다.
 *
 * 자리를 옮겨도 되는 이유는 화면이 "자리에는 뜻이 없다"고 이미 말하고 있기 때문이다. 그러니
 * 이건 정직성 문제가 아니라 배치 문제이고, 왼쪽 맨 위 모서리는 시선이 가장 늦게 닿는 자리라
 * 서사의 결론을 두기에 가장 나쁜 곳이었다.
 *
 * 🔴 살아남는 칸은 **소셜 블록 안에** 머물러야 한다. 밖으로 나가면 "선행 65팀 중 12팀,
 * 그중 1팀"이라는 부분집합 관계가 그림에서 깨진다. 그래서 가운데를 그대로 쓰지 않고 블록
 * 안으로 죄고, 죄는 방향이 일정하므로 **단계가 진행돼도 남는 칸이 앞 단계 안에 든다**
 * (12칸 안에서 1칸이 남는 것이 눈에 보인다). 칸 수는 매일 바뀌므로 좌표를 적지 않고 센다.
 */
function liveSlots(total: number, socialCount: number, live: number): Set<number> {
  const rows = Math.ceil(total / COLS);
  const centre = Math.floor(rows / 2) * COLS + Math.floor(COLS / 2);
  const start = Math.max(0, Math.min(centre - Math.floor(live / 2), socialCount - live));
  const slots = new Set<number>();
  for (let i = 0; i < live; i += 1) slots.add(start + i);
  return slots;
}

/** 단계별로 각 칸이 어떤 색을 갖는지. 순서는 카테고리 블록이고 그 안의 자리는 임의다. */
function dotsFor(focus: StageFocus, groups: StoryGroup[], live: number): Dot[] {
  const total = groups.reduce((sum, g) => sum + g.value, 0);
  const socialCount = groups.find((g) => g.key === "social")?.value ?? 0;
  const slots = liveSlots(total, socialCount, live);

  const out: Dot[] = [];
  let index = 0;
  for (const g of groups) {
    for (let i = 0; i < g.value; i += 1, index += 1) {
      const isSocial = g.key === "social";
      if (focus === "all") out.push({ color: NEUTRAL });
      else if (focus === "split") out.push({ color: CATEGORY_COLOR[g.key] });
      else if (slots.has(index)) out.push({ color: CATEGORY_COLOR.social });
      else out.push({ color: isSocial ? FILTERED : OUTSIDE });
    }
  }
  return out;
}

export function NarrowingField({
  focus,
  groups,
  live,
}: {
  focus: StageFocus;
  groups: StoryGroup[];
  /** 이 단계에서 아직 살아 있는 소셜 칸의 수. 단계가 갈수록 줄어든다 */
  live: number;
}) {
  const dots = dotsFor(focus, groups, live);
  return (
    <div
      // 히트 타깃이 아니라 그림이다. 같은 수가 옆에 텍스트로 있으므로 보조기술에는 숨긴다
      // (§7.6의 반대편 규율: 값에 닿는 길은 이미 텍스트로 열려 있다).
      aria-hidden
      data-plot="narrowing"
      className="grid gap-[0.35rem]"
      style={{ gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))` }}
    >
      {dots.map((d, i) => (
        <span
          key={i}
          className="aspect-square rounded-[2px] transition-colors duration-300 ease-out"
          style={{ backgroundColor: d.color }}
        />
      ))}
    </div>
  );
}

/**
 * 무대의 범례. 지금 단계에서 실제로 쓰이는 색만 말한다 — 쓰지 않는 색을 설명하면 그림이
 * 아니라 목록이 된다.
 *
 * 자리는 단계와 무관하게 **비워 둔 채로 유지한다**. 범례가 있는 단계에서만 자리를 차지하면
 * 고정된 무대의 높이가 단계마다 달라져, 스크롤하는 내내 카드가 위아래로 뛴다.
 */
export function NarrowingLegend({ focus, groups }: { focus: StageFocus; groups: StoryGroup[] }) {
  return (
    <div className="mt-4 min-h-5">
      {focus === "split" && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {groups.map((g) => (
            <li key={g.key} className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-[2px]"
                style={{ backgroundColor: CATEGORY_COLOR[g.key] }}
              />
              <span className="text-[var(--ink-secondary)]">
                {g.label} {g.value}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
