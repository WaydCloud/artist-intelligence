// R5 — 지표 정의를 **화면에서** 펼친다. 원장(RULES.md)으로 보내는 링크가 아니다.
//
// 왜: FM 사용자가 남긴 유일한 주의사항이 "무엇이 크로스·패스·슛인지 아는 것"이었다
// (REFERENCE §4 정의 불투명). 정의가 화면에 없으면 해석이 **조용히** 틀린다 — 화면은
// 정상으로 보이고 읽는 사람만 다른 것을 재고 있다.
//
// 문서 참조(§0·D-016 등)를 UI에 노출하지 않는다(DESIGN §6.1) — 근거는 문서에, 화면엔 결론만.

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
