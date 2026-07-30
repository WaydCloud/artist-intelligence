"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * 한 차트의 예외가 대시보드 전체를 죽이지 않게 막는다.
 *
 * 2026-07-30: genre-impulse의 신규 view 하나가 `matrix.cols`에서 TypeError를 냈고,
 * 바운더리가 없어 React 트리 전체가 언마운트됐다 -- 무관한 모듈 6개의 탭까지 못 보게 됐다.
 * 원인(미지 view의 fallthrough)은 Tunable에서 고쳤지만, 그건 이 결함 하나에 대한 답이다.
 * 이 컴포넌트는 *다음* 결함의 폭발 반경을 카드 한 장으로 묶는다.
 *
 * 콘솔 에러는 일부러 삼키지 않는다: React가 남기는 에러 로그가 탭 스모크
 * (`scripts/smoke-tabs.mjs`)의 판정 근거다. 조용히 복구하면 게이트가 초록이 된다.
 */
export class ChartBoundary extends Component<
  { children: ReactNode; label?: string },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[chart] 렌더 실패${this.props.label ? `: ${this.props.label}` : ""}`, error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <p className="text-sm leading-relaxed text-[var(--muted)]">
        이 차트를 표시하지 못함. 나머지 항목은 정상 표시.
      </p>
    );
  }
}
