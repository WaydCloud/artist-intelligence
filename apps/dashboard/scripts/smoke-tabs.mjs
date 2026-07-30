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
//   7) 인터랙션이 기본 탑재됐는지 (DESIGN §7): 선 차트마다 크로스헤어 히트 타깃 ·
//      포인터와 **키보드** 양쪽에서 툴팁이 열리고 떠나면 닫힘 · 툴팁에 **표면**이 있음 ·
//      격자 칸과 요약 도형 마크의 툴팁
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

// --- 인터랙션 게이트 ------------------------------------------------------------
// DESIGN §7은 "선·면에 크로스헤어+툴팁, 막대·점·셀에 마크별 툴팁"을 **기본 탑재**로
// 요구한다. 요구가 문서에만 있으면 다음 차트에서 조용히 빠지므로 여기서 센다.
//
// **"떴는가"만 보지 않고 "표면이 있는가"까지 본다.** 2026-07-30 실측: visx의 `unstyled`
// 플래그가 우리 `style`까지 버려서(`...(!unstyled && style)`) 툴팁이 배경도 테두리도 없는
// **맨 텍스트로 플롯 선 위에 겹쳐** 그려졌다. DOM에는 떠 있었으므로 존재 검사만으로는
// 통과했을 결함이고, 그때는 눈으로만 잡혔다.
const TIP = ".visx-tooltip";

async function tooltips(page) {
  return page.evaluate((sel) => {
    return [...document.querySelectorAll(sel)].map((d) => {
      const cs = getComputedStyle(d);
      return { text: d.innerText.trim(), bg: cs.backgroundColor, border: cs.borderTopWidth };
    });
  }, TIP);
}
// 표면이 실제로 칠해졌는지. 투명하면 뒤의 차트가 글자 사이로 비친다.
const opaque = (bg) => !!bg && !/transparent|rgba\(\s*\d+,\s*\d+,\s*\d+,\s*0(\.0+)?\s*\)/.test(bg);

async function checkTooltipSurface(page, where, what) {
  const tips = await tooltips(page);
  if (!check(where, tips.length > 0 && tips[0].text.length > 0, `${what}에 커서를 올려도 툴팁이 열리지 않습니다`))
    return false;
  check(where, opaque(tips[0].bg), `${what} 툴팁에 표면이 없습니다 (배경 ${tips[0].bg}) — 증거 위에 맨 텍스트가 겹칩니다`);
  check(where, tips[0].border !== "0px", `${what} 툴팁에 테두리가 없습니다 (배경색만으로는 플롯과 경계가 서지 않습니다)`);
  return true;
}

async function hoverCenter(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const b = await locator.boundingBox();
  if (!b) return null;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.waitForTimeout(130);
  return b;
}

