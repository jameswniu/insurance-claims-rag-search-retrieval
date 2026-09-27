import { useCallback, useLayoutEffect, useMemo, useState, type ReactNode } from "react";

import { applyMode, DevModeContext, storeDevMode, storedDevMode } from "@/devmode/mode";

/** Holds whether dev mode is on for the whole page, starting from the stored switch, and shows the page in it. */
export function DevModeProvider({ children }: { children: ReactNode }) {
  const [on, setState] = useState(storedDevMode);
  useLayoutEffect(() => {
    applyMode(on);
  }, [on]);
  const setOn = useCallback((next: boolean) => {
    setState(next);
    storeDevMode(next);
  }, []);
  const value = useMemo(() => ({ on, setOn }), [on, setOn]);
  return <DevModeContext value={value}>{children}</DevModeContext>;
}
