import { useQueryClient } from "@tanstack/react-query";
import { FileStatus } from "@/components/FileStatus";
import { BookOpen, CheckCircle2, CircleDashed, Clock, FileSpreadsheet, ShieldCheck, TrendingUp, Undo2, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Card, cx, PageHeader, PageSkeleton, Sheet } from "@/components/ui";
import { usePage } from "@/hooks/useData";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useApp } from "@/lib/store";

export const GUIDES: Record<string, { name: string; steps: string[]; file?: string }> = {
  shopify: { name: "Shopify orders", file: "orders_export.csv", steps: ["Shopify admin → Orders", "Click Export (top right)", "Choose the dates (the first time, the last 12 months or more)", "Pick 'CSV for Excel, Numbers, or other spreadsheet programs', then Export orders. Large exports arrive by email.", "Upload the file here as it is. Do not open and re-save it first.", "Sales from markets kept in your own Excel also work: one row per sale with the date, the product and the amount."] },
  shopify_products: { name: "Shopify products", file: "products_export.csv", steps: ["Shopify admin → Products", "Click Export (top right)", "Choose All products and 'CSV for Excel, Numbers, or other spreadsheet programs'", "Click Export products and upload the file here."] },
  instagram: { name: "Instagram posts", file: "one CSV with a row per post", steps: ["Open Meta Business Suite on a computer (business.facebook.com)", "Insights → Content", "Choose Instagram, posts and the dates", "Click Export data → CSV", "Upload the file here. Or take a screenshot of Insights on your phone and upload it (AI reads it)."] },
  instagram_daily: { name: "Instagram account figures", file: "6 files: Visualizaciones, Alcance, Interacciones, Visitas, Seguidores, Clics en el enlace", steps: ["Open Meta Business Suite on a computer (business.facebook.com)", "Insights → Overview, and choose Instagram", "Pick the dates (the first time, as far back as it allows)", "Click Export data and choose CSV", "You get one file per figure: Visualizaciones, Alcance, Interacciones, Visitas, Seguidores and Clics en el enlace. Upload all six together, or the ZIP, without changing them."] },
  judgeme: { name: "Judge.me reviews", file: "a CSV of reviews", steps: ["Shopify admin → Apps → Judge.me", "Open Manage reviews", "Click Export reviews and choose CSV", "Upload the file here."] },
  tiktok: { name: "TikTok", steps: ["TikTok Studio on a computer → Analytics", "Pick Content and a date range", "Click Download data (XLSX)"] },
  ga4: { name: "Google Analytics 4", steps: ["Reports → Acquisition → Traffic acquisition", "Add 'Date' and 'Landing page' as secondary dimensions", "Share this report (top right) → Download file → CSV"] },
  klaviyo: { name: "Klaviyo", steps: ["Analytics → Campaigns", "Choose the last 12 months", "Export → CSV"] },
  forms: { name: "Customer survey", steps: ["Open the form → Responses", "Click the green Sheets icon", "File → Download → CSV or Excel", "Or use the built-in form in Collect: answers arrive here automatically."] },
};

