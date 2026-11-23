/**
 * Prototype mode: the same app, reading saved snapshots of the demo data instead of a server.
 * Built with `VITE_STATIC=1` (see `make prototype`). Nothing is saved; actions show what would happen.
 */
export const STATIC = import.meta.env.VITE_STATIC === "1";

let snap: Promise<Record<string, any>> | null = null;
function snapshot() {
  if (!snap) {
    const inline = (window as any).__PROTOTYPE__;
    snap = inline ? Promise.resolve(inline) : fetch("prototype-data.json").then((r) => r.json());
  }
  return snap;
}

export class PreviewOnly extends Error {}

export async function staticGet(path: string) {
  const s = await snapshot();
  if (path in s) return structuredClone(s[path]);
  throw new PreviewOnly("This view is not part of the preview.");
}

let n = 0;
export async function staticPost(path: string, data: any) {
  const s = await snapshot();
  if (path === "/ask") {
    const q = String(data?.question || "").trim().toLowerCase().replace(/[?.!]+$/, "");
    const hit = Object.entries(s.__answers as Record<string, any>).find(([k]) => k.toLowerCase().replace(/[?.!]+$/, "") === q);
    if (hit) return structuredClone(hit[1]);
    return { ok: false, answer: "In this preview you can try the suggested questions. In the real app you can ask anything about your own data.", followups: s.__suggested };
  }
  if (path === "/decisions") {
    return { id: `preview_${++n}`, baseline_display: "your current value", metric_label: "Starting point captured:" };
  }
  if (path === "/feedback/quick" || path === "/collect/submit") return { ok: true, id: `p${++n}`, themes: [], distress: false };
  if (path === "/demo/load") return { ok: true, files: new Array(13).fill({}) };
  throw new PreviewOnly("This is a preview with sample data, so nothing is saved. In the real app this works with your own files.");
}

export async function staticQr() {
  return (await snapshot()).__qr as string;
}
