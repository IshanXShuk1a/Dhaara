import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: "rgb(var(--background-rgb) / <alpha-value>)",
          secondary: "rgb(var(--background-secondary-rgb) / <alpha-value>)",
        },
        surface: {
          DEFAULT: "rgb(var(--surface-rgb) / <alpha-value>)",
          canvas: "rgb(var(--background-rgb) / <alpha-value>)",
          panel: "rgb(var(--background-secondary-rgb) / <alpha-value>)",
          raised: "rgb(var(--surface-rgb) / <alpha-value>)",
          elevated: "rgb(var(--surface-elevated-rgb) / <alpha-value>)",
          card: "rgb(var(--surface-rgb) / <alpha-value>)",
          cardHover: "rgb(var(--surface-elevated-rgb) / <alpha-value>)",
          pill: "rgb(var(--surface-elevated-rgb) / <alpha-value>)",
          border: "var(--border)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent-rgb) / <alpha-value>)",
          soft: "rgb(var(--accent-rgb) / 0.15)",
          hover: "#40e6be",
          pink: "rgb(var(--danger-rgb) / <alpha-value>)",
          purple: "rgb(var(--info-rgb) / <alpha-value>)",
          cyan: "rgb(var(--accent-rgb) / <alpha-value>)",
        },
        status: {
          free: "rgb(var(--success-rgb) / <alpha-value>)",
          low: "rgb(var(--success-rgb) / <alpha-value>)",
          moderate: "rgb(var(--warning-rgb) / <alpha-value>)",
          high: "rgb(var(--warning-rgb) / <alpha-value>)",
          congested: "rgb(var(--danger-rgb) / <alpha-value>)",
          online: "rgb(var(--success-rgb) / <alpha-value>)",
          offline: "rgb(var(--text-muted-rgb) / <alpha-value>)",
          emergency: "rgb(var(--danger-rgb) / <alpha-value>)",
          info: "rgb(var(--info-rgb) / <alpha-value>)",
        },
        text: {
          primary: "rgb(var(--text-primary-rgb) / <alpha-value>)",
          secondary: "rgb(var(--text-secondary-rgb) / <alpha-value>)",
          muted: "rgb(var(--text-muted-rgb) / <alpha-value>)",
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
