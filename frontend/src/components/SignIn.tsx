import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, LockKeyhole } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { STATIC } from "@/lib/static";
import { Card } from "./ui";

/** Shows a sign-in screen when the hosted app is protected with a password (APP_PASSWORD). */
export function SessionGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [needed, setNeeded] = useState(false);
  const s = useQuery({
    queryKey: ["session"], enabled: !STATIC, retry: false,
    queryFn: () => fetch("/api/session").then((r) => r.json()).catch(() => ({ login_required: false, signed_in: true })),
  });
  useEffect(() => {
    const on = () => setNeeded(true);
    window.addEventListener("login-required", on);
    return () => window.removeEventListener("login-required", on);
  }, []);
  if (STATIC) return <>{children}</>;
  if (s.isLoading) return null;
  if (needed || (s.data?.login_required && !s.data?.signed_in)) {
    return <SignIn onDone={() => { setNeeded(false); qc.invalidateQueries(); }} />;
  }
  return <>{children}</>;
}

function SignIn({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: pw }) });
      const b = await r.json();
      if (!r.ok) setErr(b.error || "Could not sign in.");
      else onDone();
    } catch {
      setErr("We could not reach the server. Check your connection.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="min-h-screen grid place-items-center bg-bg px-4">
      <Card className="w-full max-w-sm">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-primary-soft text-primary"><LockKeyhole className="h-7 w-7" /></div>
        <h1 className="mt-4 text-center font-display text-2xl font-semibold">Sign in to Insight Hub</h1>
        <p className="mt-1 text-center text-sm text-ink-2">Enter the team password to see your business data.</p>
        <form onSubmit={submit} className="mt-5 space-y-3">
          <label htmlFor="pw" className="text-sm font-medium">Password</label>
          <input id="pw" type="password" autoComplete="current-password" className="input" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus />
          {err ? <p role="alert" className="rounded-xl bg-warn-soft px-3 py-2 text-sm text-warn">{err}</p> : null}
          <button className="btn-primary w-full" disabled={!pw || busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Sign in</button>
        </form>
        <p className="mt-4 text-center text-xs text-ink-3">Stay signed in for 30 days on this device. After 10 wrong attempts, sign-in pauses for 15 minutes.</p>
      </Card>
    </main>
  );
}
