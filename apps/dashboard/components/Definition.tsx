// R5 — 지표 정의를 **화면에서** 펼친다. 원장(RULES.md)으로 보내는 링크가 아니다.
//
// 왜: FM 사용자가 남긴 유일한 주의사항이 "무엇이 크로스·패스·슛인지 아는 것"이었다
// (REFERENCE §4 정의 불투명). 정의가 화면에 없으면 해석이 **조용히** 틀린다 — 화면은
// 정상으로 보이고 읽는 사람만 다른 것을 재고 있다.
//
// 문서 참조(§0·D-016 등)를 UI에 노출하지 않는다(DESIGN §6.1) — 근거는 문서에, 화면엔 결론만.

// 여러 용어를 한 번에 펼친다. 튜너의 집계 줄("해당 없음 5 · 그중 동점 22")처럼
// **라벨마다** 설명이 붙는 자리에 쓴다.
//
// 왜 라벨마다 펼침 장치를 달지 않는가: 같은 모양이 네 번 반복되면 장식이 되고, 지표 타일에서
// 이미 같은 결론을 냈다(ReportView: "행에 하나"). 그래서 줄 아래 **하나**로 모은다.
//
// 왜 `title` 속성이 아닌가: 눈에 보이는 표시가 없으면 **거기 설명이 있다는 것 자체를
// 모른다**(DESIGN §7.6). 포인터로만 닿는 경로이기도 하다.
export function Terms({ items, className = "mt-2" }: { items: [string, string][]; className?: string }) {
  const shown = items.filter(([, v]) => !!v?.trim());
  if (shown.length === 0) return null;
  return (
    <details className={`group text-xs ${className}`}>
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[var(--muted)] transition-colors duration-150 ease-out hover:text-[var(--ink-secondary)]">
        <span
          aria-hidden
          className="inline-block transition-transform duration-200 ease-out group-open:rotate-90"
        >
          ›
        </span>
        이 숫자들이 무슨 뜻인가
      </summary>
      <dl className="mt-2 grid gap-x-6 gap-y-2 border-l border-[var(--hairline)] pl-3 sm:grid-cols-2">
        {shown.map(([k, v]) => (
          <div key={k}>
            <dt className="text-[var(--ink-secondary)]">{k}</dt>
            <dd className="max-w-[68ch] leading-relaxed text-[var(--muted)]">{v}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export function Definition({
  text,
  label = "무엇을 재는가",
  className = "mb-3",
}: {
  text?: string;
  label?: string;
  className?: string;
}) {
  if (!text?.trim()) return null;
  return (
    <details className={`group text-xs ${className}`}>
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[var(--muted)] transition-colors duration-150 ease-out hover:text-[var(--ink-secondary)]">
        <span
          aria-hidden
          className="inline-block transition-transform duration-200 ease-out group-open:rotate-90"
        >
          ›
        </span>
        {label}
      </summary>
      <p className="mt-1.5 max-w-[68ch] border-l border-[var(--hairline)] pl-3 leading-relaxed text-[var(--ink-secondary)]">
        {text}
      </p>
    </details>
  );
}
