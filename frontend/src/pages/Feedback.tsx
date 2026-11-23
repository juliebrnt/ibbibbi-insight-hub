import { HeartHandshake, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Bars, SentimentStream, ShareBars } from "@/charts/charts";
import { useChartTheme } from "@/charts/EChart";
import { Card, ChartCard, cx, KpiCard, PageHeader, PageSkeleton, SentimentBadge, Stars } from "@/components/ui";
import { usePage } from "@/hooks/useData";
import { api } from "@/lib/api";
import { fmt, LANGS } from "@/lib/format";
import { useApp } from "@/lib/store";
import { NoData } from "./Home";
import { ExampleReviews, VoiceExplorer } from "@/components/VoiceExplorer";

export function Feedback() {
  const { data: d, isLoading } = usePage("feedback");
  const t = useChartTheme();
  if (isLoading || !d) return <PageSkeleton />;
  if (d.empty) return <><PageHeader title="What customers say" /><NoData page="feedback" /><ExampleReviews /></>;
  const k = d.kpis;
  const neg = d.themes.complaint_title;
  return (
    <>
      <PageHeader title="What customers say"
        what={d.ratings.title + "."}
        why={neg ? `${neg}. Fixing the top complaint is usually the cheapest way to win loyalty.` : "Understanding feelings, not just ratings, shows what to protect and what to fix."}
        todo={d.who_is_missing.flagged.length ? `Hear more from ${d.who_is_missing.flagged[0].label.toLowerCase()} customers before deciding.` : "Keep asking: add the feedback QR card to every parcel."} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Average rating" value={k.rating.value} unit="stars" change={k.rating.prev ? ((k.rating.value - k.rating.prev) / k.rating.prev) * 100 : null} help="rating" />
        <KpiCard label="NPS (12 months)" value={k.nps.value} unit="score" help="nps" />
        <KpiCard label="Positive feedback" value={k.positive_share.value} unit="pct" help="positive_share" />
        <KpiCard label="Pieces of feedback" value={k.volume.value} unit="count" change={k.volume.change} help="volume" />
      </div>

      {d.care.length ? (
        <Card className="mt-5 !bg-care-soft border-0" as="section">
          <div id="care" className="flex items-center gap-2 font-display text-lg font-semibold"><HeartHandshake className="h-5 w-5 text-care" />Consider a personal reply</div>
          <p className="mt-1 text-sm text-ink-2">These customers may be having a hard time. They are shown here for care, never for marketing, and are never quoted.</p>
          <ul className="mt-3 space-y-2">{d.care.slice(0, 5).map((c: any) => <li key={c.id} className="rounded-xl bg-surface px-3 py-2 text-sm"><span className="text-ink-3 text-xs">{fmt.date(c.date)} · {c.source}</span><div>{c.text}</div></li>)}</ul>
        </Card>
      ) : null}

      <div className="mt-5 grid lg:grid-cols-2 gap-4">
        <ChartCard title={d.stream.title} subtitle={d.stream.subtitle} table={d.stream.rows} columns={[{ key: "period", label: "Period", fmt: fmt.short }, { key: "sentiment", label: "Feeling" }, { key: "n", label: "Count" }]}>
          <SentimentStream rows={d.stream.rows} />
        </ChartCard>
        <ChartCard title={d.themes.title} subtitle={d.themes.subtitle} help="Themes come from keywords in Spanish, Catalan and English. You can edit them in Settings."
          table={d.themes.rows} columns={[{ key: "label", label: "Theme" }, { key: "n", label: "Mentions" }, { key: "neg_share", label: "Negative", fmt: (v) => fmt.pct(v) }, { key: "change_pts", label: "Change (pts)" }]}>
          <ShareBars rows={d.themes.rows.slice(0, 9)} label="label" value="share" colorFor={(r) => (r.neg_share > 0.4 ? t.sentiment.negative : t.series[0])}
            extra={(r) => r.change_pts != null && Math.abs(r.change_pts) >= 3 ? <span className={cx("chip ml-1", r.change_pts > 0 ? "bg-primary-soft text-primary" : "bg-sunken text-ink-3")}>{r.change_pts > 0 ? "rising" : "falling"}</span> : null} />
          <p className="mt-3 text-xs text-ink-3">Orange bars: mostly complaints. Blue: mostly positive.</p>
        </ChartCard>
        <ChartCard title={d.nps.title} subtitle={d.nps.subtitle} table={d.nps.detractor_reasons} columns={[{ key: "theme", label: "Detractor theme" }, { key: "n", label: "Mentions" }]}>
          {d.nps.summary.n ? (
            <>
              <div className="flex h-4 overflow-hidden rounded-full gap-[2px]" role="img" aria-label="Promoters, passives and detractors">
                <div style={{ width: fmt.pct(d.nps.summary.promoters), background: t.sentiment.positive }} />
                <div style={{ width: fmt.pct(d.nps.summary.passives), background: t.sentiment.neutral }} />
                <div style={{ width: fmt.pct(d.nps.summary.detractors), background: t.sentiment.negative }} />
              </div>
              <div className="mt-2 flex flex-wrap gap-4 text-xs text-ink-2 num"><span>Promoters {fmt.pct(d.nps.summary.promoters)}</span><span>Passives {fmt.pct(d.nps.summary.passives)}</span><span>Detractors {fmt.pct(d.nps.summary.detractors)}</span></div>
              <div className="mt-4 grid sm:grid-cols-2 gap-4 text-sm">
                <div><div className="label mb-2">Why people would not recommend</div><Reasons rows={d.nps.detractor_reasons} /></div>
                <div><div className="label mb-2">Why people love you</div><Reasons rows={d.nps.promoter_reasons} /></div>
              </div>
            </>
          ) : <p className="text-sm text-ink-3">Upload survey answers to see NPS.</p>}
        </ChartCard>
        <ChartCard title={d.fabric.title} subtitle={d.fabric.subtitle} table={d.products.rows} columns={[{ key: "product", label: "Product" }, { key: "avg", label: "Rating", fmt: fmt.stars }, { key: "n", label: "Reviews" }]}>
          <Bars rows={d.fabric.rows.map((r: any) => ({ ...r, fabric: r.fabric[0].toUpperCase() + r.fabric.slice(1) }))} x="fabric" y="avg" height={200} fmt={(v) => v?.toFixed(2)} label="stars" />
          <div className="mt-2 text-xs text-ink-3">Per product: {d.products.title}.</div>
        </ChartCard>
        <ChartCard title={d.who_is_missing.title} subtitle={d.who_is_missing.subtitle} help="Decisions should not follow only the loudest or most digital customers.">
          <div className="flex items-center gap-2 mb-3 text-sm text-ink-2"><Users className="h-4 w-4" />Share of sales vs share of feedback</div>
          <ul className="space-y-3">{d.who_is_missing.groups.filter((g: any) => g.dimension !== "Sales channel" || g.buyer_share > 0.05).map((g: any, i: number) => (
            <li key={i} className="text-sm">
              <div className="flex justify-between"><span>{g.dimension}: <b>{g.label}</b></span>{g.flag ? <span className="chip bg-warn-soft text-warn">Under-represented</span> : null}</div>
              <div className="mt-1 grid grid-cols-[70px_1fr] gap-x-2 gap-y-1 items-center text-xs text-ink-3">
                <span>Sales</span><div className="h-2 rounded-full bg-sunken"><div className="h-2 rounded-full" style={{ width: fmt.pct(g.buyer_share), background: t.series[0] }} /></div>
                <span>Feedback</span><div className="h-2 rounded-full bg-sunken"><div className="h-2 rounded-full" style={{ width: fmt.pct(g.feedback_share), background: t.series[1] }} /></div>
              </div>
            </li>))}</ul>
        </ChartCard>
        <ChartCard title={d.languages.title} subtitle={d.languages.subtitle}>
          <ShareBars rows={d.languages.rows.map((r: any) => ({ ...r, label: LANGS[r.language] || r.label }))} label="label" value="n" fmt={(v) => v.toString()} />
        </ChartCard>
      </div>
      <VoiceExplorer />
      <Quotes quotes={d.quotes} />
    </>
  );
}

