/** Tiny fetch wrapper. Errors become friendly messages, never stack traces. In prototype mode it reads saved snapshots. */
import { STATIC, staticGet, staticPost } from "./static";

export class ApiError extends Error {
  login?: boolean;
}

async function handle<T>(res: Response): Promise<T> {
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const e = new ApiError(body?.error || body?.detail || "Something went wrong. Please try again.");
    e.login = body?.login;
    if (e.login) window.dispatchEvent(new Event("login-required"));
    throw e;
  }
  return body as T;
}

const preview = (path: string, data?: unknown) => staticPost(path, data).catch((e) => { throw new ApiError(e.message); });

export const api = {
  get: <T = any>(path: string): Promise<T> =>
    STATIC ? staticGet(path).catch((e) => { throw new ApiError(e.message); }) : fetch(`/api${path}`, { credentials: "same-origin" }).then((r) => handle<T>(r)),
  post: <T = any>(path: string, data?: unknown): Promise<T> =>
    STATIC ? preview(path, data) : fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data ?? {}) }).then((r) => handle<T>(r)),
  patch: <T = any>(path: string, data?: unknown): Promise<T> =>
    STATIC ? Promise.resolve({ ok: true } as T) : fetch(`/api${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data ?? {}) }).then((r) => handle<T>(r)),
  del: <T = any>(path: string): Promise<T> => (STATIC ? Promise.resolve({ ok: true } as T) : fetch(`/api${path}`, { method: "DELETE" }).then((r) => handle<T>(r))),
  upload: <T = any>(files: File[], ws: string): Promise<T> => {
    if (STATIC) return preview("/upload");
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("ws", ws);
    return fetch("/api/upload", { method: "POST", body: fd }).then((r) => handle<T>(r));
  },
};
