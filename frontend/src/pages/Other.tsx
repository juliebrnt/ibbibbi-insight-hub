/** Weekly briefing, Collect (form + QR), public feedback form and Settings. */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileDown, Printer, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { InsightCard } from "@/components/InsightCard";
import { Logo } from "@/components/Shell";
import { Card, Delta, PageHeader, PageSkeleton, ProgressRing } from "@/components/ui";
import { usePage } from "@/hooks/useData";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useApp } from "@/lib/store";
import { STATIC, staticQr } from "@/lib/static";

export function Briefing() {
  const { ws, range } = useApp();
  const { data: b, isLoading } = usePage("briefing");
  if (isLoading || !b) return <PageSkeleton />;
  return (
    <div className="max-w-3xl mx-auto">
      <div className={STATIC ? "hidden" : "no-print flex flex-wrap gap-2 justify-end mb-4"}>
        <button className="btn-outline" onClick={() => window.print()}><Printer className="h-4 w-4" />Print or save as PDF</button>
        <a className="btn-outline" href={`/api/briefing?ws=${ws}&range=${range}&format=html`} download={`briefing_${b.end}.html`}><FileDown className="h-4 w-4" />HTML</a>
        <a className="btn-outline" href={`/api/briefing?ws=${ws}&range=${range}&format=md`}><Download className="h-4 w-4" />Markdown</a>
      </div>
      <div className="flex items-center justify-between"><Logo /><span className="text-xs text-ink-3">{b.demo ? "Demo data, not real customers" : ""}</span></div>
      <h1 className="h-page mt-6">{b.title}</h1>
      <p className="text-sm text-ink-3">{b.period} ({fmt.date(b.start)} to {fmt.date(b.end)})</p>
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-3">
        {b.kpis.map((k: any) => <div key={k.label} className="card p-4"><div className="text-xs text-ink-3">{k.label}</div><div className="mt-1 font-display text-2xl font-semibold num">{k.value}</div><Delta change={k.change} /></div>)}
      </div>
      <h2 className="mt-8 font-display text-xl font-semibold">Top three insights</h2>
      <div className="mt-3 space-y-3">{b.insights.map((i: any, n: number) => <InsightCard key={i.id} ins={i} rank={n + 1} />)}</div>
      {b.changed.length ? <><h2 className="mt-8 font-display text-xl font-semibold">What changed</h2>
        <ul className="mt-2 card divide-y divide-line">{b.changed.map((c: any) => <li key={c.metric} className="flex justify-between p-3 text-sm"><span>{c.label}</span><span className="num">{c.prev_display} → <b>{c.display}</b> <Delta change={c.change} /></span></li>)}</ul></> : null}
      {b.goals.length ? <><h2 className="mt-8 font-display text-xl font-semibold">Goals</h2>
        <div className="mt-2 grid sm:grid-cols-3 gap-3">{b.goals.map((g: any) => <div key={g.id} className="card p-4 flex items-center gap-3"><ProgressRing value={g.progress} size={56} /><div className="text-sm">{g.title}<div className="text-xs text-ink-3">now {g.current_display}</div></div></div>)}</div></> : null}
      {b.learnings.length ? <><h2 className="mt-8 font-display text-xl font-semibold">Recent learnings</h2>
        <ul className="mt-2 space-y-2">{b.learnings.map((d: any) => <li key={d.id} className="card p-4 text-sm"><b>{d.title}:</b> {d.learning}</li>)}</ul></> : null}
      <p className="mt-8 text-xs text-ink-3">Every number comes from your uploaded data. Generated {b.generated.replace("T", " ")}.</p>
    </div>
  );
}

