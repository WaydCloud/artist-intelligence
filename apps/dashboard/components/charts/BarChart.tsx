import type { BarData } from "@/lib/report";

// Horizontal magnitude bars in plain HTML — naturally responsive, handles long
// (Korean) labels, single series → one hue (length carries magnitude, not color).
//
// 🔴 이 차트에는 툴팁을 달지 않는다. 이름과 값이 이미 막대 위에 **텍스트로** 찍혀 있어서
// 툴팁은 화면에 있는 것을 한 번 더 말할 뿐이고, 그 상태의 `title` 속성은 마우스를 올려야
// 나타나면서 정보는 0인 장식이었다(DESIGN §1 "요소를 더하기 전에 뺄 것을 먼저 찾는다").
// 화면이 실제로 감추는 것은 **잘린 이름 하나**뿐이라, 표기는 그 자리에만 남긴다.
export function BarChart({ data }: { data: BarData }) {
  if (data.length === 0) return <p className="text-sm text-[var(--muted)]">데이터 없음</p>;
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="space-y-2.5">
      {data.map((d, i) => (
        <div key={i}>
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="truncate text-xs text-[var(--ink-secondary)]" title={d.name}>
              {d.name}
            </span>
            <span className="shrink-0 text-xs tabular-nums text-[var(--muted)]">
              {d.value.toLocaleString("en-US")}
            </span>
          </div>
          <div
            className="h-1.5 rounded-full"
            style={{ background: "color-mix(in srgb, var(--hairline) 55%, transparent)" }}
          >
            <div
              className="h-1.5 rounded-full transition-[width] duration-300 ease-out"
              style={{ width: `${Math.max(1, (d.value / max) * 100)}%`, background: "var(--series)" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
