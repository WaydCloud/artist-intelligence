// Guard: `next build` while `next dev` is running overwrites .next and corrupts the
// dev server ("Cannot find module './NNN.js'"). Abort the build if a dev port is listening.
//
// 이 프로젝트의 dev는 3000(next 기본) 또는 3100(대체 포트, HANDOFF 실행 메모)에서 뜬다.
// 포트를 하나만 보면 실제로 도는 쪽을 놓친다 — 3000만 검사하던 판이 3100의 dev를
// 통과시켜 build가 .next를 덮어쓸 뻔했다. 그래서 목록으로 본다.
//
// 목록 변경: AI_DEV_PORTS=3000,3100 npm run build
// 우회(다른 프로젝트가 그 포트를 쓰는 경우 등): AI_ALLOW_BUILD=1 npm run build
import { connect } from "node:net";

if (process.env.AI_ALLOW_BUILD === "1") process.exit(0);

const ports = (process.env.AI_DEV_PORTS ?? process.env.PORT ?? "3000,3100")
  .split(",")
  .map((s) => Number(s.trim()))
  .filter((n) => Number.isInteger(n) && n > 0);

const probe = (port) =>
  new Promise((resolve) => {
    const sock = connect({ port, host: "127.0.0.1" });
    const done = (isListening) => {
      sock.destroy();
      resolve(isListening ? port : null);
    };
    sock.once("connect", () => done(true));
    sock.once("error", () => done(false));
    sock.setTimeout(1500, () => done(false));
  });

const busy = (await Promise.all(ports.map(probe))).filter((p) => p !== null);

if (busy.length > 0) {
  console.error(
    `[check-dev-off] port ${busy.join(", ")} 사용 중 — dev 서버가 켜진 채 build 금지 ` +
      `(.next 덮어쓰기 → dev 크래시). dev를 끄거나 AI_ALLOW_BUILD=1로 우회하세요.`,
  );
  process.exit(1);
}
process.exit(0);
