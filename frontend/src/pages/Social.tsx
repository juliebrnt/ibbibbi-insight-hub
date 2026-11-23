import { Inbox } from "lucide-react";
import { Bars, CalendarHeat, GroupedBars, Heatmap, Lines } from "@/charts/charts";
import { Card, ChartCard, cx, KpiCard, PageHeader, PageSkeleton } from "@/components/ui";
import { usePage } from "@/hooks/useData";
import { fmt } from "@/lib/format";
import { NoData } from "./Home";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function Social() {
  const { data: d, isLoading } = usePage("social");
  if (isLoading || !d) return <PageSkeleton />;
  if (d.empty) return <><PageHeader title="What content works" /><NoData page="social" /></>;
  const k = d.kpis;
  const hours = [...new Set<number>(d.timing.rows.map((r: any) => r.hour_block))].sort((a, b) => a - b);
  const heat = d.timing.rows.map((r: any) => [hours.indexOf(r.hour_block), r.dow - 1, r.er] as [number, number, number]);
  const inbox = d.comments.inbox || [];
  return (
    <>
      <PageHeader title="What content works"
        what={d.formats.title + "."} why={d.pillars.title + ". Saves and shares spread your mission further than likes."}
        todo={inbox.length ? `Reply to ${d.comments.unanswered} waiting questions and requests, starting with partnership enquiries.` : "Keep a steady rhythm of three posts a week."} />
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard label="Posts per week" value={k.per_week.value} unit="count" help="posts_per_week" />
        <KpiCard label="Avg days between posts" value={k.avg_gap.value} unit="count" help="avg_gap" />
        <KpiCard label="Weeks with a post" value={k.weeks_active.value} unit="pct" help="weeks_active" />
        <KpiCard label="Engagement rate" value={k.er.value} unit="pct" help="er" />
        <KpiCard label="Saves per post" value={k.saves.value} unit="count" change={k.saves.change} help="saves" />
        <KpiCard label="Mission-led posts" value={k.mission_share.value} unit="pct" help="mission_share" />
      </div>
      <div className="mt-5 grid lg:grid-cols-2 gap-4">
        <ChartCard title={d.formats.title} subtitle={d.formats.subtitle} table={d.formats.rows}
          columns={[{ key: "format", label: "Format" }, { key: "posts", label: "Posts" }, { key: "saves", label: "Saves", fmt: (v) => v?.toFixed(1) }, { key: "reach", label: "Reach", fmt: fmt.num }, { key: "er", label: "Eng. rate", fmt: (v) => fmt.pct(v, 1) }]}>
          <GroupedBars rows={d.formats.rows} x="format" series={[{ key: "saves", name: "Saves per post" }, { key: "shares", name: "Shares per post" }]} fmt={(v) => v?.toFixed(0)} />
        </ChartCard>
        <ChartCard title={d.pillars.title} subtitle={d.pillars.subtitle} table={d.pillars.rows}
          columns={[{ key: "label", label: "Topic" }, { key: "posts", label: "Posts" }, { key: "saves", label: "Saves", fmt: (v) => v?.toFixed(1) }, { key: "shares", label: "Shares", fmt: (v) => v?.toFixed(1) }]}>
          <Bars rows={d.pillars.rows} x="label" y="saves" horizontal height={220} fmt={(v) => v?.toFixed(0)} label="saves per post" highlight="Mission and community" />
        </ChartCard>
        <ChartCard title={d.consistency.title} subtitle={d.consistency.subtitle} className="lg:col-span-2"
          help="Each square is a day. Darker means more posts that day.">
          <div className="overflow-x-auto"><div className="min-w-[680px]"><CalendarHeat rows={d.consistency.calendar} range={d.consistency.calendar_range as [string, string]} /></div></div>
          {d.consistency.change ? (
            <p className="mt-2 text-sm text-ink-2">Since <b>{fmt.date(d.consistency.change.switch_week)}</b> you post <b>{d.consistency.change.after_per_week}</b> times a week (before: {d.consistency.change.before_per_week}), and reach per post went from <b className="num">{fmt.num(d.consistency.change.before_reach)}</b> to <b className="num">{fmt.num(d.consistency.change.after_reach)}</b>.</p>
          ) : null}
        </ChartCard>
        <ChartCard title={d.timing.title} subtitle={d.timing.subtitle} table={d.timing.by_day} columns={[{ key: "day", label: "Day" }, { key: "posts", label: "Posts" }, { key: "er", label: "Eng. rate", fmt: (v) => fmt.pct(v, 1) }]}>
          <Heatmap xLabels={hours.map((h) => `${String(h).padStart(2, "0")}h`)} yLabels={DAYS} data={heat} height={260} fmt={(v) => `${(v * 100).toFixed(1)}%`} />
        </ChartCard>
        <ChartCard title="Weekly posting and reach" subtitle="All time · Instagram posts">
          <Lines x={d.consistency.weekly.map((w: any) => fmt.short(w.week))} series={[{ name: "Posts per week", data: d.consistency.weekly.map((w: any) => w.posts) }]} height={260} />
        </ChartCard>
      </div>

      {d.cross?.enough ? (
        <Card className="mt-4">
          <h3 className="h-card">Do mission posts bring visitors to the shop?</h3>
          <p className="mt-1 text-xs text-ink-3">{d.cross.weeks} weeks · Instagram and Google Analytics · This is a correlation, not proof of cause.</p>
          <div className="mt-3 grid sm:grid-cols-3 gap-3 text-sm">
            <Stat label="Instagram visits, weeks with mission posts" v={fmt.num(d.cross.ig_visits_with)} />
            <Stat label="Instagram visits, other weeks" v={fmt.num(d.cross.ig_visits_without)} />
            <Stat label="Correlation (0 none, 1 perfect)" v={d.cross.visits_lag0?.toFixed(2)} />
          </div>
        </Card>
      ) : null}

      <section className="mt-6">
        <h2 className="font-display text-xl font-semibold flex items-center gap-2"><Inbox className="h-5 w-5 text-primary" />Opportunity inbox</h2>
        <p className="text-sm text-ink-2">{d.comments.title}. {d.comments.subtitle}</p>
        <div className="mt-3 grid md:grid-cols-2 gap-3">
          {inbox.slice(0, 12).map((c: any) => (
            <Card key={c.id} className="!p-4">
              <div className="flex items-center gap-2"><span className={cx("chip", c.category === "partnership" ? "bg-good-soft text-good" : c.category === "sensitive" ? "bg-care-soft text-care" : c.category === "request" ? "bg-accent-soft text-accent" : "bg-primary-soft text-primary")}>{c.label}</span><span className="ml-auto text-xs text-ink-3">{fmt.date(c.date)} · {c.platform}</span></div>
              <p className="mt-2 text-[15px]">{c.text}</p>
              <p className="mt-1 text-xs text-ink-3">Not answered yet</p>
            </Card>
          ))}
        </div>
      </section>
      {d.tiktok ? <Card className="mt-4"><h3 className="h-card">TikTok is just starting</h3><p className="mt-1 text-sm text-ink-2 num">{d.tiktok.posts} videos since {fmt.date(d.tiktok.first_d)}, averaging {fmt.num(d.tiktok.views)} views and {fmt.num(d.tiktok.shares)} shares each.</p></Card> : null}
    </>
  );
}

function Stat({ label, v }: { label: string; v: any }) {
  return <div className="rounded-2xl bg-sunken p-3"><div className="text-xs text-ink-3">{label}</div><div className="mt-1 font-display text-2xl font-semibold num">{v ?? "n/a"}</div></div>;
}
