import reportsJson from "@/data/reports.json";
import type { BarData, Inference, Reliability, Report } from "@/lib/report";

// 랜딩 서사가 쓰는 수치의 단일 조달구 (DESIGN.md §7.8).
//
// 🔴 규칙 하나로 요약된다: **서사에 나오는 모든 수는 report.json에서 구조적으로 온다.**
// 지표는 라벨로, 분류 구성은 차트 id로 찾고, 못 찾으면 여기서 빌드를 세운다.
// 문장에 숫자를 적어 넣는 순간 그 화면은 데이터가 갱신돼도 늙지 않고, 늙지 않는 화면은
// **틀린 채로 산다** — 매일 수집이 도는 제품에서 이건 시간 문제가 아니라 확률 문제다.
//
// 인사이트 문자열을 파싱해 수를 꺼내지 않는다. 인사이트는 사람이 읽는 문장이라 형식이
// 계약이 아니고, 파싱하는 순간 모듈이 문구를 다듬을 때마다 랜딩이 조용히 틀린다.
// 구조적으로 없는 수는 **서사에서 뺀다**(문장을 바꾸는 쪽이 옳다).

const reports = reportsJson as unknown as Report[];

function fail(what: string): never {
  throw new Error(
    `[story] ${what}\n` +
      `랜딩 서사의 수치는 report.json에서 구조적으로 조달한다(DESIGN.md §7.8).\n` +
      `모듈 출력이 바뀌었다면 서사 문장을 고치거나 모듈이 그 값을 다시 싣게 한다. ` +
      `여기에 숫자를 적어 넣어 고치지 않는다.`,
  );
}

function report(moduleId: string): Report {
  return reports.find((r) => r.moduleId === moduleId) ?? fail(`리포트 없음: ${moduleId}`);
}

/** 지표를 **라벨로** 찾는다. 라벨은 모듈이 화면에 쓰는 이름이라 서사와 같은 말을 쓴다. */
function metricNumber(r: Report, label: string): number {
  const m = r.metrics.find((x) => x.label === label) ?? fail(`지표 없음: ${r.moduleId} · ${label}`);
  const n = typeof m.value === "number" ? m.value : Number(m.value);
  return Number.isFinite(n) ? n : fail(`지표가 수가 아님: ${r.moduleId} · ${label} = ${m.value}`);
}

function metricText(r: Report, label: string): string {
  const m = r.metrics.find((x) => x.label === label) ?? fail(`지표 없음: ${r.moduleId} · ${label}`);
  return `${m.value}${m.unit ?? ""}`;
}

/** 요약 도형(R2)을 포함해 찾는다 — 요약에 실린 차트는 `charts`에 중복하지 않기 때문. */
function barChart(r: Report, id: string): BarData {
  const all = r.summary ? [r.summary, ...r.charts] : r.charts;
  const c = all.find((x) => x.id === id) ?? fail(`차트 없음: ${r.moduleId} · ${id}`);
  return c.type === "bar" ? c.data : fail(`차트가 bar가 아님: ${r.moduleId} · ${id} = ${c.type}`);
}

function barValue(data: BarData, name: string, where: string): number {
  return data.find((d) => d.name === name)?.value ?? fail(`막대 없음: ${where} · ${name}`);
}

/** 동반 4종이 다 있는 추론만 서사에 오른다(DESIGN §6.2 — 없으면 렌더하지 않는다). */
function inference(r: Report, chartId: string): Inference {
  const found = (r.inferences ?? []).filter((i) => i.chartId === chartId);
  const ok = found.find((i) => [i.text, i.basis, i.sample, i.limits].every((v) => !!v?.trim()));
  return ok ?? fail(`동반 4종을 갖춘 추론 없음: ${r.moduleId} · ${chartId}`);
}

// ── 무대의 상태 ────────────────────────────────────────────────────────────
// 단계가 바뀔 때 옮겨 가는 것은 **지금 보는 부분집합**이지 값의 자리가 아니다(§7.8).
export type StageFocus = "all" | "split" | "narrowed";

