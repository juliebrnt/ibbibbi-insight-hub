import { CheckCircle2, Info, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";

/** Where an uploaded file's data appears, or why it does not and how to fix the file. */
export function FileStatus({ e, onMakeTrend }: { e?: any; onMakeTrend?: () => void }) {
  if (!e) return null;
  const notShown = e.status === "not_shown";
  return (
    <div className="mt-3 space-y-2 text-sm">
      {e.shown_on?.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1 text-good"><CheckCircle2 className="h-4 w-4" />Shown on</span>
          {e.shown_on.map((s: any) => <Link key={s.label} to={s.path} className="chip bg-good-soft text-good hover:underline">{s.label}</Link>)}
        </div>
      ) : null}
      {notShown || e.reasons?.length ? (
        <div className="rounded-xl bg-warn-soft p-3 text-warn">
          <div className="flex items-center gap-1.5 font-medium"><TriangleAlert className="h-4 w-4 shrink-0" />{notShown ? "Nothing from this file is shown yet" : "Part of this file is not shown"}</div>
          <ul className="mt-1 list-disc pl-5 space-y-0.5">{e.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>
          {e.fixes?.length ? <>
            <div className="mt-2 font-medium">How to fix it</div>
            <ul className="mt-0.5 list-disc pl-5 space-y-0.5">{e.fixes.map((r: string) => <li key={r}>{r}</li>)}</ul>
          </> : null}
          {onMakeTrend && notShown ? <button className="btn-soft mt-2 !min-h-[34px]" onClick={onMakeTrend}>Make a trend</button> : null}
        </div>
      ) : null}
      {e.notes?.length ? (
        <ul className="space-y-1 text-ink-2">{e.notes.map((n: string) => <li key={n} className="flex gap-1.5"><Info className="h-4 w-4 shrink-0 mt-0.5 text-ink-3" />{n}</li>)}</ul>
      ) : null}
    </div>
  );
}
