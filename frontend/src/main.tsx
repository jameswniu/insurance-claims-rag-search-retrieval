import "@/styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import { applyMode, storedDevMode } from "@/devmode/mode";
import { pageFor } from "@/page";

// The server serves this one page at / and at /dashboard, and decides who may open each. The body is marked with the
// page it shows, which the demo recorder's stylesheet reads.
const page = pageFor(window.location.pathname);
document.body.classList.add(page === "dashboard" ? "dash" : "chat");
document.title = page === "dashboard" ? "Dashboard, Claims Q&A" : "Claims Q&A";
// Dev mode goes on before the first render, so a page reloaded in it never shows light first.
applyMode(storedDevMode());

const queries = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

const root = document.getElementById("root");
if (!root) throw new Error("The page has no #root element to render into.");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queries}>
      <App page={page} />
    </QueryClientProvider>
  </StrictMode>,
);
