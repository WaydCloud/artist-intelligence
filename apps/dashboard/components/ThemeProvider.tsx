"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/**
 * 테마 하나를 **모든 표면이 나눠 쓴다.** 루트 레이아웃이 이것 하나를 감싸므로,
 * 앞으로 만드는 표면은 아무것도 하지 않아도 테마를 받는다.
 *
 * 🔴 왜 컨텍스트로 올렸나: 예전에는 페이지마다 훅을 각자 불렀고, 부르는 것을 잊으면
 * **조용히 끊겼다.** 실측(2026-07-31) 네 표면 중 둘이 그 상태였다 — `/utilities`는 아예
 * 안 걸려 다크로 보던 사람에게 흰 화면이 튀었고, `/labs`는 색은 맞는데 토글이 없어 들어가면
 * 갇혔다. 같은 사고가 랜딩에서도 한 번 났다. 세 번 났으면 그것은 실수가 아니라 구조다.
 *
 * 우선순위는 쿼리(`?theme=`) → 저장값 → OS 설정이며 이 순서가 정본이다.
 * 쿼리를 먼저 보는 것은 스모크가 테마를 지정해 열기 때문이다.
 */
export type Theme = "light" | "dark";

const ThemeContext = createContext<readonly [Theme, (t: Theme) => void] | null>(null);

function readInitial(): Theme {
  try {
    const forced = new URLSearchParams(window.location.search).get("theme");
    if (forced === "dark" || forced === "light") return forced;
    const stored = localStorage.getItem("theme");
    if (stored === "dark" || stored === "light") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // 🔴 첫 렌더에서 바로 읽지 않는다. 정적 산출물은 "light"로 그려져 있는데 브라우저의 첫
  // 렌더가 저장값을 읽어 "dark"로 시작하면, 그 값으로 그리는 것들(토글 라벨 `☀ Light`)이
  // 서버 산출물과 어긋나 하이드레이션이 통째로 깨진다(실측 — 루트가 클라이언트 렌더로
  // 넘어간다). 색 번쩍임은 `layout.tsx`의 첫 페인트 스크립트가 이미 막으므로, 상태는
  // 마운트 뒤에 정해도 눈에 보이는 손해가 없다.
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => setTheme(readInitial()), []);

  useEffect(() => {
    if (!theme) return; // 아직 안 정해진 동안 기본값을 저장하지 않는다(저장값을 덮어쓴다)
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch {
      // 저장이 막힌 환경(사생활 보호 모드 등)에서도 화면은 그대로 동작해야 한다.
    }
  }, [theme]);

  return (
    <ThemeContext.Provider value={[theme ?? "light", setTheme] as const}>
      {children}
    </ThemeContext.Provider>
  );
}

/**
 * 🔴 공급자 밖에서 부르면 **던진다.** 조용히 기본값을 돌려주면 예전과 똑같은 사고가 난다 —
 * 테마가 안 걸린 표면이 멀쩡해 보이고, 다른 테마로 열어 봐야 발견된다.
 */
export function useTheme(): readonly [Theme, (t: Theme) => void] {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme은 ThemeProvider 안에서만 쓴다 (루트 레이아웃이 감싼다)");
  return ctx;
}
