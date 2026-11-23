import { BookOpen, CheckCircle2, Circle, Lightbulb, MessagesSquare, ShieldCheck, ShoppingBag, Instagram, Target, Upload } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { GUIDES } from "@/pages/Data";
import { useApp } from "@/lib/store";
import { Card, cx, Sheet } from "./ui";

/** The first-day screen: what to bring, how to export it, and what the founders will get back. */
export function Onboarding({ have = [] as string[] }) {
  const { setWs, setUploadOpen } = useApp();
  const [guide, setGuide] = useState<string | null>(null);
  const steps = [
    { key: "orders", icon: ShoppingBag, title: "Shopify orders", why: "What sells, who comes back, busy months", guide: "shopify", time: "2 min" },
    { key: "social_posts", icon: Instagram, title: "Instagram posts", why: "Which content people save and share", guide: "instagram", time: "3 min" },
    { key: "feedback", icon: MessagesSquare, title: "Reviews, survey answers or messages", why: "What customers love and what to fix", guide: "forms", time: "2 min" },
    { key: "web_sessions", icon: BookOpen, title: "Website visits (optional)", why: "Where visitors come from and whether they buy", guide: "ga4", time: "3 min" },
  ];
  const done = steps.filter((s) => have.includes(s.key)).length;
  const preview = [
    { tag: "Marketing", title: "Reels earn 3.0x the saves of static posts", action: "Turn your two best static posts of the month into short Reels." },
    { tag: "Product", title: "Customers are asking for a wider colour range", action: "Run a two-option colour poll in Stories, then pre-order the winner." },
    { tag: "Market growth", title: "27 partnership enquiries are waiting for a reply", action: "Reply this week with a short partnership one-pager." },
  ];
  return (
    <div className="space-y-6">
      <header>
        <p className="label">Getting started</p>
        <h1 className="h-page mt-1">Welcome. Let us find out what your customers are telling you.</h1>
        <p className="mt-2 max-w-2xl text-ink-2">Bring the files you already have. About ten minutes of exporting gives you a dashboard that updates whenever you add more. Nothing leaves this computer.</p>
      </header>

      <div className="grid lg:grid-cols-[1.4fr_1fr] gap-4">
        <Card>
          <div className="flex items-center justify-between gap-3">
            <h2 className="h-card">Your first upload</h2>
            <span className="chip bg-primary-soft text-primary num">{done} of {steps.length} done</span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-sunken overflow-hidden"><div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(done / steps.length) * 100}%` }} /></div>
          <ol className="mt-4 divide-y divide-line">
            {steps.map((s) => {
              const ok = have.includes(s.key);
              return (
                <li key={s.key} className="flex items-center gap-3 py-3">
                  {ok ? <CheckCircle2 className="h-6 w-6 text-good shrink-0" aria-label="Done" /> : <Circle className="h-6 w-6 text-line shrink-0" aria-label="Not yet" />}
                  <s.icon className="h-5 w-5 text-ink-3 shrink-0" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className={cx("font-medium", ok && "text-ink-3 line-through")}>{s.title}</div>
                    <div className="text-sm text-ink-3">{s.why} · about {s.time}</div>
                  </div>
                  <button className="btn-ghost !min-h-[38px] text-primary" onClick={() => setGuide(s.guide)}>How to export</button>
                </li>
              );
            })}
          </ol>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="btn-primary" onClick={() => setUploadOpen(true)}><Upload className="h-4 w-4" />Upload files</button>
            <button className="btn-outline" onClick={() => setWs("demo")}>See it with demo data first</button>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="h-card flex items-center gap-2"><Lightbulb className="h-5 w-5 text-accent" />What you will get back</h2>
            <p className="mt-1 text-sm text-ink-3">Examples from the demo shop. Yours will come from your own data.</p>
            <ul className="mt-3 space-y-3">
              {preview.map((p) => (
                <li key={p.title} className="rounded-xl bg-sunken p-3">
                  <span className="chip bg-surface text-ink-2">{p.tag}</span>
                  <div className="mt-1.5 font-display font-semibold leading-snug">{p.title}</div>
                  <div className="mt-1 text-sm text-ink-2"><b className="text-ink">Do this:</b> {p.action}</div>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="!p-4">
            <div className="flex gap-3 text-sm">
              <ShieldCheck className="h-5 w-5 text-good shrink-0" />
              <p className="text-ink-2">Names and addresses are never stored, emails become anonymous ids, and nobody's health is ever guessed from what they buy. <Link to="/data" className="text-primary font-medium">How we protect data</Link></p>
            </div>
          </Card>
          <Card className="!p-4">
            <div className="flex gap-3 text-sm">
              <Target className="h-5 w-5 text-primary shrink-0" />
              <p className="text-ink-2">Once data is in, set up to three goals in <Link to="/plan" className="text-primary font-medium">Plan</Link> and check them each week in about fifteen minutes.</p>
            </div>
          </Card>
        </div>
      </div>

      <Sheet open={!!guide} onOpenChange={() => setGuide(null)} title={guide ? `How to export from ${GUIDES[guide].name}` : ""}>
        {guide ? <ol className="space-y-3">{GUIDES[guide].steps.map((s, i) => <li key={i} className="flex gap-3"><span className="h-7 w-7 shrink-0 rounded-full bg-primary-soft text-primary grid place-items-center text-sm font-semibold">{i + 1}</span><span className="pt-0.5">{s}</span></li>)}</ol> : null}
        <button className="btn-primary w-full mt-5" onClick={() => { setGuide(null); setUploadOpen(true); }}>I have the file, upload it</button>
      </Sheet>
    </div>
  );
}
