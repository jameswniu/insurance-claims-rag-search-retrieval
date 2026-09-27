import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The bordered box a table sits in, which scrolls sideways when the table is wider than it, as on a phone. While it
 * scrolls it is a named region that takes the focus, so a keyboard can scroll it too; otherwise it is only a box.
 */
export function TableBox({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [scrolls, setScrolls] = useState(false);
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      setScrolls(element.scrollWidth > element.clientWidth + 1);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    measure();
    return () => {
      observer.disconnect();
    };
  }, []);
  return (
    <div
      ref={box}
      role={scrolls ? "region" : undefined}
      aria-label={scrolls ? label : undefined}
      // The scrollable region pattern: a box that only scrolls takes the focus, or a keyboard could not scroll it.
      // eslint-disable-next-line jsx-a11y-x/no-noninteractive-tabindex
      tabIndex={scrolls ? 0 : undefined}
      className={cn("table-wrap", className)}
    >
      {children}
    </div>
  );
}
