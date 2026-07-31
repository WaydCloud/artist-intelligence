import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Jost } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import "./globals.css";

// 디스플레이 서체 폴백(Jost). Futura는 로컬 설치 환경에서만 렌더 — DESIGN.md §2.
const jost = Jost({ subsets: ["latin"], variable: "--font-jost", display: "swap" });

export const metadata: Metadata = {
  title: { default: "WaydCloud", template: "%s · WaydCloud" },
  description: "차트·팬덤·소셜 신호를 모아 참고용 리포트로 렌더하는 정적 대시보드.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" className={jost.variable} suppressHydrationWarning>
      <head>
        {/* 본문·한글 서체 Pretendard Variable — DESIGN.md §2 */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
        {/*
          🔴 첫 페인트 **전에** 테마를 정한다. React가 붙은 뒤에 정하면, 저장된 테마가 OS
          설정과 다른 사람에게 반대 색 화면이 한 번 번쩍인다(OS와 같으면 CSS 미디어 쿼리가
          이미 처리하므로 안 보인다 — 그래서 눈치채기 어려웠다).
          아무 선호도 없으면 속성을 **비워 둔다**. 그래야 globals.css의 OS 미디어 쿼리가 산다.
          우선순위는 ThemeProvider와 같은 순서여야 하고, 둘이 어긋나면 번쩍임이 돌아온다.
        */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var q=new URLSearchParams(location.search).get('theme');" +
              "var s=localStorage.getItem('theme');" +
              "var t=(q==='dark'||q==='light')?q:(s==='dark'||s==='light')?s:null;" +
              "if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})()",
          }}
        />
      </head>
      <body>
        {/* 테마는 여기 한 곳에서만 감싼다. 표면마다 훅을 따로 부르던 구조가 네 표면 중 둘에서
            조용히 끊겨 있었다(ThemeProvider 주석). */}
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