export function Collect() {
  const { ws } = useApp();
  const url = STATIC ? "https://your-shop.example/feedback" : `${window.location.origin}/form?ws=${ws === "demo" ? "demo" : "mine"}`;
  const sq = useQuery({ queryKey: ["qr"], queryFn: staticQr, enabled: STATIC });
  const qr = STATIC ? sq.data : `/api/collect/qr?url=${encodeURIComponent(url)}`;
  return (
    <>
      <PageHeader title="Collect feedback" what="A two-question form your customers can open from a QR code or link."
        why="Most customers never leave a review. A card in the parcel or at a market stall reaches the quiet ones, like parents buying for children."
        todo="Print the QR code on a small card for every parcel and market table." />
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="text-center">
          <img src={qr} alt="QR code for the feedback form" className="mx-auto w-56 h-56 rounded-xl bg-white p-2" />
          <p className="mt-3 text-sm break-all text-ink-2">{url}</p>
          <div className={STATIC ? "hidden" : "mt-3 flex justify-center gap-2 no-print"}>
            <a className="btn-outline" href={`/api/collect/qr?url=${encodeURIComponent(url)}`} download="feedback_qr.svg"><Download className="h-4 w-4" />Download QR</a>
            <a className="btn-soft" href={url} target="_blank" rel="noreferrer">Open the form</a>
          </div>
        </Card>
        <Card>
          <h3 className="h-card">What customers see</h3>
          <ul className="mt-3 text-sm text-ink-2 space-y-2 list-disc pl-5">
            <li>"How was your experience?" with 1 to 5 stars</li><li>"Tell us more" (optional free text, any language)</li>
            <li>Who it was for: me, a family member, my child, a gift</li><li>A clear consent tick before we may quote them</li>
          </ul>
          <p className="mt-3 text-sm text-ink-3">Answers appear in Feedback within seconds. No account, no tracking.</p>
        </Card>
      </div>
    </>
  );
}

