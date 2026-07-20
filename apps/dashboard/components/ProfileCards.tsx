// 워치리스트 프로필 카드 — signal-bridge RULES §4.1 프로필 라인 규약을 파싱해 구조화 렌더.
// 규약은 표시 향상 계약: 파싱 실패 라인은 평문 폴백(카드 아래 텍스트)으로 그대로 노출한다.

const PREFIX = "[프로필] ";

const CLASS_RE =
  /^(social-led|coincident|chart-led|social-only|chart-only|no-signal)(?:\(([+-]?\d+)d\))?$/;

// 분류는 상태(좋음/나쁨)가 아니라 정체성 — 시리즈 색으로만 구분하고 평결로 읽히는
// good/bad 토큰은 쓰지 않는다(§0). 라벨 텍스트가 항상 병기되므로 색 단독 의존 없음.
const CLASS_COLOR: Record<string, string> = {
  "social-led": "var(--series)",
  coincident: "var(--series)",
  "social-only": "var(--series3)",
  "chart-led": "var(--series2)",
  "chart-only": "var(--baseline)",
  "no-signal": "var(--muted)",
};

interface Profile {
  key: string;
  klass: string;
  leadDays: number | null;
  social: string;
  drivers: string;
  chart: string;
  yt: string | null;
  action: string;
}

export function isProfileLine(line: string): boolean {
  return line.startsWith(PREFIX);
}

function parseProfile(line: string): Profile | null {
  if (!line.startsWith(PREFIX)) return null;
  const body = line.slice(PREFIX.length);
  const arrow = body.lastIndexOf(" → ");
  const dash = body.indexOf(" — ");
  if (arrow < 0 || dash < 0 || dash > arrow) return null;
  const segs = body.slice(dash + 3, arrow).split(" · ");
  const m = CLASS_RE.exec(segs[0] ?? "");
  if (!m) return null;
  const rest = segs.slice(1);
  const social = rest.find((s) => s.startsWith("소셜 "));
  const drivers = rest.find((s) => s.startsWith("드라이버: "));
  const chart = rest.find((s) => s.startsWith("차트 "));
  const yt = rest.find((s) => s.startsWith("YT "));
  if (!social || !drivers || !chart) return null;
  return {
    key: body.slice(0, dash),
    klass: m[1],
    leadDays: m[2] != null ? Number(m[2]) : null,
    social: social.slice("소셜 ".length),
    drivers: drivers.slice("드라이버: ".length),
    chart: chart.slice("차트 ".length),
    yt: yt ? yt.slice("YT ".length) : null,
    action: body.slice(arrow + 3),
  };
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 text-xs leading-relaxed">
      <span className="w-12 shrink-0 text-[var(--muted)]">{label}</span>
      <span className="min-w-0 break-words text-[var(--ink-secondary)]">{value}</span>
    </div>
  );
}

function Card({ p }: { p: Profile }) {
  const color = CLASS_COLOR[p.klass] ?? "var(--muted)";
  const lead =
    p.leadDays != null ? ` ${p.leadDays > 0 ? "+" : ""}${p.leadDays}d` : "";
  return (
    <div className="glass-card flex flex-col gap-2 p-4 transition-colors duration-200 ease-out hover:border-[var(--baseline)]">
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-sm font-semibold tracking-tight text-[var(--ink)]" title={p.key}>
          {p.key}
        </span>
        <span className="flex shrink-0 items-center gap-1.5 text-xs text-[var(--ink-secondary)]">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: color }}
            aria-hidden
          />
          <span className="tabular-nums">
            {p.klass}
            {lead}
          </span>
        </span>
      </div>
      <div className="space-y-1">
        <Row label="소셜" value={p.social} />
        <Row label="드라이버" value={p.drivers} />
        <Row label="차트" value={p.chart} />
        {p.yt && <Row label="YT" value={p.yt} />}
      </div>
      <div className="mt-auto border-t border-[var(--hairline)] pt-2 text-xs leading-relaxed text-[var(--muted)]">
        → {p.action}
      </div>
    </div>
  );
}

export function ProfileCards({ lines }: { lines: string[] }) {
  const parsed = lines.map((l) => ({ line: l, p: parseProfile(l) }));
  const cards = parsed.filter((x) => x.p != null);
  const fallback = parsed.filter((x) => x.p == null);
  return (
    <section>
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="font-display text-sm font-medium tracking-wide">워치리스트 프로필</h2>
        <span className="text-xs text-[var(--muted)]">
          {lines.length}팀 · 참고용 신호 요약, 판단은 사람의 몫
        </span>
      </div>
      {cards.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((x, i) => (
            <Card key={i} p={x.p as Profile} />
          ))}
        </div>
      )}
      {fallback.length > 0 && (
        <ul className="mt-3 space-y-2">
          {fallback.map((x, i) => (
            <li key={i} className="text-sm leading-relaxed text-[var(--ink-secondary)]">
              {x.line}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
