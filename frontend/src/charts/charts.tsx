import { tr } from "@/lib/i18n";
import { locale } from "@/lib/i18n";
/** Ready-made charts. Each follows the same rules: thin marks, rounded bar ends, recessive axes, tooltips, one axis. */
import { axisX, axisY, base, EChart, useChartTheme } from "./EChart";

type Row = Record<string, any>;

export function Bars({ rows, x, y, horizontal = false, height = 260, fmt = (v: number) => v?.toLocaleString(locale()), color, highlight, label }: {
  rows: Row[]; x: string; y: string; horizontal?: boolean; height?: number; fmt?: (v: number) => string; color?: string; highlight?: string; label?: string;
}) {
  const t = useChartTheme();
  const cats = rows.map((r) => tr(r[x]));
  const c = color || t.series[0];
  const data = rows.map((r) => ({
    value: r[y],
    itemStyle: { color: highlight && r[x] !== highlight ? c + "66" : c, borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
  }));
  const valAxis = axisY(t, { axisLabel: { formatter: (v: number) => fmt(v) } });
  const catAxis = axisX(t, cats, horizontal ? { inverse: true, axisLabel: { width: 130, overflow: "truncate" } } : { axisLabel: { interval: 0, rotate: cats.length > 6 ? 30 : 0, width: 90, overflow: "truncate" } });
  const opt = {
    ...base(t),
    tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p: any) => `${p.name}<br/><b>${fmt(p.value)}</b>${label ? ` ${tr(label)}` : ""}` },
    xAxis: horizontal ? valAxis : catAxis,
    yAxis: horizontal ? { ...catAxis, type: "category" } : valAxis,
    series: [{ type: "bar", data, barMaxWidth: 28, barCategoryGap: "35%",
      label: { show: rows.length <= 8, position: horizontal ? "right" : "top", color: t.ink2, fontSize: 11, formatter: (p: any) => fmt(p.value) } }],
  };
  return <EChart option={opt} height={height} />;
}

export function GroupedBars({ rows, x, series, height = 260, fmt = (v: number) => v?.toLocaleString(locale()) }: {
  rows: Row[]; x: string; series: { key: string; name: string }[]; height?: number; fmt?: (v: number) => string;
}) {
  const t = useChartTheme();
  const opt = {
    ...base(t),
    tooltip: { ...base(t).tooltip, valueFormatter: (v: number) => fmt(v) },
    legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: t.ink2, fontSize: 12 } },
    grid: { ...base(t).grid, top: 36 },
    xAxis: axisX(t, rows.map((r) => tr(r[x])), { axisLabel: { interval: 0, width: 90, overflow: "truncate" } }),
    yAxis: axisY(t, { axisLabel: { formatter: (v: number) => fmt(v) } }),
    series: series.map((s, i) => ({ type: "bar", name: tr(s.name), data: rows.map((r) => r[s.key]), barMaxWidth: 22, barGap: "10%",
      itemStyle: { color: t.series[i], borderRadius: [4, 4, 0, 0] } })),
  };
  return <EChart option={opt} height={height} />;
}

export function Lines({ x, series, height = 260, fmt = (v: number) => v?.toLocaleString(locale()), area = true, markers }: {
  x: string[]; series: { name: string; data: (number | null)[]; dashed?: boolean; colorIndex?: number }[]; height?: number;
  fmt?: (v: number) => string; area?: boolean; markers?: { at: string; label: string }[];
}) {
  const t = useChartTheme();
  const opt = {
    ...base(t),
    tooltip: { ...base(t).tooltip, valueFormatter: (v: number) => (v == null ? "n/a" : fmt(v)) },
    legend: series.length > 1 ? { top: 0, left: 0, icon: "roundRect", itemWidth: 12, itemHeight: 3, textStyle: { color: t.ink2, fontSize: 12 } } : undefined,
    grid: { ...base(t).grid, top: series.length > 1 ? 36 : 16 },
    xAxis: axisX(t, x, { boundaryGap: false }),
    yAxis: axisY(t, { axisLabel: { formatter: (v: number) => fmt(v) } }),
    series: series.map((s, i) => {
      const c = t.series[s.colorIndex ?? i];
      return {
        type: "line", name: tr(s.name), data: s.data, smooth: 0.3, showSymbol: false, symbolSize: 8,
        lineStyle: { width: 2, color: c, type: s.dashed ? "dashed" : "solid" }, itemStyle: { color: c },
        areaStyle: area && !s.dashed && i === 0 ? { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: c + "33" }, { offset: 1, color: c + "00" }] } } : undefined,
        markLine: i === 0 && markers?.length ? { symbol: "none", silent: true, lineStyle: { color: t.ink3, type: "dotted" },
          label: { color: t.ink3, fontSize: 10, formatter: (p: any) => p.name }, data: markers.map((m) => ({ xAxis: m.at, name: m.label })) } : undefined,
      };
    }),
  };
  return <EChart option={opt} height={height} />;
}

const SENT_ORDER = ["positive", "neutral", "negative"] as const;
const SENT_LABEL = { positive: "Positive", neutral: "Neutral", negative: "Negative" };