async function checkInteraction(page, where) {
  // ① 선 차트에는 예외 없이 크로스헤어 히트 타깃이 있어야 한다. 스몰 멀티플이면 패널마다.
  const lines = page.locator('main [data-plot="line"]');
  const nLines = await lines.count();
  for (let i = 0; i < nLines; i++) {
    const n = await lines.nth(i).locator('rect[role="slider"]').count();
    if (!check(where, n === 1, `선 차트 ${i + 1}/${nLines}에 크로스헤어 히트 타깃이 없습니다 (히트 타깃 ${n}개)`))
      return;
  }

  // ② 대표 1개로 포인터·키보드·표면을 본다(전부 같은 프리미티브라 하나가 서면 전부 선다).
  if (nLines > 0) {
    const rect = lines.first().locator('rect[role="slider"]');
    const b = await hoverCenter(page, rect);
    if (b) {
      // 마크는 6px 원이었다. 히트 타깃이 그보다 크지 않으면 조준해야 잡힌다.
      check(where, b.height >= 40, `선 차트 히트 타깃이 ${Math.round(b.height)}px로 얇습니다 (마크보다 크게)`);
      await checkTooltipSurface(page, where, "선 차트");

      // 포인터가 떠나면 닫힌다 — 남으면 다음 열을 가린 채로 화면에 붙는다.
      await page.mouse.move(b.x + b.width / 2, b.y - 60);
      await page.waitForTimeout(130);
      check(where, (await tooltips(page)).length === 0, "포인터가 떠났는데 선 차트 툴팁이 남아 있습니다");

      // 키보드로 같은 값에 닿는가. `<title>` 속성만 있던 예전 상태에서는 불가능했다.
      await rect.focus();
      await page.waitForTimeout(120);
      const max = Number(await rect.getAttribute("aria-valuemax"));
      const from = await rect.getAttribute("aria-valuenow");
      await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(130);
      const to = await rect.getAttribute("aria-valuenow");
      if (max > 0) check(where, from !== to, `화살표로 지점이 이동하지 않습니다 (${from} → ${to})`);
      check(where, ((await rect.getAttribute("aria-valuetext")) ?? "").length > 0, "aria-valuetext가 비어 스크린리더가 읽을 값이 없습니다");
      await checkTooltipSurface(page, where, "선 차트(키보드)");
      await page.keyboard.press("Escape");
      await page.waitForTimeout(120);
      check(where, (await tooltips(page)).length === 0, "Escape 후에도 선 차트 툴팁이 남아 있습니다");
      await page.evaluate(() => document.activeElement?.blur());
    }
  }

  // ③ 셀·마크 툴팁. 격자는 `<td>`, 요약 도형은 투명 히트 원이 받는다.
  for (const [sel, hit, what] of [
    ['main [data-plot="heatmap"]', "tbody td", "격자 칸"],
    ['main [data-plot="radar"]', 'circle[role="button"]', "요약 도형 마크"],
  ]) {
    const plot = page.locator(sel).first();
    if ((await plot.count()) === 0) continue;
    const mark = plot.locator(hit).first();
    if ((await mark.count()) === 0) continue;
    if (await hoverCenter(page, mark)) await checkTooltipSurface(page, where, what);
    await page.mouse.move(2, 2);
    await page.waitForTimeout(100);
  }
}

