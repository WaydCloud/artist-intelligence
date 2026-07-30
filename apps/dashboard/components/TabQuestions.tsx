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
function goTo(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  // 도착한 카드를 잠깐 표시해 준다 — 어디로 왔는지 모르면 앵커는 반쪽이다.
  el.setAttribute("data-landed", "true");
  window.setTimeout(() => el.removeAttribute("data-landed"), 1400);
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
                    // 구획 전환으로 대상이 DOM에 붙는 것은 다음 페인트다. 그래서 한 프레임 뒤에 스크롤한다.
                    requestAnimationFrame(() => requestAnimationFrame(() => goTo(q.chartId)));
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
