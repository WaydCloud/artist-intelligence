"use client";

import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

/**
 * 테마 하나를 두 표면(리포트 대시보드·LABS)이 나눠 쓴다.
 *
 * 복제하지 않는 이유는 취향이 아니라 동작이다: 두 벌이 되면 저장 키와 `?theme=` 처리가
 * 갈라져 **한쪽에서 고른 테마가 다른 쪽으로 안 넘어간다**. 저장은 `localStorage`,
 * 강제는 쿼리(`?theme=dark`), 기본은 OS 설정 순이며 이 순서가 정본이다.
 * 쿼리를 먼저 보는 것은 스모크가 테마를 지정해 열기 때문이다.
 */
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const forced = new URLSearchParams(window.location.search).get("theme");
    const stored = localStorage.getItem("theme");
    const initial: Theme =
      forced === "dark" || forced === "light"
        ? forced
        : stored === "dark" || stored === "light"
          ? (stored as Theme)
          : window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
    setTheme(initial);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  return [theme, setTheme];
}
