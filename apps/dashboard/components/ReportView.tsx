import type { Report } from "@/lib/report";
import { KpiTile } from "@/components/KpiTile";
import { ChartCard } from "@/components/charts/ChartCard";
import { ProfileCards, isProfileLine } from "@/components/ProfileCards";

function List({ title, items, marker }: { title: string; items: string[]; marker: string }) {
  return (
    <div>
      <h2 className="mb-2 font-display text-sm font-medium tracking-wide">{title}</h2>
      <ul className="space-y-2">
        {items.map((t, i) => (
          <li key={i} className="flex gap-2 text-sm leading-relaxed text-[var(--ink-secondary)]">
            <span className="select-none text-[var(--series)]">{marker}</span>
            <span>{t}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReportView({
  report,
  dark,
  moduleIds = [],
  onSelectModule,
}: {
  report: Report;
  dark: boolean;
  moduleIds?: string[];
  onSelectModule?: (id: string) => void;
}) {
  // 프로필 라인(RULES §4.1 규약)은 카드 섹션으로 분리, 나머지는 기존 인사이트 리스트.
  const profileLines = report.insights.filter(isProfileLine);
  const insights = report.insights.filter((l) => !isProfileLine(l));
  // 교차 링크: subtitle/insight 본문에 등장하는 다른 모듈 id → 탭 링크 칩 (범용 감지)
  const haystack = [report.subtitle ?? "", ...report.insights].join("\n");
  const related = moduleIds.filter((id) => id !== report.moduleId && haystack.includes(id));
  return (
    <main className="mx-auto max-w-5xl space-y-8 px-5 py-6">
      <section>
        <h1 className="font-display text-xl font-semibold tracking-wide">{report.title}</h1>
        {report.subtitle && <p className="mt-1 break-words text-sm text-[var(--ink-secondary)]">{report.subtitle}</p>}
        <p className="mt-0.5 text-xs tabular-nums text-[var(--muted)]">생성 {report.generatedAt}</p>
        {related.length > 0 && onSelectModule && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[var(--muted)]">소스 모듈:</span>
            {related.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onSelectModule(id)}
                className="rounded border border-[var(--border)] px-2 py-0.5 text-[var(--ink-secondary)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--ink)]"
              >
                {id} ↗
              </button>
            ))}
          </div>
        )}
      </section>

      {report.metrics.length > 0 && (
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {report.metrics.map((m, i) => (
            <KpiTile key={i} m={m} />
          ))}
        </section>
      )}

      {report.charts.map((c, i) => (
        <ChartCard key={i} chart={c} dark={dark} />
      ))}

      {profileLines.length > 0 && <ProfileCards lines={profileLines} />}

      {(insights.length > 0 || report.recommendations.length > 0) && (
        <section className="grid gap-6 md:grid-cols-2">
          {insights.length > 0 && <List title="인사이트" items={insights} marker="·" />}
          {report.recommendations.length > 0 && <List title="추천" items={report.recommendations} marker="→" />}
        </section>
      )}
    </main>
  );
}
