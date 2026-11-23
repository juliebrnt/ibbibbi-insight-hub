import { Command } from "cmdk";
import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3, Database, FileText, Heart, Home, LayoutGrid, Lightbulb, MessageCircleQuestion, Moon, MessagesSquare, Plus, QrCode,
  Search, Settings, Sun, Target, Upload, X, Zap, Monitor, PenLine,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useIsMobile, useLoadDemo, useStatus } from "@/hooks/useData";
import { RANGE_LABEL, useApp, type Range } from "@/lib/store";
import { brand } from "@/theme/tokens";
import { cx, Segmented } from "./ui";
import { STATIC } from "@/lib/static";
import { UploadFlow } from "./UploadFlow";
import { QuickCapture } from "./QuickCapture";
import { Tour } from "./Tour";

export const NAV = [
  { to: "/", label: "Home", icon: Home, hint: "What is working and what to do next" },
  { to: "/feedback", label: "Feedback", icon: MessagesSquare, hint: "What customers say and feel" },
  { to: "/social", label: "Social", icon: Heart, hint: "Which content works" },
  { to: "/sales", label: "Sales", icon: BarChart3, hint: "Sales, customers and the website" },
  { to: "/ask", label: "Ask", icon: MessageCircleQuestion, hint: "Ask a question in plain words" },
  { to: "/plan", label: "Plan", icon: Target, hint: "Goals, decisions and what you learned" },
  { to: "/data", label: "Data", icon: Database, hint: "Your files, privacy and export guides" },
];
const MORE = [
  { to: "/ask", label: "Ask", icon: MessageCircleQuestion },
  { to: "/plan", label: "Plan", icon: Target },
  { to: "/data", label: "Data", icon: Database },
  { to: "/briefing", label: "Weekly briefing", icon: FileText },
  { to: "/collect", label: "Collect feedback", icon: QrCode },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Logo({ small }: { small?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className={small ? "h-8 w-8" : "h-9 w-9"} />
      <div className="leading-tight">
        <div className="font-display font-semibold text-[17px] text-ink">{brand.name}</div>
        <div className="text-[11px] text-ink-3 -mt-0.5">{brand.product}</div>
      </div>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const mobile = useIsMobile();
  const { ws, setUploadOpen, uploadOpen, captureOpen, setCaptureOpen, setPaletteOpen, setDroppedFiles } = useApp();
  const loc = useLocation();
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if (e.key === "u" && !e.metaKey && !e.ctrlKey && !(e.target as HTMLElement)?.closest("input,textarea,[contenteditable]")) setUploadOpen(true);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [setPaletteOpen, setUploadOpen]);

  // Drop files anywhere to upload
  useEffect(() => {
    let depth = 0;
    const enter = (e: DragEvent) => { if (e.dataTransfer?.types.includes("Files")) { depth++; setDragging(true); } };
    const leave = () => { depth = Math.max(0, depth - 1); if (!depth) setDragging(false); };
    const over = (e: DragEvent) => e.preventDefault();
    const drop = (e: DragEvent) => {
      e.preventDefault(); depth = 0; setDragging(false);
      const files = Array.from(e.dataTransfer?.files || []);
      if (files.length) { setDroppedFiles(files); setUploadOpen(true); }
    };
    window.addEventListener("dragenter", enter); window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over); window.addEventListener("drop", drop);
    return () => { window.removeEventListener("dragenter", enter); window.removeEventListener("dragleave", leave); window.removeEventListener("dragover", over); window.removeEventListener("drop", drop); };
  }, [setDroppedFiles, setUploadOpen]);

  const isForm = loc.pathname.startsWith("/form");
  if (isForm) return <>{children}</>;

  return (
    <div className="min-h-screen md:pl-[232px]">
      {!mobile ? <Sidebar /> : null}
      <TopBar />
      {ws === "demo" ? <DemoBanner /> : null}
      <main id="main" className={cx("mx-auto max-w-[1240px] px-4 sm:px-6 lg:px-8 pt-4 sm:pt-6", mobile ? "pb-32" : "pb-16")}>
        <div key={loc.pathname} className="page-in">{children}</div>
      </main>
      {mobile ? <BottomTabs /> : null}
      <Fab />
      <UploadFlow open={uploadOpen} onOpenChange={setUploadOpen} />
      <QuickCapture open={captureOpen} onOpenChange={setCaptureOpen} />
      <Palette />
      <Tour />
      <AnimatePresence>
        {dragging ? (
          <motion.div className="fixed inset-0 z-[60] grid place-items-center bg-primary/15 backdrop-blur-sm pointer-events-none" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="card px-10 py-8 text-center border-2 border-dashed border-primary">
              <Upload className="mx-auto h-10 w-10 text-primary" />
              <p className="mt-3 font-display text-xl font-semibold">Drop to read your files</p>
              <p className="text-sm text-ink-2">Any export: CSV, Excel, JSON, PDF, text, ZIP or screenshots</p>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 w-[232px] border-r border-line bg-surface/70 backdrop-blur flex flex-col no-print" aria-label="Main">
      <div className="px-5 pt-5 pb-6"><Logo /></div>
      <nav className="flex-1 px-3 space-y-0.5">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === "/"} data-tour={n.label.toLowerCase()}
            className={({ isActive }) => cx("flex items-center gap-3 rounded-xl px-3 min-h-[44px] text-[15px] transition-colors",
              isActive ? "bg-primary-soft text-primary font-semibold" : "text-ink-2 hover:bg-sunken hover:text-ink")}>
            <n.icon className="h-[18px] w-[18px]" aria-hidden />{n.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-3 pb-4 space-y-0.5 border-t border-line pt-3">
        {MORE.slice(3).map((n) => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => cx("flex items-center gap-3 rounded-xl px-3 min-h-[40px] text-sm",
            isActive ? "text-primary font-semibold" : "text-ink-3 hover:text-ink hover:bg-sunken")}>
            <n.icon className="h-4 w-4" aria-hidden />{n.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}

function TopBar() {
  const { ws, setWs, range, setRange, setPaletteOpen, theme, setTheme } = useApp();
  const mobile = useIsMobile();
  const nav = useNavigate();
  return (
    <div className="sticky top-0 z-20 border-b border-line/70 bg-bg/85 backdrop-blur no-print">
      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 lg:px-8 h-[60px] flex items-center gap-2 sm:gap-3">
        {mobile ? <button onClick={() => nav("/")} aria-label="Home"><Logo small /></button> : null}
        <div className="flex-1" />
        <div data-tour="workspace">
          <Segmented size="sm" label="Workspace" value={ws} onChange={setWs} options={[{ value: "demo", label: mobile ? "Demo" : "Demo data" }, { value: "mine", label: mobile ? "Mine" : "My data" }]} />
        </div>
        {!mobile ? (
          <label className="relative">
            <span className="sr-only">Date range</span>
            <select value={range} onChange={(e) => setRange(e.target.value as Range)} className="input !min-h-[40px] !w-auto pr-8 cursor-pointer" data-tour="range">
              {Object.entries(RANGE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        ) : null}
        {!mobile ? (
          <button className="btn-outline !min-h-[40px] text-ink-3 !px-3" onClick={() => setPaletteOpen(true)} aria-label="Search and jump (Ctrl K)">
            <Search className="h-4 w-4" /><span className="hidden lg:inline">Jump to</span><kbd className="hidden lg:inline text-[11px] rounded bg-sunken px-1.5 py-0.5">⌘K</kbd>
          </button>
        ) : null}
        {!STATIC ? <button className="btn-ghost !min-h-[40px] !px-2.5" aria-label="Switch theme" title="Theme"
          onClick={() => setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light")}>
          {theme === "light" ? <Sun className="h-[18px] w-[18px]" /> : theme === "dark" ? <Moon className="h-[18px] w-[18px]" /> : <Monitor className="h-[18px] w-[18px]" />}
        </button> : null}
      </div>
    </div>
  );
}

function DemoBanner() {
  const status = useStatus();
  const load = useLoadDemo();
  const empty = status.data && !status.data.has_data;
  return (
    <div className="bg-accent-soft text-ink border-b border-line/60 no-print" role="status">
      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 lg:px-8 py-2 flex items-center gap-3 text-sm">
        <span className="chip bg-surface text-accent font-semibold">Demo</span>
        <span className="flex-1 min-w-0 truncate">{STATIC ? "Prototype with demo data (made-up customers). \u201cMy data\u201d shows what the founders see before they upload anything." : "Demo data, not real customers."}</span>
        {empty ? <button className="btn-primary !min-h-[34px] !px-3" onClick={() => load.mutate()} disabled={load.isPending}>{load.isPending ? "Loading…" : "Load demo data"}</button> : null}
      </div>
    </div>
  );
}

function BottomTabs() {
  const [more, setMore] = useState(false);
  const loc = useLocation();
  const tabs = NAV.slice(0, 4);
  const moreActive = MORE.some((m) => loc.pathname.startsWith(m.to));
  return (
    <>
      <nav className="fixed bottom-0 inset-x-0 z-30 border-t border-line bg-surface/95 backdrop-blur pb-safe no-print" aria-label="Main">
        <div className="grid grid-cols-5">
          {tabs.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) => cx("flex flex-col items-center justify-center gap-0.5 min-h-[58px] text-[11px]",
              isActive ? "text-primary font-semibold" : "text-ink-3")}>
              <n.icon className="h-[22px] w-[22px]" aria-hidden />{n.label}
            </NavLink>
          ))}
          <button onClick={() => setMore(true)} className={cx("flex flex-col items-center justify-center gap-0.5 min-h-[58px] text-[11px]", moreActive ? "text-primary font-semibold" : "text-ink-3")}>
            <LayoutGrid className="h-[22px] w-[22px]" aria-hidden />More
          </button>
        </div>
      </nav>
      <MoreSheet open={more} onOpenChange={setMore} />
    </>
  );
}

function MoreSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const nav = useNavigate();
  const { range, setRange } = useApp();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl bg-surface p-5 pb-8 shadow-lift pb-safe">
          <div className="mx-auto -mt-2 mb-3 h-1.5 w-10 rounded-full bg-line" aria-hidden />
          <Dialog.Title className="font-display text-xl font-semibold">More</Dialog.Title>
          <Dialog.Description className="sr-only">More destinations and the date range</Dialog.Description>
          <div className="mt-4 grid grid-cols-3 gap-3">
            {MORE.map((m) => (
              <button key={m.to} onClick={() => { onOpenChange(false); nav(m.to); }} className="card !shadow-none flex flex-col items-center justify-center gap-2 min-h-[88px] text-sm text-ink">
                <m.icon className="h-6 w-6 text-primary" aria-hidden />{m.label}
              </button>
            ))}
          </div>
          <div className="mt-5">
            <div className="label mb-2">Date range</div>
            <div className="scroll-x"><Segmented size="sm" label="Date range" value={range} onChange={setRange}
              options={(Object.keys(RANGE_LABEL) as Range[]).map((k) => ({ value: k, label: RANGE_LABEL[k].replace("Last ", "") }))} /></div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Fab() {
  const { setUploadOpen, setCaptureOpen } = useApp();
  const mobile = useIsMobile();
  const [open, setOpen] = useState(false);
  if (!mobile) {
    return (
      <button data-tour="upload" onClick={() => setUploadOpen(true)} className="fixed bottom-6 right-6 z-30 btn-primary !rounded-2xl shadow-lift !px-5 !min-h-[52px] no-print">
        <Upload className="h-5 w-5" /> Upload data
      </button>
    );
  }
  return (
    <div className="fixed right-4 bottom-[84px] z-30 flex flex-col items-end gap-2 no-print">
      <AnimatePresence>
        {open ? (
          <>
            <motion.button initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} onClick={() => { setOpen(false); setCaptureOpen(true); }}
              className="btn-outline shadow-lift !rounded-2xl"><PenLine className="h-4 w-4" />Log feedback</motion.button>
            <motion.button initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={{ delay: 0.03 }} onClick={() => { setOpen(false); setUploadOpen(true); }}
              className="btn-outline shadow-lift !rounded-2xl"><Upload className="h-4 w-4" />Upload a file or photo</motion.button>
          </>
        ) : null}
      </AnimatePresence>
      <button data-tour="upload" onClick={() => setOpen((v) => !v)} aria-label={open ? "Close" : "Add data"} aria-expanded={open}
        className="h-14 w-14 rounded-2xl bg-primary text-primary-ink shadow-lift grid place-items-center">
        <motion.span animate={{ rotate: open ? 45 : 0 }}><Plus className="h-7 w-7" /></motion.span>
      </button>
    </div>
  );
}

function Palette() {
  const { paletteOpen, setPaletteOpen, setUploadOpen, setCaptureOpen, setWs, setTheme } = useApp();
  const nav = useNavigate();
  const load = useLoadDemo();
  const go = (fn: () => void) => { setPaletteOpen(false); fn(); };
  const item = "flex items-center gap-3 rounded-xl px-3 min-h-[44px] text-sm text-ink cursor-pointer aria-selected:bg-primary-soft aria-selected:text-primary";
  return (
    <Command.Dialog open={paletteOpen} onOpenChange={setPaletteOpen} label="Jump to"
      overlayClassName="fixed inset-0 z-40 bg-black/30"
      contentClassName="fixed left-1/2 top-[14vh] z-50 w-[calc(100vw-32px)] max-w-lg -translate-x-1/2 rounded-2xl bg-surface shadow-lift overflow-hidden">
      <div className="flex items-center gap-2 border-b border-line px-4">
        <Search className="h-4 w-4 text-ink-3" />
        <Command.Input placeholder="Where do you want to go?" className="h-14 flex-1 bg-transparent outline-none text-[15px] placeholder:text-ink-3" />
        <button onClick={() => setPaletteOpen(false)} aria-label="Close" className="text-ink-3"><X className="h-4 w-4" /></button>
      </div>
      <Command.List className="max-h-[60vh] overflow-y-auto p-2">
        <Command.Empty className="p-4 text-sm text-ink-3">Nothing found.</Command.Empty>
        <Command.Group heading="Go to" className="text-xs text-ink-3 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2">
          {[...NAV, { to: "/briefing", label: "Weekly briefing", icon: FileText, hint: "One-page summary to share" }, { to: "/collect", label: "Collect feedback", icon: QrCode, hint: "Feedback form and QR code" }, { to: "/settings", label: "Settings", icon: Settings, hint: "AI, privacy and priorities" }].map((n) => (
            <Command.Item key={n.to} value={`${n.label} ${n.hint}`} onSelect={() => go(() => nav(n.to))} className={item}>
              <n.icon className="h-4 w-4" />{n.label}<span className="ml-auto text-xs text-ink-3 truncate">{n.hint}</span>
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Do" className="text-xs text-ink-3 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2">
          <Command.Item onSelect={() => go(() => setUploadOpen(true))} className={item}><Upload className="h-4 w-4" />Upload data<kbd className="ml-auto text-[11px] rounded bg-sunken px-1.5">U</kbd></Command.Item>
          <Command.Item onSelect={() => go(() => setCaptureOpen(true))} className={item}><PenLine className="h-4 w-4" />Log a piece of customer feedback</Command.Item>
          <Command.Item onSelect={() => go(() => load.mutate())} className={item}><Zap className="h-4 w-4" />Load demo data</Command.Item>
          <Command.Item onSelect={() => go(() => setWs("demo"))} className={item}><Lightbulb className="h-4 w-4" />Switch to demo data</Command.Item>
          <Command.Item onSelect={() => go(() => setWs("mine"))} className={item}><Database className="h-4 w-4" />Switch to my data</Command.Item>
          <Command.Item onSelect={() => go(() => setTheme("dark"))} className={item}><Moon className="h-4 w-4" />Dark theme</Command.Item>
          <Command.Item onSelect={() => go(() => setTheme("light"))} className={item}><Sun className="h-4 w-4" />Light theme</Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
