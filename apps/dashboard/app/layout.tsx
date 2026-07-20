import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Jost } from "next/font/google";
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
      </head>
      <body>{children}</body>
    </html>
  );
}
