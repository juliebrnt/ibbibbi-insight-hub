import * as Dialog from "@radix-ui/react-dialog";
import * as Tip from "@radix-ui/react-tooltip";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CircleHelp, Frown, Meh, Smile, Table2, BarChart3, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useIsMobile } from "@/hooks/useData";
import { fmt } from "@/lib/format";
import { Sparkline } from "@/charts/charts";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className = "", as: As = "section" }: { children: ReactNode; className?: string; as?: any }) {
  return <As className={cx("card p-4 sm:p-5", className)}>{children}</As>;
}

export function Help({ text }: { text: string }) {
  return (
    <Tip.Root delayDuration={150}>
      <Tip.Trigger asChild>
        <button type="button" className="inline-grid place-items-center h-6 w-6 -m-1 rounded-full text-ink-3 hover:text-ink" aria-label="What does this mean?">
          <CircleHelp className="h-4 w-4" />
        </button>
      </Tip.Trigger>
      <Tip.Portal>
        <Tip.Content sideOffset={6} className="z-50 max-w-[260px] rounded-xl bg-ink px-3 py-2 text-xs leading-relaxed text-bg shadow-lift">
          {text}
          <Tip.Arrow className="fill-ink" />
        </Tip.Content>
      </Tip.Portal>
    </Tip.Root>
  );
}

