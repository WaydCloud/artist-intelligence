"use client";

import { ThemeToggle } from "@/components/ThemeToggle";
import { useTheme } from "@/components/ThemeProvider";

/**
 * 어디에나 놓을 수 있는 테마 전환 버튼.
 *
 * 표면마다 `useTheme` + `ThemeToggle`을 다시 배선하던 것이 세 벌이었고, 새 표면에서는
 * 그 배선 자체를 잊었다(`/labs`·`/utilities`). 배선을 여기 한 번만 두면 새 표면은
 * 이것 하나를 놓기만 하면 된다.
 */
export function ThemeButton() {
  const [theme, setTheme] = useTheme();
  return <ThemeToggle theme={theme} onToggle={() => setTheme(theme === "dark" ? "light" : "dark")} />;
}
