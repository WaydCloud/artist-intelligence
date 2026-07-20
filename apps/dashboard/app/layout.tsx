import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Artist Intelligence — 리포트 대시보드",
  description: "모듈이 배출한 스키마 유효 report.json을 렌더하는 범용 리포트 뷰.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
