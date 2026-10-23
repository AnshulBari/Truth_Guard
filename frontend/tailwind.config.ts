import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f4f1e9",
        surface: "#fbfaf6",
        ink: "#1c1a16",
        muted: "#726d61",
        line: "#ddd7c8",
        accent: "#2f5d50",
        "accent-soft": "#e7eee9",
        amber: "#8a4f12",
        "amber-soft": "#f7ecd9",
        danger: "#8c2f2f",
        "danger-soft": "#f8e9e6",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        display: [
          "Iowan Old Style",
          "Palatino Linotype",
          "Palatino",
          "Georgia",
          "ui-serif",
          "serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        lifted: "0 18px 45px -28px rgba(28, 26, 22, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
