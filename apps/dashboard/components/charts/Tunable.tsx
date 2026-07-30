"use client";

import { useMemo, useState } from "react";
import type {
  ImpulseRulesTunableData,
  LeadLagTunableData,
  RhythmTunableData,
  TagsTunableData,
  TunableData,
  WhitespaceTunableData,
} from "@/lib/report";
import { scopeOf, useKnob } from "@/lib/knobs";
import { Terms } from "@/components/Definition";
import { CriteriaActions, type CriteriaItem } from "./CriteriaActions";
import { ChartTooltip, useChartTooltip } from "./ChartTooltip";

// Interactive threshold views: the report ships raw data + knobs; we recompute the
// derived view client-side as the viewer turns each knob (static-first, no backend).
// 기준 원장 §2.1: 값=도메인 소유자 — 노출(슬라이더)·반박(재계산)·전달(CriteriaActions).
export function Tunable({ data, title }: { data: TunableData; title?: string }) {
  if (data.view === "leadlag") return <LeadLag data={data} title={title} />;
  if (data.view === "rhythm") return <Rhythm data={data} title={title} />;
  if (data.view === "tags") return <Tags data={data} title={title} />;
  if (data.view === "impulse-rules") return <ImpulseRules data={data} title={title} />;
  if (data.view === "whitespace") return <Whitespace data={data} title={title} />;
  // 알 수 없는 view는 **그린다고 넘기지 않는다.** 예전엔 마지막 분기가 무조건
  // Whitespace였고, genre-impulse가 새 view를 내자 `matrix.cols`에서 죽어
  // **대시보드 전체가 언마운트**됐다(2026-07-30 실측) — 한 모듈의 신규 뷰가
  // 다른 모듈의 탭까지 못 보게 만드는 구조였다. 모르면 모른다고 표시한다.
  return <UnknownView view={(data as { view?: string }).view} />;
}

// impulse-rules — genre-impulse: 두 백분위 컷(P_low·P_high)을 움직이며 어느 곡이
// 검출 규칙에 걸리는지 다시 계산한다. 규칙의 **형식**(어느 축이 하한/상한인가)은
// 리포트가 싣고, **값**(컷)은 여기서 A&R이 돌린다 — 기준 원장 §2.1의 소유 분리.
function ImpulseRules({ data, title }: { data: ImpulseRulesTunableData; title?: string }) {
  const lowKnob = data.knobs.find((k) => k.key === "lowPct") ?? data.knobs[0];
  const highKnob = data.knobs.find((k) => k.key === "highPct") ?? data.knobs[1];
  const scope = scopeOf("impulse-rules", title);
  const [lowPct, setLowPct] = useKnob(scope, "lowPct", lowKnob?.default ?? data.lowPct);
  const [highPct, setHighPct] = useKnob(scope, "highPct", highKnob?.default ?? data.highPct);
  const buckets = useMemo<Bucket[]>(() => {
    // 축의 화면 표기는 리포트가 함께 싣는다(`axisLabels`). 저장 키(`organic_ratio`)를 그대로
    // 찍으면 데이터 키가 새어 나온 것처럼 읽힌다(DESIGN §6.1). 없으면 키로 되돌아간다.
    const axLabel = (key: string) => data.axisLabels?.[key] ?? key;
    return data.rules.map((rule) => {
        const members = data.tracks
          .filter(
            (t) =>
              rule.lowAll.every((ax) => (t.pcts[ax] ?? Infinity) <= lowPct) &&
              rule.highAny.some((ax) => (t.pcts[ax] ?? -Infinity) >= highPct),
          )
          .map((t) => ({
            name: (t.watch ? "★ " : "") + t.name,
            // 어느 축이 얼마로 걸렸는지 보여야 배정을 반박할 수 있다.
            detail: data.axes.map((a) => `${axLabel(a)} P${t.pcts[a]?.toFixed(0) ?? "-"}`).join(" · "),
            flagged: t.watch,
          }))
          .sort((a, b) => a.name.localeCompare(b.name));
        return {
          name: rule.id,
          total: members.length,
          members,
          hint: `하한 ${rule.lowAll.map(axLabel).join("·")} ≤ P${lowPct} · 상한 ${rule.highAny.map(axLabel).join(" 또는 ")} ≥ P${highPct}`,
        };
    });
  }, [data, lowPct, highPct]);

  const matched = buckets.reduce((n, b) => n + b.total, 0);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
          <span>{lowKnob?.label ?? "하위 백분위 P_low"}</span>
          <input
            type="range"
            min={lowKnob?.min ?? 0}
            max={lowKnob?.max ?? 50}
            step={lowKnob?.step ?? 1}
            value={lowPct}
            onChange={(e) => setLowPct(Number(e.target.value))}
            className="accent-[var(--series)]"
            aria-label={lowKnob?.label ?? "하위 백분위 P_low"}
          />
          <b className="w-9 tabular-nums text-[var(--ink)]">P{lowPct}</b>
        </label>
        <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
          <span>{highKnob?.label ?? "상위 백분위 P_high"}</span>
          <input
            type="range"
            min={highKnob?.min ?? 50}
            max={highKnob?.max ?? 100}
            step={highKnob?.step ?? 1}
            value={highPct}
            onChange={(e) => setHighPct(Number(e.target.value))}
            className="accent-[var(--series)]"
            aria-label={highKnob?.label ?? "상위 백분위 P_high"}
          />
          <b className="w-9 tabular-nums text-[var(--ink)]">P{highPct}</b>
        </label>
      </div>

      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-[var(--ink-secondary)]">
        <span>
          비교 모집단 <b className="text-[var(--ink)]">{data.tracks.length}</b>곡
        </span>
        <span>
          이 컷에서 매치 <b className="text-[var(--ink)]">{matched}</b>곡
        </span>
        <span>
          검출 규칙 <b className="text-[var(--ink)]">{data.rules.length}</b>건
        </span>
      </div>

      <BucketRows
        buckets={buckets}
        empty="이 컷에서는 매치 없음. P_low를 올리거나 P_high를 낮추면 후보 표시"
      />

      <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">
        백분위는 <b>당일 코호트 안의 상대 위치</b>입니다. 코호트 구성이 바뀌면 같은 곡도 값이
        달라집니다. 규칙이 {data.rules.length}건뿐이라 여기 안 걸린 곡이 “해당 없음”을 뜻하지
        않습니다.
      </p>
      {data.note && <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>}

      <CriteriaActions
        title={title ?? "검출 규칙 임계"}
        summary={`매치 ${matched}곡 · 비교 모집단 ${data.tracks.length}곡 · 규칙 ${data.rules.length}건`}
        items={
          [
            lowKnob && {
              label: lowKnob.label,
              from: `P${lowKnob.default}`,
              to: `P${lowPct}`,
              changed: lowPct !== lowKnob.default,
            },
            highKnob && {
              label: highKnob.label,
              from: `P${highKnob.default}`,
              to: `P${highPct}`,
              changed: highPct !== highKnob.default,
            },
          ].filter(Boolean) as CriteriaItem[]
        }
      />
    </div>
  );
}

