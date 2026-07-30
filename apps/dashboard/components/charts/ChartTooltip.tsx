"use client";

import { useCallback, useRef } from "react";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import type { ReactNode } from "react";

// 차트 공용 툴팁. visx에서 빌리는 것은 **경계 계산**뿐이다 — 뷰포트 끝에서 툴팁을 뒤집는
// 그 수학이 직접 쓰면 지저분해지는 부분이고, 룩은 전부 우리 토큰으로 덮는다
// (`unstyled` + `applyPositionStyle`이 라이브러리 기본 스타일을 끈다 · DESIGN §7).
//
// 툴팁은 값의 **유일한** 경로가 아니다(dataviz 비협상 항목) — 각 차트가 표 뷰를 함께 낸다.
// 그래서 여기서는 포커스에도 같은 내용이 뜨게만 보장한다.

export function useChartTooltip<T>() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const t = useTooltip<T>();

  const show = useCallback(
    (e: { clientX?: number; clientY?: number; target: EventTarget | null }, datum: T) => {
      const box = containerRef.current?.getBoundingClientRect();
      if (!box) return;
      // 포커스 이벤트에는 좌표가 없다 — 대상 마크의 위치로 대신한다(키보드에서도 같은 내용).
      let cx: number, cy: number;
      if (typeof e.clientX === "number" && typeof e.clientY === "number") {
        cx = e.clientX;
        cy = e.clientY;
      } else if (e.target instanceof Element) {
        const r = e.target.getBoundingClientRect();
        cx = r.left + r.width / 2;
        cy = r.top + r.height / 2;
      } else {
        return;
      }
      t.showTooltip({ tooltipLeft: cx - box.left, tooltipTop: cy - box.top, tooltipData: datum });
    },
    [t],
  );

  return { containerRef, show, hide: t.hideTooltip, open: t.tooltipOpen, datum: t.tooltipData, left: t.tooltipLeft, top: t.tooltipTop };
}

export type ChartTooltipHandle<T> = ReturnType<typeof useChartTooltip<T>>;

export function ChartTooltip<T>({ tip, children }: { tip: ChartTooltipHandle<T>; children: ReactNode }) {
  if (!tip.open || tip.datum === undefined) return null;
  return (
    <TooltipWithBounds
      unstyled
      applyPositionStyle
      left={tip.left}
      top={tip.top}
      offsetTop={-8}
      style={{
        // 증거 레이어 위에 뜨는 표면이라 글래스·그라디언트를 쓰지 않는다(DESIGN §4).
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "0.5rem",
        boxShadow: "0 4px 16px var(--shadow)",
        padding: "0.5rem 0.625rem",
        fontSize: "0.75rem",
        lineHeight: 1.45,
        pointerEvents: "none",
        maxWidth: 240,
        zIndex: 10,
      }}
    >
      {children}
    </TooltipWithBounds>
  );
}
