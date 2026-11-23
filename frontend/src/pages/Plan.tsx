import { useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Card, cx, Delta, PageHeader, PageSkeleton, ProgressRing, Sheet } from "@/components/ui";
import { usePage } from "@/hooks/useData";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useApp } from "@/lib/store";

export function Plan() {
  const { data: d, isLoading } = usePage("plan", false);
  const { ws } = useApp();
  const qc = useQueryClient();
  const [goalOpen, setGoalOpen] = useState(false);
  const [decOpen, setDecOpen] = useState<null | "decision" | "experiment">(null);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<any>(null);
  if (isLoading || !d) return <PageSkeleton />;
  const refresh = () => qc.invalidateQueries();
  const all = [...d.decisions, ...d.experiments];
  const due = all.filter((x: any) => x.due);
  const timeline = all.filter((x: any) => !search || `${x.title} ${x.hypothesis} ${x.learning || ""}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <>
      <PageHeader title="Plan and learn"
        what={`${d.goals.length} goals, ${all.filter((x: any) => x.status === "active").length} decisions in progress.`}
        why="Writing down what you tried and what happened turns guesses into knowledge."
        todo={due.length ? `Review ${due.length} decision${due.length > 1 ? "s" : ""}: what did you learn?` : "Turn a recommendation from Home into a decision with one tap."} />

      <div className="flex items-center justify-between"><h2 className="font-display text-xl font-semibold">Goals</h2>
        <button className="btn-soft !min-h-[40px]" onClick={() => setGoalOpen(true)} disabled={d.goals.length >= 3}><Plus className="h-4 w-4" />Add goal</button></div>
      <div className="mt-3 grid lg:grid-cols-3 gap-3">
        {d.goals.map((g: any) => (
          <Card key={g.id} className="flex items-center gap-4">
            <ProgressRing value={g.progress} size={72} />
            <div className="min-w-0 flex-1">
              <div className="font-medium leading-snug">{g.title}</div>
              <div className="mt-1 text-xs text-ink-3 num">Started {g.baseline_display} · now <b className="text-ink">{g.current_display}</b> · target {g.target_display}</div>
              {g.due ? <div className="text-xs text-ink-3">By {fmt.date(String(g.due))}</div> : null}
            </div>
            <div className="flex flex-col">
              <button className="btn-ghost !min-h-[34px] !px-2" aria-label="Edit goal" onClick={() => setEditing(g)}><Pencil className="h-4 w-4" /></button>
              <button className="btn-ghost !min-h-[34px] !px-2" aria-label="Remove goal" onClick={() => api.del(`/goals/${g.id}?ws=${ws}`).then(refresh)}><Trash2 className="h-4 w-4" /></button>
            </div>
          </Card>
        ))}
        {!d.goals.length ? <Card className="md:col-span-3 text-sm text-ink-2">Pick up to three goals, for example "Raise Instagram saves by 20%" or "NPS above 50". We track progress for you.</Card> : null}
      </div>

      {due.length ? (
        <>
          <h2 className="mt-8 font-display text-xl font-semibold flex items-center gap-2"><CalendarClock className="h-5 w-5 text-accent" />Ready to review</h2>
          <div className="mt-3 grid md:grid-cols-2 gap-3">{due.map((x: any) => <ReviewCard key={x.id} d={x} onDone={refresh} />)}</div>
        </>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center gap-2 justify-between">
        <h2 className="font-display text-xl font-semibold">Decisions and learning log</h2>
        <div className="flex flex-wrap gap-2">
          <label className="relative"><Search className="absolute left-3 top-3.5 h-4 w-4 text-ink-3" /><input className="input !pl-9 !min-h-[40px] w-full sm:w-48" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search decisions" /></label>
          <button className="btn-soft !min-h-[40px]" onClick={() => setDecOpen("decision")}><Plus className="h-4 w-4" />Decision</button>
          <button className="btn-outline !min-h-[40px]" onClick={() => setDecOpen("experiment")}><Plus className="h-4 w-4" />Experiment</button>
        </div>
      </div>
      <ol className="mt-4 relative border-l-2 border-line ml-2 space-y-4">
        {timeline.map((x: any) => (
          <li key={x.id} className="ml-5">
            <span className={cx("absolute -left-[7px] mt-5 h-3 w-3 rounded-full", x.learning ? "bg-good" : x.due ? "bg-accent" : "bg-primary")} />
            <Card className="!p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={cx("chip", x.kind === "experiment" ? "bg-accent-soft text-accent" : "bg-primary-soft text-primary")}>{x.kind === "experiment" ? "Experiment" : "Decision"}</span>
                <span className="chip bg-sunken text-ink-2">{x.status === "active" ? (x.due ? "Ready to review" : "In progress") : x.status === "kept" ? "Kept" : x.status === "dropped" ? "Dropped" : "Adjusted"}</span>
                <span className="text-ink-3">Started {fmt.date(String(x.baseline_end))} · review {fmt.date(String(x.review_date))} · {x.owner}</span>
                <button className="ml-auto text-ink-3 hover:text-ink" aria-label="Delete" onClick={() => api.del(`/decisions/${x.id}?ws=${ws}`).then(refresh)}><Trash2 className="h-4 w-4" /></button>
              </div>
              <div className="mt-2 font-medium">{x.title}</div>
              {x.hypothesis ? <div className="text-sm text-ink-2">Why: {x.hypothesis}</div> : null}
              {x.metric ? <div className="mt-2 text-sm num">{x.metric_label}: {x.baseline_display}{x.result_display || x.current_display ? <> → <b>{x.result_display || x.current_display}</b></> : null} <Delta change={x.change} /></div> : null}
              {x.learning ? <div className="mt-2 rounded-xl bg-good-soft px-3 py-2 text-sm"><b>What we learned:</b> {x.learning}</div> : null}
            </Card>
          </li>
        ))}
      </ol>
      <GoalSheet open={goalOpen} onOpenChange={setGoalOpen} metrics={d.metrics} onDone={refresh} />
      <EditGoal g={editing} onClose={() => setEditing(null)} onDone={refresh} />
      <DecisionSheet kind={decOpen} onOpenChange={() => setDecOpen(null)} metrics={d.metrics} onDone={refresh} />
    </>
  );
}

function ReviewCard({ d, onDone }: { d: any; onDone: () => void }) {
  const { ws } = useApp();
  const [text, setText] = useState("");
  const [outcome, setOutcome] = useState("kept");
  return (
    <Card className="!p-4 border-accent/40">
      <div className="font-medium">{d.title}</div>
      {d.metric ? <div className="mt-1 text-sm num">{d.metric_label}: {d.baseline_display} → <b>{d.current_display ?? "n/a"}</b> <Delta change={d.change} /></div> : null}
      <label className="mt-3 block text-sm font-medium" htmlFor={`l-${d.id}`}>What did we learn?</label>
      <textarea id={`l-${d.id}`} rows={2} className="input mt-1 py-2" value={text} onChange={(e) => setText(e.target.value)} placeholder="One or two sentences" />
      <div className="mt-2 flex flex-wrap gap-2">
        <select className="input !w-auto !min-h-[40px]" value={outcome} onChange={(e) => setOutcome(e.target.value)} aria-label="Outcome"><option value="kept">Keep doing it</option><option value="adjusted">Adjust it</option><option value="dropped">Stop it</option></select>
        <button className="btn-primary !min-h-[40px]" disabled={!text.trim()} onClick={() => api.post(`/decisions/${d.id}/review`, { learning: text, outcome, ws }).then(() => { toast.success("Saved to your learning log"); onDone(); })}>Save learning</button>
      </div>
    </Card>
  );
}

function GoalSheet({ open, onOpenChange, metrics, onDone }: any) {
  const { ws } = useApp();
  const [f, setF] = useState({ title: "", metric: "ig_saves", target: "", due: "" });
  const m = metrics.find((x: any) => x.key === f.metric);
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Add a goal" description="Pick something you can measure. We capture today's value as the starting point.">
      <div className="space-y-3">
        <input className="input" placeholder="Goal, e.g. Raise Instagram saves by 20%" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} aria-label="Goal" />
        <select className="input" value={f.metric} onChange={(e) => setF({ ...f, metric: e.target.value })} aria-label="Measure">{metrics.map((x: any) => <option key={x.key} value={x.key}>{x.label}</option>)}</select>
        <input className="input" type="number" step="any" placeholder={m?.unit === "pct" ? "Target as a decimal, e.g. 0.45 for 45%" : "Target value"} value={f.target} onChange={(e) => setF({ ...f, target: e.target.value })} aria-label="Target" />
        <input className="input" type="date" value={f.due} onChange={(e) => setF({ ...f, due: e.target.value })} aria-label="By when" />
        <button className="btn-primary w-full" disabled={!f.title || !f.target} onClick={() => api.post("/goals", { ...f, target: Number(f.target), due: f.due || null, ws }).then(() => { onOpenChange(false); onDone(); toast.success("Goal added"); }).catch((e) => toast.error(e.message))}>Save goal</button>
      </div>
    </Sheet>
  );
}

function DecisionSheet({ kind, onOpenChange, metrics, onDone }: any) {
  const { ws } = useApp();
  const [f, setF] = useState({ title: "", hypothesis: "", metric: "", review_date: "", owner: "" });
  return (
    <Sheet open={!!kind} onOpenChange={onOpenChange} title={kind === "experiment" ? "Start an experiment" : "Record a decision"} description="We capture the starting value and check back on the review date.">
      <div className="space-y-3">
        <input className="input" placeholder={kind === "experiment" ? "e.g. Post two Reels a week for four weeks" : "What did you decide?"} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} aria-label="Title" />
        <input className="input" placeholder="Why do you think it will work?" value={f.hypothesis} onChange={(e) => setF({ ...f, hypothesis: e.target.value })} aria-label="Hypothesis" />
        <select className="input" value={f.metric} onChange={(e) => setF({ ...f, metric: e.target.value })} aria-label="Measure to watch"><option value="">Measure to watch (optional)</option>{metrics.map((x: any) => <option key={x.key} value={x.key}>{x.label}</option>)}</select>
        <div className="grid grid-cols-2 gap-2"><input className="input" type="date" value={f.review_date} onChange={(e) => setF({ ...f, review_date: e.target.value })} aria-label="Review date" /><input className="input" placeholder="Owner" value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} aria-label="Owner" /></div>
        <button className="btn-primary w-full" disabled={!f.title} onClick={() => api.post("/decisions", { ...f, metric: f.metric || null, review_date: f.review_date || null, kind, ws }).then(() => { onOpenChange(); onDone(); toast.success("Added to your plan"); })}>Save</button>
      </div>
    </Sheet>
  );
}

function EditGoal({ g, onClose, onDone }: { g: any; onClose: () => void; onDone: () => void }) {
  const { ws } = useApp();
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [due, setDue] = useState("");
  if (!g) return null;
  return (
    <Sheet open={!!g} onOpenChange={onClose} title="Edit goal" description={`Measured by ${g.label}. Starting point ${g.baseline_display}.`}>
      <div className="space-y-3">
        <input className="input" defaultValue={g.title} onChange={(e) => setTitle(e.target.value)} aria-label="Goal" />
        <input className="input" type="number" step="any" defaultValue={g.target} onChange={(e) => setTarget(e.target.value)} aria-label="Target" />
        <input className="input" type="date" defaultValue={g.due ? String(g.due).slice(0, 10) : ""} onChange={(e) => setDue(e.target.value)} aria-label="By when" />
        <button className="btn-primary w-full" onClick={() => api.patch(`/goals/${g.id}`, { title: title || null, target: target ? Number(target) : null, due: due || null, ws })
          .then(() => { toast.success("Goal updated"); onClose(); onDone(); })}>Save changes</button>
      </div>
    </Sheet>
  );
}
