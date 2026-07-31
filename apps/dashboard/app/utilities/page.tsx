import type { Metadata } from "next";
import Link from "next/link";
import { BrandBackdrop } from "@/components/BrandBackdrop";
import { ThemeButton } from "@/components/ThemeButton";
import { buildCriteriaLedger } from "@/lib/criteria";

export const metadata: Metadata = {
  title: "기준",
};

// 브랜드 표면 (DESIGN.md §4). 값은 증거 레이어이므로 표 위에 오버레이를 얹지 않는다.
//
// 이 화면이 하는 일은 하나다: **이 시스템이 지금 무엇을 가정하고 있는지 보여 준다.**
// 값은 여기서 바꾸지 않고 각 리포트의 튜너에서 바꾼다 — 값을 움직인 결과가 화면에서
// 어떻게 달라지는지를 같이 봐야 조정이 판단이 되기 때문이다.
export default function UtilitiesPage() {
  const ledger = buildCriteriaLedger();

  return (
    <main className="relative min-h-screen">
      <BrandBackdrop vignette={false} />

      <div className="relative mx-auto w-full max-w-4xl px-6 py-10">
        <header>
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">Utilities</p>
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="text-sm text-[var(--ink-secondary)] transition-colors duration-200 ease-out hover:text-[var(--ink)]"
              >
                처음으로
              </Link>
              <ThemeButton />
            </div>
          </div>

          <h1 className="mt-4 max-w-[22ch] break-keep font-display text-3xl font-extrabold leading-tight tracking-tight text-[var(--ink)] sm:text-5xl">
            이 시스템이 가정하고 있는 값
          </h1>
          <p className="mt-6 max-w-[52ch] break-keep leading-relaxed text-[var(--ink-secondary)]">
            분류와 판정은 임계값 위에서 나온다. 그 값을 코드 안에 숨기면 결과를 반박할 수 없으므로
            전부 여기에 적는다. 지금 {ledger.total}개다.
          </p>
          <p className="mt-3 max-w-[52ch] break-keep text-sm leading-relaxed text-[var(--muted)]">
            기준의 형식은 만드는 쪽이 소유하고 값은 담당자가 소유한다. 값을 움직이면 화면의 판정이
            달라지고, 움직이는 자리는 각 리포트 안이다.
          </p>
        </header>

        <div className="mt-14 space-y-14">
          {ledger.groups.map((g) => (
            <section key={g.moduleId}>
              <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-[var(--hairline)] pb-3">
                <h2 className="break-keep font-display text-lg font-extrabold tracking-tight text-[var(--ink)]">
                  {g.moduleTitle}
                </h2>
                <Link
                  href={g.href}
                  className="text-xs text-[var(--ink-secondary)] underline decoration-[var(--baseline)] underline-offset-4 transition-colors duration-150 ease-out hover:text-[var(--ink)]"
                >
                  여기서 값을 돌려 보기
                </Link>
              </div>

              {g.sets.map((s) => (
                <div key={s.title} className="mt-6">
                  <h3 className="break-keep text-sm text-[var(--ink)]">{s.title}</h3>
                  {s.question && (
                    <p className="mt-1 max-w-[62ch] break-keep text-xs leading-relaxed text-[var(--muted)]">
                      {s.question}
                    </p>
                  )}

                  {/* 값·범위는 증거다. 표로 두어 읽는 순서가 정해지고 스크린리더에도 닿는다. */}
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[28rem] border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-[var(--hairline)] text-left text-xs text-[var(--muted)]">
                          <th scope="col" className="py-2 pr-4 font-extrabold">
                            기준
                          </th>
                          <th scope="col" className="py-2 pr-4 text-right font-extrabold">
                            지금 값
                          </th>
                          <th scope="col" className="py-2 text-right font-extrabold">
                            움직일 수 있는 범위
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {s.criteria.map((c) => (
                          <tr key={c.label} className="border-b border-[var(--hairline)]">
                            <th
                              scope="row"
                              className="max-w-[24rem] break-keep py-2.5 pr-4 text-left font-light text-[var(--ink-secondary)]"
                            >
                              {c.label}
                            </th>
                            <td className="py-2.5 pr-4 text-right font-black tabular-nums text-[var(--ink)]">
                              {c.value}
                            </td>
                            <td className="py-2.5 text-right tabular-nums text-[var(--muted)]">
                              {c.min} ~ {c.max}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {s.definition && (
                    <p className="mt-3 max-w-[68ch] break-keep text-xs leading-relaxed text-[var(--muted)]">
                      {s.definition}
                    </p>
                  )}
                </div>
              ))}
            </section>
          ))}
        </div>

        <p className="mt-16 max-w-[68ch] break-keep border-t border-[var(--hairline)] pt-6 text-xs leading-relaxed text-[var(--muted)]">
          여기 없는 기준도 있다. 결과를 바꾸지 않는 관습값은 각 모듈 문서에 적고 이 화면에
          올리지 않는다. 사람의 결정을 바꾸는 값만 여기 온다.
        </p>
      </div>
    </main>
  );
}
