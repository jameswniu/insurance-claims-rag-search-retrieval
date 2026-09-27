import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { devLog } from "@/devmode/log";

// jsdom has no canvas. Charts measure text on one, and fall back to an estimate without it.
HTMLCanvasElement.prototype.getContext = () => null;
// Nor does it scroll. A new question's turn scrolls into view.
Element.prototype.scrollIntoView = () => undefined;

afterEach(() => {
  cleanup();
  // Dev mode, its stored settings and the console's log belong to one test.
  devLog.reset();
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-mode");
  document.documentElement.style.removeProperty("--console-h");
});
