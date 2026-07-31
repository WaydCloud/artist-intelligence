import Link from "next/link";
import { ThemeButton } from "@/components/ThemeButton";
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
    <main className="relative min-h-screen">
      <BrandBackdrop vignette={false} />
      <div className="relative mx-auto w-full max-w-4xl px-6 py-10">
        {/* 머리부는 랜딩·기준 화면과 같은 모양이다: 작은 라벨 → 큰 제목 → 본문.
            표면마다 머리부의 모양이 다르면 같은 제품의 화면으로 읽히지 않는다. */}
        <header>
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">Labs</p>
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="text-sm text-[var(--ink-secondary)] transition-colors duration-200 ease-out hover:text-[var(--ink)]"
              >
                처음으로
              </Link>
              {/* 들어와서 테마를 못 바꾸면 뒤로 나갔다 와야 한다. 표면마다 나갈 길과 바꿀 길이 함께 있어야 한다. */}
              <ThemeButton />
            </div>
          </div>

          {/* 페이지 수위의 경고. 항목 수위 경고(셀마다 확실성 등급)와 **둘 다** 둔다 —
              링크로 특정 항목만 공유되면 페이지 경고가 따라가지 않는다.
              상자를 걷어냈다: 경고가 이 화면의 제목 자리에 오면 상자로 가둘 때보다 크게 읽히고,
              같은 공백이 테두리 없이는 여백이 된다(진입부 배치 규율 §7.1.2). */}
          <h1 className="mt-4 max-w-[22ch] break-keep font-display text-3xl font-extrabold leading-tight tracking-tight text-[var(--ink)] sm:text-5xl">
            측정이 아니라 가설
          </h1>
          <p className="mt-6 max-w-[52ch] break-keep leading-relaxed text-[var(--ink-secondary)]">
            장르가 어떤 경로로 퍼졌는지에 대한 현재 추정입니다. 반증되면 버전을 올려 갱신합니다.
            리포트 탭의 측정값과 같은 무게로 읽지 마십시오.
          </p>
          <p className="mt-3 max-w-[52ch] break-keep text-sm leading-relaxed text-[var(--muted)]">
            항목마다 확실성 등급이 함께 붙습니다. 등급이 &lsquo;중간&rsquo;에 못 미치는 항목은 목록에서
            빼고 몇 건을 뺐는지 적습니다. 판단은 사람의 몫입니다.
          </p>
          {/* 카피 규율 면제를 화면에서 밝힌다(DESIGN.md §6.1 예외 ②). 원장 문장을
              표시용으로 고쳐 쓰면 화면이 정본과 달라지므로 원문 그대로 싣는다. */}
          <p className="mt-3 max-w-[52ch] break-keep text-sm leading-relaxed text-[var(--muted)]">
            근거 문장은 원장에 적힌 그대로입니다. 화면에 맞춰 다듬지 않았습니다.
          </p>
        </header>

        <section className="mt-14">
          <ImpulseLedger data={labs as LabsData} />
        </section>
      </div>
    </main>
  );
}
