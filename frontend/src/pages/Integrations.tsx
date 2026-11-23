import { locale } from "@/lib/i18n";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, Clock, KeyRound, Laptop, Loader2, Plug, RefreshCw, ShieldCheck, TriangleAlert, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { PlatformIcon } from "@/components/PlatformIcon";
import { Card, cx, PageHeader, PageSkeleton, Sheet } from "@/components/ui";
import { useIsMobile, usePage } from "@/hooks/useData";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { STATIC } from "@/lib/static";

export const STATUS: Record<string, { label: string; c: string }> = {
  connected: { label: "Connected", c: "bg-good-soft text-good" },
  uploaded: { label: "Data from your files", c: "bg-primary-soft text-primary" },
  demo: { label: "Demo data", c: "bg-accent-soft text-accent" },
  error: { label: "Sync error", c: "bg-warn-soft text-warn" },
  expired: { label: "Access expired", c: "bg-warn-soft text-warn" },
  available: { label: "Not connected", c: "bg-sunken text-ink-2" },
  coming_soon: { label: "Coming soon", c: "bg-sunken text-ink-3" },
};

export function when(s?: string | null) {
  if (!s) return "Never";
  const d = new Date(s.length === 10 ? s + "T00:00:00" : s);
  return d.toLocaleString(locale(), { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function useRefresh() {
  const { ws } = useApp();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    const t = toast.loading("Refreshing data from your connected sources…");
    try {
      const r = await api.post("/refresh", { ws });
      const failed = (r.results || []).filter((x: any) => x.status !== "ok");
      if (failed.length) toast.error(`${r.note}`, { id: t, duration: 8000 });
      else toast.success(r.note, { id: t, duration: 6000 });
      qc.invalidateQueries();
    } catch (e: any) {
      toast.error(e.message, { id: t });
    } finally {
      setBusy(false);
    }
  }
  return { run, busy };
}

export function RefreshButton({ compact }: { compact?: boolean }) {
  const { run, busy } = useRefresh();
  return (
    <button className={cx("btn-outline", compact && "!min-h-[38px] !px-3")} onClick={run} disabled={busy} data-tour="refresh">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Refresh data
    </button>
  );
}

export function Integrations() {
  const { data: d, isLoading } = usePage("integrations", false);
  const { ws, setUploadOpen } = useApp();
  const mobile = useIsMobile();
  const [connectKey, setConnectKey] = useState<string | null>(null);
  if (isLoading || !d) return <PageSkeleton />;
  const connected = d.integrations.filter((i: any) => ["connected", "uploaded", "demo", "error", "expired"].includes(i.status));
  return (
    <>
      <PageHeader title="Integrations"
        what={`${connected.length} source${connected.length === 1 ? "" : "s"} feeding your dashboards. Last refresh: ${when(d.last_refresh)}.`}
        why="Every page adapts to what is connected. More sources means sharper, cross-channel insights."
        todo={ws === "demo" ? "Switch to My data to connect your own accounts." : "Connect Shopify and Judge.me directly; upload exports for the rest."}
        right={<RefreshButton />} />

      {mobile ? (
        <div className="mb-4 flex gap-3 rounded-2xl bg-sunken p-4 text-sm"><Laptop className="h-5 w-5 text-ink-3 shrink-0" />
          <p>For security, connecting accounts and uploading data is done on a computer. On your phone you can view everything and refresh connected sources.</p></div>
      ) : null}

      {d.categories.map((cat: any) => {
        const items = d.integrations.filter((i: any) => i.category === cat.key);
        if (!items.length) return null;
        return (
          <section key={cat.key} className="mb-7">
            <h2 className="font-display text-xl font-semibold mb-3">{cat.label}</h2>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
              {items.map((i: any) => <IntegrationCard key={i.key} i={i} ws={ws} mobile={mobile} onConnect={() => setConnectKey(i.key)} onUpload={() => setUploadOpen(true)} />)}
            </div>
          </section>
        );
      })}

      <Card className="!p-4">
        <div className="flex gap-3 text-sm text-ink-2">
          <ShieldCheck className="h-5 w-5 text-good shrink-0" />
          <p>We never ask for your account passwords. Direct connections use an access key you create in the platform yourself, with read-only permissions where possible.
            Keys are stored encrypted on the server and never shown in the browser or saved in code. You can disconnect at any time, and should also remove the key in the platform to fully revoke access.</p>
        </div>
      </Card>
      <ConnectSheet k={connectKey} i={d.integrations.find((x: any) => x.key === connectKey)} onClose={() => setConnectKey(null)} />
    </>
  );
}

function IntegrationCard({ i, ws, mobile, onConnect, onUpload }: { i: any; ws: string; mobile: boolean; onConnect: () => void; onUpload: () => void }) {
  const [open, setOpen] = useState(false);
  const { ws: w } = useApp();
  const qc = useQueryClient();
  const st = STATUS[i.status] || STATUS.available;
  const live = i.live === "available";
  const isLive = ["connected", "error", "expired"].includes(i.status);
  async function disconnect() {
    const r = await api.del(`/connections/${i.key}?ws=${w}`);
    if (r.ok === false) return toast.error(r.error);
    toast(r.note);
    qc.invalidateQueries();
  }
  return (
    <Card className="!p-4 flex flex-col">
      <div className="flex items-start gap-3">
        <PlatformIcon icon={i.icon} name={i.name} k={i.key} size={40} />
        <div className="min-w-0 flex-1">
          <div className="font-medium leading-tight">{i.name}</div>
          <span className={cx("chip mt-1", st.c)}>{i.status === "connected" ? <CheckCircle2 className="h-3 w-3" /> : i.status === "error" || i.status === "expired" ? <TriangleAlert className="h-3 w-3" /> : null}{st.label}</span>
        </div>
      </div>
      <p className="mt-3 text-sm text-ink-2">{i.data.slice(0, 3).join(" · ")}</p>
      {i.error ? <p className="mt-2 rounded-xl bg-warn-soft px-3 py-2 text-xs text-warn">{i.error}</p> : null}
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div><dt className="text-ink-3">Last authorised</dt><dd className="num">{i.last_authorised ? when(i.last_authorised) : isLive ? "Unknown" : "Not applicable"}</dd></div>
        <div><dt className="text-ink-3">Last synchronised</dt><dd className="num">{when(i.last_synced)}</dd></div>
        {i.rows ? <div className="col-span-2"><dt className="text-ink-3">Data held</dt><dd className="num">{i.rows.toLocaleString(locale())} records{i.date_min ? `, ${new Date(i.date_min + "T00:00:00").toLocaleDateString(locale(), { month: "short", year: "numeric" })} to ${new Date(i.date_max + "T00:00:00").toLocaleDateString(locale(), { month: "short", year: "numeric" })}` : ""}</dd></div> : null}
      </dl>
      <button className="mt-3 flex items-center gap-1 text-xs font-medium text-primary" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        Requirements and permissions <ChevronDown className={cx("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <dl className="mt-2 space-y-2 rounded-xl bg-sunken p-3 text-xs text-ink-2">
          <div><dt className="font-semibold text-ink">Account needed</dt><dd>{i.account}</dd></div>
          <div><dt className="font-semibold text-ink">How it connects</dt><dd>{i.auth}</dd></div>
          {i.permissions.length ? <div><dt className="font-semibold text-ink">Permissions requested</dt><dd>{i.permissions.join(", ")}</dd></div> : null}
          <div><dt className="font-semibold text-ink">Data retrieved</dt><dd>{i.data.join(", ")}</dd></div>
          <div><dt className="font-semibold text-ink">Platform limits</dt><dd>{i.limits}</dd></div>
          <div><dt className="font-semibold text-ink">Approval or set-up</dt><dd>{i.approval}</dd></div>
          {i.upload ? <div><dt className="font-semibold text-ink">Until it is connected, upload</dt><dd>{i.upload}</dd></div> : null}
        </dl>
      ) : null}
      <div className="mt-auto pt-3 flex flex-wrap gap-2">
        {live && !isLive ? (
          <button className="btn-primary !min-h-[38px]" onClick={onConnect} disabled={mobile || ws === "demo" || STATIC}
            title={ws === "demo" ? "Switch to My data to connect" : mobile ? "Connect from a computer" : undefined}>
            <Plug className="h-4 w-4" />Connect
          </button>
        ) : null}
        {isLive && !mobile ? <button className="btn-outline !min-h-[38px]" onClick={disconnect}>Disconnect</button> : null}
        {!live ? <button className="btn-outline !min-h-[38px]" disabled title="Needs platform approval first"><Clock className="h-4 w-4" />Coming soon</button> : null}
        {i.upload && !mobile ? <button className="btn-ghost !min-h-[38px]" onClick={onUpload}><Upload className="h-4 w-4" />Upload export</button> : null}
      </div>
      {live && !isLive && (ws === "demo" || STATIC) ? <p className="mt-2 text-xs text-ink-3">{STATIC ? "Connecting works in the installed app with My data." : "Switch to My data to connect your own store."}</p> : null}
    </Card>
  );
}

function ConnectSheet({ k, i, onClose }: { k: string | null; i: any; onClose: () => void }) {
  const qc = useQueryClient();
  const [shop, setShop] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  if (!k || !i) return null;
  async function connect() {
    setBusy(true);
    try {
      const r = await api.post(`/connections/${k}`, { shop_domain: shop, token, ws: "mine" });
      if (!r.ok) return toast.error(r.error, { duration: 8000 });
      toast.success(`Connected to ${r.account}. ${r.sync?.message || ""}`, { duration: 7000 });
      setToken("");
      qc.invalidateQueries();
      onClose();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Sheet open={!!k} onOpenChange={onClose} title={`Connect ${i.name}`} description="Takes about five minutes. You create a read-only key in your own account; no platform review is needed.">
      <ol className="space-y-3">
        {(i.guide || []).map((s: string, n: number) => (
          <li key={n} className="flex gap-3 text-sm"><span className="h-7 w-7 shrink-0 rounded-full bg-primary-soft text-primary grid place-items-center text-sm font-semibold">{n + 1}</span><span className="pt-0.5">{s}</span></li>
        ))}
      </ol>
      <div className="mt-5 space-y-3">
        <label className="block text-sm font-medium" htmlFor="shop">Shop address</label>
        <input id="shop" className="input" placeholder="your-store.myshopify.com" value={shop} onChange={(e) => setShop(e.target.value)} autoComplete="off" />
        <label className="block text-sm font-medium" htmlFor="tok">{k === "shopify" ? "Admin API access token" : "Private API token"}</label>
        <input id="tok" className="input font-mono" type="password" placeholder="Paste the key here" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
        <p className="flex gap-2 text-xs text-ink-3"><KeyRound className="h-4 w-4 shrink-0" />The key is checked with {i.name}, then stored encrypted on the server. It is never shown again or sent to the browser.</p>
        <button className="btn-primary w-full" disabled={busy || !shop || token.length < 10} onClick={connect}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}Check and connect
        </button>
      </div>
    </Sheet>
  );
}