function Reasons({ rows }: { rows: any[] }) {
  const labels: any = { design: "Colour and design range", shipping: "Shipping", price: "Price", fit: "Fit and sizing", softness: "Softness", emotional: "Emotional value", service: "Service", gifting: "Gifting", fabric: "Fabric", children: "Children's needs", packaging: "Packaging" };
  if (!rows.length) return <p className="text-ink-3">Not enough answers yet.</p>;
  return <ol className="space-y-1">{rows.slice(0, 4).map((r) => <li key={r.theme} className="flex justify-between"><span>{labels[r.theme] || r.theme}</span><span className="num text-ink-3">{r.n}</span></li>)}</ol>;
}

function Quotes({ quotes }: { quotes: any[] }) {
  const { ws } = useApp();
  const [filter, setFilter] = useState("all");
  const [consent, setConsent] = useState<Record<string, boolean>>({});
  const shown = quotes.filter((q) => filter === "all" || q.sentiment === filter).slice(0, 12);
  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div><h2 className="font-display text-xl font-semibold">In their words</h2><p className="text-xs text-ink-3">Quotes are for your team only unless the customer agreed to be quoted.</p></div>
        <select className="input !w-auto !min-h-[38px]" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter quotes"><option value="all">All</option><option value="positive">Positive</option><option value="negative">Negative</option></select>
      </div>
      <div className="mt-3 grid md:grid-cols-2 xl:grid-cols-3 gap-3">
        {shown.map((q) => {
          const ok = consent[q.id] ?? q.consent_quote;
          return (
            <Card key={q.id} className="!p-4">
              <div className="flex items-center gap-2 flex-wrap"><SentimentBadge s={q.sentiment} /><Stars n={q.rating} /><span className="text-xs text-ink-3 ml-auto">{fmt.date(q.date)}</span></div>
              <blockquote className="mt-2 text-[15px] leading-relaxed">“{q.text}”</blockquote>
              <div className="mt-2 flex items-center justify-between text-xs text-ink-3"><span>{q.source}{q.product ? ` · ${q.product.split(" - ")[0]}` : ""}</span>
                <label className="flex items-center gap-1.5 cursor-pointer"><input type="checkbox" checked={!!ok} onChange={(e) => { setConsent({ ...consent, [q.id]: e.target.checked }); api.patch(`/feedback/${q.id}/consent?ws=${ws}`, { consent: e.target.checked }).then(() => toast(e.target.checked ? "Marked as OK to quote" : "Not OK to quote")); }} />OK to quote</label></div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