/** A chart card with a finding-style title, period/source subtitle and a "view as table" toggle. */
export function ChartCard({ title, subtitle, children, table, columns, className = "", action, help }: {
  title: string; subtitle?: string; children: ReactNode; table?: Record<string, any>[]; columns?: { key: string; label: string; fmt?: (v: any) => string }[];
  className?: string; action?: ReactNode; help?: string;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Card className={cx("flex flex-col", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="h-card flex items-center gap-2">{title}{help ? <Help text={help} /> : null}</h3>
          {subtitle ? <p className="mt-1 text-xs text-ink-3">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-1 shrink-0 no-print">
          {action}
          {table && columns ? (
            <button className="btn-ghost !min-h-[36px] !px-2" onClick={() => setAsTable((v) => !v)} aria-label={asTable ? "View as chart" : "View as table"} title={asTable ? "View as chart" : "View as table"}>
              {asTable ? <BarChart3 className="h-4 w-4" /> : <Table2 className="h-4 w-4" />}
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-3 flex-1 min-w-0">{asTable && table && columns ? <DataTable rows={table} columns={columns} /> : children}</div>
    </Card>
  );
}

export function DataTable({ rows, columns, max = 50 }: { rows: Record<string, any>[]; columns: { key: string; label: string; fmt?: (v: any) => string }[]; max?: number }) {
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-ink-3">{columns.map((c) => <th key={c.key} className="px-1 py-2 font-medium text-xs">{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => (
            <tr key={i} className="border-t border-line/70">
              {columns.map((c) => <td key={c.key} className="px-1 py-2 num text-ink-2">{c.fmt ? c.fmt(r[c.key]) : (r[c.key] ?? "").toString()}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function useCountUp(target: number | null | undefined, ms = 600) {
  const reduce = useReducedMotion();
  const [v, setV] = useState<number | null>(target ?? null);
  const prev = useRef(0);
  useEffect(() => {
    if (target == null) return setV(null);
    if (reduce || document.hidden) return setV(target);
    const from = prev.current;
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - k, 3);
      setV(from + (target - from) * e);
      if (k < 1) raf = requestAnimationFrame(step);
      else prev.current = target;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms, reduce]);
  return v;
}

export function Delta({ change, goodWhenUp = true }: { change?: number | null; goodWhenUp?: boolean }) {
  if (change == null || !isFinite(change)) return null;
  const up = change > 0;
  const good = up === goodWhenUp;
  return (
    <span className={cx("chip num", Math.abs(change) < 1 ? "bg-sunken text-ink-2" : good ? "bg-good-soft text-good" : "bg-warn-soft text-warn")}>
      <span aria-hidden>{up ? "▲" : "▼"}</span>
      {Math.abs(change).toFixed(0)}%<span className="sr-only">{up ? " up" : " down"} on previous period</span>
    </span>
  );
}

export function KpiCard({ label, value, unit, change, spark, help, compact }: {
  label: string; value: number | null | undefined; unit: string; change?: number | null; spark?: (number | null)[]; help?: string; compact?: boolean;
}) {
  const v = useCountUp(value ?? null);
  const shown = v == null ? "n/a" : unit === "score" ? Math.round(v).toString() : fmt.unit(v, unit);
  return (
    <div className={cx("card flex flex-col justify-between", compact ? "p-3.5" : "p-4 sm:p-5")}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs sm:text-sm text-ink-2 truncate">{label}</span>
        {help ? <Help text={help} /> : null}
      </div>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-x-2 gap-y-1">
        <span className={cx("num font-display font-semibold text-ink leading-none whitespace-nowrap", compact ? "text-2xl" : "text-[28px] xl:text-[30px]")}>
          {shown}{unit === "stars" && v != null ? <span className="text-base text-ink-3"> / 5</span> : null}
        </span>
        <Delta change={change} />
      </div>
      {spark && spark.length > 1 && !compact ? <div className="mt-3"><Sparkline data={spark} /></div> : null}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-10 w-2/3" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>
      <div className="grid lg:grid-cols-2 gap-4"><Skeleton className="h-72" /><Skeleton className="h-72" /></div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, body, children }: { icon: any; title: string; body: string; children?: ReactNode }) {
  return (
    <div className="card p-8 sm:p-12 text-center flex flex-col items-center">
      <div className="h-16 w-16 rounded-3xl bg-primary-soft text-primary grid place-items-center"><Icon className="h-8 w-8" /></div>
      <h2 className="mt-5 font-display text-2xl font-semibold">{title}</h2>
      <p className="mt-2 max-w-md text-ink-2">{body}</p>
      {children ? <div className="mt-6 flex flex-wrap gap-3 justify-center">{children}</div> : null}
    </div>
  );
}

/** "What is happening, why it matters, what to do" at the top of every screen. */
export function PageHeader({ title, what, why, todo, right }: { title: string; what?: ReactNode; why?: ReactNode; todo?: ReactNode; right?: ReactNode }) {
  return (
    <header className="mb-5 sm:mb-7">
      <div className="flex items-start justify-between gap-4">
        <h1 className="h-page">{title}</h1>
        {right}
      </div>
      {what || why || todo ? (
        <div className="mt-4 grid gap-2.5 sm:grid-cols-3">
          {what ? <Brief label="What is happening" tone="primary">{what}</Brief> : null}
          {why ? <Brief label="Why it matters" tone="neutral">{why}</Brief> : null}
          {todo ? <Brief label="What to do" tone="accent">{todo}</Brief> : null}
        </div>
      ) : null}
    </header>
  );
}

function Brief({ label, tone, children }: { label: string; tone: "primary" | "neutral" | "accent"; children: ReactNode }) {
  const c = tone === "primary" ? "bg-primary-soft" : tone === "accent" ? "bg-accent-soft" : "bg-sunken";
  return (
    <div className={cx("rounded-2xl px-4 py-3", c)}>
      <div className="label !text-[11px]">{label}</div>
      <div className="mt-1 text-[15px] leading-snug text-ink">{children}</div>
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size = "md", label }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; size?: "sm" | "md"; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-xl bg-sunken p-1">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cx("rounded-lg px-3 font-medium transition-colors whitespace-nowrap", size === "sm" ? "min-h-[32px] text-xs" : "min-h-[38px] text-sm",
            value === o.value ? "bg-surface text-ink shadow-card" : "text-ink-2 hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Bottom sheet on phones, centred dialog on larger screens. */
export function Sheet({ open, onOpenChange, title, description, children, wide }: {
  open: boolean; onOpenChange: (v: boolean) => void; title: string; description?: string; children: ReactNode; wide?: boolean;
}) {
  const mobile = useIsMobile();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-describedby={description ? undefined : undefined}>
              <motion.div
                className={cx("fixed z-50 bg-surface shadow-lift flex flex-col focus:outline-none",
                  mobile ? "inset-x-0 bottom-0 max-h-[92dvh] rounded-t-3xl pb-safe" : cx("left-1/2 top-[6vh] -translate-x-1/2 max-h-[88vh] rounded-3xl w-[calc(100vw-32px)]", wide ? "max-w-4xl" : "max-w-xl"))}
                initial={mobile ? { y: "100%" } : { opacity: 0, y: 12, x: "-50%" }}
                animate={mobile ? { y: 0 } : { opacity: 1, y: 0, x: "-50%" }}
                exit={mobile ? { y: "100%" } : { opacity: 0, y: 12, x: "-50%" }}
                transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
              >
                {mobile ? <div className="mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-line" aria-hidden /> : null}
                <div className="flex items-start justify-between gap-3 px-5 pt-4 sm:px-6 sm:pt-6">
                  <div>
                    <Dialog.Title className="font-display text-xl font-semibold">{title}</Dialog.Title>
                    {description ? <Dialog.Description className="mt-1 text-sm text-ink-2">{description}</Dialog.Description> : null}
                  </div>
                  <Dialog.Close className="btn-ghost !min-h-[40px] !px-2.5 -mr-2" aria-label="Close"><X className="h-5 w-5" /></Dialog.Close>
                </div>
                <div className="overflow-y-auto px-5 pb-5 pt-3 sm:px-6 sm:pb-6">{children}</div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}

export function SentimentBadge({ s }: { s: string }) {
  const map: any = {
    positive: { Icon: Smile, c: "bg-good-soft text-good", l: "Positive" },
    neutral: { Icon: Meh, c: "bg-sunken text-ink-2", l: "Neutral" },
    negative: { Icon: Frown, c: "bg-warn-soft text-warn", l: "Negative" },
  };
  const m = map[s] || map.neutral;
  return <span className={cx("chip", m.c)}><m.Icon className="h-3.5 w-3.5" aria-hidden />{m.l}</span>;
}

export function Stars({ n }: { n?: number | null }) {
  if (n == null) return null;
  return <span className="text-accent text-sm tracking-tight" aria-label={`${n} out of 5 stars`}>{"★".repeat(Math.round(n))}<span className="text-line">{"★".repeat(5 - Math.round(n))}</span></span>;
}

export function ProgressRing({ value, size = 64, stroke = 7, label }: { value: number | null; size?: number; stroke?: number; label?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value ?? 0));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label || `${Math.round(v * 100)}% of the way`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="rgb(var(--sunken))" strokeWidth={stroke} fill="none" />
      <motion.circle cx={size / 2} cy={size / 2} r={r} stroke="rgb(var(--primary))" strokeWidth={stroke} fill="none" strokeLinecap="round"
        strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - v) }} transition={{ duration: 0.8, ease: "easeOut" }}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="num" fontSize={size / 4.2} fontWeight={600} fill="rgb(var(--ink))">
        {value == null ? "–" : `${Math.round(v * 100)}%`}
      </text>
    </svg>
  );
}

export function FadeIn({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  return <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay }}>{children}</motion.div>;
}
