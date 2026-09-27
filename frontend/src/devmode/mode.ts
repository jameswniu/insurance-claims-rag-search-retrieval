import { createContext, useContext } from "react";

// Dev mode is the dark theme and the console, for someone debugging an answer. The page opens light whatever the
// system prefers. Only the switch and the console's height are remembered, in this browser's storage, and storage can
// be blocked, in a private window or by a policy: then every read finds nothing, every write is dropped, and the page
// works the same, forgetting both on reload.

const MODE_KEY = "claims-qa:dev-mode";
const HEIGHT_KEY = "claims-qa:console-height";
// The browser's own bar takes the page's background in each mode.
const THEME_COLOR = { light: "#f5f7f9", dev: "#141a21" };

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Blocked or full: the setting lasts until the page reloads.
  }
}

export function storedDevMode(): boolean {
  return read(MODE_KEY) === "on";
}

export function storeDevMode(on: boolean): void {
  write(MODE_KEY, on ? "on" : "off");
}

export function storedConsoleHeight(): number | null {
  const height = Number(read(HEIGHT_KEY));
  return Number.isFinite(height) && height > 0 ? height : null;
}

export function storeConsoleHeight(height: number): void {
  write(HEIGHT_KEY, String(Math.round(height)));
}

/** Shows the page in one mode: dark under data-mode="dev" on the root element, light without it. */
export function applyMode(on: boolean): void {
  const root = document.documentElement;
  if (on) root.setAttribute("data-mode", "dev");
  else root.removeAttribute("data-mode");
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", on ? THEME_COLOR.dev : THEME_COLOR.light);
}

export interface DevMode {
  on: boolean;
  setOn: (on: boolean) => void;
}

export const DevModeContext = createContext<DevMode>({ on: false, setOn: () => undefined });

export function useDevMode(): DevMode {
  return useContext(DevModeContext);
}
