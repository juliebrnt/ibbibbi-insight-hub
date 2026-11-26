/**
 * Spanish translation for everything on screen: interface text, generated insights, alerts, tooltips.
 * Same rules as shared/i18n_core.py (keep them in step): exact match, then a template with numbers,
 * months and weekdays as {0}, {1}…, then wildcard patterns where {x}/{y} are names and {z} is kept as written.
 * Customer words (reviews, comments, product names) are marked translate="no" and are never changed.
 */
const files = import.meta.glob("../../../shared/i18n/es*.json", { eager: true }) as Record<string, any>;

const MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const ABBR_EN = MONTHS_EN.map((m) => m.slice(0, 3));
const ABBR_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"];
const DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const WORDS: Record<string, string> = {};
MONTHS_EN.forEach((m, i) => (WORDS[m] = MONTHS_ES[i]));
ABBR_EN.forEach((m, i) => (WORDS[m] = ABBR_ES[i]));
DAYS_EN.forEach((m, i) => (WORDS[m] = DAYS_ES[i]));
WORDS.May = "mayo"; // the full name and the abbreviation are the same word in English

const TOKEN = new RegExp(`\\d[\\d,.]*\\d|\\d|\\b(?:${[...MONTHS_EN, ...DAYS_EN].join("|")})\\b|\\b(?:${ABBR_EN.join("|")})\\b(?!\\w)`, "g");
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const exact = new Map<string, string>();
const patterns: { rx: RegExp; es: string; groups: string[] }[] = [];
for (const data of Object.values(files)) {
  const d = data.default ?? data;
  for (const [en, es] of Object.entries<string>(d.strings || {})) {
    exact.set(en, es);
    const low = en.charAt(0).toLowerCase() + en.slice(1);
    if (/^[A-Z]/.test(en) && en !== en.toUpperCase() && !exact.has(low)) exact.set(low, es.charAt(0).toLowerCase() + es.slice(1));
  }
  for (const [en, es] of Object.entries<string>(d.patterns || {})) {
    const groups: string[] = [];
    const rx = esc(en).replace(/\\\{([xyz])\\\}/g, (_m, g) => (groups.push(g), g === "z" ? "(.*)" : "(.+?)"));
    patterns.push({ rx: new RegExp(`^${rx}$`), es, groups });
  }
}

function templatize(s: string): [string, string[]] {
  const vals: string[] = [];
  const t = s.replace(/\{/g, "{{").replace(/\}/g, "}}").replace(TOKEN, (m) => (vals.push(m), `{${vals.length - 1}}`));
  return [t, vals];
}

function esValue(v: string) {
  if (WORDS[v]) return WORDS[v];
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$|^\d+\.\d+$/.test(v)) return v.replace(/,/g, "\u0000").replace(/\./g, ",").replace(/\u0000/g, ".");
  return v;
}

function fill(t: string, vals: string[]) {
  return t.replace(/\{(\d+)\}/g, (_m, i) => esValue(vals[+i] ?? "")).replace(/\{\{/g, "{").replace(/\}\}/g, "}");
}

const untemplate = (part: string, vals: string[]) => part.replace(/\{(\d+)\}/g, (m, i) => vals[+i] ?? m);
const cap = (src: string, out: string) => (/^[A-Z]/.test(src) && /^[a-záéíóú]/.test(out) ? out.charAt(0).toUpperCase() + out.slice(1) : out);

function core(s: string): string {
  if (exact.has(s)) return exact.get(s)!;
  const [t, vals] = templatize(s);
  if (exact.has(t)) return fill(exact.get(t)!, vals);
  if (vals.length && !/[A-Za-z]/.test(t.replace(/[{}]/g, ""))) {
    return fill(t.replace(/€\{(\d+)\}/g, "{$1} €").replace(/\{(\d+)\}%/g, "{$1} %"), vals);
  }
  for (const p of patterns) {
    const m = p.rx.exec(t);
    if (!m) continue;
    let out = p.es;
    p.groups.forEach((g, i) => {
      const raw = untemplate(m[i + 1], vals);
      let tr = g === "z" ? raw : translate(raw);
      if (tr !== raw && !p.es.startsWith(`{${g}}`)) tr = tr.charAt(0).toLowerCase() + tr.slice(1);
      out = out.replace(`{${g}}`, () => tr);
    });
    const result = fill(out, vals);
    if (result !== s) return result;
  }
  return s;
}

function sentence(p: string): string {
  const t = translate(p + ".");
  return t !== p + "." && t.endsWith(".") ? t.slice(0, -1) : translate(p);
}

function full(s: string): string {
  const r = core(s);
  if (r !== s) return r;
  for (const sep of [" · ", ". "]) {
    if (!s.includes(sep)) continue;
    const parts = s.split(sep);
    // a sentence split off at ". " keeps its full stop while it is looked up
    const out = parts.map((p, i) => (sep === ". " && i < parts.length - 1 ? sentence(p) : translate(p)));
    if (out.some((o, i) => o !== parts[i])) return out.join(sep);
  }
  const last = s.slice(-1);
  if ((last === "." || last === ":") && s.length > 3) {
    const inner = core(s.slice(0, -1));
    if (inner !== s.slice(0, -1)) return inner + last;
  }
  return s;
}

