import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "rgb(var(--color-cockpit-bg-rgb) / <alpha-value>)",
          canvas: "rgb(var(--color-canvas-solid-rgb) / <alpha-value>)",
          panel: "rgb(var(--color-surface-panel-rgb) / <alpha-value>)",
          raised: "rgb(var(--color-surface-raised-rgb) / <alpha-value>)",
          card: "rgb(var(--color-card-bg-rgb) / <alpha-value>)",
          cardHover: "rgb(var(--color-card-hover-rgb) / <alpha-value>)",
          pill: "rgb(var(--color-pill-bg-rgb) / <alpha-value>)",
          border: "var(--color-card-border)",
        },
        accent: {
          DEFAULT: "#3b82f6",
          soft: "#1d4ed8",
          pink: "#ff2a70",
          purple: "#9333ea",
          cyan: "#06b6d4",
        },
        status: {
          free: "#22c55e",
          low: "#84cc16",
          moderate: "#eab308",
          high: "#f97316",
          congested: "#ef4444",
          online: "#22c55e",
          offline: "#6b7280",
          emergency: "#dc2626",
        },
        text: {
          primary: "rgb(var(--color-text-primary-rgb) / <alpha-value>)",
          secondary: "rgb(var(--color-text-secondary-rgb) / <alpha-value>)",
          muted: "rgb(var(--color-text-muted-rgb) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
    },
  },
  plugins: [],
};

export default config;
