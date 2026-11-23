import "@fontsource-variable/fraunces";
import "@fontsource-variable/inter";
import "./theme/tokens.css";
import * as Tip from "@radix-ui/react-tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, MemoryRouter, Route, Routes } from "react-router-dom";
import { STATIC } from "./lib/static";
const Router: any = STATIC ? MemoryRouter : BrowserRouter;
import { Toaster } from "sonner";
import { Shell } from "./components/Shell";
import { SessionGate } from "./components/SignIn";
import { AppProvider } from "./lib/store";
import { Ask } from "./pages/Ask";
import { Data } from "./pages/Data";
import { Feedback } from "./pages/Feedback";
import { Home } from "./pages/Home";
import { Briefing, Collect, PublicForm, SettingsPage } from "./pages/Other";
import { Plan } from "./pages/Plan";
import { Integrations } from "./pages/Integrations";
import { Sales } from "./pages/Sales";
import { Social } from "./pages/Social";

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <AppProvider>
        <Tip.Provider>
          <SessionGate>
          <Router>
            <Shell>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/feedback" element={<Feedback />} />
                <Route path="/social" element={<Social />} />
                <Route path="/sales" element={<Sales />} />
                <Route path="/ask" element={<Ask />} />
                <Route path="/plan" element={<Plan />} />
                <Route path="/data" element={<Data />} />
                <Route path="/integrations" element={<Integrations />} />
                <Route path="/briefing" element={<Briefing />} />
                <Route path="/collect" element={<Collect />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/form" element={<PublicForm />} />
                <Route path="*" element={<Home />} />
              </Routes>
            </Shell>
          </Router>
          </SessionGate>
          <Toaster position="top-center" richColors closeButton toastOptions={{ style: { borderRadius: 14 } }} />
        </Tip.Provider>
      </AppProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
