import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Camera, Check, ClipboardPaste, FileUp, Loader2, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { STATIC } from "@/lib/static";
import { cx, Sheet } from "./ui";

type Staged = { upload_id: string; file_name: string; error?: string; tables: any[] };
type Step = "pick" | "reading" | "check" | "done";

/** Detect, Check, Import. A friendly stepper that works as a bottom sheet on phones. */
export function UploadFlow({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { ws, droppedFiles, setDroppedFiles } = useApp();
  const qc = useQueryClient();
  const [step, setStep] = useState<Step>("pick");
  const [items, setItems] = useState<{ up: Staged; t: any }[]>([]);
  const [errors, setErrors] = useState<{ name: string; error: string }[]>([]);
  const [idx, setIdx] = useState(0);
  const [results, setResults] = useState<any[]>([]);
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const target = ws === "demo" ? "demo" : "mine";

  useEffect(() => {
    if (open && droppedFiles.length) {
      const f = droppedFiles;
      setDroppedFiles([]);
      read(f);
    }
    if (!open) setTimeout(reset, 250);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function reset() {
    setStep("pick"); setItems([]); setErrors([]); setIdx(0); setResults([]); setPaste("");
  }

  async function read(files: File[]) {
    setStep("reading");
    try {
      const staged: Staged[] = await api.upload(files, target);
      ingest(staged);
    } catch (e: any) {
      toast.error(e.message); setStep("pick");
    }
  }
  async function readPaste() {
    if (!paste.trim()) return;
    setStep("reading");
    try { ingest([await api.post("/upload/paste", { text: paste, ws: target })]); } catch (e: any) { toast.error(e.message); setStep("pick"); }
  }
  function ingest(staged: Staged[]) {
    const its: { up: Staged; t: any }[] = [];
    const errs: { name: string; error: string }[] = [];
    staged.forEach((s) => {
      if (s.error) errs.push({ name: s.file_name, error: s.error });
      s.tables.forEach((t) => its.push({ up: s, t: { ...t, mode: "new_only", useFlexible: t.flexible_suggested } }));
    });
    setErrors(errs); setItems(its); setIdx(0);
    setTimeout(() => setStep(its.length ? "check" : "pick"), 700); // let the "reading" moment register
  }

  const cur = items[idx];
  function update(patch: any) {
    setItems((xs) => xs.map((x, i) => (i === idx ? { ...x, t: { ...x.t, ...patch } } : x)));
  }

  async function confirm() {
    const { up, t } = cur;
    setBusy(true);
    try {
      let res;
      if (t.kind === "image") {
        const r = await api.post(`/upload/${up.upload_id}/${t.index}/extract`);
        if (!r.ok) { toast.error(r.error); setBusy(false); return next({ ok: false, error: r.error, name: t.name }); }
        update(r.table); setBusy(false); return;
      }
      res = await api.post("/import", { upload_id: up.upload_id, index: t.index, table_type: t.useFlexible ? null : t.table_type, mapping: t.mapping,
        privacy: t.privacy, mode: t.mode, flexible: t.useFlexible, ws: target });
      if (!res.ok) { toast.error(res.error); setBusy(false); return; }
      next({ ...res, name: t.name });
    } catch (e: any) { toast.error(e.message); } finally { setBusy(false); }
  }
  function next(r: any) {
    const all = [...results, r];
    setResults(all);
    if (idx + 1 < items.length) setIdx(idx + 1);
    else { setStep("done"); qc.invalidateQueries(); }
  }
  async function undo(id: string) {
    await api.post(`/datasets/${id}/undo`);
    setResults((rs) => rs.map((r) => (r.dataset_id === id ? { ...r, undone: true } : r)));
    qc.invalidateQueries();
    toast("Import undone");
  }

  const steps = ["Detect", "Check", "Import"];
  const active = step === "pick" || step === "reading" ? 0 : step === "check" ? 1 : 2;

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Add your data" description={target === "demo" ? "Adding to the demo workspace." : "Adding to My data. Everything stays on this computer."} wide>
      <ol className="mb-5 flex items-center gap-2 text-sm" aria-label="Progress">
        {steps.map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span className={cx("grid h-7 w-7 place-items-center rounded-full text-xs font-semibold", i < active ? "bg-primary text-primary-ink" : i === active ? "bg-primary-soft text-primary ring-2 ring-primary/40" : "bg-sunken text-ink-3")}>
              {i < active ? <Check className="h-4 w-4" /> : i + 1}</span>
            <span className={i === active ? "font-medium" : "text-ink-3"}>{s}</span>
            {i < 2 ? <span className="mx-1 h-px w-6 bg-line" /> : null}
          </li>
        ))}
      </ol>

      {step === "pick" ? (
        <div className="space-y-4">
          {STATIC ? <div className="rounded-2xl bg-accent-soft p-4 text-sm"><b>This is a preview.</b> In the real app the founders drop in any export here (Shopify, Instagram, a survey, a spreadsheet, even a screenshot). It is recognised in seconds, personal data is removed, and every chart updates. The Demo workspace shows what that looks like.</div> : null}
          <button onClick={() => fileRef.current?.click()} className="w-full rounded-3xl border-2 border-dashed border-line hover:border-primary bg-sunken/50 p-8 text-center transition-colors">
            <FileUp className="mx-auto h-10 w-10 text-primary" />
            <div className="mt-3 font-display text-lg font-semibold">Drop files here or tap to choose</div>
            <div className="mt-1 text-sm text-ink-2">Shopify, Instagram, TikTok, Google Analytics, Klaviyo, surveys, any spreadsheet, PDF, text, ZIP or screenshots. Up to 50 MB each.</div>
          </button>
          <input ref={fileRef} type="file" multiple hidden onChange={(e) => e.target.files?.length && read(Array.from(e.target.files))} />
          <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => e.target.files?.length && read(Array.from(e.target.files))} />
          <div className="grid sm:grid-cols-2 gap-3">
            <button className="btn-outline" onClick={() => camRef.current?.click()}><Camera className="h-4 w-4" />Take a photo or screenshot</button>
            <a className="btn-outline" href="/api/demo/files/mercadillo_ventas.csv" download><Sparkles className="h-4 w-4" />Get a sample unknown file</a>
          </div>
          <div>
            <label className="label" htmlFor="paste">Or paste customer messages or a table</label>
            <textarea id="paste" value={paste} onChange={(e) => setPaste(e.target.value)} rows={4} className="input mt-2 py-2" placeholder="One message per paragraph. We will split them for you." />
            <button className="btn-soft mt-2" disabled={!paste.trim()} onClick={readPaste}><ClipboardPaste className="h-4 w-4" />Read pasted text</button>
          </div>
          {errors.map((e) => <Problem key={e.name} name={e.name} text={e.error} />)}
        </div>
      ) : null}

      {step === "reading" ? <Reading /> : null}

      {step === "check" && cur ? (
        <div>
          {errors.map((e) => <Problem key={e.name} name={e.name} text={e.error} />)}
          {items.length > 1 ? <p className="text-xs text-ink-3 mb-2">Table {idx + 1} of {items.length}</p> : null}
          <CheckTable t={cur.t} update={update} />
          <div className="sticky bottom-0 -mx-5 sm:-mx-6 mt-5 border-t border-line bg-surface px-5 sm:px-6 pt-4 flex flex-wrap gap-2 justify-end">
            <button className="btn-ghost" onClick={() => next({ skipped: true, name: cur.t.name })}>Skip this one</button>
            <button className="btn-primary" onClick={confirm} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              {cur.t.kind === "image" ? "Read with AI" : cur.t.recipe ? "Import (same as last time)" : "Looks right, import"}
            </button>
          </div>
        </div>
      ) : null}

      {step === "done" ? (
        <div className="space-y-3">
          <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex items-center gap-3 rounded-2xl bg-good-soft p-4">
            <div className="grid h-10 w-10 place-items-center rounded-full bg-good text-white"><Check className="h-5 w-5" /></div>
            <div><div className="font-semibold">Done. Your dashboards are updated.</div><div className="text-sm text-ink-2">Here is what we did with each file.</div></div>
          </motion.div>
          {results.map((r, i) => <Report key={i} r={r} onUndo={undo} />)}
          <div className="flex justify-end gap-2 pt-2"><button className="btn-outline" onClick={reset}>Add more</button><button className="btn-primary" onClick={() => onOpenChange(false)}>Close</button></div>
        </div>
      ) : null}
    </Sheet>
  );
}