// 선행·지연 목록. 115행을 세로로 쏟던 자리다(스크롤 세 화면).
//
// 🔴 **"상위 N행"으로 자르지 않는다.** 이 목록은 선행 일수 내림차순이라 위쪽이 소셜 선행,
// **아래쪽이 차트 선행 — 반례**다. 위에서 30행만 남기면 반례가 통째로 사라지고, 그것은
// 이 탭의 요약이 "선행 수"가 아니라 **반례를 포함한 구성**인 이유를 지워 버린다.
// 정보가 가장 적은 곳은 양 끝이 아니라 **가운데(0일 근처)**다. 그래서 가운데를 접고,
// 접었다는 사실과 접힌 구간을 적는다(DESIGN §7.5 "자를 때는 자른다고 적는다").
//
// 이름으로 좁히는 한 줄을 위에 둔다(§7 "필터는 차트 위 한 줄"). 115팀에서 특정 팀을
// 찾는 것은 스크롤이 아니라 검색의 일이고, 좁히는 동안에는 접지 않는다 —
// 찾는 사람은 이미 목록을 좁혀 놓았다.
const EDGE_ROWS = 15;

interface LeadLagRow {
  key: string;
  lead: number | null;
  posts: number;
  censored: boolean;
  weak: boolean;
}

