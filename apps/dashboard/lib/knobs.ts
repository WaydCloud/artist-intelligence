"use client";

// 기준 값을 주소창에 실어 "내가 본 기준"을 링크 하나로 재현한다.
// 정적 우선(ARCHITECTURE): 서버도 저장소도 없이 URL이 상태를 갖는다.
// 값=도메인 소유자(AGENTS §2.1) 원칙의 마지막 한 칸 — 노출·반박에 이어 전달까지.

import { useCallback, useEffect, useState } from "react";

const PREFIX = "k.";

export function paramName(scope: string, key: string): string {
  return `${PREFIX}${scope}.${key}`;
}

/**
 * 한 리포트에 같은 view의 튜너가 둘 이상 있을 수 있으므로(chart-history 실측: 2개)
 * 제목으로 스코프를 가른다. 순서가 아니라 제목에 묶여야 링크가 오래 간다.
 */
export function scopeOf(view: string, title?: string): string {
  if (!title) return view;
  let h = 5381;
  for (let i = 0; i < title.length; i++) h = ((h << 5) + h + title.charCodeAt(i)) >>> 0;
  return `${view}${h.toString(36)}`;
}

/** 주소창의 기준 값. window가 없는 렌더(SSR·프리렌더)에서는 null. */
export function readKnob(scope: string, key: string): number | null {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get(paramName(scope, key));
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

/** 기본값이면 주소에서 지운다 — 링크에 남는 건 실제로 바꾼 기준뿐. */
export function writeKnob(scope: string, key: string, value: number, isDefault: boolean): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (isDefault) url.searchParams.delete(paramName(scope, key));
  else url.searchParams.set(paramName(scope, key), String(value));
  window.history.replaceState(null, "", url);
}

export function currentUrl(): string {
  return typeof window === "undefined" ? "" : window.location.href;
}

/**
 * 기준 노브 하나의 상태. 초기값은 기본값으로 렌더하고(하이드레이션 일치),
 * 마운트 뒤 주소창 값이 있으면 그걸로 덮는다.
 */
export function useKnob(
  scope: string,
  key: string,
  def: number,
): [number, (v: number) => void] {
  const [value, setValue] = useState<number>(def);

  useEffect(() => {
    const fromUrl = readKnob(scope, key);
    if (fromUrl != null) setValue(fromUrl);
  }, [scope, key]);

  const set = useCallback(
    (v: number) => {
      setValue(v);
      writeKnob(scope, key, v, v === def);
    },
    [scope, key, def],
  );

  return [value, set];
}
