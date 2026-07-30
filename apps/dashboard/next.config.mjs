/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export → 정적 우선(D-003). 링크 하나로 즉시·항상 동작, 라이브 백엔드 불필요.
  output: "export",
  images: { unoptimized: true },
  // 리포트는 빌드타임에 modules/*/output/report.json → data/reports.json 으로 수집(collect-reports.mjs).
  //
  // ⚠ `distDir`를 갈아 끼워 dev를 켜 둔 채 build를 돌리는 우회는 **동작하지 않는다**
  // (2026-07-30 실측: `AI_DIST_DIR=.next-verify`로 빌드했는데도 `.next`가 프로덕션
  // 산출물로 덮여 dev가 하이드레이션 없는 HTML을 내보냈다 — 화면은 그려지는데 아무것도
  // 눌리지 않는 상태라 알아채기까지 오래 걸린다). **build 전에 dev를 끈다**(check-dev-off).
};

export default nextConfig;