function Reading() {
  const msgs = ["Reading your file", "Finding the real header row", "Checking dates and number formats", "Recognising where it came from", "Looking for personal data"];
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((x) => Math.min(x + 1, msgs.length - 1)), 260); return () => { clearInterval(t); }; }, []);
  return (
    <div className="py-10 text-center" role="status" aria-live="polite">
      <motion.div className="mx-auto h-16 w-16 rounded-3xl bg-primary-soft grid place-items-center" animate={{ rotate: [0, 6, -6, 0] }} transition={{ repeat: Infinity, duration: 1.4 }}>
        <FileUp className="h-8 w-8 text-primary" />
      </motion.div>
      <div className="mt-4 font-display text-lg font-semibold">{msgs[i]}…</div>
      <div className="mx-auto mt-4 h-1.5 w-48 overflow-hidden rounded-full bg-sunken"><motion.div className="h-full bg-primary" initial={{ width: "5%" }} animate={{ width: "95%" }} transition={{ duration: 1.4 }} /></div>
    </div>
  );
}

function Problem({ name, text }: { name: string; text: string }) {
  return <div className="flex gap-3 rounded-2xl bg-warn-soft p-3 text-sm mb-3"><TriangleAlert className="h-5 w-5 text-warn shrink-0" /><div><b>{name}</b><div className="text-ink-2">{text}</div></div></div>;
}

