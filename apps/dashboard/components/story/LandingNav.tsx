"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ThemeButton } from "@/components/ThemeButton";

// 랜딩 상단 크롬. 히어로를 지나면 나타난다.
//
// 토글은 하나이고 처음부터 끝까지 같은 자리에 있다. 스크롤에 따라 나타나는 것은
// **막대와 이동 링크**다. (상태 자체는 루트의 ThemeProvider가 들고 있으므로 토글이 여럿이어도
// 갈라지지 않지만, 같은 화면에 토글이 둘일 이유는 없다.)
//
// 🔴 스크롤 좌표를 재지 않는다(§7.8). 히어로 끝의 파수꾼 요소가 화면에서 빠졌는지만 본다 —
// 좌표 계산은 주소 이동·확대·모바일 주소창에서 어긋난다.
// 움직임이 설명하는 것: **히어로를 떠났고 이제 이동 수단이 필요한 자리라는 것**(§7.7).

const LINKS = [
  { href: "/artist-intelligence", label: "리포트" },
  { href: "/labs", label: "Labs" },
];

/** 히어로 끝의 파수꾼과 맨 위 앵커. 페이지가 같은 id를 심어야 하므로 여기서 내보낸다. */
export const HERO_SENTINEL_ID = "hero-end";
export const PAGE_TOP_ID = "page-top";

export function LandingNav() {
  const [past, setPast] = useState(false);

  useEffect(() => {
    const sentinel = document.getElementById(HERO_SENTINEL_ID);
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      ([entry]) => setPast(!entry.isIntersecting && entry.boundingClientRect.top < 0),
      { threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="fixed inset-x-0 top-0 z-30">
      <div
        // 막대의 표면만 페이드한다. 높이는 처음부터 자리를 차지하고 있어 나타날 때
        // 아래 내용이 밀리지 않는다(밀리면 그것은 설명이 아니라 사고다).
        className="border-b transition-[background-color,border-color,backdrop-filter] duration-300 ease-out"
        style={{
          backgroundColor: past ? "var(--glass-bg)" : "transparent",
          borderColor: past ? "var(--glass-border)" : "transparent",
          backdropFilter: past ? "blur(16px)" : "none",
          WebkitBackdropFilter: past ? "blur(16px)" : "none",
        }}
      >
        <nav className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-6">
          <Link
            href={`#${PAGE_TOP_ID}`}
            aria-hidden={!past}
            tabIndex={past ? 0 : -1}
            // 🔴 작은 워드마크는 히어로의 것을 그대로 줄이면 안 된다. 14px에 굵기 100 +
            // 메탈을 걸었더니 유령처럼 사라졌다 — 얇은 획은 크기가 줄면 먼저 없어지고,
            // 메탈은 획이 좁아 색 변화가 아니라 흐림으로만 남는다(§2.1의 하한).
            // 그래서 여기서는 단색으로 가고 굵기를 한 칸만 올린다. 얇은 인상은 자간이 낸다.
            className="font-display text-sm font-extralight uppercase tracking-[0.3em] text-[var(--ink)] transition-opacity duration-300 ease-out"
            style={{ opacity: past ? 1 : 0, paddingLeft: "0.3em" }}
          >
            WaydCloud
          </Link>

          <div
            className="ml-auto flex items-center gap-5 transition-opacity duration-300 ease-out"
            style={{ opacity: past ? 1 : 0 }}
          >
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-hidden={!past}
                tabIndex={past ? 0 : -1}
                className="text-sm text-[var(--ink-secondary)] transition-colors duration-150 ease-out hover:text-[var(--ink)]"
              >
                {l.label}
              </Link>
            ))}
          </div>

          {/* 토글은 언제나 있다. 나타나는 것은 위의 둘뿐 */}
          <div className={past ? "" : "ml-auto"}>
            <ThemeButton />
          </div>
        </nav>
      </div>
    </div>
  );
}
