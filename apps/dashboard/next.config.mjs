/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export → 정적 우선(D-003). 링크 하나로 즉시·항상 동작, 라이브 백엔드 불필요.
  output: "export",
  images: { unoptimized: true },
  // 리포트는 빌드타임에 modules/*/output/report.json → data/reports.json 으로 수집(collect-reports.mjs).
};

export default nextConfig;