function LeadLagList({
  rows,
  maxAbs,
  minPosts,
}: {
  rows: LeadLagRow[];
  maxAbs: number;
  minPosts: number;
}) {
  const [query, setQuery] = useState("");
  const [openMid, setOpenMid] = useState(false);

  const needle = query.trim().toLowerCase();
  const shown = needle ? rows.filter((r) => r.key.toLowerCase().includes(needle)) : rows;
  // 좁히는 중이거나 펼친 상태면 접지 않는다. 접을 값이 없을 때도(양 끝 + 최소 1행) 접지 않는다.
  const folding = !needle && !openMid && shown.length > EDGE_ROWS * 2 + 1;
  const head = folding ? shown.slice(0, EDGE_ROWS) : shown;
  const tail = folding ? shown.slice(-EDGE_ROWS) : [];
  // 접힌 구간은 **접힌 행들의** 값으로 말한다. 보이는 경계 행(+26일 · -9일)을 적으면
  // 화면에 있는 값을 감춰진 범위라고 말하는 셈이다.
  const mid = folding ? shown.slice(EDGE_ROWS, shown.length - EDGE_ROWS) : [];
  const fmtLead = (v: number) => `${v > 0 ? "+" : ""}${v}일`;

  const row = (r: LeadLagRow) => {
    const lead = r.lead ?? 0;
    const w = (Math.abs(lead) / maxAbs) * 50;
    // 판정 근거가 약한 행은 지우지 않고 흐리게 — 도구가 대신 결론내지 않는다
    const held = r.weak || r.censored;
    // 화면에 그대로 적을 짧은 사유. 자세한 뜻은 아래 캡션이 한 번 설명한다.
    const why = [r.weak ? `표본 ${r.posts}건 < ${minPosts}건` : null, r.censored ? "좌측 절단" : null]
      .filter(Boolean)
      .join(" · ");
    return (
      <div key={r.key} className={`flex items-center gap-2 text-xs ${held ? "opacity-45" : ""}`}>
        <div className="w-28 truncate text-right text-[var(--ink-secondary)]" title={r.key}>
          {r.key}
        </div>
        <div className="relative h-4 flex-1">
          <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--baseline)]" />
          <div
            className="absolute inset-y-0.5 rounded-sm"
            style={
              lead >= 0
                ? { left: "50%", width: `${w}%`, background: "var(--series)" }
                : { right: "50%", width: `${w}%`, background: "var(--series2)" }
            }
          />
        </div>
        {/* `+127일`이 w-10에서 두 줄로 접혀 있었다 — 숫자 칸은 최댓값이 들어갈
            만큼 잡고 줄바꿈을 막는다. 값이 접히면 읽는 사람이 두 값으로 센다. */}
        <div className="w-12 shrink-0 whitespace-nowrap text-right tabular-nums text-[var(--muted)]">
          {fmtLead(lead)}
        </div>
        {/* 사유를 그대로 적는다 — 툴팁도 `title`도 없다(위 주석 참고).
            칸은 사유 두 개가 같이 들어갈 폭으로 잡는다. 좁게 잡아 잘라 두면
            감춰진 것을 툴팁에서 잘린 텍스트로 옮긴 것일 뿐이다. */}
        <div className="w-40 shrink-0 truncate text-[var(--muted)]">{why}</div>
      </div>
    );
  };

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
        <label className="flex items-center gap-2">
          <span className="text-[var(--ink-secondary)]">팀 이름으로 좁히기</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="이름 일부"
            className="w-40 rounded border px-2 py-0.5 text-xs text-[var(--ink)] placeholder:text-[var(--muted)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--series)]"
            style={{ borderColor: "var(--hairline)", background: "var(--plane)" }}
          />
        </label>
        {/* 좁히면 위의 집계(선행·지연 수)와 목록의 수가 달라진다. 그 사실을 적지 않으면
            좁힌 목록의 길이가 전체 수로 읽힌다. */}
        <span className="tabular-nums text-[var(--muted)]">
          {needle
            ? `${shown.length}팀 표시 · 위 집계는 전체 ${rows.length}팀 기준`
            : `${rows.length}팀 · 선행 일수 내림차순`}
        </span>
      </div>

      {shown.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">이름에 “{query.trim()}”가 든 팀 없음</p>
      ) : (
        <div className="space-y-1">
          {head.map(row)}
          {folding && (
            <button
              type="button"
              onClick={() => setOpenMid(true)}
              aria-expanded={false}
              className="flex w-full items-center gap-2 rounded-sm py-1 text-left text-xs text-[var(--muted)] transition-colors duration-150 ease-out hover:bg-[var(--hairline)] hover:text-[var(--ink-secondary)]"
            >
              <span className="w-28 shrink-0 text-right">가운데 {mid.length}팀</span>
              <span className="flex-1 border-t border-dashed" style={{ borderColor: "var(--baseline)" }} />
              <span className="shrink-0 tabular-nums">
                {fmtLead(mid[0].lead ?? 0)} ~ {fmtLead(mid[mid.length - 1].lead ?? 0)} 접힘 · 펼치기
              </span>
            </button>
          )}
          {tail.map(row)}
          {openMid && !needle && (
            <button
              type="button"
              onClick={() => setOpenMid(false)}
              aria-expanded
              className="mt-1 rounded-sm px-1 py-0.5 text-xs text-[var(--muted)] transition-colors duration-150 ease-out hover:text-[var(--ink-secondary)]"
            >
              가운데 접기
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function UnknownView({ view }: { view?: string }) {
  return (
    <p className="text-sm text-[var(--ink-secondary)]">
      이 대시보드가 아직 모르는 뷰입니다{view ? ` (view=${view})` : ""}. 리포트 데이터는 그대로
      있으며, 렌더러가 갱신되면 표시됩니다.
    </p>
  );
}

// 집계 막대는 접힌 요약이고, 펼치면 그 칸에 들어간 곡이 나온다.
// 곡 수만 보이면 반박할 대상이 없다 — 배정이 틀렸는지는 곡 이름을 봐야 눈에 띈다.
// <details>를 쓰는 이유: 상태 없이 키보드·스크린리더가 그대로 동작한다.
interface BucketMember {
  name: string;
  detail: string;
  flagged?: boolean;
}
interface Bucket {
  name: string;
  total: number;
  /** 막대 안에 겹쳐 표시할 몫(동점 등). 없으면 0 */
  highlight?: number;
  muted?: boolean;
  members: BucketMember[];
  /**
   * 행이 무엇으로 정해졌는지(예: 규칙의 하한·상한 축). **보이는 텍스트로 렌더된다.**
   *
   * 예전에는 `title` 속성이라 포인터로만 닿았고, 눈에 보이는 표시가 없어 **거기 설명이
   * 있다는 것 자체를 알 수 없었다**(DESIGN §7.6). 화면에 이미 있는 값을 되풀이하는
   * hint는 넣지 않는다 — 곡 수는 오른쪽 숫자가, 동점 몫은 막대의 두 번째 색이 말한다.
   */
  hint?: string;
}

function BucketRows({ buckets, empty }: { buckets: Bucket[]; empty: string }) {
  // 모션이 여기 있는 이유(DESIGN §5·§7.7): 노브를 돌리면 **곡이 칸 사이를 옮겨 다닌다**.
  // 그것이 이 위젯의 전부인데, 폭이 즉시 갈아 끼워지면 얼마나 옮겨갔는지 보이지 않는다.
  // 움직이는 것은 **막대 폭 하나**다. 곡 수 숫자는 즉시 바뀐다 — 지금 값이 무엇인지는
  // 기다리게 만들 것이 아니고, 정확한 값은 언제나 숫자 쪽에 있다.
  //
  // 🔴 **행 재정렬은 애니메이션하지 않는다.** 칸이 곡 수로 정렬돼 있어 임계를 움직이면
  // 순서가 자주 뒤집히는데, `layout` 위치 전환을 걸었더니 22px짜리 행 셋이 서로를 통과하며
  // **이름과 숫자가 겹쳐 읽을 수 없는 더미**가 됐다(2026-07-30 실측: `33`과 `14`가 한 줄에
  // 포개짐). 게다가 슬라이더는 **연속 입력**이라 드래그 중에는 전환이 끝나지 않는다 —
  // 크로스헤어에 전환을 넣지 않는 것과 같은 이유다. 겹치는 순간 증거가 안 읽힌다.
  //
  // 남은 폭 전환은 CSS라 `useReducedMotion`을 부르지 않는다 — globals.css의 안전망이
  // 전역에서 즉시 완료로 만든다(§5). 흩어진 전환을 컴포넌트마다 다시 묻지 않는 이유다.
  const maxCount = Math.max(1, ...buckets.map((b) => b.total));
  if (buckets.length === 0) return <p className="text-sm text-[var(--muted)]">{empty}</p>;
  return (
    <div className="space-y-0.5">
      {buckets.map((b) => {
        const w = (b.total / maxCount) * 100;
        const hi = b.highlight ?? 0;
        const hiW = b.total > 0 ? (hi / b.total) * w : 0;
        return (
          <details key={b.name} className="group rounded-sm">
            <summary className="cursor-pointer list-none rounded-sm py-0.5 text-xs hover:bg-[var(--hairline)]">
              <span className="flex items-center gap-2">
              <span
                className="w-3 shrink-0 text-center text-[var(--muted)] transition-transform duration-150 group-open:rotate-90"
                aria-hidden
              >
                ›
              </span>
              <span className="w-32 shrink-0 truncate text-right text-[var(--ink-secondary)]" title={b.name}>
                {b.name}
              </span>
              <span className="relative h-4 flex-1">
                <span
                  className="absolute inset-y-0.5 left-0 rounded-sm transition-[width] duration-150 ease-out"
                  style={{
                    width: `${w}%`,
                    background: b.muted ? "var(--baseline)" : "var(--series)",
                    opacity: b.muted ? 0.6 : 1,
                  }}
                />
                {hi > 0 && !b.muted && (
                  <span
                    className="absolute inset-y-0.5 rounded-sm transition-[left,width] duration-150 ease-out"
                    style={{ left: `${w - hiW}%`, width: `${hiW}%`, background: "var(--series2)" }}
                  />
                )}
              </span>
              <span className="w-8 shrink-0 text-right tabular-nums text-[var(--muted)]">{b.total}</span>
              </span>
              {/* 행이 무엇으로 정해졌는지는 **보이는 자리**에 적는다. 라벨 아래 한 줄이라
                  접힌 상태에서도 읽히고, 라벨 칸(w-32)에 맞춰 들여쓰면 어느 행의 것인지 붙는다. */}
              {b.hint && (
                <span className="mt-0.5 block pl-[calc(0.75rem+8rem+1rem)] text-[11px] leading-snug text-[var(--muted)]">
                  {b.hint}
                </span>
              )}
            </summary>
            <ul className="mb-1 ml-5 mt-1 space-y-0.5 border-l pl-3 text-xs" style={{ borderColor: "var(--hairline)" }}>
              {b.members.map((m) => (
                <li key={m.name} className="flex items-baseline gap-2">
                  <span className="truncate text-[var(--ink-secondary)]" title={m.name}>
                    {m.name}
                  </span>
                  <span
                    className="shrink-0 tabular-nums"
                    style={{ color: m.flagged ? "var(--series2)" : "var(--muted)" }}
                  >
                    {m.detail}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        );
      })}
    </div>
  );
}

// view=tags — sonic-profile 악기 구성. 검출 임계는 A&R 소유라 코드가 아니라 노브에 있다.
// 태거가 상위 k개만 남기므로, 임계가 그 절단선 아래로 내려간 곡은 곡 수가 **하한**이 된다.
function Tags({ data, title }: { data: TagsTunableData; title?: string }) {
  const knob = data.knobs.find((k) => k.key === "min_prob") ?? data.knobs[0];
  const scope = scopeOf("tags", title);
  const [minProb, setMinProb] = useKnob(scope, knob?.key ?? "min_prob", knob?.default ?? 0.3);
  const topBuckets = data.topBuckets ?? 14;

  const { buckets, hidden, lowerBound } = useMemo(() => {
    const map = new Map<string, BucketMember[]>();
    let cut = 0;
    for (const track of data.tracks) {
      if (track.truncated && track.floor > minProb) cut++;
      for (const l of track.labels) {
        if (l.p < minProb) continue;
        const list = map.get(l.label) ?? [];
        list.push({ name: track.name, detail: l.p.toFixed(2) });
        map.set(l.label, list);
      }
    }
    const all = [...map.entries()]
      .map(([name, members]) => ({
        name,
        total: members.length,
        members: members.sort((a, b) => Number(b.detail) - Number(a.detail) || a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
    return { buckets: all.slice(0, topBuckets), hidden: Math.max(0, all.length - topBuckets), lowerBound: cut };
  }, [data, minProb, topBuckets]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
          <span>{knob?.label ?? "검출로 볼 최소 확률"}</span>
          <input
            type="range"
            min={knob?.min ?? 0.05}
            max={knob?.max ?? 0.9}
            step={knob?.step ?? 0.05}
            value={minProb}
            onChange={(e) => setMinProb(Number(e.target.value))}
            className="accent-[var(--series)]"
            aria-label={knob?.label ?? "검출로 볼 최소 확률"}
          />
          <b className="w-9 tabular-nums text-[var(--ink)]">{minProb.toFixed(2)}</b>
        </label>
      </div>

      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-[var(--ink-secondary)]">
        <span>관측 <b className="text-[var(--ink)]">{data.tracks.length}</b>곡</span>
        <span>이 임계에서 잡힌 악기 <b className="text-[var(--ink)]">{buckets.length + hidden}</b>종</span>
        {/* `title`을 걷어냈다: 같은 설명이 아래 ⚠ 문장으로 **이미 화면에 있다**.
            화면에 있는 것을 툴팁이 되풀이하면 정보는 0이고 장식만 남는다(DESIGN §7.6). */}
        {lowerBound > 0 && (
          <span>
            곡 수가 하한인 곡 <b className="text-[var(--ink)]">{lowerBound}</b>
          </span>
        )}
      </div>

      <BucketRows buckets={buckets} empty="이 임계에서 검출된 악기 없음. 슬라이더를 낮추면 후보 표시" />

      {hidden > 0 && (
        <p className="mt-2 text-xs text-[var(--muted)]">상위 {buckets.length}종만 표시 · {hidden}종 생략</p>
      )}
      {lowerBound > 0 && (
        <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
          ⚠ {lowerBound}곡은 곡 수가 <b>하한</b>입니다. 태깅 당시 상위 라벨만 저장돼, 임계를 넘는 악기가
          더 있어도 세지 못합니다. 임계를 올리면 이 수가 줄어듭니다.
        </p>
      )}
      {data.note && <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>}

      <CriteriaActions
        title={title ?? "악기 검출 기준"}
        items={
          knob
            ? [
                {
                  label: knob.label,
                  from: knob.default.toFixed(2),
                  to: minProb.toFixed(2),
                  changed: minProb !== knob.default,
                },
              ]
            : []
        }
        summary={`악기 ${buckets.length + hidden}종 · 관측 ${data.tracks.length}곡${
          lowerBound > 0 ? ` · 하한 ${lowerBound}곡` : ""
        }`}
      />
    </div>
  );
}

// view=whitespace — a gap map: proven markets (≥threshold roster acts) × top acts,
// empty cell = greenfield the act hasn't reached.
function Whitespace({ data, title }: { data: WhitespaceTunableData; title?: string }) {
  // 칸 툴팁은 `Heatmap`과 같은 규율이다(DESIGN §7.6): 칸에서 멀리 떨어진 머리글을
  // 되짚지 않게 좌표를 커서 옆에서 말하고, 칸마다 `tabIndex`를 뿌리는 대신 행·열
  // 머리글을 `<th scope>`로 선언해 표 의미로 닿게 한다.
  const tip = useChartTooltip<{ row: string; col: string; text: string; gap: boolean }>();
  const knob = data.knobs?.[0];
  const scope = scopeOf("whitespace", title);
  const [threshold, setThreshold] = useKnob(scope, knob?.key ?? "threshold", knob?.default ?? 2);
  const { matrix } = data;
  const topRows = data.topRows ?? 10;

  const { provenIdx, rowIdx } = useMemo(() => {
    const nCols = matrix.cols.length;
    // 시장 강도 = 열별 진입 팀 수(전체 로스터) → 개척 시장 = 강도 ≥ 임계
    const strength = Array.from({ length: nCols }, (_, j) =>
      matrix.cells.reduce((n, row) => n + (row[j] != null ? 1 : 0), 0),
    );
    const proven = Array.from({ length: nCols }, (_, j) => j).filter(
      (j) => strength[j] >= threshold,
    );
    // reach = 행별 진입 시장 수 → 상위 팀 선택(표시)
    const reach = matrix.rows.map((_, i) =>
      matrix.cols.reduce((n, _c, j) => n + (matrix.cells[i][j] != null ? 1 : 0), 0),
    );
    const rows = matrix.rows
      .map((_, i) => i)
      .sort((a, b) => reach[b] - reach[a] || matrix.rows[a].localeCompare(matrix.rows[b]))
      .slice(0, topRows);
    return { provenIdx: proven, rowIdx: rows };
  }, [matrix, threshold, topRows]);

  const topGap = rowIdx.length
    ? provenIdx.filter((j) => matrix.cells[rowIdx[0]][j] == null).length
    : 0;
  const gapBox = {
    background: "color-mix(in srgb, var(--good) 16%, transparent)",
    border: "1px solid var(--good)",
  };

  return (
    <div className="relative" ref={tip.containerRef}>
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs">
        <label htmlFor="tunable-knob" className="text-[var(--ink-secondary)]">
          {knob?.label ?? "기준"}
        </label>
        <input
          id="tunable-knob"
          type="range"
          min={knob?.min ?? 1}
          max={knob?.max ?? 6}
          step={knob?.step ?? 1}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          className="accent-[var(--series)]"
          aria-label={knob?.label ?? "기준"}
        />
        <span className="tabular-nums font-medium">{threshold}팀+</span>
        <span className="text-[var(--muted)]">
          개척 시장 <b className="tabular-nums text-[var(--ink)]">{provenIdx.length}</b>개국
          {rowIdx.length ? ` · ${matrix.rows[rowIdx[0]]} 미개척 ${topGap}개국` : ""}
        </span>
      </div>

      {provenIdx.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">이 기준에서는 개척 시장 없음. 슬라이더를 낮추면 후보 표시</p>
      ) : (
        <div className="overflow-x-auto">
          <table data-plot="heatmap" className="border-separate" style={{ borderSpacing: 2 }}>
            <thead>
              <tr>
                <th />
                {provenIdx.map((j) => (
                  <th
                    key={j}
                    scope="col"
                    className="px-2 pb-1 text-center text-xs font-normal text-[var(--muted)]"
                  >
                    {matrix.cols[j]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowIdx.map((i) => (
                <tr key={i}>
                  <th scope="row" className="pr-3 text-left font-normal">
                    <div
                      className="max-w-[160px] truncate text-xs text-[var(--ink-secondary)]"
                      title={matrix.rows[i]}
                    >
                      {matrix.rows[i]}
                    </div>
                  </th>
                  {provenIdx.map((j) => {
                    const v = matrix.cells[i][j];
                    const datum = {
                      row: matrix.rows[i],
                      col: matrix.cols[j],
                      text: v == null ? "미개척" : `${v}위`,
                      gap: v == null,
                    };
                    return (
                      <td
                        key={j}
                        style={{ width: 40, height: 26 }}
                        onPointerMove={(e) => tip.show(e, datum)}
                        onPointerLeave={tip.hide}
                      >
                        {v == null ? (
                          <div className="h-6 rounded" style={gapBox} />
                        ) : (
                          <div
                            className="flex h-6 items-center justify-center rounded text-xs tabular-nums text-[var(--muted)]"
                            style={{ background: "var(--hairline)" }}
                          >
                            {v}
                          </div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ChartTooltip tip={tip}>
        {tip.datum && (
          <>
            <div
              className={`font-medium ${tip.datum.gap ? "text-[var(--good)]" : "text-[var(--ink)]"}`}
            >
              {tip.datum.text}
            </div>
            <div className="mt-0.5 text-[var(--ink-secondary)]">{tip.datum.row}</div>
            <div className="text-[var(--muted)]">{tip.datum.col}</div>
          </>
        )}
      </ChartTooltip>

      <div className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted)]">
        <span className="inline-block h-3 w-3 rounded" style={gapBox} />
        <span>미개척</span>
        <span
          className="ml-2 inline-block h-3 w-3 rounded"
          style={{ background: "var(--hairline)" }}
        />
        <span>진입(숫자=순위)</span>
      </div>

      {data.note && (
        <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>
      )}

      <CriteriaActions
        title={title ?? "개척 시장"}
        items={[
          {
            label: knob?.label ?? "기준",
            from: String(knob?.default ?? 2),
            to: String(threshold),
            changed: threshold !== (knob?.default ?? 2),
          },
        ]}
        summary={`개척 시장 ${provenIdx.length}개국`}
      />
    </div>
  );
}

// view=rhythm — sonic-profile: 마디 킥 프로파일 × 명명 템플릿의 코사인 정합을 클라이언트에서
// 다시 계산한다. 템플릿이 서로 직교하지 않아 1위는 순위일 뿐이므로, 화면은 세 가지를 같이 낸다:
// 배정 임계 미만인 '해당 없음' 버킷 · 1·2위가 근소차인 '동점' 몫 · 두 기준의 슬라이더.
// 막대 하나에 곡 수만 찍으면 그 형식 자체가 순위를 판정으로 되돌린다.
function cosine(profile: number[], positions: number[], bins: number): number {
  const n = Math.min(profile.length, bins);
  if (n === 0) return 0;
  const a = profile.slice(0, n);
  const aMean = a.reduce((s, v) => s + v, 0) / n;
  const t: number[] = Array.from({ length: n }, (_, i) => (positions.includes(i) ? 1 : 0));
  const tMean = t.reduce((s, v) => s + v, 0) / n;
  let dot = 0;
  let na = 0;
  let nt = 0;
  for (let i = 0; i < n; i++) {
    const da = a[i] - aMean;
    const dt = t[i] - tMean;
    dot += da * dt;
    na += da * da;
    nt += dt * dt;
  }
  // 완전 평탄한 프로파일은 노름 0 — 0을 돌려주고 임계가 배정을 막는다.
  // 여기서 임의의 이름을 뽑으면 "리듬 없음"이 "정박"으로 둔갑한다.
  return na > 0 && nt > 0 ? dot / Math.sqrt(na * nt) : 0;
}

function Rhythm({ data, title }: { data: RhythmTunableData; title?: string }) {
  const kM = data.knobs.find((k) => k.key === "min_match");
  const kT = data.knobs.find((k) => k.key === "tie_gap");
  const scope = scopeOf("rhythm", title);
  const [minMatch, setMinMatch] = useKnob(scope, "min_match", kM?.default ?? 0.3);
  const [tieGap, setTieGap] = useKnob(scope, "tie_gap", kT?.default ?? 0.05);

  const { buckets, assigned, ties, noMatch } = useMemo(() => {
    const names = Object.keys(data.templates);
    const acc = new Map<string, { tie: number; members: BucketMember[] }>();
    const bucketOf = (k: string) => {
      const cur = acc.get(k) ?? { tie: 0, members: [] };
      acc.set(k, cur);
      return cur;
    };

    let nTie = 0;
    let nNone = 0;
    for (const track of data.tracks) {
      const scored = names
        .map((name) => ({ name, score: cosine(track.profile, data.templates[name], data.bins) }))
        // 동점은 이름순으로 깬다 — 객체 키 순서에 배정이 좌우되면 안 된다
        .sort((x, y) => y.score - x.score || x.name.localeCompare(y.name));
      const top = scored[0];
      if (!top || top.score < minMatch) {
        nNone++;
        bucketOf(data.noMatchLabel).members.push({
          name: track.name,
          // 어디에 가장 가까웠는지는 남긴다 — 배정하지 않을 뿐 정보를 버리지는 않는다
          // 빈 대시는 0으로도 읽힌다. 결측은 결측이라고 적는다(§0).
          detail: top ? `최고 ${top.name} ${top.score.toFixed(2)}` : "정합도 없음",
        });
        continue;
      }
      const gap = scored.length > 1 ? top.score - scored[1].score : Infinity;
      const tie = gap < tieGap;
      if (tie) nTie++;
      const b = bucketOf(top.name);
      if (tie) b.tie++;
      b.members.push({
        name: track.name,
        detail: tie
          ? `${top.score.toFixed(2)} · 동점 ${scored[1].name} ${scored[1].score.toFixed(2)}`
          : top.score.toFixed(2),
        flagged: tie,
      });
    }
    const rows: Bucket[] = [...acc.entries()]
      .map(([name, v]) => ({
        name,
        total: v.members.length,
        highlight: v.tie,
        muted: name === data.noMatchLabel,
        members: v.members.sort(
          (a, b) => parseFloat(b.detail) - parseFloat(a.detail) || a.name.localeCompare(b.name),
        ),
        // hint를 두지 않는다: 곡 수는 오른쪽 숫자가, 동점 몫은 막대의 두 번째 색과 범례가
        // 이미 말하고, '해당 없음'의 뜻은 위 `Terms`가 보이는 텍스트로 설명한다.
        // 화면에 있는 것을 한 번 더 적으면 정보가 아니라 잡음이 된다(DESIGN §7.6).
      }))
      .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
    return {
      buckets: rows,
      assigned: data.tracks.length - nNone,
      ties: nTie,
      noMatch: nNone,
    };
  }, [data, minMatch, tieGap]);

  const fmt = (v: number) => v.toFixed(2);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
          <span>{kM?.label ?? "유형 배정 최소 정합도"}</span>
          <input
            type="range"
            min={kM?.min ?? 0}
            max={kM?.max ?? 0.8}
            step={kM?.step ?? 0.05}
            value={minMatch}
            onChange={(e) => setMinMatch(Number(e.target.value))}
            className="accent-[var(--series)]"
            aria-label={kM?.label ?? "유형 배정 최소 정합도"}
          />
          <b className="w-9 tabular-nums text-[var(--ink)]">{fmt(minMatch)}</b>
        </label>
        <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
          <span>{kT?.label ?? "동점으로 볼 1위−2위 차"}</span>
          <input
            type="range"
            min={kT?.min ?? 0}
            max={kT?.max ?? 0.3}
            step={kT?.step ?? 0.01}
            value={tieGap}
            onChange={(e) => setTieGap(Number(e.target.value))}
            className="accent-[var(--series)]"
            aria-label={kT?.label ?? "동점으로 볼 1위−2위 차"}
          />
          <b className="w-9 tabular-nums text-[var(--ink)]">{fmt(tieGap)}</b>
        </label>
      </div>

      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-[var(--ink-secondary)]">
        <span>관측 <b className="text-[var(--ink)]">{data.tracks.length}</b>곡</span>
        <span>유형 배정 <b className="text-[var(--ink)]">{assigned}</b></span>
        <span>
          해당 없음 <b className="text-[var(--ink)]">{noMatch}</b>
        </span>
        <span>
          그중 동점 <b className="text-[var(--ink)]">{ties}</b>
        </span>
      </div>

      {/* 두 라벨의 뜻은 `title` 속성에만 있었다. 보이는 표시가 없으면 거기 설명이 있다는
          것 자체를 모르고, 키보드로는 닿을 방법도 없다(DESIGN §7.6). */}
      <Terms
        className="mb-4 -mt-2"
        items={[
          ["해당 없음", "정합도가 임계 미만인 곡. '다른 유형'이 아니라 '해당 없음'입니다."],
          [
            "그중 동점",
            "1위와 2위의 정합도 차가 동점 폭 미만인 곡. 표본이 조금만 흔들려도 순서가 뒤집힙니다.",
          ],
        ]}
      />

      <BucketRows buckets={buckets} empty="이 기준에서는 집계할 곡이 없음" />

      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-[var(--muted)]">
        <span className="inline-block h-3 w-3 rounded" style={{ background: "var(--series)" }} />
        <span>유형 배정</span>
        <span className="ml-2 inline-block h-3 w-3 rounded" style={{ background: "var(--series2)" }} />
        <span>그중 동점(1·2위 근소차, 뒤집힐 수 있음)</span>
        <span
          className="ml-2 inline-block h-3 w-3 rounded"
          style={{ background: "var(--baseline)", opacity: 0.6 }}
        />
        <span>해당 없음</span>
        <span className="ml-2">행을 클릭하면 그 칸에 든 곡과 정합도가 펼쳐집니다</span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
        정합도는 −1~1이며 0은 &quot;닮지도 반대도 아님&quot;입니다. 임계를 0까지 내리면 어떤 곡도
        해당 없음이 되지 않아 반대로 생긴 곡까지 유형을 받습니다.
      </p>
      {data.note && <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>}

      <CriteriaActions
        title={title ?? "리듬 유형 기준"}
        items={[
          kM && {
            label: kM.label,
            from: fmt(kM.default),
            to: fmt(minMatch),
            changed: minMatch !== kM.default,
          },
          kT && {
            label: kT.label,
            from: fmt(kT.default),
            to: fmt(tieGap),
            changed: tieGap !== kT.default,
          },
        ].filter(Boolean) as CriteriaItem[]}
        summary={`유형 배정 ${assigned} · 해당 없음 ${noMatch} · 그중 동점 ${ties}`}
      />
    </div>
  );
}

// view=leadlag — θ 슬라이더: 브리지 RULES §3 온셋 정의 그대로 클라이언트 재계산.
// 소셜 온셋 = 첫 게시수 ≥ θ_social · 차트 온셋 = 첫 순위 ≤ θ_rank · lead = 차트 − 소셜(일).
const DAY_MS = 86400000;

function LeadLag({ data, title }: { data: LeadLagTunableData; title?: string }) {
  // 판단 보류 사유는 `title` 속성에만 있었다 — 캡션이 "마우스를 올리면 사유"라고
  // 안내할 정도로 **포인터 전용 경로**였고 키보드로는 닿지 않았다(DESIGN §7.6).
  //
  // 툴팁이 아니라 **보이는 텍스트**로 내놓는다. 처음엔 ⓘ를 포커스 가능한 마크로 만들어
  // 툴팁을 달았는데, 실제 렌더에서 최소 표본 기준이 20건이면 **110행 중 대부분이 보류**라
  // 탭 정지가 100개 넘게 생겼다 — 격자에 `tabIndex`를 뿌리지 않기로 한 것과 같은 벽이다.
  // 사유는 짧아서(`표본 12건 < 20건` · `좌측 절단`) 그냥 적으면 감춰진 것이 0이 되고
  // 인터랙션도 0이 된다. 여기서는 그게 더 나은 답이다(§1: 더하기 전에 뺄 것을 먼저).
  const kS = data.knobs.find((k) => k.key === "theta_social");
  const kR = data.knobs.find((k) => k.key === "theta_rank");
  const kP = data.knobs.find((k) => k.key === "min_posts");
  const kC = data.knobs.find((k) => k.key === "exclude_censored");
  const scope = scopeOf("leadlag", title);
  const [thetaS, setThetaS] = useKnob(scope, "theta_social", kS?.default ?? 1);
  const [thetaR, setThetaR] = useKnob(scope, "theta_rank", kR?.default ?? 200);
  const [minPosts, setMinPosts] = useKnob(scope, "min_posts", kP?.default ?? 1);
  const [censoredFlag, setCensoredFlag] = useKnob(scope, "exclude_censored", kC?.default ? 1 : 0);
  const hideCensored = censoredFlag === 1;

  const rows = useMemo(() => {
    const out: {
      key: string;
      klass: string;
      lead: number | null;
      posts: number;
      censored: boolean;
      weak: boolean;
    }[] = [];
    for (const [key, s] of Object.entries(data.series)) {
      let sOnset: string | null = null;
      if (s.social)
        for (let i = 0; i < data.socialDates.length; i++)
          if ((s.social[i] ?? 0) >= thetaS) {
            sOnset = data.socialDates[i];
            break;
          }
      let cOnset: string | null = null;
      if (s.chart)
        for (let i = 0; i < data.chartDates.length; i++) {
          const v = s.chart[i];
          if (v != null && v <= thetaR) {
            cOnset = data.chartDates[i];
            break;
          }
        }
      if (!sOnset && !cOnset) continue;
      const ev = data.evidence?.[key];
      const posts = ev?.posts ?? 0;
      // 좌측 절단은 차트 온셋이 기본 기준일 때만 유효한 판정 — θ_rank를 조이면 온셋이 뒤로 밀린다
      const censored = Boolean(ev?.censored) && thetaR >= (kR?.default ?? thetaR);
      const weak = Boolean(data.evidence) && posts < minPosts;
      if (hideCensored && censored) continue;
      if (sOnset && cOnset) {
        const lead = Math.round((Date.parse(cOnset) - Date.parse(sOnset)) / DAY_MS);
        out.push({
          key,
          klass: lead > 0 ? "social-led" : lead < 0 ? "chart-led" : "coincident",
          lead,
          posts,
          censored,
          weak,
        });
      } else {
        out.push({ key, klass: sOnset ? "social-only" : "chart-only", lead: null, posts, censored, weak });
      }
    }
    return out;
  }, [data, thetaS, thetaR, minPosts, hideCensored, kR]);

  const count = (c: string) => rows.filter((r) => r.klass === c).length;
  // 판정 가능 = 표본 하한 통과 + 비검열. 나머지는 지우지 않고 흐리게 표시(RULES §3.1: 행 삭제 금지)
  const decidable = rows.filter((r) => r.klass === "social-led" && !r.weak && !r.censored).length;
  const joined = rows
    .filter((r) => r.lead != null)
    .sort((a, b) => (b.lead ?? 0) - (a.lead ?? 0) || a.key.localeCompare(b.key));
  const maxAbs = Math.max(1, ...joined.map((r) => Math.abs(r.lead ?? 0)));

  const onOff = (v: number) => (v === 1 ? "켜기" : "끄기");
  const criteriaItems: CriteriaItem[] = [
    kS && { label: kS.label, from: String(kS.default), to: String(thetaS), changed: thetaS !== kS.default },
    kR && { label: kR.label, from: String(kR.default), to: String(thetaR), changed: thetaR !== kR.default },
    kP && data.evidence
      ? { label: kP.label, from: String(kP.default), to: String(minPosts), changed: minPosts !== kP.default }
      : null,
    kC && data.evidence
      ? {
          label: kC.label,
          from: onOff(kC.default ? 1 : 0),
          to: onOff(censoredFlag),
          changed: censoredFlag !== (kC.default ? 1 : 0),
        }
      : null,
  ].filter(Boolean) as CriteriaItem[];

  function Slider({
    knob,
    value,
    onChange,
  }: {
    knob: typeof kS;
    value: number;
    onChange: (v: number) => void;
  }) {
    return (
      <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
        <span>{knob?.label ?? "기준"}</span>
        <input
          type="range"
          min={knob?.min ?? 1}
          max={knob?.max ?? 200}
          step={knob?.step ?? 1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="accent-[var(--series)]"
          aria-label={knob?.label ?? "기준"}
        />
        <b className="w-8 tabular-nums text-[var(--ink)]">{value}</b>
      </label>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Slider knob={kS} value={thetaS} onChange={setThetaS} />
        <Slider knob={kR} value={thetaR} onChange={setThetaR} />
        {kP && data.evidence && <Slider knob={kP} value={minPosts} onChange={setMinPosts} />}
        {kC && data.evidence && (
          <label className="flex items-center gap-2 text-xs text-[var(--ink-secondary)]">
            <input
              type="checkbox"
              checked={hideCensored}
              onChange={(e) => setCensoredFlag(e.target.checked ? 1 : 0)}
              className="accent-[var(--series)]"
            />
            <span>{kC.label}</span>
          </label>
        )}
      </div>
      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-[var(--ink-secondary)]">
        <span>소셜 선행 <b className="text-[var(--ink)]">{count("social-led")}</b></span>
        {data.evidence && (
          <span>
            그중 판정 가능 <b className="text-[var(--ink)]">{decidable}</b>
          </span>
        )}
        <span>동시 <b className="text-[var(--ink)]">{count("coincident")}</b></span>
        <span>차트 선행 <b className="text-[var(--ink)]">{count("chart-led")}</b></span>
        <span>소셜-온리 <b className="text-[var(--ink)]">{count("social-only")}</b></span>
        <span>차트-온리 <b className="text-[var(--ink)]">{count("chart-only")}</b></span>
      </div>

      {/* 여섯 라벨 중 뜻이 자명하지 않은 것만 적는다. '소셜 선행'·'동시'는 말 그대로이므로
          되풀이하지 않는다(§1: 더하기 전에 뺄 것을 먼저). */}
      <Terms
        className="mb-4 -mt-2"
        items={[
          ...(data.evidence
            ? ([["그중 판정 가능", "표본 하한을 넘고 차트 온셋이 좌측 절단도 아닌 팀."]] as [string, string][])
            : []),
          ["소셜-온리", "소셜 온셋만 잡힌 팀. 차트 온셋이 아직 없어 선행 일수를 낼 수 없습니다."],
          ["차트-온리", "차트 온셋만 잡힌 팀. 수집한 소셜 표본에서 온셋 기준을 넘지 못했습니다."],
        ]}
      />

      {joined.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">이 기준에서는 소셜·차트 상승 시작이 모두 잡힌 팀 없음</p>
      ) : (
        <LeadLagList rows={joined} maxAbs={maxAbs} minPosts={minPosts} />
      )}

      <div className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted)]">
        <span className="inline-block h-3 w-3 rounded" style={{ background: "var(--series)" }} />
        <span>양수 = 소셜이 먼저</span>
        <span className="ml-2 inline-block h-3 w-3 rounded" style={{ background: "var(--series2)" }} />
        <span>음수 = 차트가 먼저</span>
        {/* '좌측 절단'의 뜻은 아래 `note`(리포트가 싣는다)가 이미 정의한다 — 여기서
            되풀이하면 같은 문장이 두 줄로 남는다. */}
        {data.evidence && <span className="ml-2">흐린 행 = 판단 보류 · 사유는 행 오른쪽</span>}
      </div>
      {data.note && <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{data.note}</p>}

      <CriteriaActions
        title={title ?? "선행 판별"}
        items={criteriaItems}
        summary={
          `소셜 선행 ${count("social-led")}` +
          (data.evidence ? ` · 그중 판정 가능 ${decidable}` : "") +
          ` · 동시 ${count("coincident")} · 차트 선행 ${count("chart-led")}` +
          ` · 소셜-온리 ${count("social-only")} · 차트-온리 ${count("chart-only")}`
        }
      />
    </div>
  );
}
