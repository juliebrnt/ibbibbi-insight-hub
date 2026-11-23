import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Workspace = "demo" | "mine";
export type Range = "28d" | "90d" | "365d" | "all";
export type Theme = "light" | "dark" | "system";

type Ctx = {
  ws: Workspace;
  setWs: (w: Workspace) => void;
  range: Range;
  setRange: (r: Range) => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
  uploadOpen: boolean;
  setUploadOpen: (v: boolean) => void;
  captureOpen: boolean;
  setCaptureOpen: (v: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  droppedFiles: File[];
  setDroppedFiles: (f: File[]) => void;
};

const AppCtx = createContext<Ctx>(null as any);

function stored<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, v: string) {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* private mode */
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [ws, setWsState] = useState<Workspace>(() => (import.meta.env.VITE_STATIC === "1" ? "demo" : stored("ih-ws", "demo")));
  const [range, setRangeState] = useState<Range>(() => stored("ih-range", "90d"));
  const [theme, setThemeState] = useState<Theme>(() => stored("ih-theme", "system"));
  const [uploadOpen, setUploadOpen] = useState(false);
  const [captureOpen, setCaptureOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [droppedFiles, setDroppedFiles] = useState<File[]>([]);

  useEffect(() => {
    if (import.meta.env.VITE_STATIC === "1") return;
    const el = document.documentElement;
    if (theme === "system") delete el.dataset.theme;
    else el.dataset.theme = theme;
    window.dispatchEvent(new Event("themechange"));
  }, [theme]);

  return (
    <AppCtx.Provider
      value={{
        ws,
        setWs: (w) => (setWsState(w), save("ih-ws", w)),
        range,
        setRange: (r) => (setRangeState(r), save("ih-range", r)),
        theme,
        setTheme: (t) => (setThemeState(t), t === "system" ? (() => { try { localStorage.removeItem("ih-theme"); } catch { /* */ } })() : save("ih-theme", t)),
        uploadOpen,
        setUploadOpen,
        captureOpen,
        setCaptureOpen,
        paletteOpen,
        setPaletteOpen,
        droppedFiles,
        setDroppedFiles,
      }}
    >
      {children}
    </AppCtx.Provider>
  );
}

export const useApp = () => useContext(AppCtx);

export const RANGE_LABEL: Record<Range, string> = { "28d": "Last 4 weeks", "90d": "Last 3 months", "365d": "Last 12 months", all: "All time" };