export function Data() {
  const { data: d, isLoading } = usePage("datasets", false);
  const { setUploadOpen } = useApp();
  const qc = useQueryClient();
  const [guide, setGuide] = useState<string | null>(null);
  const [flex, setFlex] = useState<any>(null);
  if (isLoading || !d) return <PageSkeleton />;
  async function undo(id: string, name: string) {
    await api.post(`/datasets/${id}/undo`);
    qc.invalidateQueries();
    toast(`Removed ${name}`);
  }
  return (
    <>
      <PageHeader title="Your data"
        what={`${d.datasets.length} files imported.`} why="The more sources you add, the more reliable the insights become."
        todo={d.next ? <><span>{d.next.title}</span> <span>{d.next.todo}</span></> : "Everything is added. Download the latest exports once a month."}
        right={<button className="btn-primary hidden md:inline-flex" onClick={() => setUploadOpen(true)}><Upload className="h-4 w-4" />Upload</button>} />

      <WhatToAdd items={d.checklist || []} onGuide={setGuide} />

      <div className="space-y-3">
        {d.datasets.map((x: any) => (
          <Card key={x.id} className="!p-4">
            <div className="flex flex-wrap items-start gap-3">
              <div className="h-10 w-10 rounded-xl bg-primary-soft text-primary grid place-items-center shrink-0"><FileSpreadsheet className="h-5 w-5" /></div>
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{x.file_name}{x.sheet ? <span className="text-ink-3"> · {x.sheet}</span> : null}</div>
                <div className="text-sm text-ink-2">{x.flexible ? "Your own dataset" : x.source_label} · {x.rows_imported.toLocaleString("en-GB")} rows{x.date_min ? ` · ${fmt.date(String(x.date_min))} – ${fmt.date(String(x.date_max))}` : ""}</div>
                <div className="text-xs text-ink-3"><span>Added</span> <span>{fmt.date(String(x.created_at).slice(0, 10))}</span></div>
              </div>
              <span className={cx("chip", x.quality >= 0.95 ? "bg-good-soft text-good" : "bg-warn-soft text-warn")}>Quality {Math.round(x.quality * 100)}%</span>
              <div className="flex gap-1">
                {x.flexible ? <button className="btn-soft !min-h-[38px]" onClick={() => setFlex(x)}><TrendingUp className="h-4 w-4" />{x.flex_config?.trend ? "Edit trend" : "Make a trend"}</button> : null}
                <button className="btn-ghost !min-h-[38px]" onClick={() => undo(x.id, x.file_name)} title="Undo import"><Undo2 className="h-4 w-4" /><span className="sr-only">Undo import</span></button>
              </div>
            </div>
            <FileStatus e={x.explain} onMakeTrend={x.flexible && x.explain?.fixes?.some((f: string) => f.includes("Make a trend")) ? () => setFlex(x) : undefined} />
          </Card>
        ))}
      </div>

      <Card className="mt-6">
        <h2 className="h-card flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-good" />How we look after this data</h2>
        <ul className="mt-2 space-y-1.5 text-sm text-ink-2 list-disc pl-5">
          <li>Everything stays on this computer. Nothing is sent anywhere unless you switch AI analysis on.</li>
          <li>Names and addresses are not stored. Emails and phone numbers become anonymous ids, so repeat customers can be counted without knowing who they are.</li>
          <li><b>We never estimate anyone's health, personal circumstances or other sensitive traits</b> from what they buy or say, and never suggest targeting people that way.</li>
          <li>Messages from people having a hard time are flagged for a personal reply, never used in marketing. Quotes need consent.</li>
          <li>Export or delete everything at any time in Settings.</li>
        </ul>
      </Card>
      <Sheet open={!!guide} onOpenChange={() => setGuide(null)} title={guide ? `How to download: ${GUIDES[guide].name}` : ""} description={guide && GUIDES[guide].file ? `You will get: ${GUIDES[guide].file}` : undefined}>
        {guide ? <ol className="space-y-3">{GUIDES[guide].steps.map((s, i) => <li key={i} className="flex gap-3"><span className="h-7 w-7 shrink-0 rounded-full bg-primary-soft text-primary grid place-items-center text-sm font-semibold">{i + 1}</span><span className="pt-0.5">{s}</span></li>)}</ol> : null}
        <button className="btn-primary w-full mt-5" onClick={() => { setGuide(null); setUploadOpen(true); }}>I have the file, upload it</button>
      </Sheet>
      <FlexSheet ds={flex} onClose={() => setFlex(null)} />
    </>
  );
}

