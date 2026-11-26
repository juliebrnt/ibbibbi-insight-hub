import { STATIC } from "@/lib/static";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

const STEPS = [
  { title: "Welcome to your Insight Hub", body: "Home shows what is working, what is not, and the one or two things to do next. It takes five minutes a week." },
  STATIC ? { title: "Full potential or Today", body: "Switch at the top between Full potential (everything, once more data is added) and Today (what the current data already shows)." }
    : { title: "Demo or your own data", body: "Switch between the demo (made-up customers) and My data at the top. They are never mixed." },
  { title: "Drop in any file", body: "Upload any export or screenshot. We recognise it, protect personal data and turn it into charts in seconds." },
  { title: "Ask and plan", body: "Ask questions in plain words, and turn any insight into a decision with one tap. We check back on whether it worked." },
];

export function Tour() {
  const [i, setI] = useState<number | null>(null);
  useEffect(() => {
    try {
      if (!localStorage.getItem("ih-tour")) setTimeout(() => setI(0), 800);
    } catch { /* no storage */ }
  }, []);
  const close = () => { setI(null); try { localStorage.setItem("ih-tour", "1"); } catch { /* */ } };
  return (
    <AnimatePresence>
      {i != null ? (
        <motion.div role="dialog" aria-label="Quick tour" className="fixed z-50 left-4 right-4 bottom-[92px] md:left-auto md:right-6 md:bottom-24 md:w-[360px] card p-5 shadow-lift no-print"
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}>
          <div className="label">Step {i + 1} of {STEPS.length}</div>
          <div className="mt-1 font-display text-lg font-semibold">{STEPS[i].title}</div>
          <p className="mt-1 text-sm text-ink-2">{STEPS[i].body}</p>
          <div className="mt-4 flex justify-between">
            <button className="btn-ghost !min-h-[40px]" onClick={close}>Skip</button>
            <button className="btn-primary !min-h-[40px]" onClick={() => (i + 1 < STEPS.length ? setI(i + 1) : close())}>{i + 1 < STEPS.length ? "Next" : "Start"}</button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
