// Sequential violet ramp (palette v2, 단조 명도) for heatmap rank encoding.
// rank 1 (best) = strongest; higher rank recedes toward the surface. Theme-aware:
// dark mode uses steps chosen for the dark surface.
const SEQ_LIGHT = ["#2e1065", "#4c1d95", "#6d28d9", "#8b5cf6", "#a78bfa", "#ddd6fe"];
const SEQ_DARK = ["#c4b5fd", "#a78bfa", "#8b5cf6", "#6d28d9", "#5b21b6", "#3c1a78"];

// 시퀀셜 램프 위의 한 점. t=0 이 가장 진한 끝(강함), t=1 이 가장 옅은 끝이다.
// 순위든 값이든 **어느 끝이 강한가를 부르는 쪽이 정하고** 여기에는 t만 넘긴다.
export function seqColor(t: number, dark: boolean): string {
  const ramp = dark ? SEQ_DARK : SEQ_LIGHT;
  const u = Math.min(1, Math.max(0, t));
  return ramp[Math.round(u * (ramp.length - 1))];
}

export function rankColor(rank: number, maxRank: number, dark: boolean): string {
  if (maxRank <= 1) return seqColor(0, dark);
  return seqColor((rank - 1) / (maxRank - 1), dark);
}

// Contrast-safe ink for text on a given fill (WCAG relative luminance).
export function textOn(hex: string): string {
  const h = hex.replace("#", "");
  const ch = (i: number) => parseInt(h.slice(i, i + 2), 16) / 255;
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const L = 0.2126 * lin(ch(0)) + 0.7152 * lin(ch(2)) + 0.0722 * lin(ch(4));
  return L > 0.45 ? "#101014" : "#ffffff";
}