export interface StoryStep {
  id: string;
  /** 왼쪽 작은 라벨. 지금 무엇을 세고 있는지 */
  kicker: string;
  /** 단계의 문장 */
  headline: string;
  body: string;
  focus: StageFocus;
  /** 이 단계에서 아직 살아 있는 소셜 칸의 수 */
  live: number;
  /** 무대 위에 크게 뜨는 수와 그 단위 */
  count: number;
  countLabel: string;
  /**
   * 이 단계가 관측이 아니라 **해석**이면 여기 실린다(D-039 · §6.2).
   * 해석 단계는 무대를 그 해석이 나온 상태로 되돌린다 — 주장과 그림을 같은 화면에 두지 않으면
   * 읽는 사람이 "이 말이 어디서 나왔나"를 스스로 되짚어야 한다.
   */
  inference?: Inference;
}

export interface StoryGroup {
  key: "social" | "chart" | "same";
  label: string;
  value: number;
}

export interface LandingStory {
  generatedAt: string;
  hero: { label: string; value: string }[];
  narrative: {
    kicker: string;
    question: string;
    /** 무대의 판독 규칙. 칸 하나가 팀 하나이고 자리에는 뜻이 없다 */
    stageNote: string;
    total: number;
    groups: StoryGroup[];
    survivors: number;
    steps: StoryStep[];
    /** 선행 일수 상위 팀. 이름이 있는 목록이 그대로 답은 아니라는 것이 서사의 반전 */
    leaders: { name: string; value: number }[];
    reliability?: Reliability;
    notAnswered: string[];
    href: string;
  };
  rails: {
    moduleId: string;
    title: string;
    /** 이 모듈이 앞장서 묻는 질문. 카드의 머리글은 라벨이 아니라 질문이다(D-043의 원칙) */
    question: string;
    /** 구획 수 = 그 탭이 답하는 질문의 수 */
    questionCount: number;
    headline: string;
    unit: string;
    href: string;
    /** 방금 따라온 서사가 이 모듈에서 나왔는가 */
    isStory: boolean;
  }[];
}

// 모듈 카드에 세울 대표 지표. 어느 수를 앞에 둘지는 표시 판단이라 여기 모아 둔다
// (모듈이 지표 순서를 바꿔도 랜딩의 얼굴이 따라 흔들리지 않게).
const RAIL_METRIC: Record<string, string> = {
  "chart-history": "조사한 나라",
  "fandom-pulse": "곡 라벨로 잡힌 팀",
  "genre-impulse": "오늘 본 곡",
  "signal-bridge": "추적 아티스트",
  "sonic-profile": "관측 트랙",
  "yt-pulse": "수집한 영상",
};

/** 서사가 어느 모듈에서 나오는가. 링크와 카드 표시가 같은 값을 봐야 둘이 어긋나지 않는다. */
const STORY_MODULE = "signal-bridge";

