import type { Metric } from "@/lib/report";

// 정의(R5)는 타일이 아니라 **KPI 행에 하나** 붙는다(ReportView) — 타일마다 펼침 장치를
// 달면 같은 모양이 6번 반복돼 정보가 아니라 잡음이 된다(2026-07-30 육안 검사).

function fmt(v: number | string): string {
  return typeof v === "number" ? v.toLocaleString("en-US") : v;
}

export function KpiTile({ m }: { m: Metric }) {
  const up = typeof m.delta === "number" && m.delta > 0;
  const down = typeof m.delta === "number" && m.delta < 0;
  return (
    <div className="glass-card p-4 transition-colors duration-200 ease-out hover:border-[var(--baseline)]">
      <div className="text-[11px] tracking-wide text-[var(--muted)]">{m.label}</div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        {/* 수치는 큰 글자로, 이름·제목 같은 문자열 값은 **줄여서 자르지 않고 접는다**.
            잘린 라벨은 없는 값을 만들어 낸다(`RESCENE - LO...`). 크기도 문자열일 때는
            낮춘다 — 24px로 두 줄이 되면 타일이 값이 아니라 덩어리로 읽힌다.
            tabular-nums도 숫자일 때만 쓴다(큰 숫자에서 자간이 벌어져 보인다). */}
        <span
          className={
            typeof m.value === "number"
              ? "truncate text-2xl font-black tracking-tight text-[var(--ink)]"
              : "text-base font-extrabold leading-snug tracking-tight text-[var(--ink)]"
          }
        >
          {fmt(m.value)}
        </span>
        {m.unit && <span className="shrink-0 text-xs text-[var(--ink-secondary)]">{m.unit}</span>}
      </div>
      {typeof m.delta === "number" && (
        <div
          className="mt-0.5 text-xs tabular-nums"
          style={{ color: up ? "var(--good)" : down ? "var(--bad)" : "var(--muted)" }}
        >
          {up ? "▲" : down ? "▼" : "→"} {Math.abs(m.delta).toLocaleString("en-US")}
        </div>
      )}
      {m.hint && (
        <div className="mt-1 truncate text-xs text-[var(--muted)]" title={m.hint}>
          {m.hint}
        </div>
      )}
    </div>
  );
}
