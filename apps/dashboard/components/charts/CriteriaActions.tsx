"use client";

// 기준을 되돌려주는 표면. 도구는 결과에 대한 승인을 묻지 않는다 —
// 기준을 조정한 사람이 그 기준을 그대로 들고 나갈 수 있게만 한다.

import { useCallback, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { currentUrl } from "@/lib/knobs";

export interface CriteriaItem {
  label: string;
  from: string;
  to: string;
  changed: boolean;
}

async function copy(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // 보안 컨텍스트가 아니면 아래 폴백으로
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

/**
 * 보는 사람의 로컬 날짜. toISOString()은 UTC라 KST 기준 자정~오전 9시에 하루가 밀린다
 * (실측: 로컬 2026-07-29 08:59 → UTC 2026-07-28). 제안서에 찍히는 날짜는 작성자의 날짜여야 한다.
 */
function todayLocal(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function proposalText(title: string, items: CriteriaItem[], summary: string): string {
  const changed = items.filter((i) => i.changed);
  const lines = [`기준 제안 · ${title}`, `작성 ${todayLocal()}`, ""];

  lines.push("바꾼 값");
  if (changed.length === 0) lines.push("  없음. 기본 기준 그대로");
  else for (const i of changed) lines.push(`  ${i.label}  ${i.from} → ${i.to}`);

  lines.push("", "이 기준에서의 결과", `  ${summary}`);

  const url = currentUrl();
  if (url) lines.push("", "같은 화면 재현", `  ${url}`);

  return lines.join("\n");
}

export function CriteriaActions({
  title,
  items,
  summary,
}: {
  title: string;
  items: CriteriaItem[];
  summary: string;
}) {
  const [status, setStatus] = useState("");
  const still = useReducedMotion();

  const say = useCallback((msg: string) => {
    setStatus(msg);
    window.setTimeout(() => setStatus(""), 2400);
  }, []);

  const btn =
    "rounded border px-2.5 py-1 text-xs text-[var(--ink-secondary)] transition-colors " +
    "hover:text-[var(--ink)] focus-visible:outline focus-visible:outline-2 " +
    "focus-visible:outline-offset-2 focus-visible:outline-[var(--series)]";
  const btnStyle = { borderColor: "var(--hairline)", background: "var(--plane)" };

  const changedCount = items.filter((i) => i.changed).length;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-3" style={{ borderColor: "var(--hairline)" }}>
      <button
        type="button"
        className={btn}
        style={btnStyle}
        onClick={async () => {
          const ok = await copy(proposalText(title, items, summary));
          say(ok ? "제안 내용 복사됨" : "복사 실패. 주소창의 값을 직접 전달");
        }}
      >
        이 기준으로 제안
      </button>
      <button
        type="button"
        className={btn}
        style={btnStyle}
        onClick={async () => {
          const url = currentUrl();
          const ok = url ? await copy(url) : false;
          say(ok ? "링크 복사됨" : "복사 실패. 주소창을 직접 복사");
        }}
      >
        링크 복사
      </button>
      {/* 조정 여부는 장식이 아니라 정보 — muted는 라이트에서 AA 미달(4.01)이라 쓰지 않는다 */}
      <span className="text-xs text-[var(--ink-secondary)]">
        {changedCount > 0 ? `기본값에서 ${changedCount}개 조정됨` : "기본 기준"}
      </span>
      {/* 복사는 화면에 아무 흔적을 남기지 않는 동작이라, 이 한 줄이 유일한 결과다.
          그래서 **도착했다는 사실**만 모션이 말한다(DESIGN §7.7) — 즉시 갈아 끼우면
          같은 자리에 이미 있던 문구가 바뀐 것인지 새로 뜬 것인지 구별되지 않는다.
          `role="status"`는 바깥에 고정한다: 안쪽이 교체돼도 낭독 대상은 이 자리다. */}
      <span role="status" aria-live="polite" className="text-xs text-[var(--good)]">
        <AnimatePresence initial={false} mode="wait">
          {status && (
            <motion.span
              key={status}
              initial={still ? false : { opacity: 0, y: 2 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: still ? 0 : 0.15, ease: "easeOut" }}
              className="inline-block"
            >
              {status}
            </motion.span>
          )}
        </AnimatePresence>
      </span>
    </div>
  );
}