const cache = new Map<string, string>();
export function translate(s: string): string {
  const k = s.trim();
  // Numbers alone are translated too (30,312 € style), anything else without letters is left as it is.
  if (!k || !/[A-Za-z]|\d[.,]\d|[€%]/.test(k)) return s;
  let out = cache.get(k);
  if (out === undefined) {
    out = cap(k, full(k));
    cache.set(k, out);
  }
  if (out === k) return s;
  const lead = s.slice(0, s.length - s.trimStart().length);
  const trail = s.slice(s.trimEnd().length);
  return lead + out + trail;
}

/* ---------------- live DOM translation ---------------- */
const ATTRS = ["placeholder", "aria-label", "title"];
const original = new WeakMap<Node, string>();
const shown = new WeakMap<Node, string>();
const origAttr = new WeakMap<Element, Record<string, string>>();
let observer: MutationObserver | null = null;
let active = false;

const skip = (el: Element | null) => !!el?.closest('[translate="no"], script, style, textarea, code, pre');

/** Original text of a node, ignoring our own translation of it. */
const src = (n: Text) => (shown.get(n) === n.nodeValue && original.has(n) ? original.get(n)! : n.nodeValue || "");

/**
 * React writes `{n} sources` as two text nodes ("8", " sources"), which mean nothing on their own.
 * When an element holds only text, translate the joined sentence and put it in the first node.
 */
function doGroup(parent: Element): boolean {
  const nodes = Array.from(parent.childNodes);
  if (nodes.length < 2 || !nodes.every((x) => x.nodeType === Node.TEXT_NODE)) return false;
  const texts = nodes as Text[];
  const parts = texts.map(src);
  const whole = parts.join("");
  const es = translate(whole);
  texts.forEach((t, i) => original.set(t, parts[i]));
  const out = es !== whole ? [es, ...parts.slice(1).map(() => "")] : texts.map((t) => translate(parts[texts.indexOf(t)]));
  texts.forEach((t, i) => {
    shown.set(t, out[i]);
    if (t.nodeValue !== out[i]) t.nodeValue = out[i];
  });
  return true;
}

function doText(n: Text) {
  if (skip(n.parentElement)) return;
  if (n.parentElement && doGroup(n.parentElement)) return;
  const cur = n.nodeValue || "";
  if (shown.get(n) === cur) return; // our own change
  original.set(n, cur);
  const es = translate(cur);
  if (es !== cur) {
    shown.set(n, es);
    n.nodeValue = es;
  }
}

function doAttrs(el: Element) {
  if (skip(el)) return;
  for (const a of ATTRS) {
    const v = el.getAttribute(a);
    if (!v) continue;
    const store = origAttr.get(el) || {};
    if (store[`es:${a}`] === v) continue;
    store[a] = v;
    const es = translate(v);
    store[`es:${a}`] = es;
    origAttr.set(el, store);
    if (es !== v) el.setAttribute(a, es);
  }
}

function walk(root: Node) {
  if (root.nodeType === Node.TEXT_NODE) return doText(root as Text);
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const el = root as Element;
  if (skip(el)) return;
  doAttrs(el);
  const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n: Node | null = tw.nextNode();
  while (n) {
    if (n.nodeType === Node.TEXT_NODE) doText(n as Text);
    else doAttrs(n as Element);
    n = tw.nextNode();
  }
}

function restore(root: Node) {
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n: Node | null = tw.currentNode;
  while (n) {
    if (n.nodeType === Node.TEXT_NODE && original.has(n) && shown.get(n) === n.nodeValue) n.nodeValue = original.get(n)!;
    if (n.nodeType === Node.ELEMENT_NODE) {
      const st = origAttr.get(n as Element);
      if (st) for (const a of ATTRS) if (st[a] && st[`es:${a}`] === (n as Element).getAttribute(a)) (n as Element).setAttribute(a, st[a]);
    }
    n = tw.nextNode();
  }
}

/** For chart labels: translate before the chart library draws (and maybe shortens) them. */
export const tr = (s: any) => (active && typeof s === "string" ? translate(s) : s);
export const locale = () => (active ? "es-ES" : "en-GB");

export function setLanguage(lang: "en" | "es") {
  document.documentElement.lang = lang === "es" ? "es" : "en-GB";
  if (lang === "es" && !active) {
    active = true;
    walk(document.body);
    observer = new MutationObserver((muts) => {
      for (const m of muts) {
        if (m.type === "characterData") doText(m.target as Text);
        else if (m.type === "attributes") doAttrs(m.target as Element);
        else m.addedNodes.forEach(walk);
      }
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  } else if (lang === "en" && active) {
    active = false;
    observer?.disconnect();
    observer = null;
    restore(document.body);
  }
}
