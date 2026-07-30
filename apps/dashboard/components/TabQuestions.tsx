"use client";

import type { TabQuestion } from "@/lib/report";

// R1 — 이 탭에서 **답할 수 있는 질문**을 첫 화면이 명시하고, 각 질문이 해당 패널로 앵커된다.
//
// 🔴 FM 데이터 허브의 최대 실패가 이것이다. 기능이 부족한 게 아니라 **자기 사용법을 못
// 가르쳤다**: "거기 너무 많은 게 있어서 무엇을 봐야 할지 알 수 없었다. 딱 이런 가이드를
// 찾고 있었다." 기능이 유용해지려면 **외부 가이드가 필요했다**는 뜻이다(REFERENCE §4).
//
// 그래서 이 블록은 장식이 아니라 진입 경로다. 질문을 누르면 그 답이 있는 카드로 내려간다.

// 정적 export를 유지하므로 라우팅 대신 스크롤로 이동한다. hash를 직접 쓰지 않는 이유는
// 대시보드가 hash를 **탭 딥링크**로 쓰고 있어서다(#sonic-profile) — 덮어쓰면 탭이 튄다.
// 🔴 대상이 **아직 DOM에 없을 수 있다.** 다른 구획의 차트로 가는 경우 구획 전환이 먼저
// 일어나는데, 새 구획은 `AnimatePresence mode="wait"`라 **이전 구획의 나가는 모션이 끝난
// 뒤에야** 마운트된다(0.22s). 예전에는 두 프레임(약 32ms) 뒤에 한 번만 찾아보고 없으면
// 조용히 포기했고, 그래서 **구획만 바뀌고 스크롤도 도착 표시도 일어나지 않았다**
// (2026-07-30 실측: sonic-profile 질문 4개 중 3개 · chart-history 4개 중 2개).
// 질문을 눌러도 아무 일이 없는 것은 R1이 고치려던 실패 그 자체다.
//
// 프레임 수를 늘려 맞추지 않는다 — 모션 시간이 바뀌면 같은 결함이 조용히 돌아온다.
// **대상이 나타날 때까지 기다렸다가** 간다. 이 요구는 이제 `smoke:tabs`가 센다.
//
// 도착 표시를 지우는 타이머를 카드마다 기억한다. 같은 카드로 1.4초 안에 두 번 가면
// **첫 번째 타이머가 두 번째 표시를 지워버린다** — genre-impulse처럼 두 질문이 같은
// 차트를 가리키는 탭에서 실제로 그렇게 됐다(2026-07-30 실측). 표시가 바로 사라지면
// 두 번째 클릭은 아무 일도 안 한 것으로 읽힌다.
const landedTimers = new WeakMap<Element, number>();

function goTo(id: string, deadlineMs = 900) {
  const t0 = performance.now();
  const tick = () => {
    const el = document.getElementById(id);
    if (!el) {
      if (performance.now() - t0 < deadlineMs) requestAnimationFrame(tick);
      return;
    }
    // 부드러운 스크롤은 이 화면에서 가장 큰 모션이다. CSS의 `scroll-behavior`는 여기에
    // 닿지 않는다 — `scrollIntoView`에 `behavior`를 명시하면 그 값이 CSS를 이긴다.
    // 그래서 globals.css의 안전망과 별개로 여기서 한 번 더 묻는다(DESIGN §5).
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    el.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    // 도착한 카드를 잠깐 표시해 준다 — 어디로 왔는지 모르면 앵커는 반쪽이다.
    const prev = landedTimers.get(el);
    if (prev !== undefined) window.clearTimeout(prev);
    el.setAttribute("data-landed", "true");
    landedTimers.set(
      el,
      window.setTimeout(() => {
        el.removeAttribute("data-landed");
        landedTimers.delete(el);
      }, 1400),
    );
  };
  requestAnimationFrame(tick);
}

export function TabQuestions({
  questions,
  notAnswered,
  onBeforeJump,
}: {
  questions?: TabQuestion[];
  notAnswered?: string[];
  // 구획을 쓰는 리포트에서는 대상 차트가 다른 구획에 있을 수 있다. 구획을 먼저 열지
  // 않으면 대상이 DOM에 없어 질문을 눌러도 아무 일도 일어나지 않는다(끊긴 앵커와 같다).
  onBeforeJump?: (chartId: string) => void;
}) {
  const qs = questions ?? [];
  const no = notAnswered ?? [];
  if (qs.length === 0 && no.length === 0) return null;

  // 카드가 아니다. 요약 도형 옆에 같은 글래스 상자를 하나 더 놓으면 표면당 강조가
  // 둘이 되어 위계가 사라지고(DESIGN §1 미니멀리즘), 내용이 짧은 쪽 아래에 빈 상자가
  // 남는다. 여기는 본문 텍스트이므로 배경 위에 그대로 놓는다 — 카드는 도형만 쓴다.
  return (
    <section className="py-1">
      {qs.length > 0 && (
        <>
          <h2 className="font-display text-sm font-medium tracking-wide text-[var(--ink)]">
            이 화면에서 답할 수 있는 질문
          </h2>
          <ol className="mt-3 space-y-2">
            {qs.map((q, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed">
                <span className="shrink-0 tabular-nums text-[var(--muted)]">{i + 1}</span>
                <button
                  type="button"
                  onClick={() => {
                    onBeforeJump?.(q.chartId);
                    // 대기는 `goTo`가 한다 — 구획 전환 모션이 끝나야 대상이 마운트되고,
                    // 그 시간은 여기서 셀 값이 아니다.
                    goTo(q.chartId);
                  }}
                  className="max-w-[46ch] text-left text-[15px] leading-relaxed text-[var(--ink-secondary)] underline decoration-[var(--baseline)] decoration-1 underline-offset-4 transition-colors duration-150 ease-out hover:text-[var(--ink)] hover:decoration-[var(--series)]"
                >
                  {q.q}
                </button>
              </li>
            ))}
          </ol>
        </>
      )}

      {/* R7 — 못 답하는 질문을 화면이 먼저 말한다. 커버리지 정직 규율의 UI 형태다.
          FM에서 "찾을 수 없다"로 남은 질문들(시간대·세트피스·압박)이 이 자리의 근거다. */}
      {no.length > 0 && (
        <div className={qs.length > 0 ? "mt-4 border-t border-[var(--hairline)] pt-3" : ""}>
          <h3 className="text-xs font-medium tracking-wide text-[var(--muted)]">이 화면이 답하지 않는 것</h3>
          <ul className="mt-2 space-y-1">
            {no.map((t, i) => (
              <li key={i} className="flex max-w-[68ch] gap-2 text-xs leading-relaxed text-[var(--muted)]">
                <span aria-hidden className="select-none">
                  ×
                </span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
