import type { Reliability } from "@/lib/report";

// R8 — "이 화면을 어디까지 믿을지"를 도구가 먼저 말하는 줄.
//
// 왜 1급 요소인가: 사용자가 도구를 신뢰하는 이유는 정확해서가 아니라 **얼마나 못 미더운지를
// 도구가 먼저 말해서**다(REFERENCE §3 기제 ④, 이식 가치 최상). FM은 이걸 "고용한 분석관의
// 능력치"로 게임 안에 수치화해 두었고, 사용자는 그래서 어디까지 믿을지 스스로 조정했다.
//
// 🔴 각주 금지. 이 줄은 플롯 **위**에 온다 — 카드 바닥에 두면 각주가 되고 각주는 안 읽힌다.
// 색을 쓰지 않는 것도 규율이다: 상태색(--good/--bad)은 예약되어 있고(dataviz), 신뢰도를
// 빨갛게 칠하면 정보가 아니라 경고로 읽혀 사용자가 그 줄을 무시하기 시작한다.

const FIELDS: { key: keyof Reliability; label: string }[] = [
  { key: "sample", label: "표본" },
  { key: "accuracy", label: "정확도" },
  { key: "missing", label: "결측" },
  { key: "engine", label: "엔진" },
];

export function ReliabilityLine({ r }: { r?: Reliability }) {
  const items = FIELDS.map((f) => ({ ...f, v: r?.[f.key] })).filter((f) => !!f.v?.trim());
  if (items.length === 0) return null;
  return (
    <dl className="mb-4 flex flex-wrap gap-x-4 gap-y-1 border-y border-[var(--hairline)] py-2 text-xs leading-relaxed">
      {items.map((f) => (
        <div key={f.key} className="flex min-w-0 gap-1.5">
          <dt className="shrink-0 text-[var(--muted)]">{f.label}</dt>
          <dd className="min-w-0 text-[var(--ink-secondary)]">{f.v}</dd>
        </div>
      ))}
    </dl>
  );
}
