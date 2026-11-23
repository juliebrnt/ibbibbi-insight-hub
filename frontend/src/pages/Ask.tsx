import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Loader2, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Bars } from "@/charts/charts";
import { Card, cx, DataTable, PageHeader } from "@/components/ui";
import { useStatus } from "@/hooks/useData";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";

type Msg = { q: string; a?: any; loading?: boolean };

export function Ask() {
  const { ws } = useApp();
  const status = useStatus();
  const sugg = useQuery({ queryKey: ["ask-sugg"], queryFn: () => api.get("/ask/suggestions") });
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);

  async function ask(text: string) {
    if (!text.trim()) return;
    setQ("");
    setMsgs((m) => [...m, { q: text, loading: true }]);
    try {
      const a = await api.post("/ask", { question: text, ws });
      setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { q: text, a } : x)));
    } catch (e: any) {
      setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { q: text, a: { answer: e.message, ok: false } } : x)));
    }
  }
  const ai = status.data?.ai_enabled;
  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader title="Ask your data" />
      <p className="-mt-3 mb-5 text-sm text-ink-2">
        {ai ? <><Sparkles className="inline h-4 w-4 text-accent" /> AI is on: ask in your own words. Answers come only from your data, and every answer shows how it was worked out.</>
          : "Pick a question or type one. Answers come only from your data. Turn on AI in Settings to ask anything in your own words."}
      </p>
      <div className="space-y-5">
        {msgs.map((m, i) => (
          <div key={i}>
            <div translate="no" className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-ink">{m.q}</div>
            <div className="mt-3">{m.loading ? <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" />Looking at your data…</div> : <Answer a={m.a} onAsk={ask} />}</div>
          </div>
        ))}
        <div ref={end} />
      </div>
      {!msgs.length ? (
        <div className="grid sm:grid-cols-2 gap-2">
          {(sugg.data?.suggested || []).map((s: string) => (
            <button key={s} onClick={() => ask(s)} className="card !rounded-2xl text-left px-4 py-3 min-h-[52px] text-[15px] hover:border-primary transition-colors">{s}</button>
          ))}
        </div>
      ) : null}
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="sticky bottom-[76px] md:bottom-4 mt-6 flex gap-2 rounded-2xl bg-surface p-2 shadow-lift border border-line">
        <input value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 bg-transparent px-3 outline-none text-[15px] min-h-[44px]" placeholder="For example: which colour sells best?" aria-label="Your question" />
        <button className="btn-primary !px-4" disabled={!q.trim()} aria-label="Ask"><Send className="h-4 w-4" /></button>
      </form>
    </div>
  );
}

function Answer({ a, onAsk }: { a: any; onAsk: (q: string) => void }) {
  const [how, setHow] = useState(false);
  const cols = a.table?.length ? Object.keys(a.table[0]).filter((k) => k !== "dow").map((k) => ({ key: k, label: k.replace(/_/g, " ") })) : [];
  return (
    <Card className="!p-4 sm:!p-5">
      {a.ai_written ? <span className="chip bg-accent-soft text-accent mb-2"><Sparkles className="h-3 w-3" />Written by AI from your data</span> : null}
      <p className={cx("text-[15px] leading-relaxed", !a.ok && "text-ink-2")}>{a.answer}</p>
      {a.chart?.rows?.length ? <div className="mt-3"><Bars rows={a.chart.rows} x={a.chart.x} y={a.chart.y} horizontal={a.chart.rows.length > 5} height={Math.max(200, Math.min(360, a.chart.rows.length * 34))} label={a.chart.label} /></div> : null}
      {a.method ? (
        <div className="mt-3">
          <button className="text-xs text-primary font-medium flex items-center gap-1" onClick={() => setHow((v) => !v)} aria-expanded={how}>How I got this <ChevronDown className={cx("h-3.5 w-3.5", how && "rotate-180")} /></button>
          {how ? (
            <div className="mt-2 rounded-xl bg-sunken p-3 text-xs text-ink-2 space-y-2">
              <p>{a.method}</p>
              {a.sql ? <pre className="whitespace-pre-wrap font-mono text-[11px]">{a.sql}</pre> : null}
              {a.sources?.length ? <p>Data used: {a.sources.join(", ")}</p> : null}
              {cols.length ? <DataTable rows={a.table} columns={cols} max={20} /> : null}
            </div>
          ) : null}
        </div>
      ) : null}
      {a.followups?.length ? <div className="mt-3 flex flex-wrap gap-2">{a.followups.map((f: string) => <button key={f} onClick={() => onAsk(f)} className="chip bg-primary-soft text-primary !py-1.5">{f}</button>)}</div> : null}
    </Card>
  );
}
