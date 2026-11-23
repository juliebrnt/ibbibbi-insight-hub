import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useEffect, useState } from "react";

/** Fetch a page payload for the current workspace and date range. */
export function usePage<T = any>(name: string, withRange = true) {
  const { ws, range } = useApp();
  const qs = `?ws=${ws}${withRange ? `&range=${range}` : ""}`;
  return useQuery<T>({ queryKey: [name, ws, withRange ? range : ""], queryFn: () => api.get<T>(`/${name}${qs}`) });
}

export function useStatus() {
  const { ws } = useApp();
  return useQuery({ queryKey: ["status", ws], queryFn: () => api.get(`/status?ws=${ws}`) });
}

export function useRefreshAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}

export function useLoadDemo() {
  const refresh = useRefreshAll();
  const { setWs } = useApp();
  return useMutation({
    mutationFn: () => api.post("/demo/load"),
    onSuccess: (r: any) => {
      setWs("demo");
      refresh();
      toast.success(`Demo data loaded: ${r.files.length} files read and analysed`);
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useMediaQuery(q: string) {
  const [m, setM] = useState(() => (typeof window !== "undefined" ? window.matchMedia(q).matches : false));
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [q]);
  return m;
}

export const useIsMobile = () => useMediaQuery("(max-width: 767px)");

/** Re-render charts when the theme changes. */
export function useThemeTick() {
  const [t, setT] = useState(0);
  useEffect(() => {
    const on = () => setT((x) => x + 1);
    window.addEventListener("themechange", on);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", on);
    return () => (window.removeEventListener("themechange", on), mq.removeEventListener("change", on));
  }, []);
  return t;
}
