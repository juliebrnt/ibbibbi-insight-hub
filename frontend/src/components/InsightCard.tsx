import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ChevronDown, HeartHandshake, Lightbulb, Plus, Sparkles, Trophy, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cx } from "./ui";

const KIND: any = {
  opportunity: { Icon: Lightbulb, c: "bg-primary-soft text-primary", l: "Opportunity" },
  risk: { Icon: TriangleAlert, c: "bg-warn-soft text-warn", l: "Watch out" },
  care: { Icon: HeartHandshake, c: "bg-care-soft text-care", l: "Care first" },
  win: { Icon: Trophy, c: "bg-good-soft text-good", l: "Working well" },
};

export function InsightCard({ ins, rank, compact }: { ins: any; rank?: number; compact?: boolean }) {
  const { ws } = useApp();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [added, setAdded] = useState(false);
  const k = KIND[ins.kind] || KIND.opportunity;

  async function addToPlan() {
    try {
      const d = await api.post("/decisions", { title: ins.recommended_action.split(". ")[0].replace(/\.$/, ""), hypothesis: ins.title, metric: ins.metric,
        insight_id: ins.id, linked_goal: ins.linked_goal, ws });
      setAdded(true);
      qc.invalidateQueries({ queryKey: ["plan"] });
      toast.success(d.baseline_display ? `Added to Plan. Starting point: ${d.metric_label} ${d.baseline_display}` : "Added to Plan", {
        action: { label: "Undo", onClick: () => api.del(`/decisions/${d.id}?ws=${ws}`).then(() => { setAdded(false); qc.invalidateQueries({ queryKey: ["plan"] }); }) },
      });
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  return (
    <motion.article layout className={cx("card flex flex-col p-4 sm:p-5", compact && "h-full")}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className={cx("chip", k.c)}><k.Icon className="h-3.5 w-3.5" aria-hidden />{k.l}</span>
        <span className="chip bg-sunken text-ink-2">{ins.linked_goal}</span>
        {ins.ai_written ? <span className="chip bg-accent-soft text-accent"><Sparkles className="h-3 w-3" />Worded by AI, numbers checked</span> : null}
        {ins.urgency ? <span className={cx("chip", ins.urgency === "This week" ? "bg-accent-soft text-accent" : "bg-sunken text-ink-3")}>{ins.urgency}</span> : null}
        {rank ? <span className="ml-auto text-xs text-ink-3 num">#{rank}</span> : null}
      </div>
      <h3 className="mt-3 font-display text-[19px] leading-snug font-semibold">{ins.title}</h3>
      <p className="mt-2 text-sm text-ink-2 leading-relaxed">{ins.finding}</p>
      {!compact ? <p className="mt-2 text-sm text-ink-3 leading-relaxed">{ins.why_it_matters}</p> : null}
      <div className="mt-3 rounded-xl bg-accent-soft/70 px-3 py-2.5 text-sm"><b className="text-ink">Do this: </b><span className="text-ink-2">{ins.recommended_action}</span></div>
      {ins.measure && !compact ? <p className="mt-2 text-xs text-ink-2"><b className="text-ink">How to measure success: </b>{ins.measure}</p> : null}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3">
        <span>Effort: <b className="text-ink-2">{ins.effort}</b></span>
        <span>Confidence: <b className="text-ink-2">{Math.round(ins.confidence * 100)}%</b></span>
        <span className="min-w-0 max-w-full truncate">Impact: <b className="text-ink-2">{ins.expected_impact}</b></span>
      </div>
      <div className="mt-auto pt-3 flex items-center gap-2 flex-wrap">
        {ins.kind !== "care" ? (
          <button className={cx(added ? "btn-soft" : "btn-primary", "!min-h-[40px]")} onClick={addToPlan} disabled={added}>
            <Plus className="h-4 w-4" />{added ? "In your plan" : "Add to plan"}
          </button>
        ) : <Link to="/feedback#care" className="btn-primary !min-h-[40px]">See messages</Link>}
        <button className="btn-ghost !min-h-[40px]" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          Evidence <ChevronDown className={cx("h-4 w-4 transition-transform", open && "rotate-180")} />
        </button>
      </div>
      {open ? (
        <div className="mt-3 rounded-xl border border-line overflow-hidden">
          <table className="w-full text-xs">
            <tbody>
              {ins.evidence.map((e: any, i: number) => (
                <tr key={i} className="border-t first:border-t-0 border-line">
                  <td className="px-3 py-2 text-ink-2">{e.label}</td>
                  <td className="px-3 py-2 num font-semibold text-right">{e.value == null ? "n/a" : typeof e.value === "number" ? e.value.toLocaleString("en-GB") : e.value}</td>
                  <td className="px-3 py-2 text-ink-3 hidden sm:table-cell">{e.period} · {e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Link to={ins.page} className="block border-t border-line px-3 py-2 text-xs text-primary font-medium">Open the full analysis →</Link>
        </div>
      ) : null}
    </motion.article>
  );
}
