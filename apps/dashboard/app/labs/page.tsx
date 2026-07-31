import Link from "next/link";
import type { Metadata } from "next";
import labs from "@/data/labs.json";
import { BrandBackdrop } from "@/components/BrandBackdrop";
import { ImpulseLedger } from "@/components/labs/ImpulseLedger";
import type { LabsData } from "@/lib/labs";

export const metadata: Metadata = {
  title: "Labs",
};

// 브랜드 표면 (DESIGN.md §4). 배경·크롬은 브랜드 미학, 본문·표는 dataviz 토큰만.
//
// 🔴 LABS가 따로 있는 이유: 여기 실리는 것은 **측정이 아니라 가설**이다. 채택 모듈은
// `모듈 CLI → 스키마 유효 report.json → 대시보드`를 지나지만(AGENTS §0) 임펄스 원장은
// 연구 산출물이라 그 계약 밖이다. 두 표면을 한 화면에 섞으면 읽는 사람이 증거와
// 가설을 같은 무게로 읽는다.
export default function LabsPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <BrandBackdrop vignette={false} />
      <div className="relative mx-auto w-full max-w-4xl px-6 py-10">
        <header className="space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h1 className="font-display text-2xl font-medium uppercase tracking-[0.2em] text-[var(--ink)]">
              Labs
            </h1>
            <Link
              href="/"
              className="text-sm text-[var(--ink-secondary)] transition-colors duration-200 ease-out hover:text-[var(--ink)]"
            >
              처음으로
            </Link>
          </div>
          {/* 페이지 수위의 경고. 항목 수위 경고(셀마다 확실성 등급)와 **둘 다** 둔다 —
              링크로 특정 항목만 공유되면 페이지 경고가 따라가지 않는다. */}
          <div
            className="rounded-lg border p-4"
            style={{ borderColor: "var(--border)", background: "var(--plane)" }}
          >
            <p className="text-sm leading-relaxed text-[var(--ink-secondary)]">
              여기 실린 것은 <strong className="font-medium text-[var(--ink)]">측정이 아니라 가설</strong>입니다.
              장르가 어떤 경로로 퍼졌는지에 대한 현재 추정이며, 반증되면 버전을 올려 갱신합니다. 리포트 탭의
              측정값과 같은 무게로 읽지 마십시오.
            </p>
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
              항목마다 확실성 등급이 함께 붙습니다. 등급이 &lsquo;중간&rsquo;에 못 미치는 항목은 목록에서
              빼고 몇 건을 뺐는지 적습니다. 판단은 사람의 몫입니다.
            </p>
            {/* 카피 규율 면제를 화면에서 밝힌다(DESIGN.md §6.1 예외 ②). 원장 문장을
                표시용으로 고쳐 쓰면 화면이 정본과 달라지므로 원문 그대로 싣는다. */}
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
              근거 문장은 원장에 적힌 그대로입니다. 화면에 맞춰 다듬지 않았습니다.
            </p>
          </div>
        </header>

        <section className="mt-8">
          <ImpulseLedger data={labs as LabsData} />
        </section>
      </div>
    </main>
  );
}
