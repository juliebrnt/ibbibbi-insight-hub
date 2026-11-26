import { Info, Lightbulb } from "lucide-react";
import type { ReactNode } from "react";
import { fmt } from "@/lib/format";
import { Card, cx } from "./ui";

/** One decision helper: a plain answer, one simple visual, one next step and how it was worked out. */
function DecisionCard({ title, subtitle, children, todo, lead, note, className = "" }: {
  title: string; subtitle?: string; children: ReactNode; todo?: string; lead?: string; note?: string; className?: string;
}) {
  return (
    <Card className={cx("flex flex-col", className)}>
      <span className="chip bg-accent-soft text-accent self-start flex items-center gap-1"><Lightbulb className="h-3.5 w-3.5" />Decision helper</span>
      <h3 className="h-card mt-2">{title}</h3>
      {subtitle ? <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p> : null}
      <div className="mt-4 flex-1">{children}</div>
      {todo ? <div className="mt-4 rounded-2xl bg-primary-soft p-3 text-sm"><span className="font-semibold text-primary">Do this: </span>{lead ? <><span>{lead}</span> </> : null}<span>{todo}</span></div> : null}
      {note ? <p className="mt-2 flex gap-1.5 text-xs text-ink-3"><Info className="h-3.5 w-3.5 shrink-0 mt-0.5" /><span>{note}</span></p> : null}
    </Card>
  );
}

const signed = (v: number | null | undefined) => (v == null ? "n/a" : `${v > 0 ? "+" : ""}${v}%`);