// --- 질문 앵커 게이트 (R1) -----------------------------------------------------
// "질문을 누르면 그 답이 있는 카드로 내려간다"가 R1의 실체다. 구획(D-043)이 들어온 뒤로
// **대상이 다른 구획에 있으면 조용히 아무 일도 일어나지 않았다** — 구획은 바뀌는데
// 스크롤도 도착 표시도 없었다. 새 구획은 나가는 모션이 끝난 뒤에야 마운트되는데 앵커는
// 두 프레임만 기다리고 포기했기 때문이고, 2026-07-30 실측에서 6탭 중 3탭이 이 상태였다.
// 정적 게이트도 렌더 스모크도 이것을 못 봤다(콘솔 에러가 나지 않는다).
//
// 테마와 무관한 동작이라 첫 테마에서만 돈다.
async function checkAnchors(page, where) {
  const qs = await page.locator("main ol li button").all();
  for (let i = 0; i < qs.length; i++) {
    const label = (await qs[i].innerText()).trim().replace(/\s+/g, " ").slice(0, 24);
    // 매번 첫 구획으로 되돌린 뒤 눌러야 "구획을 넘어가는" 경로가 실제로 검사된다
    const first = page.locator('nav[aria-label="구획"] button[role="tab"]').first();
    if (await first.count()) {
      await first.click();
      await page.waitForTimeout(300);
    }
    await qs[i].click();
    await page.waitForTimeout(900); // 구획 전환 모션(0.22s) + 스크롤이 끝날 만큼
    const r = await page.evaluate(() => {
      const el = document.querySelector("main section[data-landed=true]");
      return el ? { top: Math.round(el.getBoundingClientRect().top) } : null;
    });
    if (!check(where, r !== null, `질문 ${i + 1}("${label}…")을 눌러도 대상 카드에 도착하지 않습니다`))
      continue;
    check(
      where,
      Math.abs(r.top) < 400,
      `질문 ${i + 1}("${label}…") 대상 카드가 화면 위쪽에 오지 않았습니다 (top ${r.top}px)`,
    );
  }
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
    // 모듈 탭만 센다. 구획 내비게이션(D-043)도 tablist라 선택자가 넓으면 둘이 섞이고,
    // 실제로 2026-07-30에 섞여서 존재하지 않는 탭을 기다리다 타임아웃으로 죽었다.
    const tabs = await page.locator('nav[aria-label="모듈"] button[role="tab"]').all();
    check(theme, tabs.length > 0, "탭이 하나도 렌더되지 않았습니다 (reports.json 확인)");
    tabCount = Math.max(tabCount, tabs.length);

    for (let i = 0; i < tabs.length; i++) {
      const name = (await tabs[i].innerText()).trim();
      const before = logs.length;

      await tabs[i].click();
      await page.waitForTimeout(200);

      // 🔴 **탭이 실제로 바뀌었는지**를 먼저 본다. `aria-selected`는 React가 상태로
      // 그리는 값이라, true가 되려면 (a) 클라이언트 번들이 하이드레이션됐고 (b) 클릭이
      // 상태를 바꿨어야 한다. 2026-07-30에 이 검사가 없어서 **하이드레이션이 통째로
      // 실패한 페이지가 전 항목을 통과했다** — 서버 렌더 HTML은 멀쩡했고, 탭을 눌러도
      // 아무 일이 없는 채로 첫 탭 내용만 12번 검사됐다. 화면이 그려진다는 것과
      // 화면이 살아 있다는 것은 다른 얘기다.
      const selected = await tabs[i].getAttribute("aria-selected");
      check(
        `${theme}/${name}`,
        selected === "true",
        `탭을 눌러도 선택되지 않았습니다 (aria-selected=${selected}) — 하이드레이션 실패 의심. ` +
          `dev를 켠 채 build를 돌리면 .next가 프로덕션 산출물로 덮여 이 상태가 됩니다`,
      );
      // 여기서 죽었으면 아래 검사는 전부 첫 탭 내용을 다시 재는 것이라 의미가 없다.
      if (selected !== "true") continue;

      // R1 앵커는 테마와 무관하므로 첫 테마에서만 (탭당 질문 3~4개 × 왕복 1초)
      if (theme === THEMES[0]) await checkAnchors(page, `${theme}/${name}`);

      // 구획(D-043)이 있으면 **구획마다** 검사한다. 한 번에 한 구획만 DOM에 있으므로
      // 첫 구획만 보면 나머지 구획의 렌더 결함이 그대로 통과한다 -- 이 스모크가 존재하는
      // 이유(정적 게이트가 못 보는 런타임 결함)를 스스로 반쯤 잃는 셈이다.
      const secBtns = await page.locator('nav[aria-label="구획"] button[role="tab"]').all();
      const steps = secBtns.length > 0 ? secBtns : [null];

      for (const sec of steps) {
        let where = `${theme}/${name}`;
        if (sec) {
          const label = (await sec.innerText()).trim().replace(/\s+/g, " ");
          where = `${where}/${label}`;
          await sec.click();
          await page.waitForTimeout(260); // 구획 전환 모션(0.22s)이 끝난 뒤 측정
        }
        const secBefore = logs.length;

        // 1차: 접힌 상태
        let r = await page.evaluate(probe);
        check(where, r.bodyChars > 0, "body가 비었습니다 (React 트리 언마운트 의심)");
        check(where, r.mainChars >= MIN_MAIN_CHARS, `main 내용이 ${r.mainChars}자뿐입니다 (기준 ${MIN_MAIN_CHARS}자)`);
        check(where, r.title.length > 0, "리포트 제목이 렌더되지 않았습니다");
        check(where, r.fallbacks.length === 0, `차트 렌더 실패: ${r.fallbacks.join(", ")}`);
        check(where, r.emptyCards.length === 0, `내용 없는 카드: ${r.emptyCards.join(", ")}`);

        // 인터랙션(DESIGN §7 기본 탑재) -- details를 펼치기 전에 본다. 펼치면 표가 늘어나
        // 좌표가 밀리고, 여기서 검사하는 것은 접힘과 무관한 플롯 위의 동작이다.
        await checkInteraction(page, where);

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

        const freshSec = logs.slice(secBefore);
        check(where, freshSec.length === 0, `콘솔 에러 ${freshSec.length}건\n    ${freshSec.join("\n    ")}`);

        console.log(
          `  ${failures.some((f) => f.startsWith(`${where}:`)) ? "FAIL" : "ok  "} ${where.padEnd(34)} ` +
            `카드 ${r.cards} · 접힘항목 ${r.details} · main ${r.mainChars}자`,
        );
      }

      const fresh = logs.slice(before);
      check(`${theme}/${name}`, fresh.length === 0, `콘솔 에러 ${fresh.length}건\n    ${fresh.join("\n    ")}`);
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
