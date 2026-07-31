"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ReliabilityLine } from "@/components/ReliabilityLine";
import { NarrowingField, NarrowingLegend } from "@/components/story/NarrowingField";
import type { Inference } from "@/lib/report";
import type { LandingStory, StoryStep } from "@/lib/story";

// 좁혀지는 서사 (DESIGN.md §7.8 · D-056).
//
// 이 서사가 성립하는 이유는 반전이 있어서가 아니라 **증거가 순서를 요구하기 때문**이다.
// 126에서 1로 줄어드는 과정은 126과 1을 나란히 놓아서는 전달되지 않는다 — 무엇이 걸러
// 냈는지가 각 단계에 있고, 그 걸러 낸 것이 곧 이 관측의 한계다. 그래서 한계가 마지막
// 각주로 밀리지 않는다.
//
// 🔴 결론도 같은 리듬으로 간다. 다섯 단계를 천천히 끌고 와 놓고 마지막 한 화면에 해석 둘과
// 미답 질문 다섯을 함께 쏟으면 거기서부터는 아무도 읽지 않는다(실측). 한 채널에 최대 셋이라는
// 규칙(§7.1.1)은 서사의 **끝에서 먼저** 무너진다 — 거기가 남은 것을 몰아 두기 가장 쉬운 자리라서.
//
// 🔴 스크롤을 가로채지 않는다. `scroll-snap`도 스크롤 위치 조작도 없고, 활성 단계는
// 교차 관측으로만 정해진다. 스크롤 좌표 계산은 주소 이동·확대·모바일 주소창에서 어긋난다.

type Narrative = LandingStory["narrative"];

const GRADE: Record<Inference["confidence"], string> = {
  low: "확실성 낮음",
  medium: "확실성 보통",
  high: "확실성 높음",
};

/**
 * 해석 단계 (D-039 · §6.2).
 *
 * 여기서는 동반 4종을 **접지 않고 그대로 보여준다.** 배지 뒤에 접어 두는 것은 자리가 없을 때의
 * 방편인데 이 화면에는 자리가 남고, 접어 두면 근거가 있다는 사실 자체를 모른다(§7.6과 같은 방향).
 *
 * 🔴 해석 문장을 관측 문장보다 크게 쓰지 않는다. 배지에 메탈릭을 금지한 이유와 같다 —
 * 해석이 화려하면 신뢰가 아니라 권위로 읽힌다.
 */
