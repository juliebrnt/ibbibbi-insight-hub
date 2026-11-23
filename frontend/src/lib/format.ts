const eur0 = new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const eur2 = new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR", maximumFractionDigits: 2, minimumFractionDigits: 2 });
const n0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const n1 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

export const fmt = {
  eur: (v?: number | null) => (v == null ? "n/a" : Math.abs(v) >= 100 ? eur0.format(v) : eur2.format(v)),
  num: (v?: number | null) => (v == null ? "n/a" : Math.abs(v) < 100 && v % 1 ? n1.format(v) : n0.format(v)),
  pct: (v?: number | null, d = 0) => (v == null ? "n/a" : `${(v * 100).toFixed(d)}%`),
  change: (v?: number | null) => (v == null ? "" : `${v > 0 ? "+" : ""}${v.toFixed(0)}%`),
  stars: (v?: number | null) => (v == null ? "n/a" : v.toFixed(1)),
  date: (s?: string | null) => (s ? new Date(s + (s.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : ""),
  short: (s?: string | null) => (s ? new Date(s + (s.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : ""),
  month: (s?: string | null) => (s ? new Date(s + "T00:00:00").toLocaleDateString("en-GB", { month: "short", year: "2-digit" }) : ""),
  unit: (v: number | null | undefined, unit: string) =>
    unit === "eur" ? fmt.eur(v) : unit === "pct" ? fmt.pct(v, 1) : unit === "stars" ? fmt.stars(v) : fmt.num(v),
};

export const LANGS: Record<string, string> = { es: "Spanish", ca: "Catalan", en: "English", fr: "French", pt: "Portuguese", unknown: "Unknown" };
