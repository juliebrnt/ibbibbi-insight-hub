import ReactECharts from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, FunnelChart, HeatmapChart, LineChart } from "echarts/charts";
import { CalendarComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useMemo } from "react";
import { chartDark, chartLight, cssVar, isDark, sentiment, sequential } from "@/theme/tokens";
import { useThemeTick } from "@/hooks/useData";

echarts.use([BarChart, LineChart, HeatmapChart, FunnelChart, GridComponent, TooltipComponent, LegendComponent, CalendarComponent,
  VisualMapComponent, MarkLineComponent, SVGRenderer]);

export function useChartTheme() {
  const tick = useThemeTick();
  return useMemo(() => {
    const dark = isDark();
    return {
      dark,
      series: dark ? chartDark : chartLight,
      sentiment: dark ? sentiment.dark : sentiment.light,
      sequential,
      ink: cssVar("ink"),
      ink2: cssVar("ink-2"),
      ink3: cssVar("ink-3"),
      line: cssVar("line"),
      surface: cssVar("surface"),
      primary: cssVar("primary"),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);
}

export type ChartTheme = ReturnType<typeof useChartTheme>;

/** Shared, recessive axis and tooltip styling. */
export function base(t: ChartTheme) {
  return {
    textStyle: { fontFamily: "'Inter Variable', system-ui, sans-serif", color: t.ink2 },
    animationDuration: 400,
    tooltip: {
      trigger: "axis",
      backgroundColor: t.surface,
      borderColor: t.line,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: t.ink, fontSize: 12 },
      extraCssText: "border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.12);",
      axisPointer: { type: "line", lineStyle: { color: t.line } },
    },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
  };
}

export function axisX(t: ChartTheme, data: any[], extra: any = {}) {
  return {
    type: "category", data, axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
    axisLabel: { color: t.ink3, fontSize: 11, hideOverlap: true, ...(extra.axisLabel || {}) }, ...extra,
  };
}

export function axisY(t: ChartTheme, extra: any = {}) {
  return { type: "value", splitLine: { lineStyle: { color: t.line, opacity: 0.6 } }, axisLabel: { color: t.ink3, fontSize: 11, ...(extra.axisLabel || {}) }, ...extra };
}

export function EChart({ option, height = 260, className = "" }: { option: any; height?: number; className?: string }) {
  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      notMerge
      lazyUpdate
      opts={{ renderer: "svg" }}
      style={{ height, width: "100%" }}
      className={className}
    />
  );
}
