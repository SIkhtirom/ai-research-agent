import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./types/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "electric-indigo": "#0000ff",
        "cobalt-pulse": "#4141fc",
        "periwinkle-veil": "#8b8bfe",
        "lime-beacon": "#7fd579",
        "orchid-whisper": "#d896ff",
        "midnight-void": "#0d0d0d",
        "carbon-panel": "#161616",
        "graphite-lift": "#252525",
        "steel-hover": "#3b3b3b",
        "pure-signal": "#ffffff",
        "soft-mist": "#eaeaea",
        charcoal: "#333333",
        "warm-filament": "#b8ad97",
      },
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        caption: [
          "10px",
          { lineHeight: "1.25", letterSpacing: "-0.2px" },
        ],
        "body-lg": [
          "16px",
          { lineHeight: "1.5", letterSpacing: "-0.32px" },
        ],
        subheading: [
          "24px",
          { lineHeight: "1.15", letterSpacing: "-0.36px" },
        ],
        display: [
          "64px",
          { lineHeight: "1.1", letterSpacing: "-1.28px" },
        ],
      },
      borderRadius: {
        sm: "2px",
        pill: "1440px",
      },
    },
  },
  plugins: [],
};
export default config;