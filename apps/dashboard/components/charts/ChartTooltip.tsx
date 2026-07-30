"use client";

import { useCallback, useRef } from "react";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import type { ReactNode } from "react";

// 차트 공용 툴팁. visx에서 빌리는 것은 **경계 계산**뿐이다 — 뷰포트 끝에서 툴팁을 뒤집는
// 그 수학이 직접 쓰면 지저분해지는 부분이고, 룩은 전부 우리 토큰으로 덮는다(DESIGN §7).
//
// 🔴 `unstyled`를 쓰지 않는다. visx는 `...(!unstyled && style)`이라 **unstyled를 주면
// 우리 `style`까지 버린다** — 라이브러리 기본만 끄는 플래그가 아니다. 그 상태에서는 배경도
// 테두리도 없는 맨 텍스트가 플롯 선 위에 겹쳐 그려졌다(2026-07-30 육안 검사에서 실제로
// 발생 · DESIGN §4 "증거 위에 오버레이 금지"의 반대 방향 위반: 오버레이가 표면을 잃었다).
// 기본 스타일을 끄는 것은 `unstyled`가 아니라 **`style`을 주는 것 자체**다(visx의
// `defaultStyles`는 style prop의 기본값일 뿐이라 우리가 주면 남지 않는다).
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

  // 크로스헤어처럼 **마크가 아닌 위치**에 띄울 때. 스냅된 데이터 좌표를 쓰기 때문에
  // 포인터의 raw 좌표(`show`)로는 안 된다 — 툴팁이 선에서 떨어져 따라다니면 어느 지점을
  // 말하는지 흐려진다. 좌표는 컨테이너 기준(px)이고 변환은 부르는 쪽이 한다(차트마다
  // viewBox 배율이 다르다).
  const showAt = useCallback(
    (left: number, top: number, datum: T) => {
      t.showTooltip({ tooltipLeft: left, tooltipTop: top, tooltipData: datum });
    },
    [t],
  );

  return {
    containerRef,
    show,
    showAt,
    hide: t.hideTooltip,
    open: t.tooltipOpen,
    datum: t.tooltipData,
    left: t.tooltipLeft,
    top: t.tooltipTop,
  };
}

export type ChartTooltipHandle<T> = ReturnType<typeof useChartTooltip<T>>;

export function ChartTooltip<T>({ tip, children }: { tip: ChartTooltipHandle<T>; children: ReactNode }) {
  if (!tip.open || tip.datum === undefined) return null;
  return (
    <TooltipWithBounds
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
        // 통합 툴팁은 `시리즈명 값` 줄이 여럿이라 240px에서는 시리즈명이 잘렸다.
        maxWidth: 300,
        zIndex: 10,
      }}
    >
      {children}
    </TooltipWithBounds>
  );
}