function FlexSheet({ ds, onClose }: { ds: any; onClose: () => void }) {
  const qc = useQueryClient();
  const cfg = ds?.flex_config;
  const cols = cfg?.columns || [];
  const [date, setDate] = useState("");
  const [value, setValue] = useState("");
  const [text, setText] = useState("");
  const [label, setLabel] = useState("");
  if (!ds) return null;
  const d = date || cfg.trend?.date || cfg.suggestion.date || "";
  const v = value || cfg.trend?.value || cfg.suggestion.value || "";
  async function save() {
    const vl = cols.find((c: any) => c.column === v)?.label;
    await api.post(`/datasets/${ds.id}/flex`, { trend: d && v ? { date: d, value: v, label: label || cfg.title, value_label: vl } : null, text_column: text || null });
    qc.invalidateQueries();
    toast.success(text ? "Trend saved and text analysed for feedback themes" : "Trend saved. Check Home for what it shows.");
    onClose();
  }
  return (
    <Sheet open={!!ds} onOpenChange={onClose} title="Make a trend from your file" description={`${ds.file_name}: pick a date and a number to follow over time.`}>
      <div className="space-y-3">
        <input className="input" placeholder="Name, e.g. Market stalls" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Name" />
        <label className="block text-sm">Date column<select className="input mt-1" value={d} onChange={(e) => setDate(e.target.value)}>{cols.filter((c: any) => c.type === "date").map((c: any) => <option key={c.column} value={c.column}>{c.label}</option>)}</select></label>
        <label className="block text-sm">Number to follow<select className="input mt-1" value={v} onChange={(e) => setValue(e.target.value)}>{cols.filter((c: any) => c.type === "number").map((c: any) => <option key={c.column} value={c.column}>{c.label}</option>)}</select></label>
        <label className="block text-sm">Also analyse a text column as feedback (optional)<select className="input mt-1" value={text} onChange={(e) => setText(e.target.value)}><option value="">No</option>{cols.filter((c: any) => ["text", "category"].includes(c.type)).map((c: any) => <option key={c.column} value={c.column}>{c.label}</option>)}</select></label>
        <button className="btn-primary w-full" onClick={save} disabled={!d || !v}>Save</button>
      </div>
    </Sheet>
  );
}

const STATUS: Record<string, { icon: any; cls: string; label: string }> = {
  ok: { icon: CheckCircle2, cls: "text-good", label: "Added" },
  partial: { icon: Clock, cls: "text-warn", label: "Part added" },
  old: { icon: Clock, cls: "text-warn", label: "Out of date" },
  missing: { icon: CircleDashed, cls: "text-ink-3", label: "Not added" },
};

/** The exact files that make the hub work, and what to download next for each. */
function WhatToAdd({ items, onGuide }: { items: any[]; onGuide: (g: string) => void }) {
  if (!items.length) return null;
  const done = items.filter((i) => i.status === "ok").length;
  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="h-card flex items-center gap-2"><BookOpen className="h-5 w-5 text-accent" />What to add</h2>
        <span className="text-sm text-ink-2 num"><span>{done}</span> <span>of</span> <span>{items.length}</span> <span>added</span></span>
      </div>
      <p className="mt-1 text-sm text-ink-2">These are the files the hub reads best. Download each one exactly as the platform gives it and upload it without changes.</p>
      <ul className="mt-3 divide-y divide-line">
        {items.map((it) => {
          const st = STATUS[it.status];
          const Icon = st.icon;
          return (
            <li key={it.key} className="py-3 flex flex-wrap items-start gap-3">
              <Icon className={cx("h-5 w-5 shrink-0 mt-0.5", st.cls)} />
              <div className="min-w-0 flex-1">
                <div className="font-medium"><span>{it.name}</span>{it.essential ? null : <span className="ml-2 chip bg-sunken text-ink-3">Optional</span>}</div>
                <div className="text-sm text-ink-2">{it.shows}</div>
                <div className={cx("mt-0.5 text-sm", it.status === "ok" ? "text-ink-3" : "text-ink")}>{it.status === "missing" ? it.todo : <><span>{it.detail}</span> <span>{it.todo}</span></>}</div>
              </div>
              <button className="btn-soft !min-h-[36px]" onClick={() => onGuide(it.guide)}>{it.status === "missing" ? "How to download it" : "Get the latest"}</button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
