"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Inference } from "@/lib/report";

// R4 · D-039 — 자동 추론을 **버리지 않고 태그해** 보여준다.
//
// 불변식이 금지하는 것은 **평결**이고, 꼬리표 달린 추론은 평결이 아니다 — 출처가 명시된
// 해석이며 사람이 채택·기각할 대상이다. FM 커뮤니티가 자동 결론을 버린 이유는 결론이
// 있었기 때문이 아니라 **근거가 안 보였기 때문**이다(REFERENCE §4).
//
// 규약 정본은 DESIGN §6.2:
//   · 동반 4종(basis·sample·confidence·limits) 하나라도 없으면 **렌더하지 않는다**
//   · 배치는 항상 관측 **아래**, 배지로 구분
//   · 배지를 누르면 근거가 펼쳐진다
//   · 배지에 메탈릭 금지 — 추론이 화려하면 신뢰가 아니라 권위로 읽힌다

const GRADE: Record<Inference["confidence"], string> = {
  low: "확실성 낮음",
  medium: "확실성 보통",
  high: "확실성 높음",
};

// 계약(스키마 required)이 이미 막지만 렌더 층에서도 거부한다 — 계약을 우회한 경로로
// 들어온 추론이 근거 없이 화면에 오르는 일이 없도록.
function complete(i: Inference): boolean {
  return [i.text, i.basis, i.sample, i.limits].every((v) => !!v?.trim()) && !!GRADE[i.confidence];
}

function InferenceItem({ inf }: { inf: Inference }) {
  const [open, setOpen] = useState(false);
  const still = useReducedMotion();
  return (
    <li className="border-l-2 border-[var(--hairline)] pl-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="text-micro shrink-0 rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] tracking-wide text-[var(--ink-secondary)] transition-colors duration-150 ease-out hover:border-[var(--baseline)] hover:text-[var(--ink)]"
        >
          AI추론 {open ? "▴" : "▾"}
        </button>
        <span className="text-micro shrink-0 text-[10px] tabular-nums text-[var(--muted)]">{GRADE[inf.confidence]}</span>
        <p className="min-w-0 max-w-[68ch] text-sm leading-relaxed text-[var(--ink-secondary)]">{inf.text}</p>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            // 상태 변화를 설명하는 모션만 쓴다(DESIGN §5·§7). reduced-motion에서는 즉시 완료.
            initial={still ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={still ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: still ? 0 : 0.2, ease: "easeOut" }}
            style={{ overflow: "hidden" }}
          >
            <dl className="mt-2 grid gap-x-4 gap-y-1.5 text-xs leading-relaxed sm:grid-cols-[auto_1fr]">
              {[
                ["근거", inf.basis],
                ["표본", inf.sample],
                ["못 보는 것", inf.limits],
              ].map(([k, v]) => (
                <div key={k} className="sm:contents">
                  <dt className="text-[var(--muted)]">{k}</dt>
                  <dd className="max-w-[68ch] text-[var(--ink-secondary)]">{v}</dd>
                </div>
              ))}
            </dl>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

export function InferenceBlock({ items, nested = false }: { items: Inference[]; nested?: boolean }) {
  const shown = items.filter(complete);
  if (shown.length === 0) return null;
  return (
    <section className={nested ? "mt-4 border-t border-[var(--hairline)] pt-4" : "glass-card p-5"}>
      <h2 className="mb-1 font-display text-sm font-extrabold tracking-wide">해석</h2>
      <p className="mb-3 text-xs text-[var(--muted)]">
        자동으로 붙인 해석. 관측이 아니며 채택·기각은 읽는 사람의 몫. 배지를 누르면 근거가 열림
      </p>
      <ul className="space-y-3">
        {shown.map((inf, i) => (
          <InferenceItem key={i} inf={inf} />
        ))}
      </ul>
    </section>
  );
}
