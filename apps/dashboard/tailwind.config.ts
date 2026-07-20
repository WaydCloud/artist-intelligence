import type { Config } from "tailwindcss";

// Colors are driven by CSS custom properties (see app/globals.css) so light/dark
// swap in one place. Tailwind here carries layout, spacing, and type only.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        plane: "var(--plane)",
        ink: "var(--ink)",
        secondary: "var(--ink-secondary)",
        muted: "var(--muted)",
        hairline: "var(--hairline)",
        series: "var(--series)",
      },
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
      },
    },
  },
  plugins: [],
};

export default config;
