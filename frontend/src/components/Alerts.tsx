import { BellRing, ChevronDown, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";
import { Card, cx } from "./ui";

/** Meaningful changes only. Each shows the size, comparison period, calculation, source and a next step. */
export function AlertsPanel({ data, limit = 4 }: { data: any; limit?: number }) {
  const [all, setAll] = useState(false);
  if (!data) return null;
  const alerts = data.alerts || [];
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="h-card flex items-center gap-2"><BellRing className="h-5 w-5 text-accent" />Alerts</h2>
          <p className="mt-1 text-xs text-ink-3">{data.period}</p>
        </div>
        <span className="chip bg-sunken text-ink-2 num">{alerts.length} {alerts.length === 1 ? "alert" : "alerts"}</span>
      </div>
      {!alerts.length ? (
        <p className="mt-3 text-sm text-ink-2">{data.quiet ? `No significant changes. We checked: ${data.checked.join(", ").toLowerCase()}.` : "Not enough data yet to compare periods reliably."}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {(all ? alerts : alerts.slice(0, limit)).map((a: any) => <AlertRow key={a.id} a={a} />)}
        </ul>
      )}
      {alerts.length > limit ? <button className="mt-3 text-sm text-primary font-medium" onClick={() => setAll((v) => !v)}>{all ? "Show fewer" : `Show all ${alerts.length}`}</button> : null}
      <p className="mt-3 text-[11px] text-ink-3">Only changes above a set size, with enough data behind them, raise an alert. Small wobbles are ignored.</p>
    </Card>
  );
}

function AlertRow({ a }: { a: any }) {
  const [open, setOpen] = useState(false);
  const Icon = a.direction === "up" ? TrendingUp : TrendingDown;
  return (
    <li className={cx("rounded-xl border px-3 py-2.5", a.tone === "warning" ? "border-warn/30 bg-warn-soft/50" : "border-good/30 bg-good-soft/50")}>
      <button className="flex w-full items-start gap-2 text-left" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <Icon className={cx("mt-0.5 h-4 w-4 shrink-0", a.tone === "warning" ? "text-warn" : "text-good")} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{a.title}<span className="sr-only">{a.tone === "warning" ? " (needs attention)" : " (good news)"}</span></span>
          <span className="block text-xs text-ink-2">{a.what}{a.context ? ` ${a.context}` : ""}</span>
        </span>
        <ChevronDown className={cx("mt-0.5 h-4 w-4 shrink-0 text-ink-3 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <dl className="mt-2 ml-6 space-y-1 text-xs text-ink-2">
          <div><dt className="inline font-semibold text-ink">Compared: </dt><dd className="inline">{a.period}</dd></div>
          <div><dt className="inline font-semibold text-ink">Calculation: </dt><dd className="inline">{a.calculation}</dd></div>
          <div><dt className="inline font-semibold text-ink">Source: </dt><dd className="inline">{a.source}{a.sample ? ` (${a.sample})` : ""}</dd></div>
          <div><dt className="inline font-semibold text-ink">Why it matters: </dt><dd className="inline">{a.why}</dd></div>
          <div><dt className="inline font-semibold text-ink">Next step: </dt><dd className="inline">{a.next_step}</dd></div>
        </dl>
      ) : null}
    </li>
  );
}

export function Disclaimer({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cx("text-xs text-ink-3", className)}>
      <button className="underline underline-offset-2 hover:text-ink" onClick={() => setOpen((v) => !v)} aria-expanded={open}>About these recommendations</button>
      {open ? (
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Recommendations are based on the data available at the time of analysis, and results depend on how complete it is.</li>
          <li>Estimates and patterns are not guarantees. Links between channels are correlations unless stated otherwise.</li>
          <li>Business decisions remain yours; the platform does not guarantee financial or commercial outcomes.</li>
          <li>Wording marked "AI" was written by an AI model from your figures, and every number in it was checked against your data.</li>
        </ul>
      ) : null}
    </div>
  );
}