function InferenceStep({ inf }: { inf: Inference }) {
  return (
    <div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-micro rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] tracking-wide text-[var(--ink-secondary)]">
          AI추론
        </span>
        <span className="text-micro text-[10px] tabular-nums text-[var(--muted)]">
          {GRADE[inf.confidence]}
        </span>
      </div>
      <p className="mt-4 max-w-[42ch] break-keep text-lg leading-relaxed text-[var(--ink)]">
        {inf.text}
      </p>
      <dl className="mt-6 max-w-[46ch] space-y-3 border-t border-[var(--hairline)] pt-4 text-sm leading-relaxed">
        {[
          ["근거", inf.basis],
          ["표본", inf.sample],
          ["못 보는 것", inf.limits],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-[var(--muted)]">{k}</dt>
            <dd className="mt-0.5 break-keep text-[var(--ink-secondary)]">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function StepBody({ step }: { step: StoryStep }) {
  if (step.inference) return <InferenceStep inf={step.inference} />;
  return (
    <>
      <h3 className="mt-3 max-w-[30ch] break-keep font-display text-xl font-extrabold leading-snug tracking-tight text-[var(--ink)] sm:text-2xl">
        {step.headline}
      </h3>
      <p className="mt-4 max-w-[46ch] break-keep text-sm leading-relaxed text-[var(--ink-secondary)] sm:text-base">
        {step.body}
      </p>
    </>
  );
}

export function LeadNarrative({ narrative }: { narrative: Narrative }) {
  const { steps, groups } = narrative;
  const [active, setActive] = useState(0);
  const stepRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    // 화면 한가운데 10% 띠에 들어온 단계가 활성이다. 띠를 벗어난 동안에는 마지막 활성이
    // 그대로 남으므로 단계 사이 여백에서 무대가 비지 않는다.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const index = Number((entry.target as HTMLElement).dataset.stepIndex);
          if (Number.isInteger(index)) setActive(index);
        }
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 },
    );
    const nodes = stepRefs.current.filter((n): n is HTMLElement => !!n);
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [steps.length]);

  const current = steps[active] ?? steps[0];

  return (
    <section aria-labelledby="story-heading" className="mx-auto w-full max-w-6xl px-6">
      <header className="pb-10 pt-24">
        <p className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">{narrative.kicker}</p>
        <h2
          id="story-heading"
          className="mt-4 max-w-[22ch] break-keep font-display text-3xl font-extrabold leading-tight tracking-tight text-[var(--ink)] sm:text-5xl"
        >
          {narrative.question}
        </h2>
        {/* R8 — 신뢰도는 플롯 위에 온다. 아래로 내리면 각주가 되고 각주는 안 읽힌다. */}
        <div className="mt-8 max-w-[68ch]">
          <ReliabilityLine r={narrative.reliability} />
        </div>
      </header>

      <div className="lg:grid lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-14">
        {/* 무대. DOM에서 먼저 오므로 좁은 폭에서는 위에 고정되고 문장이 그 아래로 흐른다. */}
        {/* 넓은 폭에서는 문장의 눈높이에 맞춰 내려 세운다(위에 붙이면 문장과 따로 논다). */}
        <div className="sticky top-14 z-10 -mx-6 bg-[var(--plane)] px-6 py-4 lg:top-[22vh] lg:col-start-2 lg:row-start-1 lg:mx-0 lg:self-start lg:bg-transparent lg:px-0 lg:py-0">
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-7">
            <div className="flex items-baseline justify-between gap-4">
              <p className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">{current.kicker}</p>
              <p className="tabular-nums text-[var(--ink)]">
                <span className="font-display text-2xl font-black sm:text-3xl">{current.count}</span>
                <span className="ml-1 text-sm text-[var(--ink-secondary)]">{current.countLabel}</span>
              </p>
            </div>

            <div className="mt-4">
              <NarrowingField focus={current.focus} groups={groups} live={current.live} />
            </div>

            <NarrowingLegend focus={current.focus} groups={groups} />

            <p className="mt-4 break-keep border-t border-[var(--hairline)] pt-3 text-xs leading-relaxed text-[var(--muted)]">
              {narrative.stageNote}
            </p>
            {/* 서사를 끝까지 봐야 수치에 닿는 구조를 만들지 않는다. 어느 단계에서든 원자료로 나간다. */}
            <Link
              href={narrative.href}
              className="mt-2 inline-block text-xs text-[var(--ink-secondary)] underline decoration-[var(--baseline)] underline-offset-4 transition-colors duration-150 ease-out hover:text-[var(--ink)]"
            >
              이 수치의 원자료 보기
            </Link>
          </div>
        </div>

        {/* 문장. 비활성 단계도 읽히는 색으로 둔다(흐리면 대비가 무너진다). */}
        <ol className="lg:col-start-1 lg:row-start-1">
          {steps.map((step, i) => (
            <li
              key={step.id}
              ref={(node) => {
                stepRefs.current[i] = node;
              }}
              data-step-index={i}
              data-active={i === active}
              className="flex min-h-[62vh] flex-col justify-center border-l-2 border-[var(--hairline)] pl-5 transition-colors duration-300 ease-out data-[active=true]:border-[var(--series)] lg:min-h-[78vh]"
            >
              <p className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">
                <span className="tracking-[0.18em]">{String(i + 1).padStart(2, "0")}</span> · {step.kicker}
              </p>
              <StepBody step={step} />
            </li>
          ))}
        </ol>
      </div>

      {/* R7 — 답하지 않는 것은 한계 서술과 다르다. 해석 옆에 나란히 두면 둘이 주의를 나눠 갖고
          결국 둘 다 안 읽히므로, 자기 화면을 통째로 갖는다. */}
      <div className="flex min-h-[80vh] flex-col justify-center border-t border-[var(--hairline)] py-20">
        <p className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">한계</p>
        <h3 className="mt-4 max-w-[22ch] break-keep font-display text-2xl font-extrabold leading-tight tracking-tight text-[var(--ink)] sm:text-4xl">
          이 화면이 답하지 않는 것
        </h3>
        <ul className="mt-10 max-w-[62ch]">
          {narrative.notAnswered.map((q, i) => (
            <li
              key={q}
              className="flex gap-4 border-t border-[var(--hairline)] py-4 first:border-t-0 first:pt-0"
            >
              <span className="text-micro shrink-0 pt-1 text-[10px] tabular-nums text-[var(--muted)]">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="break-keep leading-relaxed text-[var(--ink-secondary)]">{q}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