export function SentimentStream({ rows, height = 260 }: { rows: { period: string; sentiment: string; n: number }[]; height?: number }) {
  const t = useChartTheme();
  const periods = [...new Set(rows.map((r) => r.period))].sort();
  const opt = {
    ...base(t),
    legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: t.ink2, fontSize: 12 } },
    grid: { ...base(t).grid, top: 36 },
    xAxis: axisX(t, periods.map((p) => new Date(p + "T00:00:00").toLocaleDateString(locale(), { month: "short", day: periods.length < 20 ? "numeric" : undefined, year: periods.length >= 20 ? "2-digit" : undefined })), { boundaryGap: false }),
    yAxis: axisY(t),
    series: SENT_ORDER.map((s) => ({
      type: "line", name: tr(SENT_LABEL[s]), stack: "s", smooth: 0.4, showSymbol: false,
      lineStyle: { width: 1.5, color: t.surface }, itemStyle: { color: t.sentiment[s] },
      areaStyle: { color: t.sentiment[s], opacity: 0.85 },
      data: periods.map((p) => rows.find((r) => r.period === p && r.sentiment === s)?.n ?? 0),
    })),
  };
  return <EChart option={opt} height={height} />;
}

export function Sparkline({ data, height = 36, color }: { data: (number | null)[]; height?: number; color?: string }) {
  const vals = data.filter((v): v is number => v != null);
  if (vals.length < 2) return <div style={{ height }} />;
  const w = 120, h = height, min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - 3 - (((v ?? min) - min) / span) * (h - 6)}`);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full" style={{ height }} aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke={color || "rgb(var(--primary))"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function CalendarHeat({ rows, range, height = 170 }: { rows: { date: string; n: number }[]; range: [string, string]; height?: number }) {
  const t = useChartTheme();
  const opt = {
    tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p: any) => `${new Date(p.value[0] + "T00:00:00").toLocaleDateString(locale(), { weekday: "short", day: "numeric", month: "short" })}<br/><b>${p.value[1]} post${p.value[1] === 1 ? "" : "s"}</b>` },
    visualMap: { show: false, min: 0, max: 2, inRange: { color: [t.sequential[1], t.sequential[4]] } },
    calendar: {
      range, top: 22, left: 28, right: 4, cellSize: ["auto", 13], splitLine: { show: false },
      itemStyle: { color: t.dark ? "#2b2826" : "#f1ece6", borderColor: t.surface, borderWidth: 2.5 },
      dayLabel: { firstDay: 1, nameMap: ["S", "M", "T", "W", "T", "F", "S"], color: t.ink3, fontSize: 10 },
      monthLabel: { color: t.ink3, fontSize: 10, nameMap: "EN" }, yearLabel: { show: false },
    },
    series: [{ type: "heatmap", coordinateSystem: "calendar", data: rows.map((r) => [r.date, r.n]) }],
  };
  return <EChart option={opt} height={height} />;
}

export function Heatmap({ xLabels, yLabels, data, height = 300, fmt = (v: number) => `${(v * 100).toFixed(0)}%`, max }: {
  xLabels: string[]; yLabels: string[]; data: [number, number, number | null][]; height?: number; fmt?: (v: number) => string; max?: number;
}) {
  const t = useChartTheme();
  xLabels = xLabels.map(tr);
  yLabels = yLabels.map(tr);
  const vals = data.map((d) => d[2]).filter((v): v is number => v != null);
  const opt = {
    tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p: any) => `${yLabels[p.value[1]]} · ${xLabels[p.value[0]]}<br/><b>${p.value[2] == null ? "n/a" : fmt(p.value[2])}</b>` },
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: xLabels, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: t.ink3, fontSize: 11 }, splitArea: { show: false } },
    yAxis: { type: "category", data: yLabels, inverse: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: t.ink3, fontSize: 11 } },
    visualMap: { show: false, min: 0, max: max ?? (Math.max(...vals, 0.01)), inRange: { color: [t.sequential[0], t.sequential[5]] } },
    series: [{ type: "heatmap", data: data.filter((d) => d[2] != null), itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 },
      label: { show: xLabels.length <= 8, fontSize: 10, color: t.dark ? "#fff" : "#1c2b3a", formatter: (p: any) => fmt(p.value[2]) } }],
  };
  return <EChart option={opt} height={height} />;
}

export function Funnel({ steps, height = 220 }: { steps: { step: string; value: number }[]; height?: number }) {
  const max = Math.max(...steps.map((s) => s.value || 0), 1);
  return (
    <div className="space-y-3 py-2" style={{ minHeight: height / 2 }}>
      {steps.map((s, i) => (
        <div key={s.step}>
          <div className="flex justify-between text-sm"><span className="text-ink-2">{s.step}</span><span className="num font-medium">{(s.value ?? 0).toLocaleString(locale())}
            {i > 0 && steps[i - 1].value ? <span className="text-ink-3 font-normal"> · {((s.value / steps[i - 1].value) * 100).toFixed(1)}% of previous</span> : null}</span></div>
          <div className="mt-1 h-3 rounded-full bg-sunken overflow-hidden"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(1.5, (s.value / max) * 100)}%`, opacity: 1 - i * 0.2 }} /></div>
        </div>
      ))}
    </div>
  );
}

/** Horizontal share bars with labels, used for themes and comparisons (no chart library needed). */
export function ShareBars({ rows, label, value, fmt = (v: number) => `${(v * 100).toFixed(0)}%`, max, extra, colorFor }: {
  rows: Row[]; label: string; value: string; fmt?: (v: number) => string; max?: number; extra?: (r: Row) => React.ReactNode; colorFor?: (r: Row) => string;
}) {
  const m = max ?? Math.max(...rows.map((r) => r[value] || 0), 0.0001);
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={i}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-ink truncate">{r[label]}</span>
            <span className="num text-ink-2 shrink-0">{fmt(r[value])}{extra ? <> {extra(r)}</> : null}</span>
          </div>
          <div className="mt-1.5 h-2 rounded-full bg-sunken overflow-hidden">
            <div className="h-full rounded-full transition-all" style={{ width: `${Math.max(2, (r[value] / m) * 100)}%`, background: colorFor ? colorFor(r) : "rgb(var(--primary))" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
