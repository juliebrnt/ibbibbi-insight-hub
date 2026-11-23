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
  if (path === "/refresh") return { ok: true, refreshed_at: s.__refreshed, live_connections: 0, results: [],
    note: "This prototype shows a fixed demo snapshot, so there is nothing new to fetch. In the real app, Refresh pulls the latest data from every connected account." };
  if (path === "/reply/draft") {
    const es = data?.language === "es" || data?.language === "ca";
    const neg = data?.sentiment === "negative";
    return { draft: es ? (neg ? "Gracias por contárnoslo y lo sentimos mucho. ¿Nos escribes un mensaje para ayudarte personalmente? El equipo de iBBIBBI" : "¡Muchísimas gracias por tus palabras! Nos alegra mucho. Un abrazo, el equipo de iBBIBBI")
      : (neg ? "Thank you for telling us, and we are sorry. Could you send us a message so we can help personally? The iBBIBBI team" : "Thank you so much for your kind words. It means a lot to us. The iBBIBBI team"), kind: neg ? "negative" : "positive" };
  }
  throw new PreviewOnly("This is a preview with sample data, so nothing is saved. In the real app this works with your own files.");
}

export async function staticQr() {
  return (await snapshot()).__qr as string;
}
