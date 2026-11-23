import { ArrowRight, CalendarCheck, HeartHandshake, PenLine, Sparkles, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { InsightCard } from "@/components/InsightCard";
import { Card, Delta, EmptyState, KpiCard, PageHeader, PageSkeleton, ProgressRing } from "@/components/ui";
import { useIsMobile, useLoadDemo, usePage } from "@/hooks/useData";
import { useApp } from "@/lib/store";
import { Onboarding } from "@/components/Onboarding";
import { AlertsPanel, Disclaimer } from "@/components/Alerts";
import { PlatformIcon } from "@/components/PlatformIcon";
import { RefreshButton, STATUS, when } from "@/pages/Integrations";
import { DEFINITIONS } from "@/lib/definitions";
import { useStatus } from "@/hooks/useData";

const EMPTY: Record<string, { title: string; body: string; shows: string[] }> = {
  feedback: { title: "No customer feedback yet", body: "Upload reviews, survey answers or pasted WhatsApp and Instagram messages, in any language.",
    shows: ["How customers feel over time", "The themes they mention most, and which are complaints", "NPS and why people would or would not recommend you", "Messages that need a personal reply", "Who is missing from your feedback"] },
  social: { title: "No social media data yet", body: "Upload your Instagram or TikTok export, or a screenshot of Insights.",
    shows: ["Which formats and topics earn saves and shares", "Your posting consistency, day by day", "The best days and times to post", "Product requests, sizing questions and partnership enquiries waiting for a reply"] },
  sales: { title: "No sales data yet", body: "Upload your Shopify orders export (and Google Analytics for the website).",
    shows: ["Revenue and orders against last period and last year", "Best-selling products, fabrics and colours", "How many customers come back", "Busy months such as October", "Where website visitors come from and whether they buy"] },
};

export function NoData({ page }: { page?: string }) {
  const { ws, setWs, setUploadOpen } = useApp();
  const load = useLoadDemo();
  const e = page ? EMPTY[page] : undefined;
  return (
    <EmptyState icon={Sparkles} title={e && ws === "mine" ? e.title : ws === "mine" ? "Your workspace is ready" : "Let us show you around"}
      body={e && ws === "mine" ? e.body : ws === "mine" ? "Drop in any export you have (Shopify orders, Instagram, reviews, a survey) and you will see what it says within seconds. Nothing leaves this computer."
        : "Load the demo workspace to explore with realistic, made-up customers."}>
      {e && ws === "mine" ? (
        <div className="w-full max-w-md text-left mb-2">
          <div className="label mb-2">Once it is uploaded, this page shows</div>
          <ul className="space-y-1.5 text-sm text-ink-2">{e.shows.map((s) => <li key={s} className="flex gap-2"><span className="text-primary">✓</span>{s}</li>)}</ul>
        </div>
      ) : null}
      <button className="btn-primary" onClick={() => setUploadOpen(true)}><Upload className="h-4 w-4" />Upload data</button>
      {ws === "mine" ? <button className="btn-outline" onClick={() => setWs("demo")}>See it with demo data</button> :
        <button className="btn-outline" onClick={() => load.mutate()} disabled={load.isPending}>{load.isPending ? "Loading…" : "Load demo data"}</button>}
    </EmptyState>
  );
}

function FirstDay() {
  const { ws } = useApp();
  const st = useStatus();
  if (ws === "demo") return <><PageHeader title="Good to see you" /><NoData /></>;
  const c = st.data?.counts || {};
  return <Onboarding have={Object.keys(c).filter((k) => c[k] > 0)} />;
}

export function Home() {
  const { data, isLoading } = usePage("home");
  const mobile = useIsMobile();
  if (isLoading || !data) return <PageSkeleton />;
  if (!data.kpis.length && !data.insights.length) return <FirstDay />;
  return mobile ? <Today d={data} /> : <CommandCentre d={data} />;
}

const helpKey = (k: string) => (k === "per_week" ? "posts_per_week" : DEFINITIONS[k] ? k : undefined);

/** Which sources feed the dashboards, their status and the last refresh. */
function SourceStrip({ d }: { d: any }) {
  return (
    <div className="mb-5 card !p-3 sm:!p-4 flex flex-wrap items-center gap-x-4 gap-y-3">
      <div className="flex items-center gap-2 min-w-0">
        <span className="label !text-[11px] shrink-0">Connected</span>
        <div className="flex -space-x-1.5">
          {d.sources.slice(0, 8).map((s: any) => (
            <span key={s.key} title={`${s.name}: ${(STATUS[s.status] || STATUS.available).label}, synced ${when(s.last_synced)}`}><PlatformIcon icon={s.icon} name={s.name} k={s.key} size={30} /></span>
          ))}
        </div>
        <span className="text-sm text-ink-2 truncate">{d.sources.length} sources</span>
      </div>
      <span className="text-xs text-ink-3">Last refresh: <span className="num">{when(d.last_refresh)}</span></span>
      <div className="ml-auto flex items-center gap-2">
        <Link to="/integrations" className="btn-ghost !min-h-[38px]">Manage</Link>
        <RefreshButton compact />
      </div>
    </div>
  );
}

function Unlock({ d }: { d: any }) {
  if (!d.unlock?.length) return null;
  return (
    <Card className="mt-4">
      <h3 className="h-card">Unlock more insights</h3>
      <p className="mt-1 text-sm text-ink-2">These sources are not connected yet. Each one adds pages and recommendations.</p>
      <ul className="mt-3 grid sm:grid-cols-2 gap-2">
        {d.unlock.map((u: any) => (
          <li key={u.key}><Link to="/integrations" className="flex items-center gap-3 rounded-xl border border-line p-3 hover:border-primary">
            <PlatformIcon icon={u.icon} name={u.name} k={u.key} size={34} />
            <span className="min-w-0"><span className="block text-sm font-medium">{u.name}</span><span className="block text-xs text-ink-3 truncate">{u.unlocks.join(" · ")}</span></span>
          </Link></li>
        ))}
      </ul>
    </Card>
  );
}

function CommandCentre({ d }: { d: any }) {
  const top = d.insights.find((i: any) => i.kind !== "care");
  return (
    <>
      <PageHeader title="This week at a glance"
        what={d.changed[0] ? <>{d.changed[0].label} {d.changed[0].change > 0 ? "up" : "down"} {Math.abs(d.changed[0].change).toFixed(0)}% ({d.changed[0].prev_display} to {d.changed[0].display}).</> : "Things are steady."}
        why={top ? top.title + "." : undefined}
        todo={top ? top.recommended_action.split(". ")[0].replace(/\.$/, "") + "." : undefined} />
      <SourceStrip d={d} />
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">{d.kpis.map((k: any) => <KpiCard key={k.key} {...k} help={helpKey(k.key) || k.help} compact={false} />)}</div>
      <p className="mt-2 text-xs text-ink-3">{d.period.label} ({d.period.start} to {d.period.end}), compared with the same number of days before. Hover the ? for how each figure is calculated.</p>
      <div className="mt-5"><AlertsPanel data={d.alerts} /></div>

      {d.care ? (
        <Link to="/feedback#care" className="mt-5 flex items-center gap-3 rounded-2xl bg-care-soft px-4 py-3 text-sm">
          <HeartHandshake className="h-5 w-5 text-care shrink-0" /><span><b>{d.care} messages</b> may come from someone having a hard time. Consider a personal reply.</span><ArrowRight className="ml-auto h-4 w-4" />
        </Link>
      ) : null}

      <div className="mt-7 flex items-end justify-between"><h2 className="font-display text-2xl font-semibold">Top recommendations</h2><Link to="/plan" className="text-sm text-primary font-medium">See your plan →</Link></div>
      <div className="mt-3 grid lg:grid-cols-3 gap-4">{d.insights.filter((i: any) => i.kind !== "care").slice(0, 3).map((i: any, n: number) => <InsightCard key={i.id} ins={i} rank={n + 1} />)}</div>
      <Disclaimer className="mt-2" />
      <Unlock d={d} />

      <div className="mt-6 grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-1">
          <h3 className="h-card">What changed</h3>
          <ul className="mt-3 divide-y divide-line">
            {d.changed.length ? d.changed.map((c: any) => (
              <li key={c.metric} className="flex items-center justify-between py-2.5 text-sm"><span className="text-ink-2">{c.label}</span><span className="flex items-center gap-2 num"><b>{c.display}</b><Delta change={c.change} goodWhenUp={c.good === (c.change > 0)} /></span></li>
            )) : <li className="py-3 text-sm text-ink-3">No big changes this period.</li>}
          </ul>
        </Card>
        <Card>
          <h3 className="h-card">Goals</h3>
          <ul className="mt-3 space-y-3">
            {d.goals.length ? d.goals.map((g: any) => (
              <li key={g.id} className="flex items-center gap-3"><ProgressRing value={g.progress} size={52} stroke={6} /><div className="min-w-0"><div className="text-sm font-medium truncate">{g.title}</div><div className="text-xs text-ink-3 num">Now {g.current_display} · target {g.target_display}</div></div></li>
            )) : <li className="text-sm text-ink-3">No goals yet. <Link to="/plan" className="text-primary">Set up to three</Link>.</li>}
          </ul>
        </Card>
        <Card>
          <h3 className="h-card flex items-center gap-2"><CalendarCheck className="h-5 w-5 text-primary" />Ready to review</h3>
          {d.due.length ? <ul className="mt-3 space-y-2">{d.due.map((x: any) => <li key={x.id} className="text-sm"><Link to="/plan" className="text-ink hover:text-primary">{x.title}</Link>{x.change != null ? <span className="ml-2"><Delta change={x.change} /></span> : null}</li>)}</ul>
            : <p className="mt-3 text-sm text-ink-3">Nothing due. Decisions come back here on their review date.</p>}
        </Card>
      </div>

      {d.insights.length > 3 ? (
        <>
          <h2 className="mt-8 font-display text-xl font-semibold">More insights</h2>
          <div className="mt-3 grid md:grid-cols-2 xl:grid-cols-3 gap-4">{d.insights.filter((i: any) => i.kind !== "care").slice(3).map((i: any) => <InsightCard key={i.id} ins={i} compact />)}</div>
        </>
      ) : null}
      {d.waiting.length ? (
        <Card className="mt-6">
          <h3 className="h-card">Not enough data yet</h3>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-2">{d.waiting.map((w: any) => <li key={w.id}>• {w.message}</li>)}</ul>
        </Card>
      ) : null}
    </>
  );
}

/** Mobile "Today": three numbers, three swipeable insights, one action, quick capture. */
function Today({ d }: { d: any }) {
  const { setCaptureOpen } = useApp();
  const ins = d.insights.filter((i: any) => i.kind !== "care").slice(0, 3);
  const next = ins[0];
  const hour = new Date().getHours();
  return (
    <div>
      <p className="text-sm text-ink-3">{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
      <h1 className="h-page mt-0.5">{hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"}</h1>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {d.kpis.slice(0, 3).map((k: any) => <KpiCard key={k.key} {...k} spark={undefined} help={undefined} compact />)}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-ink-3">
        <span>{d.period.label} · refreshed <span className="num">{when(d.last_refresh)}</span></span>
        <RefreshButton compact />
      </div>
      <div className="mt-4"><AlertsPanel data={d.alerts} limit={2} /></div>
      {d.care ? (
        <Link to="/feedback#care" className="mt-3 flex items-center gap-3 rounded-2xl bg-care-soft px-4 py-3 text-sm">
          <HeartHandshake className="h-5 w-5 text-care shrink-0" /><span><b>{d.care}</b> messages may need a personal reply</span>
        </Link>
      ) : null}
      {next ? (
        <div className="mt-4 rounded-3xl bg-primary text-primary-ink p-5">
          <div className="text-xs uppercase tracking-wide opacity-80">Do this next</div>
          <div className="mt-1 font-display text-xl font-semibold leading-snug">{next.recommended_action.split(". ")[0].replace(/\.$/, "")}.</div>
          <div className="mt-2 text-sm opacity-90">{next.title}</div>
        </div>
      ) : null}
      <div className="mt-5 flex items-center justify-between"><h2 className="font-display text-lg font-semibold">Top insights</h2><span className="text-xs text-ink-3">Swipe →</span></div>
      <div className="scroll-x -mx-4 px-4 mt-2 flex gap-3 pb-2">
        {ins.map((i: any, n: number) => <div key={i.id} className="snap shrink-0 w-[86%]"><InsightCard ins={i} rank={n + 1} compact /></div>)}
      </div>
      <Disclaimer className="mt-1" />
      {d.goals.length ? (
        <details className="mt-4 card p-4" open>
          <summary className="cursor-pointer font-display text-lg font-semibold">Goals</summary>
          <ul className="mt-3 space-y-3">{d.goals.map((g: any) => (
            <li key={g.id} className="flex items-center gap-3"><ProgressRing value={g.progress} size={46} stroke={5} /><div className="min-w-0"><div className="text-sm font-medium">{g.title}</div><div className="text-xs text-ink-3 num">Now {g.current_display} · target {g.target_display}</div></div></li>))}</ul>
        </details>
      ) : null}
      <details className="mt-3 card p-4">
        <summary className="cursor-pointer font-display text-lg font-semibold">Channels ({d.sources.length})</summary>
        <ul className="mt-3 space-y-2">{d.sources.map((s: any) => (
          <li key={s.key} className="flex items-center gap-3 text-sm"><PlatformIcon icon={s.icon} name={s.name} k={s.key} size={30} /><span className="flex-1">{s.name}</span><span className="text-xs text-ink-3 num">{when(s.last_synced)}</span></li>))}</ul>
        <Link to="/integrations" className="mt-3 inline-block text-sm text-primary font-medium">See all integrations →</Link>
      </details>
      <button onClick={() => setCaptureOpen(true)} className="mt-4 w-full card flex items-center gap-3 p-4 text-left">
        <span className="h-11 w-11 rounded-2xl bg-accent-soft text-accent grid place-items-center"><PenLine className="h-5 w-5" /></span>
        <span><span className="block font-medium">Log customer feedback</span><span className="text-sm text-ink-3">Type or paste a message in seconds</span></span>
      </button>
      <Link to="/briefing" className="mt-3 block text-center text-sm text-primary font-medium py-3">Open the weekly briefing →</Link>
    </div>
  );
}
