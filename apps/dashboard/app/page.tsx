import Link from "next/link";
import { BrandBackdrop } from "@/components/BrandBackdrop";
import { HERO_SENTINEL_ID, LandingNav, PAGE_TOP_ID } from "@/components/story/LandingNav";
import { LeadNarrative } from "@/components/story/LeadNarrative";
import { buildLandingStory } from "@/lib/story";

// 브랜드 표면 (DESIGN.md §4) — 배경·크롬에 글로우·비네트·글래스·메탈릭 허용.
// 서사 무대는 증거 레이어라 그 안에서 dataviz 토큰만 쓴다(LeadNarrative 참고).
//
// 수치는 전부 buildLandingStory()가 report.json에서 조달한다(§7.8). 이 파일에 숫자를
// 적어 넣지 않는다 — 매일 수집이 도는 제품에서 적어 넣은 수는 언젠가 반드시 틀린다.

const SURFACES = [
  { href: "/labs", title: "Labs", description: "장르 확산 경로의 가설 원장. 측정이 아니라 추정" },
  { href: "/utilities", title: "Utilities", description: "이 시스템이 가정하고 있는 임계값 전부" },
];

function formatDay(iso: string): string {
  return iso.slice(0, 10);
}

export default function LandingPage() {
  const story = buildLandingStory();

  return (
    // 🔴 `overflow-hidden`을 걸지 않는다. 조상에 걸면 서사 무대의 `position: sticky`가
    // 죽어(스크롤포트가 그 조상으로 바뀐다) 무대가 통째로 사라진다. BrandBackdrop은
    // `absolute inset-0`이라 애초에 넘칠 것이 없어 가둘 이유도 없다.
    <main className="relative">
      <BrandBackdrop />

      <div id={PAGE_TOP_ID} />
      <LandingNav />

      {/* 히어로. 시네마틱 = 넓은 여백 + 큰 명암 대비이고, 장식은 여기까지다. */}
      <section className="relative mx-auto flex min-h-[86vh] w-full max-w-6xl flex-col justify-center px-6 pb-24 pt-20">
        <p className="font-display text-xs uppercase tracking-[0.28em] text-[var(--muted)]">
          Artist Intelligence
        </p>
        {/* 워드마크는 굵기 규칙의 예외다(§2.1): 가장 얇게 + 넓은 자간.
            자간을 주면 마지막 글자 뒤에도 그만큼 공백이 붙어 글자열이 왼쪽으로 밀린 것처럼
            보이므로, 같은 값만큼 왼쪽 패딩으로 되돌려 그리드에 맞춘다. */}
        <h1
          className="metal-text mt-6 font-display text-4xl font-thin uppercase leading-none tracking-[0.3em] sm:text-7xl"
          style={{ paddingLeft: "0.3em" }}
        >
          WaydCloud
        </h1>
        {/* 무엇을 재는지는 바로 아래 지표 넷이 말한다. 여기서 다시 열거하면 같은 말을 두 번 한다. */}
        <p className="mt-8 max-w-[20ch] break-keep text-lg leading-relaxed text-[var(--ink-secondary)] sm:text-xl">
          매일 재서 증거로 남긴다. 판단은 사람의 몫.
        </p>

        {/* 값이 위, 설명이 아래다. 설명이 길어 어떤 칸만 두 줄이 되는데, 설명을 위에 두면
            그 칸의 값만 아래로 밀려 숫자들의 밑줄이 어긋난다. */}
        <dl className="mt-16 grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-4">
          {story.hero.map((s) => (
            // `flex-col-reverse`는 주축이 아래에서 위로 흐르므로 `justify-end`가 **위쪽** 정렬이다.
            // 이걸 빼면 내용이 칸 바닥으로 몰려, 라벨이 두 줄인 칸의 숫자만 위로 밀려 올라간다
            // (좁은 폭에서 라벨이 접히자 실제로 그렇게 됐다).
            <div key={s.label} className="flex flex-col-reverse justify-end gap-1.5">
              <dt className="break-keep text-xs leading-snug tracking-wide text-[var(--muted)]">
                {s.label}
              </dt>
              <dd className="font-display text-2xl font-black tabular-nums tracking-tight text-[var(--ink)] sm:text-3xl">
                {s.value}
              </dd>
            </div>
          ))}
        </dl>

        <p className="mt-16 text-xs tracking-wide text-[var(--muted)]">
          아래로 내리면 관측 하나를 처음부터 끝까지 따라갑니다
        </p>
        {/* 상단 크롬이 나타나는 지점. 높이 0이라 배치에 영향을 주지 않는다 */}
        <div id={HERO_SENTINEL_ID} aria-hidden className="absolute bottom-0 h-px w-px" />
      </section>

      {/* 서사 본편. 증거 레이어이므로 배경 장식이 그 위에 오지 않는다. */}
      <div className="relative border-t border-[var(--hairline)] bg-[var(--plane)]">
        <LeadNarrative narrative={story.narrative} />

        {/* 모듈 레일. 서사에서 나온 사람이 실제 화면으로 들어가는 자리. */}
        <section id="rails" className="mx-auto w-full max-w-6xl px-6 pb-24 pt-28">
          <h2 className="font-display text-xs tracking-[0.04em] text-[var(--muted)]">지금 도는 관측</h2>
          <p className="mt-4 max-w-[52ch] break-keep text-sm leading-relaxed text-[var(--ink-secondary)]">
            방금 따라온 것은 여섯 갈래 중 하나다. 나머지가 무엇을 묻는지 아래에 있다.
          </p>
          {/* 카드의 머리글은 라벨이 아니라 **질문**이다(구획과 같은 원칙). 규모 숫자는
              히어로가 이미 말했으므로 여기서는 뒤로 물린다 — 같은 일을 두 번 하지 않는다. */}
          <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {story.rails.map((r) => (
              <li key={r.moduleId}>
                <Link
                  href={r.href}
                  className="glass-card group flex h-full flex-col p-6 transition-colors duration-200 ease-out hover:border-[var(--baseline)]"
                >
                  <span className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
                    <span className="break-keep">{r.title}</span>
                    {r.isStory && (
                      <span className="text-micro rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--ink-secondary)]">
                        방금 본 관측
                      </span>
                    )}
                  </span>
                  <span className="mt-4 max-w-[20ch] break-keep font-display text-lg font-extrabold leading-snug tracking-tight text-[var(--ink)]">
                    {r.question}
                  </span>
                  <span className="mt-auto pt-6 text-xs tabular-nums text-[var(--muted)]">
                    질문 {r.questionCount}개 · {r.unit} {r.headline}
                  </span>
                  <span className="mt-1.5 text-xs tracking-wide text-[var(--muted)] transition-colors duration-200 ease-out group-hover:text-[var(--ink-secondary)]">
                    리포트 열기
                  </span>
                </Link>
              </li>
            ))}
          </ul>

          <ul className="mt-4 grid gap-4 sm:grid-cols-2">
            {SURFACES.map((s) => (
              <li key={s.href}>
                <Link
                  href={s.href}
                  className="glass-card group flex h-full flex-col p-6 transition-colors duration-200 ease-out hover:border-[var(--baseline)]"
                >
                  <span className="font-display text-sm font-extrabold tracking-wide text-[var(--ink)]">
                    {s.title}
                  </span>
                  <span className="mt-2 text-sm text-[var(--ink-secondary)]">{s.description}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <footer className="border-t border-[var(--hairline)]">
          <div className="mx-auto w-full max-w-6xl px-6 py-10 text-xs leading-relaxed text-[var(--muted)]">
            <p className="max-w-[68ch] break-keep">
              이 화면의 수치는 관측이고 평가가 아니다. 어느 팀이 뜬다거나 뜨지 않는다는 말을
              하지 않으며, 표본과 관측 창의 한계를 화면마다 함께 적는다.
            </p>
            <p className="mt-3">마지막 관측 {formatDay(story.generatedAt)}</p>
          </div>
        </footer>
      </div>
    </main>
  );
}
