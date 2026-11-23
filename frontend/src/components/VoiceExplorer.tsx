import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Loader2, MessageSquareReply, Send, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmt, LANGS } from "@/lib/format";
import { STATIC } from "@/lib/static";
import { useApp } from "@/lib/store";
import { Card, cx, SentimentBadge, Sheet, Stars } from "./ui";

type F = { source: string; rating: string; sentiment: string; theme: string; from: string; to: string; q: string };
const EMPTY: F = { source: "", rating: "", sentiment: "", theme: "", from: "", to: "", q: "" };

/** Every review, survey answer, message and comment in one list, filterable, with an honest Reply option. */
export function VoiceExplorer() {
  const { ws } = useApp();
  const [f, setF] = useState<F>(EMPTY);
  const [reply, setReply] = useState<any>(null);
  const qs = new URLSearchParams({ ws, limit: "60", ...(f.source && { source: f.source }), ...(f.rating && { rating: f.rating }), ...(f.sentiment && { sentiment: f.sentiment }),
    ...(f.theme && { theme: f.theme }), ...(f.from && { date_from: f.from }), ...(f.to && { date_to: f.to }), ...(f.q && { q: f.q }) }).toString();
  const { data, isLoading } = useQuery({
    queryKey: ["voice", ws, STATIC ? "" : qs],
    queryFn: () => api.get(STATIC ? `/voice?ws=${ws}&limit=400` : `/voice?${qs}`),
  });
  const items = useMemo(() => {
    if (!data) return [];
    if (!STATIC) return data.items;
    return data.items.filter((r: any) => (!f.source || r.source === f.source) && (!f.sentiment || r.sentiment === f.sentiment)
      && (!f.theme || (r.themes || "").split(",").includes(f.theme)) && (!f.from || (r.date || "") >= f.from) && (!f.to || (r.date || "") <= f.to)
      && (!f.q || (r.text || "").toLowerCase().includes(f.q.toLowerCase()))
      && (!f.rating || (f.rating === "low" ? r.rating != null && r.rating <= 3 : f.rating === "high" ? r.rating >= 4 : String(r.rating) === f.rating))).slice(0, 60);
  }, [data, f]);
  const set = (k: keyof F) => (e: any) => setF({ ...f, [k]: e.target.value });
  const active = Object.values(f).some(Boolean);

  return (
    <section className="mt-6" aria-labelledby="voice-h">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="voice-h" className="font-display text-xl font-semibold">All customer feedback</h2>
          <p className="text-sm text-ink-2">Reviews, survey answers, messages and social comments from every connected source.</p>
        </div>
        {active ? <button className="btn-ghost !min-h-[36px]" onClick={() => setF(EMPTY)}>Clear filters</button> : null}
      </div>
      <div className="mt-3 grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2">
        <select className="input !min-h-[40px]" value={f.source} onChange={set("source")} aria-label="Platform">
          <option value="">All platforms</option>{(data?.sources || []).map((s: any) => <option key={s.source} value={s.source}>{s.source} ({s.n})</option>)}
        </select>
        <select className="input !min-h-[40px]" value={f.rating} onChange={set("rating")} aria-label="Rating">
          <option value="">Any rating</option><option value="high">4 to 5 stars</option><option value="low">1 to 3 stars</option>
          {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} stars</option>)}
        </select>
        <select className="input !min-h-[40px]" value={f.sentiment} onChange={set("sentiment")} aria-label="Sentiment">
          <option value="">Any feeling</option><option value="positive">Positive</option><option value="neutral">Neutral</option><option value="negative">Negative</option>
        </select>
        <select className="input !min-h-[40px]" value={f.theme} onChange={set("theme")} aria-label="Theme">
          <option value="">Any theme</option>{(data?.themes || []).map((t: any) => <option key={t.key} value={t.key}>{t.label}</option>)}
        </select>
        <input className="input !min-h-[40px]" type="date" value={f.from} onChange={set("from")} aria-label="From date" />
        <input className="input !min-h-[40px]" type="date" value={f.to} onChange={set("to")} aria-label="To date" />
        <input className="input !min-h-[40px] col-span-2 md:col-span-1" placeholder="Search words" value={f.q} onChange={set("q")} aria-label="Search" />
      </div>
      <p className="mt-2 text-xs text-ink-3 num">{isLoading ? "Loading…" : `Showing ${items.length} of ${STATIC ? items.length : data?.total ?? 0}`}</p>
      <div className="mt-2 grid md:grid-cols-2 gap-3">
        {items.map((r: any) => <FeedbackCard key={r.id} r={r} onReply={() => setReply(r)} />)}
      </div>
      {!isLoading && !items.length ? <Card className="mt-2 text-sm text-ink-2">Nothing matches these filters.</Card> : null}
      <ReplySheet r={reply} onClose={() => setReply(null)} />
    </section>
  );
}

