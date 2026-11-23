import { tr } from "@/lib/i18n";
import { useState } from "react";
import { Bars, Funnel, Heatmap, Lines } from "@/charts/charts";
import { ChartCard, KpiCard, PageHeader, PageSkeleton, Segmented } from "@/components/ui";
import { usePage } from "@/hooks/useData";
import { fmt } from "@/lib/format";
import { NoData } from "./Home";

export function Sales() {
  const { data, isLoading } = usePage("sales");
  const [tab, setTab] = useState<"sales" | "customers" | "web">("sales");
  if (isLoading || !data) return <PageSkeleton />;
  const s = data.sales, w = data.web;
  if (s.empty && w.empty && !data.flex.length) return <><PageHeader title="Sales and customers" /><NoData page="sales" /></>;
  return (
    <>
      <PageHeader title="Sales and customers"
        what={!s.empty ? s.revenue_chart.title + "." : w.trend.title + "."}
        why={!s.empty ? s.loyalty.title + ". A second purchase costs far less to win than a new customer." : undefined}
        todo={!s.empty ? "Plan stock and content for October early, and send a care-first follow-up email 30 days after purchase." : undefined}
        right={<div className="hidden sm:block"><Segmented label="Section" value={tab} onChange={setTab} options={[{ value: "sales", label: "Sales" }, { value: "customers", label: "Customers" }, { value: "web", label: "Website" }]} /></div>} />
      <div className="sm:hidden mb-4 scroll-x"><Segmented label="Section" value={tab} onChange={setTab} options={[{ value: "sales", label: "Sales" }, { value: "customers", label: "Customers" }, { value: "web", label: "Website" }]} /></div>

      {tab === "sales" && !s.empty ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard label="Revenue" value={s.kpis.revenue.value} unit="eur" change={s.kpis.revenue.change} spark={s.kpis.revenue.spark} help="revenue" />
            <KpiCard label="Orders" value={s.kpis.orders.value} unit="count" change={s.kpis.orders.change} spark={s.kpis.orders.spark} help="orders" />
            <KpiCard label="Average order" value={s.kpis.aov.value} unit="eur" change={s.kpis.aov.change} help="aov" />
            <KpiCard label="Gifts" value={s.kpis.gift_share.value} unit="pct" help="gift_share" />
          </div>
          <div className="mt-5 grid lg:grid-cols-2 gap-4">
            <ChartCard title={s.revenue_chart.title} subtitle={s.revenue_chart.subtitle} className="lg:col-span-2" table={s.revenue_chart.current}
              columns={[{ key: "period", label: "Period", fmt: fmt.date }, { key: "orders", label: "Orders" }, { key: "revenue", label: "Revenue", fmt: fmt.eur }]}>
              <Lines x={s.revenue_chart.current.map((r: any) => fmt.short(r.period))} fmt={(v) => fmt.eur(v)}
                series={[{ name: "This period", data: s.revenue_chart.current.map((r: any) => r.revenue) },
                  ...(s.revenue_chart.last_year.length ? [{ name: "Same period last year", data: s.revenue_chart.last_year.map((r: any) => r.revenue), dashed: true, colorIndex: 1 }] : [])]} />
            </ChartCard>
            <ChartCard title={s.fabric.title} subtitle={s.fabric.subtitle} table={s.fabric.rows} columns={[{ key: "label", label: "Fabric" }, { key: "units", label: "Units" }, { key: "revenue", label: "Revenue", fmt: fmt.eur }]}>
              <Bars rows={s.fabric.rows} x="label" y="units" height={220} label="units" />
            </ChartCard>
            <ChartCard title={s.line.title} subtitle={s.line.subtitle} table={s.line.rows} columns={[{ key: "label", label: "Line" }, { key: "units", label: "Units" }, { key: "revenue", label: "Revenue", fmt: fmt.eur }]}>
              <Bars rows={s.line.rows} x="label" y="units" height={220} label="units" />
            </ChartCard>
            <ChartCard title={s.products.title} subtitle={s.products.subtitle} table={s.products.rows} columns={[{ key: "product", label: "Product" }, { key: "units", label: "Units" }, { key: "revenue", label: "Revenue", fmt: fmt.eur }]}>
              <Bars rows={s.products.rows.slice(0, 8)} x="product" y="revenue" horizontal height={280} fmt={(v) => fmt.eur(v)} />
            </ChartCard>
            <ChartCard title={s.channels.title} subtitle={s.channels.subtitle} table={s.channels.rows} columns={[{ key: "channel", label: "Channel" }, { key: "orders", label: "Orders" }, { key: "revenue", label: "Revenue", fmt: fmt.eur }]}>
              <Bars rows={s.channels.rows} x="channel" y="revenue" horizontal height={220} fmt={(v) => fmt.eur(v)} />
            </ChartCard>
            <ChartCard title={s.seasonality.title} subtitle={s.seasonality.subtitle} table={s.seasonality.rows} columns={[{ key: "month", label: "Month" }, { key: "orders", label: "Avg orders", fmt: fmt.num }]}>
              <Bars rows={s.seasonality.rows} x="month" y="orders" height={220} fmt={(v) => v?.toFixed(0)} highlight="Oct" label="orders" />
              {Object.keys(s.seasonality.awareness || {}).length ? <p className="mt-1 text-xs text-ink-3">Key dates from your business profile: {Object.entries(s.seasonality.awareness).map(([m, l]) => `${tr(l)} (${tr(m)})`).join(", ")}.</p> : null}
            </ChartCard>
            <ChartCard title={s.codes.title} subtitle={s.codes.subtitle} table={s.codes.rows} columns={[{ key: "code", label: "Code" }, { key: "orders", label: "Orders" }, { key: "avg_discount", label: "Avg discount", fmt: fmt.eur }]}>
              {s.codes.rows.length ? <Bars rows={s.codes.rows} x="code" y="orders" height={220} label="orders" /> : <p className="text-sm text-ink-3">No codes used.</p>}
            </ChartCard>
          </div>
        </>
      ) : null}

      {tab === "customers" && !s.empty ? (
        <div className="grid lg:grid-cols-2 gap-4">
          <ChartCard title={s.loyalty.title} subtitle={s.loyalty.subtitle} table={s.loyalty.rows} columns={[{ key: "grp", label: "Group" }, { key: "customers", label: "Customers" }]}>
            <Bars rows={s.loyalty.rows} x="grp" y="customers" height={240} label="customers" />
          </ChartCard>
          <ChartCard title={s.cohorts.title} subtitle={s.cohorts.subtitle} help="Each row is a month's new customers. Each square shows the share who bought again 1 to 6 months later.">
            <Heatmap xLabels={["+1m", "+2m", "+3m", "+4m", "+5m", "+6m"]} yLabels={s.cohorts.rows.map((r: any) => fmt.month(r.cohort))}
              data={s.cohorts.rows.flatMap((r: any, y: number) => r.retention.map((v: number | null, x: number) => [x, y, v]))} height={340} max={0.2} />
          </ChartCard>
          <ChartCard title="New and returning customers" subtitle={`${s.period.label} · Shopify orders`}>
            <div className="grid grid-cols-2 gap-3">
              <KpiCard label="New customers" value={s.kpis.new_customers.value} unit="count" help="new_customers" compact />
              <KpiCard label="Repeat purchase rate" value={s.kpis.repeat_rate.value} unit="pct" help="repeat_rate" compact />
            </div>
          </ChartCard>
          {data.email && !data.email.empty ? (
            <ChartCard title={data.email.title} subtitle={data.email.subtitle} table={data.email.rows} columns={[{ key: "campaign", label: "Campaign" }, { key: "open_rate", label: "Open rate", fmt: (v) => fmt.pct(v, 1) }, { key: "revenue", label: "Revenue", fmt: fmt.eur }]}>
              <Bars rows={data.email.rows} x="campaign" y="open_rate" horizontal height={260} fmt={(v) => fmt.pct(v, 0)} />
            </ChartCard>
          ) : null}
        </div>
      ) : null}

      {tab === "web" && !w.empty ? (
        <>
          <div className="grid grid-cols-3 gap-3">
            <KpiCard label="Visits" value={w.kpis.sessions.value} unit="count" change={w.kpis.sessions.change} help="sessions" />
            <KpiCard label="Conversion" value={w.kpis.conversion.value} unit="pct" help="conversion" />
            <KpiCard label="Web revenue" value={w.kpis.revenue.value} unit="eur" help="web_revenue" />
          </div>
          <div className="mt-5 grid lg:grid-cols-2 gap-4">
            <ChartCard title={w.trend.title} subtitle={w.trend.subtitle}><Lines x={w.trend.rows.map((r: any) => fmt.short(r.period))} series={[{ name: "Visits", data: w.trend.rows.map((r: any) => r.sessions) }]} /></ChartCard>
            <ChartCard title={w.funnel.title} subtitle={w.funnel.subtitle}><Funnel steps={w.funnel.steps} /></ChartCard>
            <ChartCard title={w.sources.title} subtitle={w.sources.subtitle} table={w.sources.rows} columns={[{ key: "source", label: "Where they came from" }, { key: "sessions", label: "Visits", fmt: fmt.num }, { key: "conv_rate", label: "Conversion", fmt: (v) => fmt.pct(v, 1) }]}>
              <Bars rows={w.sources.rows} x="source" y="sessions" horizontal height={240} />
            </ChartCard>
            <ChartCard title={w.devices.title} subtitle={w.devices.subtitle} table={w.devices.rows} columns={[{ key: "device", label: "Device" }, { key: "sessions", label: "Visits", fmt: fmt.num }, { key: "conv_rate", label: "Conversion", fmt: (v) => fmt.pct(v, 1) }]}>
              <Bars rows={w.devices.rows} x="device" y="conv_rate" height={220} fmt={(v) => fmt.pct(v, 1)} label="conversion" />
            </ChartCard>
          </div>
        </>
      ) : null}
      {(tab === "web" && w.empty) || (tab !== "web" && s.empty) ? <NoData page="sales" /> : null}

      {data.flex.length ? (
        <div className="mt-6 grid lg:grid-cols-2 gap-4">
          {data.flex.map((f: any) => (
            <ChartCard key={f.id} title={f.trend.label || f.title} subtitle={`By month · ${f.title} (your own file)`}>
              <Bars rows={f.series.map((r: any) => ({ ...r, m: fmt.month(r.period) }))} x="m" y="value" height={220} fmt={(v) => (f.trend.value_label || "").includes("€") ? fmt.eur(v) : fmt.num(v)} />
            </ChartCard>
          ))}
        </div>
      ) : null}
    </>
  );
}