/** Does Instagram sell? Orders after each kind of post, against quiet days in the same weeks. */
export function InstagramSales({ d }: { d: any }) {
  if (!d) return null;
  const max = Math.max(5, ...d.rows.map((r: any) => Math.abs(r.lift || 0)));
  const part = (kind: string, label: string) => {
    const rows = d.rows.filter((r: any) => r.kind === kind);
    if (!rows.length) return null;
    return (
      <div>
        <div className="label mb-1.5">{label}</div>
        <ul className="space-y-1.5">
          {rows.map((r: any) => (
            <li key={r.label} className="grid grid-cols-[minmax(0,12rem)_1fr_3.5rem] items-center gap-2 text-sm">
              <span className="truncate">{r.label} <span className="text-ink-3 num">({r.posts})</span></span>
              <span className="relative h-2.5 rounded-full bg-sunken">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <span className={cx("absolute inset-y-0 rounded-full", (r.lift || 0) >= 0 ? "bg-good left-1/2" : "bg-warn right-1/2")}
                  style={{ width: `${(Math.abs(r.lift || 0) / max) * 50}%` }} />
              </span>
              <span className={cx("text-right num font-medium", (r.lift || 0) > 0 ? "text-good" : (r.lift || 0) < 0 ? "text-warn" : "text-ink-3")}>{signed(r.lift)}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  };
  return (
    <DecisionCard title={d.title} subtitle={d.subtitle} todo={d.todo} note={d.note}>
      <p className="text-sm text-ink-2 mb-3">Extra orders in the two days after each kind of post (number of posts in brackets).</p>
      <div className="grid md:grid-cols-2 gap-5">{part("format", "By format")}{part("topic", "By topic")}</div>
      {d.visits ? <p className="mt-4 text-sm"><span>On days with more profile visits than usual, orders were</span> <b className="num">{signed(d.visits.lift)}</b><span>.</span></p> : null}
    </DecisionCard>
  );
}

const GROUP_STYLE: Record<string, { cls: string; text: string; what: string }> = {
  grow: { cls: "bg-good-soft", text: "text-good", what: "Loved and selling" },
  promote: { cls: "bg-accent-soft", text: "text-accent", what: "Loved, but losing ground" },
  fix: { cls: "bg-warn-soft", text: "text-warn", what: "Selling, but rated lower" },
  rethink: { cls: "bg-care-soft", text: "text-care", what: "Rated lower and losing ground" },
};

/** Product decision map: grow, show again, fix first, rethink. */
export function ProductMap({ d }: { d: any }) {
  if (!d) return null;
  return (
    <DecisionCard title={d.title} subtitle={d.subtitle} todo={d.todo} note={d.note} className="lg:col-span-2">
      <p className="text-sm text-ink-2 mb-3"><span>{d.summary}</span>. <span>Average rating</span> <b className="num">{d.average_rating?.toLocaleString()}</b><span>, whole shop</span> <b className="num">{signed(d.brand_trend)}</b>.</p>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {(["grow", "promote", "fix", "rethink"] as const).map((g) => {
          const rows = d.rows.filter((r: any) => r.group === g);
          const st = GROUP_STYLE[g];
          return (
            <div key={g} className={cx("rounded-2xl p-3", st.cls)}>
              <div className={cx("font-semibold", st.text)}>{rows[0]?.group_label || { grow: "Grow", promote: "Show it again", fix: "Fix first", rethink: "Rethink" }[g]} <span className="num">({rows.length})</span></div>
              <div className="text-xs text-ink-2">{st.what}</div>
              <ul className="mt-2 space-y-2">
                {rows.length ? rows.map((r: any) => (
                  <li key={r.product} className="rounded-xl bg-surface p-2 text-sm" title={r.reason}>
                    <div className="font-medium" translate="no">{r.product}</div>
                    <div className="text-xs text-ink-3 num">
                      <span>{r.rating != null ? `★ ${r.rating.toFixed(1)}` : "Few reviews"}</span><span> · </span><span>{signed(r.vs_brand)}</span> <span>vs shop</span>
                    </div>
                    {r.issue && g !== "grow" ? <div className="mt-1 text-xs"><span className="chip bg-warn-soft text-warn">{r.issue}</span></div> : null}
                  </li>
                )) : <li className="text-xs text-ink-3">None right now</li>}
              </ul>
            </div>
          );
        })}
      </div>
    </DecisionCard>
  );
}

/** Seasonal planning guide: the usual range for the next months, and what sells in the peak. */
export function SeasonalPlan({ d }: { d: any }) {
  if (!d) return null;
  const max = Math.max(...d.rows.map((r: any) => r.high));
  return (
    <DecisionCard title={d.title} subtitle={d.subtitle} todo={d.todo} note={d.note} className="lg:col-span-2">
      <p className="text-sm text-ink-2 mb-3">Usual number of orders for the coming months.</p>
      <ul className="grid md:grid-cols-2 gap-x-10 gap-y-2">
        {d.rows.map((r: any) => (
          <li key={r.month} className="grid grid-cols-[7.5rem_1fr_5.5rem] items-center gap-2 text-sm">
            <span className={r.index >= 1.2 ? "font-semibold text-accent" : ""}>{r.label}</span>
            <span className="relative h-3 rounded-full bg-sunken">
              <span className={cx("absolute inset-y-0 rounded-full", r.index >= 1.2 ? "bg-accent" : "bg-primary/70")}
                style={{ left: `${(r.low / max) * 100}%`, width: `${((r.high - r.low) / max) * 100}%` }} />
            </span>
            <span className="text-right num text-ink-2">{r.low}–{r.high}</span>
          </li>
        ))}
      </ul>
      {d.sellers?.length ? (
        <div className="mt-4"><div className="label mb-1"><span>Best sellers in a usual</span> <span>{d.peak}</span></div>
          <div className="flex flex-wrap gap-1.5">{d.sellers.map((s: any) => <span key={s.product} className="chip bg-sunken text-ink-2"><span translate="no">{s.product}</span>&nbsp;<span className="num">· {s.units}</span></span>)}</div>
        </div>
      ) : null}
    </DecisionCard>
  );
}

/** Customer groups: who they are, what they are worth, one action each. */
export function CustomerGroups({ d }: { d: any }) {
  if (!d) return null;
  return (
    <DecisionCard title={d.title} subtitle={d.subtitle} todo={d.todo} lead={d.todo_lead} note={d.note} className="lg:col-span-2">
      <div className="hidden md:grid grid-cols-[11rem_1fr_1fr_minmax(0,2fr)] gap-3 text-xs text-ink-3 mb-1 px-1">
        <span>Group</span><span>Share of customers</span><span>Share of revenue · average spend</span><span>What to do</span>
      </div>
      <ul className="divide-y divide-line">
        {d.rows.map((r: any) => (
          <li key={r.group} className="grid md:grid-cols-[11rem_1fr_1fr_minmax(0,2fr)] gap-x-3 gap-y-1 py-2.5 px-1 text-sm items-center">
            <span><span className="font-medium">{r.label}</span><span className="block text-xs text-ink-3">{r.rule}</span></span>
            <Share v={r.share} n={r.customers} />
            <Share v={r.revenue_share} sub={r.avg_spend != null ? fmt.eur(r.avg_spend) : undefined} accent />
            <span className="text-ink-2">{r.action}</span>
          </li>
        ))}
      </ul>
    </DecisionCard>
  );
}

function Share({ v, n, sub, accent }: { v: number; n?: number; sub?: string; accent?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-2 flex-1 rounded-full bg-sunken overflow-hidden"><span className={cx("block h-full rounded-full", accent ? "bg-accent" : "bg-primary")} style={{ width: `${Math.min(100, v * 100)}%` }} /></span>
      <span className="num w-24 text-right text-ink-2">{fmt.pct(v)}{n != null ? <span className="text-ink-3"> ({n.toLocaleString()})</span> : null}{sub ? <span className="text-ink-3"> · {sub}</span> : null}</span>
    </span>
  );
}