export function FeedbackCard({ r, onReply }: { r: any; onReply?: () => void }) {
  return (
    <Card className="!p-4 flex flex-col">
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip bg-sunken text-ink-2">{r.platform && r.kind === "review" ? r.platform : r.source}</span>
        {r.example ? <span className="chip bg-accent-soft text-accent">Example, not real</span> : null}
        <SentimentBadge s={r.sentiment} /><Stars n={r.rating} />
        <span className="ml-auto text-xs text-ink-3">{fmt.date(r.date)}</span>
      </div>
      <p className="mt-2 text-[15px] leading-relaxed">{r.text}</p>
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-ink-3">
        {r.product ? <span>{String(r.product).split(" - ")[0]} ·</span> : null}
        {(r.theme_labels || r.themes || []).map((t: string) => <span key={t} className="chip bg-primary-soft text-primary">{t}</span>)}
        {r.language ? <span>{LANGS[r.language] || r.language}</span> : null}
      </div>
      {r.reply?.status === "published" ? <p className="mt-2 rounded-xl bg-good-soft px-3 py-2 text-xs"><b>Your reply (published):</b> {r.reply.text}</p> : null}
      {r.reply?.status === "failed" ? <p className="mt-2 rounded-xl bg-warn-soft px-3 py-2 text-xs">Your last reply could not be published. Try again.</p> : null}
      {onReply && r.reply?.status !== "published" ? (
        <div className="mt-auto pt-3"><button className="btn-soft !min-h-[38px]" onClick={onReply}><MessageSquareReply className="h-4 w-4" />Reply</button></div>
      ) : null}
    </Card>
  );
}

function ReplySheet({ r, onClose }: { r: any; onClose: () => void }) {
  const { ws } = useApp();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const draft = useQuery({
    queryKey: ["draft", r?.id], enabled: !!r,
    queryFn: () => api.post("/reply/draft", { text: r.text, sentiment: r.sentiment, themes: (r.themes || "").split(",").filter(Boolean), language: r.language, distress: !!r.distress }),
  });
  const value = text || draft.data?.draft || "";
  if (!r) return null;
  async function publish() {
    setBusy(true);
    try {
      const res = await api.post("/reply", { id: r.id, text: value, ws });
      if (!res.ok) toast.error(res.error, { duration: 8000 });
      else { toast.success("Reply published on the review"); qc.invalidateQueries({ queryKey: ["voice"] }); close(); }
    } catch (e: any) { toast.error(e.message); } finally { setBusy(false); }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { toast("Select the text and copy it"); }
  }
  function close() { setText(""); onClose(); }
  return (
    <Sheet open={!!r} onOpenChange={close} title="Reply to this customer" description={r.reply?.how}>
      <blockquote className="rounded-xl bg-sunken p-3 text-sm">“{r.text}”</blockquote>
      <label className="mt-4 flex items-center justify-between text-sm font-medium" htmlFor="reply-text">
        Your reply {draft.data ? <span className="chip bg-accent-soft text-accent font-normal"><Sparkles className="h-3 w-3" />{draft.data.ai_written ? "Suggested by AI" : "Suggested draft"}, edit before sending</span> : null}
      </label>
      <textarea id="reply-text" rows={5} className="input mt-1 py-2" value={value} onChange={(e) => setText(e.target.value)} />
      {r.distress ? <p className="mt-2 text-xs text-care">This person may be having a hard time. Keep the reply personal and gentle, with no selling.</p> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {r.reply?.direct ? (
          <button className="btn-primary" disabled={busy || value.trim().length < 2} onClick={publish}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Publish reply
          </button>
        ) : null}
        <button className="btn-outline" onClick={copy}>{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? "Copied" : "Copy reply"}</button>
        {r.reply?.url ? <a className="btn-ghost" href={r.reply.url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />Open {r.platform || "the platform"}</a> : null}
      </div>
      {!r.reply?.direct ? <p className={cx("mt-3 text-xs text-ink-3")}>Nothing is sent from here for this source. Copy the reply and post it on the platform.</p> : null}
    </Sheet>
  );
}

/** Made-up reviews shown before any review platform is connected, clearly labelled and never counted. */
export function ExampleReviews() {
  const { data } = useQuery({ queryKey: ["examples"], queryFn: () => api.get("/reviews/examples") });
  if (!data) return null;
  return (
    <section className="mt-6">
      <div className="rounded-2xl bg-accent-soft p-4 text-sm">
        <b>Example reviews.</b> {data.note} Connect Shopify reviews (Judge.me) on the Integrations page, or upload a reviews export, to see your real ones with a Reply button.
      </div>
      <div className="mt-3 grid md:grid-cols-2 gap-3">{data.items.map((r: any) => <FeedbackCard key={r.id} r={r} />)}</div>
    </section>
  );
}
