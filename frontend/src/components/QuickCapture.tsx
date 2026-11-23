import { useQueryClient } from "@tanstack/react-query";
import { HeartHandshake } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cx, Sheet } from "./ui";

const SOURCES = ["Instagram DM", "WhatsApp", "Email", "In person", "Phone", "Market stall"];

/** Log a piece of customer feedback in under 10 seconds. */
export function QuickCapture({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { ws } = useApp();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [source, setSource] = useState(SOURCES[0]);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const r = await api.post("/feedback/quick", { text, source, ws });
      qc.invalidateQueries();
      onOpenChange(false);
      setText("");
      if (r.distress) toast("Saved. This sounds like someone having a hard time; consider a personal reply.", { icon: <HeartHandshake className="h-4 w-4" /> });
      else toast.success(`Saved${r.themes.length ? `: ${r.themes.join(", ").toLowerCase()}` : ""}`, {
        action: { label: "Undo", onClick: () => api.del(`/feedback/${r.id}?ws=${ws}`).then(() => qc.invalidateQueries()) },
      });
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Log customer feedback" description="Type or paste what a customer said. We will sort it into themes.">
      <textarea autoFocus value={text} onChange={(e) => setText(e.target.value)} rows={4} className="input py-3 text-base" placeholder="For example: 'Loved it, but I wish it came in green'" aria-label="Feedback" />
      <div className="mt-3 label">Where did it come from?</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {SOURCES.map((s) => (
          <button key={s} onClick={() => setSource(s)} className={cx("chip !px-3 !py-2 min-h-[36px] border", s === source ? "bg-primary text-primary-ink border-primary" : "bg-surface border-line text-ink-2")}>{s}</button>
        ))}
      </div>
      <button className="btn-primary w-full mt-5 !min-h-[52px]" disabled={text.trim().length < 3 || busy} onClick={save}>Save feedback</button>
      <p className="mt-2 text-xs text-ink-3 text-center">Emails and phone numbers are removed automatically.</p>
    </Sheet>
  );
}
