/**
 * Design tokens. To rebrand in five minutes:
 * 1. Change `brand` below (and the matching RGB triplets in tokens.css).
 * 2. Replace assets/logo.svg and frontend/public/favicon.svg (+ run scripts/make_icons.py).
 * Chart colours are a colour-blind-safe categorical palette, validated for light and dark surfaces.
 */
export const brand = {
  name: "iBBIBBI",
  product: "Insight Hub",
  primary: "#2E5E5A", // deep sage teal: calm, dignified
  accent: "#C0683F", // warm terracotta
};

export const radii = { sm: 10, md: 14, lg: 20, xl: 28 };
export const spacing = { gutter: 16, section: 28 };
export const type = { display: "'Fraunces Variable', Georgia, serif", sans: "'Inter Variable', system-ui, sans-serif" };

/** Categorical slots in fixed order. Never cycle; fold extra series into "Other". */
export const chartLight = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const chartDark = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"];
/** Sequential (one hue, light to dark) for heatmaps. */
export const sequential = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
/** Sentiment uses icon + label as well as colour. */
export const sentiment = {
  light: { positive: "#1baf7a", neutral: "#a8a29e", negative: "#eb6834" },
  dark: { positive: "#199e70", neutral: "#78716c", negative: "#d95926" },
};

export function isDark() {
  const t = document.documentElement.dataset.theme;
  if (t === "dark") return true;
  if (t === "light") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function cssVar(name: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  return v.includes(" ") ? `rgb(${v.split(" ").join(",")})` : v;
}