export function PublicForm() {
  const ws = new URLSearchParams(window.location.search).get("ws") === "demo" ? "demo" : "mine";
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [who, setWho] = useState("");
  const [consent, setConsent] = useState(false);
  const [sent, setSent] = useState(false);
  async function submit() {
    try {
      await api.post("/collect/submit", { text: (text || "(no comment)") + (who ? ` [for: ${who}]` : ""), rating: rating || null, consent_quote: consent, ws, source: "Feedback form", line: who === "My child" ? "children" : null });
      setSent(true);
    } catch (e: any) { toast.error(e.message); }
  }
  return (
    <div className="min-h-screen bg-bg px-4 py-10">
      <div className="mx-auto max-w-md">
        <Logo />
        {sent ? (
          <Card className="mt-8 text-center"><h1 className="font-display text-2xl font-semibold">Thank you</h1><p className="mt-2 text-ink-2">Your words help us make headwear that feels like you.</p></Card>
        ) : (
          <Card className="mt-8">
            <h1 className="font-display text-2xl font-semibold">How was your experience?</h1>
            <div className="mt-4 flex gap-2" role="radiogroup" aria-label="Rating">
              {[1, 2, 3, 4, 5].map((n) => <button key={n} role="radio" aria-checked={rating === n} onClick={() => setRating(n)} className={`h-12 w-12 rounded-xl text-2xl ${n <= rating ? "bg-accent-soft text-accent" : "bg-sunken text-ink-3"}`}>★</button>)}
            </div>
            <label className="mt-5 block text-sm font-medium" htmlFor="t">Tell us more (any language)</label>
            <textarea id="t" rows={4} className="input mt-1 py-2" value={text} onChange={(e) => setText(e.target.value)} />
            <div className="mt-4 text-sm font-medium">Who was it for?</div>
            <div className="mt-2 flex flex-wrap gap-2">{["Me", "A family member", "My child", "A gift"].map((w) => <button key={w} onClick={() => setWho(w)} className={`chip !py-2 !px-3 border ${who === w ? "bg-primary text-primary-ink border-primary" : "border-line"}`}>{w}</button>)}</div>
            <label className="mt-4 flex gap-2 text-sm text-ink-2"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />You may quote my words (without my name).</label>
            <button className="btn-primary w-full mt-5" disabled={!rating && !text.trim()} onClick={submit}>Send</button>
            <p className="mt-3 text-xs text-ink-3">We do not ask for your name or email. Your answer is stored privately by iBBIBBI.</p>
          </Card>
        )}
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { ws } = useApp();
  const qc = useQueryClient();
  const { data: s, isLoading } = useQuery({ queryKey: ["settings", ws], queryFn: () => api.get(`/settings?ws=${ws}`) });
  const [confirm, setConfirm] = useState("");
  if (isLoading || !s) return <PageSkeleton />;
  const save = (patch: any) => api.post("/settings", { ...patch, ws }).then(() => { qc.invalidateQueries(); toast.success("Saved"); });
  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" />
      <Card>
        <h2 className="h-card flex items-center gap-2"><Sparkles className="h-5 w-5 text-accent" />AI analysis</h2>
        <label className="mt-3 flex items-center justify-between gap-4">
          <span className="text-sm text-ink-2">When on, short, anonymised summaries (no names, emails, phone numbers, handles or links) are sent to the AI service to word insights, answer free questions and read screenshots. Numbers are always checked against your data.</span>
          <input type="checkbox" className="h-6 w-6 accent-[rgb(var(--primary))]" checked={s.ai_enabled} onChange={(e) => save({ ai_enabled: e.target.checked })} disabled={!s.ai_configured} />
        </label>
        {!s.ai_configured ? <p className="mt-2 text-xs text-ink-3">No API key set. Add ANTHROPIC_API_KEY to the .env file to enable. Everything else works without it.</p> : null}
      </Card>
      <Card className="mt-4">
        <h2 className="h-card">What matters most right now</h2>
        <p className="text-sm text-ink-2">Recommendations are ranked by impact, confidence and these priorities.</p>
        <div className="mt-3 space-y-3">
          {Object.entries(s.priorities).map(([k, v]: any) => (
            <label key={k} className="grid grid-cols-[100px_1fr_32px] sm:grid-cols-[140px_1fr_40px] items-center gap-3 text-sm"><span>{k}</span>
              <input type="range" min={0} max={2} step={0.1} defaultValue={v} onMouseUp={(e) => save({ priorities: { ...s.priorities, [k]: Number((e.target as HTMLInputElement).value) } })} onTouchEnd={(e) => save({ priorities: { ...s.priorities, [k]: Number((e.target as HTMLInputElement).value) } })} />
              <span className="num text-ink-3">{Number(v).toFixed(1)}</span></label>
          ))}
        </div>
      </Card>
      <Card className="mt-4">
        <h2 className="h-card">Feedback themes</h2>
        <div className="mt-2 flex flex-wrap gap-2">{Object.values(s.themes).map((t: any) => <span key={t} className="chip bg-sunken text-ink-2">{t}</span>)}</div>
        <p className="mt-2 text-xs text-ink-3">Edit the keywords in backend/app/analytics/text.py (THEMES). Spanish, Catalan and English are supported.</p>
      </Card>
      <Card className="mt-4">
        <h2 className="h-card">Connectors (coming later)</h2>
        <ul className="mt-2 text-sm space-y-1">{s.connectors.map((c: any) => <li key={c.key} className="flex justify-between"><span>{c.name}</span><span className="text-ink-3">{c.configured ? "Configured" : "Upload files for now"}</span></li>)}</ul>
      </Card>
      <Card className="mt-4">
        <h2 className="h-card flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-warn" />Your data</h2>
        <label className="mt-3 flex items-center justify-between text-sm"><span>Delete customer messages and comments older than</span>
          <select className="input !w-auto" defaultValue={s.retention_days || ""} onChange={(e) => save({ retention_days: Number(e.target.value) || 0 })}><option value="">Keep</option><option value="365">1 year</option><option value="730">2 years</option></select></label>
        <div className="mt-4 flex flex-wrap gap-2">
          <a className={STATIC ? "hidden" : "btn-outline"} href={`/api/export?ws=${ws}`}><Download className="h-4 w-4" />Export everything (ZIP)</a>
        </div>
        <div className="mt-4 rounded-2xl bg-warn-soft p-4 text-sm">
          <b>Delete everything in this workspace.</b> This cannot be undone. Type DELETE to confirm.
          <div className="mt-2 flex gap-2"><input className="input !min-h-[40px]" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Type DELETE" />
            <button className="btn-primary !bg-warn !min-h-[40px]" disabled={confirm !== "DELETE"} onClick={() => api.post("/delete-all", { ws, confirm }).then(() => { setConfirm(""); qc.invalidateQueries(); toast("Deleted"); })}>Delete</button></div>
        </div>
      </Card>
    </div>
  );
}
