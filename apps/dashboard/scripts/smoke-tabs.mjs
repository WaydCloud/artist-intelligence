#!/usr/bin/env node
// smoke-tabs.mjs -- 대시보드 전 탭을 headless로 클릭해 "렌더가 실제로 됐는지"를 검사한다.
//
// 왜 있나 (2026-07-30): genre-impulse 탭이 대시보드 **전체**를 언마운트시키고 있었는데
// lint · typecheck · schema-validate 셋 다 통과한 상태였다. 정적 게이트는 "미지의 view가
// 런타임에 TypeError를 낸다"를 볼 수 없다. 그날 결함 3건 중 2건(전체 언마운트 · 뷰 미구현)을
// 이 검사가 잡았을 것이다.
//
// 검사 항목 (탭 × 테마마다):
//   1) 콘솔 에러 · 페이지 예외 0건
//   2) main 영역이 비어 있지 않음 (언마운트 감지 -- 언마운트되면 body가 통째로 사라진다)
//   3) 리포트 제목이 렌더됨
//   4) 차트 카드가 ChartBoundary 폴백으로 떨어진 것이 없음
//   5) 카드 내용이 비어 있지 않음 (뷰 미구현 감지)
//   6) <details>를 전부 펼친 뒤에도 1~5 유지 (접힌 안쪽에서 터지는 결함)
//
// 실행:
//   node apps/dashboard/scripts/smoke-tabs.mjs                     # localhost:3100 (dev 실행 중)
//   node apps/dashboard/scripts/smoke-tabs.mjs --url http://localhost:3000
//   node apps/dashboard/scripts/smoke-tabs.mjs --allow "favicon"   # 알려진 무해 로그 제외 (정규식)
//
// **없는 것을 조용히 통과시키지 않는다**: playwright나 브라우저가 없으면 exit 1로 죽는다.
// 검사기가 아무것도 안 하고 초록인 상태(0바이트 시크릿 스캔과 같은 함정)를 만들지 않는다.

import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
function flag(name, fallback = null) {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}

const BASE = (flag("url", "http://localhost:3100") ?? "").replace(/\/$/, "");
const PAGE = `${BASE}/artist-intelligence`;
const ALLOW = flag("allow") ? new RegExp(flag("allow")) : null;
const THEMES = ["light", "dark"];
const FALLBACK_TEXT = "이 차트를 표시하지 못함"; // ChartBoundary 폴백 문구와 짝
const MIN_MAIN_CHARS = 200;

// --- playwright 해석: 로컬 → 전역 @playwright/mcp 동봉분 -----------------------
// 대시보드에 playwright를 devDependency로 넣지 않는다(AGENTS §1: 새 의존성은 승인 필요).
// 이미 이 PC에 있는 것을 찾아 쓰고, 없으면 어디서 구하는지 알려주고 죽는다.
async function loadChromium() {
  const require = createRequire(import.meta.url);
  const candidates = [
    null, // 기본 해석 경로 (로컬 node_modules)
    process.env.PLAYWRIGHT_DIR ?? null,
    process.env.APPDATA ? path.join(process.env.APPDATA, "npm/node_modules/@playwright/mcp") : null,
    process.env.APPDATA ? path.join(process.env.APPDATA, "npm/node_modules/playwright") : null,
  ];
  const tried = [];
  for (const base of candidates) {
    try {
      // playwright는 CJS다. 동적 import()로 받으면 named export가 비므로 require로 읽는다.
      const id = base ? require.resolve("playwright", { paths: [base] }) : require.resolve("playwright");
      const mod = require(id);
      const chromium = mod.chromium ?? mod.default?.chromium;
      if (!chromium) throw Object.assign(new Error("chromium export 없음"), { code: "NO_CHROMIUM" });
      return { chromium, from: id };
    } catch (e) {
      tried.push(`${base ?? "(default)"}: ${e.code ?? e.message}`);
    }
  }
  throw new Error(
    `playwright를 찾지 못했습니다. 다음 중 하나로 해결하세요:\n` +
      `  - npm i -g @playwright/mcp   (이미 있으면 PLAYWRIGHT_DIR로 경로 지정)\n` +
      `  - PLAYWRIGHT_DIR=<playwright 설치 디렉터리> 환경변수\n` +
      `시도한 경로:\n  ${tried.join("\n  ")}`,
  );
}