export function buildLandingStory(): LandingStory {
  const bridge = report("signal-bridge");
  const chart = report("chart-history");
  const sonic = report("sonic-profile");

  const total = metricNumber(bridge, "두 신호가 다 있는 팀");
  const socialLed = metricNumber(bridge, "소셜 선행");
  const sampled = metricNumber(bridge, "표본을 채운 선행");
  const survivors = metricNumber(bridge, "판정 가능 선행");
  const offChart = metricNumber(bridge, "차트 밖에서 도는 팀");

  const mix = barChart(bridge, "class-mix");
  const groups: StoryGroup[] = [
    { key: "social", label: "소셜이 먼저", value: barValue(mix, "소셜이 먼저", "class-mix") },
    { key: "chart", label: "차트가 먼저", value: barValue(mix, "차트가 먼저", "class-mix") },
    { key: "same", label: "같은 날", value: barValue(mix, "같은 날", "class-mix") },
  ];

  // 구성의 합이 모집단과 어긋나면 무대의 칸 수가 거짓이 된다. 리포트가 바뀌면 여기서 선다.
  const sum = groups.reduce((a, g) => a + g.value, 0);
  if (sum !== total) fail(`구성의 합(${sum})이 모집단(${total})과 다르다`);
  if (groups[0].value !== socialLed) fail(`'소셜이 먼저'(${groups[0].value})와 지표(${socialLed})가 다르다`);
  // 좁혀지는 서사는 각 단계가 앞 단계의 부분집합일 때만 성립한다. 순서가 뒤집히면 그림이
  // "줄어든다"고 말하면서 실제로는 늘어나므로, 여기서 세운다.
  if (!(survivors <= sampled && sampled <= socialLed))
    fail(`좁혀지는 순서가 깨졌다: 선행 ${socialLed} → 표본 ${sampled} → 통과 ${survivors}`);

  const leaders = barChart(bridge, "lead-days")
    .slice(0, 5)
    .map((d) => ({ name: d.name, value: d.value }));

  // 🔴 두 관문을 한 단계에 몰지 않는다. 원장(signal-bridge RULES §3.1)이 "소표본은 기준값이
  // 정하는 문제이고 검열은 시간이 푸는 문제라 두 축을 섞어 보고하지 않는다"고 정해 두었는데,
  // 65에서 1로 한 번에 줄이면 **무엇이 걸러 냈는지**가 그림에서 사라진다.
  const steps: StoryStep[] = [
    {
      id: "cohort",
      kicker: "모집단",
      headline: `두 신호가 다 있는 팀 ${total}팀`,
      body: "소셜에서 도는 것이 보이고 차트에도 오른 팀만 여기 있다. 둘 중 하나만 있으면 순서를 잴 수 없다.",
      focus: "all",
      live: 0,
      count: total,
      countLabel: "팀",
    },
    {
      id: "split",
      kicker: "순서",
      headline: groups.map((g) => `${g.label} ${g.value}`).join(" · "),
      body: "어느 쪽이 먼저 움직였는지로 갈랐다. 소셜이 먼저인 쪽이 더 많지만 반대 방향도 그만큼 있다. 순서는 시간 순서일 뿐 인과가 아니다.",
      focus: "split",
      live: 0,
      count: total,
      countLabel: "팀",
    },
    {
      id: "social",
      kicker: "선행",
      headline: `소셜이 먼저였던 ${socialLed}팀`,
      body: `여기서 목록을 뽑으면 이름이 나온다. ${leaders
        .slice(0, 3)
        .map((l) => `${l.name} ${l.value}일`)
        .join(" · ")} 순이다.`,
      focus: "narrowed",
      live: socialLed,
      count: socialLed,
      countLabel: "팀",
    },
    {
      id: "sample",
      kicker: "표본",
      headline: `게시가 기준에 못 미치는 팀을 빼면 ${sampled}팀`,
      body: "며칠 먼저였는지는 게시가 몇 건이었는지에 달렸다. 창 전체에서 게시가 몇 건 안 되면 그 며칠이 우연과 구별되지 않는다. 이 관문은 우리가 정한 기준값이라 시간이 지나도 저절로 풀리지 않는다.",
      focus: "narrowed",
      live: sampled,
      count: sampled,
      countLabel: "팀",
    },
    {
      id: "censor",
      kicker: "절단",
      headline: `수집 첫날에 이미 차트에 있던 팀을 빼면 ${survivors}팀`,
      body: "차트에 처음 보인 날이 수집을 시작한 날과 같으면 그날 올라온 것인지 이미 있었던 것인지 알 수 없다. 앞의 관문과 달리 이건 시간이 푼다. 수집이 쌓이면 이 줄은 다시 늘어난다.",
      focus: "narrowed",
      live: survivors,
      count: survivors,
      countLabel: "팀",
    },
    // 여기부터는 관측이 아니라 해석이다. 서사의 리듬을 그대로 이어 **한 화면에 하나씩** 둔다.
    // 예전에는 해석 둘과 미답 질문 다섯이 한 화면에 함께 있었고, 다섯 단계를 천천히 끌고 와
    // 놓고 마지막에만 정보를 쏟는 형태라 아무도 읽지 않고 지나갔다.
    {
      id: "reading-mix",
      kicker: "해석",
      headline: "",
      body: "",
      focus: "split",
      live: 0,
      count: total,
      countLabel: "팀",
      inference: inference(bridge, "class-mix"),
    },
    {
      id: "reading-solid",
      kicker: "해석",
      headline: "",
      body: "",
      focus: "narrowed",
      live: survivors,
      count: survivors,
      countLabel: "팀",
      inference: inference(bridge, "lead-days"),
    },
  ];

  return {
    generatedAt: bridge.generatedAt,
    // 라벨은 이름표가 아니라 **그 수가 무엇을 뜻하는지**를 말한다. "차트 밖에서 도는 팀"은
    // 이 제품에서 가장 흥미로운 수인데 이름표만으로는 뜻이 서지 않았다.
    // 🔴 "아직 차트에 없는"처럼 앞날을 함의하는 말을 쓰지 않는다 — 차트에 없다는 것은
    // 이번 수집 창에서 보이지 않았다는 뜻이지 앞으로 오른다는 뜻이 아니다.
    hero: [
      { label: "소셜과 차트에서 이름을 따라가는 팀", value: metricText(bridge, "추적 아티스트") },
      { label: "순위를 매일 걷어 오는 나라", value: metricText(chart, "조사한 나라") },
      { label: "30초 프리뷰로 소리를 잰 곡", value: metricText(sonic, "관측 트랙") },
      { label: "차트에는 없고 소셜에서만 도는 팀", value: `${offChart}팀` },
    ],
    narrative: {
      kicker: "관측 하나를 끝까지",
      question: "소셜이 차트보다 먼저 움직이는가",
      stageNote: `칸 하나가 팀 하나다. 전체 ${total}칸이고 자리에는 뜻이 없다.`,
      total,
      groups,
      survivors,
      steps,
      leaders,
      reliability: bridge.reliability,
      notAnswered: bridge.notAnswered ?? [],
      href: `/artist-intelligence#${STORY_MODULE}`,
    },
    rails: reports.map((r) => {
      const picked = RAIL_METRIC[r.moduleId];
      // 고른 지표가 없거나 사라졌으면 첫 수치 지표로 물러선다. 여기서 빌드를 세우지 않는 이유는
      // 새 모듈이 붙었을 때 랜딩이 그 모듈을 조용히 빠뜨리는 것보다 낫기 때문이다.
      const m =
        (picked ? r.metrics.find((x) => x.label === picked) : undefined) ??
        r.metrics.find((x) => typeof x.value === "number") ??
        fail(`레일에 실을 수치 지표가 없음: ${r.moduleId}`);
      // 🔴 카드가 말할 것은 규모가 아니라 **질문**이다. 크기는 히어로가 이미 말했고, 여기서
      // 다시 말하면 같은 일을 두 번 한다. 서사를 막 끝낸 사람에게 필요한 것은 "나머지 다섯은
      // 무엇을 묻는가"이며, 그 답은 리포트가 구획 머리글로 이미 갖고 있다.
      const question =
        r.sections?.[0]?.question ??
        r.questions?.[0]?.q ??
        fail(`앞장서 물을 질문이 없음: ${r.moduleId}`);
      return {
        moduleId: r.moduleId,
        title: r.title,
        question,
        questionCount: r.sections?.length ?? r.questions?.length ?? 0,
        headline: `${m.value}${m.unit ?? ""}`,
        unit: m.label,
        href: `/artist-intelligence#${r.moduleId}`,
        isStory: r.moduleId === STORY_MODULE,
      };
    }),
  };
}
