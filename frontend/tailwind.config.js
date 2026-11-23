/** Colours come from CSS variables defined in src/theme/tokens.css (see src/theme/tokens.ts). */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"), surface: v("surface"), sunken: v("sunken"), line: v("line"),
        ink: v("ink"), "ink-2": v("ink-2"), "ink-3": v("ink-3"),
        primary: v("primary"), "primary-ink": v("primary-ink"), "primary-soft": v("primary-soft"),
        accent: v("accent"), "accent-soft": v("accent-soft"),
        good: v("good"), "good-soft": v("good-soft"), warn: v("warn"), "warn-soft": v("warn-soft"), care: v("care"), "care-soft": v("care-soft"),
      },
      fontFamily: { display: ["'Fraunces Variable'", "Georgia", "serif"], sans: ["'Inter Variable'", "system-ui", "sans-serif"] },
      borderRadius: { xl: "14px", "2xl": "20px", "3xl": "28px" },
      boxShadow: { card: "var(--shadow-card)", lift: "var(--shadow-lift)" },
      transitionDuration: { DEFAULT: "200ms" },
    },
  },
  plugins: [],
};