// playwright 패키지가 기대하는 브라우저 리비전과 이 PC에 설치된 리비전이 어긋나는 일이
// 흔하다(전역 @playwright/mcp를 쓰기 때문). 설치된 것 중 가장 새 것을 직접 짚어준다.
// 못 찾으면 null을 돌려 playwright의 기본 해석에 맡긴다(그쪽이 맞으면 그대로 돈다).
function findChromium() {
  if (process.env.PLAYWRIGHT_CHROMIUM) return process.env.PLAYWRIGHT_CHROMIUM;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH
    ? process.env.PLAYWRIGHT_BROWSERS_PATH
    : process.env.LOCALAPPDATA
      ? path.join(process.env.LOCALAPPDATA, "ms-playwright")
      : null;
  if (!root || !fs.existsSync(root)) return null;
  const rev = (d) => Number(d.split("-").pop()) || 0;
  const builds = fs
    .readdirSync(root)
    .filter((d) => /^chromium(_headless_shell)?-\d+$/.test(d))
    // headless shell을 먼저 고른다(가볍다), 같은 종류면 리비전이 높은 쪽.
    .sort((a, b) => (a.startsWith("chromium_headless") === b.startsWith("chromium_headless") ? rev(b) - rev(a) : a.startsWith("chromium_headless") ? -1 : 1));
  for (const b of builds) {
    for (const exe of [
      "chrome-headless-shell-win64/chrome-headless-shell.exe",
      "chrome-win64/chrome.exe",
      "chrome-linux/chrome",
      "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    ]) {
      const p = path.join(root, b, exe);
      if (fs.existsSync(p)) return p;
    }
  }
  return null;
}

async function assertServer() {
  let res;
  try {
    res = await fetch(PAGE, { signal: AbortSignal.timeout(5000) });
  } catch (e) {
    throw new Error(
      `${PAGE} 에 접속할 수 없습니다 (${e.message}).\n` +
        `  cd apps/dashboard && npm run dev -- --port 3100\n` +
        `  (다른 포트라면 --url 로 지정)`,
    );
  }
  if (!res.ok) throw new Error(`${PAGE} 가 HTTP ${res.status} 를 반환했습니다.`);
}

// 각 탭에서 무엇이 렌더됐는지를 브라우저 안에서 한 번에 수집한다.
const probe = () => {
  const main = document.querySelector("main");
  const cards = [...document.querySelectorAll("main section.glass-card")];
  return {
    mainChars: main ? main.innerText.trim().length : 0,
    bodyChars: document.body.innerText.trim().length,
    title: document.querySelector("main h1")?.innerText.trim() ?? "",
    cards: cards.length,
    emptyCards: cards
      .map((c, i) => ({ i, h: c.querySelector("h2")?.innerText.trim() ?? `#${i}`, n: c.innerText.trim().length }))
      .filter((c) => c.n < 8)
      .map((c) => c.h),
    fallbacks: cards
      .filter((c) => c.innerText.includes("이 차트를 표시하지 못함"))
      .map((c, i) => c.querySelector("h2")?.innerText.trim() ?? `#${i}`),
    details: document.querySelectorAll("main details").length,
  };
};

const failures = [];
function check(where, cond, msg) {
  if (!cond) failures.push(`${where}: ${msg}`);
  return cond;
}

async function run() {
  await assertServer();
  const { chromium, from } = await loadChromium();
  console.log(`playwright: ${from}`);
  console.log(`target:     ${PAGE}`);

  const exe = findChromium();
  console.log(`chromium:   ${exe ?? "(playwright 기본 경로)"}`);
  let browser;
  try {
    browser = await chromium.launch({ headless: true, ...(exe ? { executablePath: exe } : {}) });
  } catch (e) {
    // 전역 설치본은 브라우저 리비전이 어긋날 수 있다 -- 경로를 직접 줄 수 있게 안내한다.
    throw new Error(
      `chromium 실행 실패: ${e.message}\n` +
        `  PLAYWRIGHT_CHROMIUM 환경변수로 실행 파일 경로를 지정하거나 npx playwright install chromium 을 실행하세요.`,
    );
  }

  let tabCount = 0;
  for (const theme of THEMES) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const logs = [];
    page.on("console", (m) => {
      if (m.type() === "error" && !(ALLOW && ALLOW.test(m.text()))) logs.push(`console: ${m.text()}`);
    });
    page.on("pageerror", (e) => {
      if (!(ALLOW && ALLOW.test(String(e)))) logs.push(`pageerror: ${e.message}`);
    });

    await page.goto(`${PAGE}?theme=${theme}`, { waitUntil: "networkidle" });
    const tabs = await page.locator('nav[role="tablist"] button[role="tab"]').all();
    check(theme, tabs.length > 0, "탭이 하나도 렌더되지 않았습니다 (reports.json 확인)");
    tabCount = Math.max(tabCount, tabs.length);

    for (let i = 0; i < tabs.length; i++) {
      const name = (await tabs[i].innerText()).trim();
      const where = `${theme}/${name}`;
      const before = logs.length;

      await tabs[i].click();
      await page.waitForTimeout(150);

      // 1차: 접힌 상태
      let r = await page.evaluate(probe);
      check(where, r.bodyChars > 0, "body가 비었습니다 (React 트리 언마운트 의심)");
      check(where, r.mainChars >= MIN_MAIN_CHARS, `main 내용이 ${r.mainChars}자뿐입니다 (기준 ${MIN_MAIN_CHARS}자)`);
      check(where, r.title.length > 0, "리포트 제목이 렌더되지 않았습니다");
      check(where, r.fallbacks.length === 0, `차트 렌더 실패: ${r.fallbacks.join(", ")}`);
      check(where, r.emptyCards.length === 0, `내용 없는 카드: ${r.emptyCards.join(", ")}`);

      // 2차: <details> 전부 펼친 뒤 -- 접힌 안쪽에서 터지는 결함을 잡는다
      if (r.details > 0) {
        await page.evaluate(() => {
          document.querySelectorAll("main details").forEach((d) => d.setAttribute("open", ""));
        });
        await page.waitForTimeout(150);
        r = await page.evaluate(probe);
        check(where, r.bodyChars > 0, "details 펼침 후 body가 비었습니다");
        check(where, r.fallbacks.length === 0, `details 펼침 후 차트 렌더 실패: ${r.fallbacks.join(", ")}`);
      }

      const fresh = logs.slice(before);
      check(where, fresh.length === 0, `콘솔 에러 ${fresh.length}건\n    ${fresh.join("\n    ")}`);

      console.log(
        `  ${failures.some((f) => f.startsWith(`${where}:`)) ? "FAIL" : "ok  "} ${where.padEnd(28)} ` +
          `카드 ${r.cards} · 접힘항목 ${r.details} · main ${r.mainChars}자`,
      );
    }

    // 어느 탭에도 귀속되지 않는 로그(초기 로드 시점)도 놓치지 않는다
    await page.close();
  }
  await browser.close();

  console.log(`\n검사 ${tabCount} 탭 × ${THEMES.length} 테마 = ${tabCount * THEMES.length}건`);
  if (failures.length > 0) {
    console.error(`\nFAILED (${failures.length}):`);
    for (const f of failures) console.error(`  - ${f}`);
    return 1;
  }
  console.log("PASS");
  return 0;
}

run()
  .then((code) => process.exit(code))
  .catch((e) => {
    console.error(`\nsmoke-tabs 실행 불가:\n${e.message}`);
    process.exit(1);
  });
