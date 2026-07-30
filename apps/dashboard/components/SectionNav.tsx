"use client";

import type { Section } from "@/lib/report";

// D-043 — 구획 내비게이션. 한 번에 한 구획만 보여주기 위한 장치다.
//
// 왜 알약(pill) 탭이 아닌가: 이 페이지에는 이미 모듈 탭이 알약 형태로 있다. 같은 모양을
// 한 단 아래 또 놓으면 두 층의 위계가 무너지고, 반복되는 둥근 상자가 곧 짜침이 된다.
// 여기서는 번호 + 이름 + 얇은 밑줄만 쓴다(에디토리얼 · DESIGN §1 미니멀리즘: 표면당 강조 1개).
//
// 번호를 붙이는 이유는 장식이 아니라 **순서가 의미를 갖기 때문**이다. 구획은 임의의 묶음이
// 아니라 읽는 차례이고, 번호가 그 차례를 말한다.

export function SectionNav({
  sections,
  active,
  onSelect,
}: {
  sections: Section[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <nav
      className="-mx-5 flex gap-7 overflow-x-auto px-5 sm:mx-0 sm:px-0"
      role="tablist"
      aria-label="구획"
    >
      {sections.map((s, i) => {
        const on = s.id === active;
        return (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onSelect(s.id)}
            className="group shrink-0 pb-2.5 pt-1 text-left"
          >
            <span className="flex items-baseline gap-2">
              <span
                className={`font-display text-[10px] tabular-nums tracking-[0.2em] transition-colors duration-200 ease-out ${
                  on ? "text-[var(--series)]" : "text-[var(--muted)] group-hover:text-[var(--ink-secondary)]"
                }`}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <span
                className={`font-display text-sm tracking-wide transition-colors duration-200 ease-out ${
                  on ? "text-[var(--ink)]" : "text-[var(--muted)] group-hover:text-[var(--ink-secondary)]"
                }`}
              >
                {s.label}
              </span>
            </span>
            {/* 활성 표시는 밑줄 하나. 배경·테두리를 쓰지 않아 아래 내용과 경쟁하지 않는다. */}
            <span
              aria-hidden
              className={`mt-2 block h-px transition-colors duration-200 ease-out ${
                on ? "bg-[var(--series)]" : "bg-transparent"
              }`}
            />
          </button>
        );
      })}
    </nav>
  );
}