function CheckTable({ t, update }: { t: any; update: (p: any) => void }) {
  if (t.kind === "image") {
    return <div className="rounded-2xl bg-sunken p-4 text-sm"><b>{t.name}</b><p className="mt-1 text-ink-2">{t.message}</p></div>;
  }
  const fields = t.table_type ? t.fields[t.table_type] : [];
  const conf = Math.round((t.confidence || 0) * 100);
  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-primary-soft p-4">
        <div className="text-sm text-ink-2">{t.name} · {t.rows.toLocaleString("en-GB")} rows{t.delimiter ? ` · ${t.delimiter}-separated` : ""}{t.header_row > 1 ? ` · headers found on row ${t.header_row}` : ""}</div>
        {t.useFlexible ? (
          <div className="mt-1 font-display text-lg font-semibold">This looks like something new. We will keep it as your own dataset.</div>
        ) : (
          <div className="mt-1 font-display text-lg font-semibold">We think this is {t.label} <span className="chip bg-surface text-primary align-middle">{t.recipe ? "Saved recipe" : `${conf}% sure`}</span></div>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <select className="input !w-auto !min-h-[38px]" value={t.useFlexible ? "flexible" : t.table_type}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "flexible") update({ useFlexible: true });
              else { const c = t.candidates.find((c: any) => c.table_type === v); update({ useFlexible: false, table_type: v, mapping: c?.mapping || {}, label: c?.label || v }); }
            }} aria-label="What is this file?">
            {t.candidates.map((c: any) => <option key={c.table_type} value={c.table_type}>{c.label} ({Math.round(c.confidence * 100)}%)</option>)}
            <option value="flexible">Something else (keep as my own dataset)</option>
          </select>
          <select className="input !w-auto !min-h-[38px]" value={t.mode} onChange={(e) => update({ mode: e.target.value })} aria-label="If rows already exist">
            <option value="new_only">Add new rows only</option><option value="replace">Replace matching rows</option>
          </select>
        </div>
      </div>

      {!t.useFlexible ? (
        <details open={!t.recipe} className="rounded-2xl border border-line">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Check the columns ({Object.keys(t.mapping || {}).length} matched)</summary>
          <div className="divide-y divide-line">
            {fields.map((f: any) => {
              const m = t.mapping?.[f.name];
              return (
                <div key={f.name} className="grid grid-cols-[1fr_auto] sm:grid-cols-[1fr_1fr_auto] items-center gap-2 px-4 py-2 text-sm">
                  <div className="text-ink">{f.label}{f.required ? <span className="text-accent"> *</span> : null}</div>
                  <select className="input !min-h-[38px] col-span-2 sm:col-span-1 order-3 sm:order-none" value={m?.column || ""} aria-label={`Column for ${f.label}`}
                    onChange={(e) => update({ mapping: { ...t.mapping, [f.name]: e.target.value ? { column: e.target.value, score: 100 } : undefined } })}>
                    <option value="">Not in this file</option>
                    {t.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <span className={cx("chip justify-self-end", !m ? "bg-sunken text-ink-3" : m.score >= 90 ? "bg-good-soft text-good" : "bg-warn-soft text-warn")}>{!m ? "–" : m.score >= 90 ? "Sure" : "Check"}</span>
                </div>
              );
            })}
          </div>
        </details>
      ) : (
        <div className="rounded-2xl border border-line p-4 text-sm text-ink-2">
          We found {t.profile.filter((p: any) => p.type === "date").length} date column(s), {t.profile.filter((p: any) => p.type === "number").length} number column(s) and {t.profile.filter((p: any) => ["text", "category"].includes(p.type)).length} text column(s). After importing you can turn it into a trend, analyse its text, or ask questions about it.
        </div>
      )}

      {t.privacy?.length ? (
        <div className="rounded-2xl border border-line p-4">
          <div className="flex items-center gap-2 font-medium"><ShieldCheck className="h-5 w-5 text-good" />Personal data we found</div>
          <p className="mt-1 text-xs text-ink-3">This file relates to people affected by cancer. We keep only what is needed to find patterns.</p>
          <ul className="mt-3 space-y-2">
            {t.privacy.map((p: any, i: number) => (
              <li key={p.column} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="min-w-[140px] font-medium">{p.column}</span><span className="text-ink-3 text-xs">e.g. {p.example}</span>
                <select className="input !w-auto !min-h-[36px] ml-auto" value={p.action} aria-label={`What to do with ${p.column}`}
                  onChange={(e) => update({ privacy: t.privacy.map((x: any, j: number) => (j === i ? { ...x, action: e.target.value } : x)) })}>
                  <option value="drop">Do not store</option><option value="hash">Replace with anonymous id</option><option value="keep">Keep as is</option>
                </select>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <details className="rounded-2xl border border-line">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Preview the first rows</summary>
        <div className="overflow-x-auto px-2 pb-3">
          <table className="text-xs"><thead><tr>{t.columns.slice(0, 10).map((c: string) => <th key={c} className="px-2 py-1 text-left text-ink-3 font-medium whitespace-nowrap">{c}</th>)}</tr></thead>
            <tbody>{t.preview.map((r: any, i: number) => <tr key={i} className="border-t border-line">{t.columns.slice(0, 10).map((c: string) => <td key={c} className="px-2 py-1 whitespace-nowrap max-w-[180px] truncate">{r[c] ?? ""}</td>)}</tr>)}</tbody></table>
        </div>
      </details>
    </div>
  );
}

function Report({ r, onUndo }: { r: any; onUndo: (id: string) => void }) {
  if (r.skipped) return <div className="rounded-2xl bg-sunken p-3 text-sm text-ink-2">{r.name}: skipped</div>;
  if (!r.ok) return <Problem name={r.name} text={r.error} />;
  const rep = r.report || {};
  return (
    <div className="rounded-2xl border border-line p-4 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div><div className="font-medium">{r.name}</div><div className="text-ink-3">{r.flexible ? "Saved as your own dataset" : r.label}</div></div>
        {r.undone ? <span className="chip bg-sunken text-ink-3">Undone</span> : <button className="btn-ghost !min-h-[34px]" onClick={() => onUndo(r.dataset_id)}>Undo import</button>}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <span className="chip bg-good-soft text-good">{(rep.imported ?? 0).toLocaleString("en-GB")} imported</span>
        {rep.fixed ? <span className="chip bg-primary-soft text-primary">{rep.fixed.toLocaleString("en-GB")} values tidied</span> : null}
        {rep.skipped ? <span className="chip bg-warn-soft text-warn">{rep.skipped} skipped</span> : null}
        {rep.duplicates ? <span className="chip bg-sunken text-ink-2">{rep.duplicates} already there</span> : null}
      </div>
      <ul className="mt-2 list-disc pl-5 text-ink-2 space-y-0.5">{(rep.notes || []).map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
      {rep.issues?.length ? <details className="mt-2 text-ink-3"><summary className="cursor-pointer">{rep.issues.length} rows to look at</summary>
        <ul className="mt-1">{rep.issues.slice(0, 10).map((x: any, i: number) => <li key={i}>Row {x.row}: {x.problem}</li>)}</ul></details> : null}
      {r.flexible ? <Link to="/data" className="btn-soft mt-3">Turn it into a trend</Link> : null}
    </div>
  );
}
