import { Inbox } from "lucide-react";
import { Bars, CalendarHeat, GroupedBars, Heatmap, Lines } from "@/charts/charts";
import { Card, ChartCard, cx, KpiCard, PageHeader, PageSkeleton, Segmented, ShareBarsLite } from "@/components/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { PlatformIcon } from "@/components/PlatformIcon";
import { tr } from "@/lib/i18n";
import { fmt } from "@/lib/format";
import { NoData } from "./Home";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const ICON: Record<string, string> = { Instagram: "siInstagram", TikTok: "siTiktok", LinkedIn: "siLinkedin", Facebook: "siFacebook" };

export function Social() {
  const { ws, range } = useApp();
  const [plat, setPlat] = useState<string>("");
  const { data: d, isLoading } = useQuery<any>({
    queryKey: ["social", ws, range, plat],
    queryFn: () => api.get(`/social?ws=${ws}&range=${range}${plat ? `&platform=${encodeURIComponent(plat)}` : ""}`),
  });
  if (isLoading || !d) return <PageSkeleton />;
  if (d.empty) return <><PageHeader title="What content works" /><NoData page="social" /></>;
  const k = d.kpis;
  const has = (m: string) => (d.available || []).includes(m);
  const summary = (d.platform_summary || []).find((x: any) => x.platform === d.platform);
  const hours = [...new Set<number>(d.timing.rows.map((r: any) => r.hour_block))].sort((a, b) => a - b);
  const heat = d.timing.rows.map((r: any) => [hours.indexOf(r.hour_block), r.dow - 1, r.er] as [number, number, number]);
  const inbox = d.comments.inbox || [];
  return (
    <>
      <PageHeader title="What content works"
        what={d.formats.title + "."} why={d.pillars.title + ". Saves and shares spread your mission further than likes."}
        todo={inbox.length ? `Reply to ${d.comments.unanswered} waiting questions and requests, starting with partnership enquiries.` : "Keep a steady rhythm of three posts a week."} />
      {(d.platform_summary || []).length > 1 ? (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Segmented label="Platform" value={d.platform} onChange={(v) => setPlat(v)}
            options={d.platform_summary.map((x: any) => ({ value: x.platform, label: `${x.platform} (${x.total_posts})` }))} />
          <span className="text-xs text-ink-3">Only connected platforms are shown, each with the metrics it actually provides.</span>
        </div>
      ) : null}
      <div className="mb-3 flex items-center gap-2 text-sm text-ink-2">
        <PlatformIcon icon={ICON[d.platform]} name={d.platform} size={28} />
        <span><b>{d.platform}</b>{summary?.first ? <><span> · </span><span>Since</span> <span>{fmt.date(String(summary.first))}</span></> : null}
          <span> · </span><span>Metrics available</span>: <span>{(d.available || []).map(tr).join(", ")}</span></span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard label="Posts per week" value={k.per_week.value} unit="count" help="posts_per_week" />
        <KpiCard label="Avg days between posts" value={k.avg_gap.value} unit="count" help="avg_gap" />
        <KpiCard label="Weeks with a post" value={k.weeks_active.value} unit="pct" help="weeks_active" />
        <KpiCard label={summary?.er_basis === "views" ? "Engagement rate (of views)" : "Engagement rate"} value={k.er.value} unit="pct"
          help={summary?.er_basis === "views" ? `This platform does not report reach, so engagement is divided by views instead. Calculated as (likes + comments + saves + shares) divided by views, averaged across posts. Source: ${d.platform}.` : "er"} />
        {has("saves") ? <KpiCard label="Saves per post" value={k.saves.value} unit="count" change={k.saves.change} help="saves" /> : null}
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
          <p className="mt-1 text-xs text-ink-3">{`${d.cross.weeks} weeks · Instagram and Google Analytics · This is a correlation, not proof of cause.`}</p>
          <div className="mt-3 grid sm:grid-cols-3 gap-3 text-sm">
            <Stat label="Instagram visits, weeks with mission posts" v={fmt.num(d.cross.ig_visits_with)} />
            <Stat label="Instagram visits, other weeks" v={fmt.num(d.cross.ig_visits_without)} />
            <Stat label="Correlation (0 none, 1 perfect)" v={d.cross.visits_lag0?.toFixed(2)} />
          </div>
        </Card>
      ) : null}

      {d.comments?.analysis && !d.comments.analysis.empty ? <CommentAnalysis a={d.comments.analysis} /> : null}

      <section className="mt-6">
        <h2 className="font-display text-xl font-semibold flex items-center gap-2"><Inbox className="h-5 w-5 text-primary" />Opportunity inbox</h2>
        <p className="text-sm text-ink-2">{d.comments.title}. {d.comments.subtitle}</p>
        <div className="mt-3 grid md:grid-cols-2 gap-3">
          {inbox.slice(0, 12).map((c: any) => (
            <Card key={c.id} className="!p-4">
              <div className="flex items-center gap-2"><span className={cx("chip", c.category === "partnership" ? "bg-good-soft text-good" : c.category === "sensitive" ? "bg-care-soft text-care" : c.category === "request" ? "bg-accent-soft text-accent" : "bg-primary-soft text-primary")}>{c.label}</span><span className="ml-auto text-xs text-ink-3">{fmt.date(c.date)} · {c.platform}</span></div>
              <p className="mt-2 text-[15px]" translate="no">{c.text}</p>
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

function CommentAnalysis({ a }: { a: any }) {
  return (
    <section className="mt-6">
      <h2 className="font-display text-xl font-semibold">What people say in comments</h2>
      <p className="text-sm text-ink-2">{a.subtitle}</p>
      <div className="mt-3 grid lg:grid-cols-3 gap-4">
        <ChartCard title={a.title} subtitle="Share of comments that are questions, requests, sizing or partnership enquiries" table={a.by_pillar}
          columns={[{ key: "label", label: "Topic" }, { key: "comments", label: "Comments" }, { key: "meaningful_share", label: "Questions or requests", fmt: (v) => fmt.pct(v) }]}>
          <ShareBarsLite rows={a.by_pillar.map((r: any) => ({ label: r.label, value: r.meaningful_share }))} />
          {a.by_format.length ? <p className="mt-3 text-xs text-ink-3">By format: {a.by_format.map((f: any) => `${f.key} ${fmt.pct(f.meaningful_share)}`).join(" · ")}</p> : null}
        </ChartCard>
        <ChartCard title={a.themes[0] ? `${a.themes[0].label} is the most discussed subject` : "Subjects in comments"} subtitle="Themes mentioned in comments">
          <ShareBarsLite rows={a.themes.map((t: any) => ({ label: t.label, value: t.n, neg: t.neg / Math.max(t.n, 1) }))} count />
        </ChartCard>
        <Card>
          <h3 className="h-card">Questions and unmet needs</h3>
          {a.emerging.length ? (
            <ul className="mt-2 space-y-1 text-sm">{a.emerging.map((e: any) => <li key={e.category} className="flex justify-between gap-2"><span>{e.label}</span><span className="chip bg-accent-soft text-accent num">rising {e.change > 0 ? "+" : ""}{e.change}%</span></li>)}</ul>
          ) : <p className="mt-2 text-sm text-ink-3">No category is rising sharply.</p>}
          <p className="mt-2 text-xs text-ink-3">Recent half of the period compared with the earlier half.</p>
          {a.needs_examples.length ? <><div className="label mt-4 mb-1">What people ask for</div><ul className="space-y-1 text-sm text-ink-2">{a.needs_examples.map((t: string) => <li key={t} translate="no">“{t}”</li>)}</ul></> : null}
        </Card>
      </div>
    </section>
  );
}
