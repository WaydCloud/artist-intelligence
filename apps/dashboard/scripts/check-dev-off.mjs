// Guard: `next build` while `next dev` is running overwrites .next and corrupts the
// dev server ("Cannot find module './NNN.js'"). Abort the build if :3000 is listening.
// Override (e.g. dev running on another port on purpose): AI_ALLOW_BUILD=1 npm run build
import { connect } from "node:net";

const port = Number(process.env.PORT || 3000);
if (process.env.AI_ALLOW_BUILD === "1") process.exit(0);

const sock = connect({ port, host: "127.0.0.1" });
const done = (listening) => {
  sock.destroy();
  if (listening) {
    console.error(
      `[check-dev-off] port ${port} is in use — dev server가 켜진 채 build 금지 ` +
        `(.next 덮어쓰기 → dev 크래시). dev를 끄거나 AI_ALLOW_BUILD=1로 우회하세요.`,
    );
    process.exit(1);
  }
  process.exit(0);
};
sock.once("connect", () => done(true));
sock.once("error", () => done(false));
sock.setTimeout(1500, () => done(false));
