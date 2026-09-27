import { ArrowDownToLine, ChevronDown, ChevronUp, Eraser, SquareTerminal } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { Hint } from "@/components/ui/tooltip";
import { EVENT_TYPES, type Severity } from "@/devmode/capture";
import { clock, devLog, useDevLog, type DevLog, type LogEntry, type TurnInfo } from "@/devmode/log";
import { storeConsoleHeight, storedConsoleHeight } from "@/devmode/mode";
import { cn } from "@/lib/cn";

// The console docks under the composer at 280px, or 45% of a phone's height, and folds to a 36px strip.
const STRIP_PX = 36;
const DEFAULT_PX = 280;
const MIN_PX = 140;
const NARROW_PX = 640;
const STEP_PX = 24;

const RANK: Record<Severity, number> = { info: 0, warn: 1, error: 2 };
const LEVEL_TEXT: Record<Severity, string> = { info: "INFO", warn: "WARN", error: "ERROR" };
const LEVELS = [
  { value: "0", label: "All levels" },
  { value: "1", label: "Warnings and errors" },
  { value: "2", label: "Errors only" },
];

function tallest(): number {
  return Math.max(MIN_PX, window.innerHeight - 240);
}

function fit(height: number): number {
  return Math.round(Math.min(Math.max(height, MIN_PX), tallest()));
}

function startingHeight(): number {
  const wanted = window.innerWidth < NARROW_PX ? window.innerHeight * 0.45 : DEFAULT_PX;
  return fit(storedConsoleHeight() ?? wanted);
}

/** The request an event belongs to: the server's id once it arrived, and the question's number on this page before. */
function requestOf(entry: LogEntry, turns: ReadonlyMap<number, TurnInfo>): string {
  if (entry.turn === null) return "page";
  return turns.get(entry.turn)?.requestId?.slice(0, 8) ?? `turn ${entry.turn}`;
}

function requestLabel(turn: number, info: TurnInfo): string {
  const question = info.question.length > 40 ? `${info.question.slice(0, 40).trimEnd()}…` : info.question;
  return `${info.requestId?.slice(0, 8) ?? `Turn ${turn}`}: ${question}`;
}

function Row({ entry, request }: { entry: LogEntry; request: string }) {
  const [open, setOpen] = useState(false);
  return (
    <li className={cn("console-row", `sev-${entry.severity}`)}>
      <button
        type="button"
        className="console-line"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
      >
        <span className="when">{clock(entry.at)}</span>
        <span className="level">{LEVEL_TEXT[entry.severity]}</span>
        <span className="request">{request}</span>
        <span className="kind">{entry.type}</span>
        <span className="summary">{entry.summary}</span>
      </button>
      {open && <pre className="console-detail">{JSON.stringify(entry.detail, null, 2)}</pre>}
    </li>
  );
}

/**
 * Dev mode's console: every event the server sent for this page's questions, and what went wrong on the page's side,
 * as the browser received them. It shows only what the server already sent this user, and it grants nothing more.
 */
export function DevConsole({ log = devLog }: { log?: DevLog }) {
  const view = useDevLog(log);
  const [open, setOpen] = useState(true);
  const [height, setHeight] = useState(startingHeight);
  const [request, setRequest] = useState("all");
  const [type, setType] = useState("all");
  const [level, setLevel] = useState("0");
  const [search, setSearch] = useState("");
  const [follow, setFollow] = useState(true);
  const drag = useRef<{ y: number; height: number } | null>(null);
  const list = useRef<HTMLOListElement>(null);

  // The composer and the end of the thread sit above the console, however tall it is.
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--console-h", `${open ? height : STRIP_PX}px`);
    return () => {
      root.style.removeProperty("--console-h");
    };
  }, [open, height]);

  useEffect(() => {
    const refit = () => {
      setHeight((current) => fit(current));
    };
    window.addEventListener("resize", refit);
    return () => {
      window.removeEventListener("resize", refit);
    };
  }, []);

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const least = Number(level);
    return view.entries.filter(
      (entry) =>
        (request === "all" || String(entry.turn) === request) &&
        (type === "all" || entry.type === type) &&
        RANK[entry.severity] >= least &&
        (!needle || `${entry.summary} ${JSON.stringify(entry.detail)}`.toLowerCase().includes(needle)),
    );
  }, [view.entries, request, type, level, search]);

  const newest = shown.at(-1)?.seq;
  useLayoutEffect(() => {
    const box = list.current;
    if (follow && open && box) box.scrollTop = box.scrollHeight;
  }, [follow, open, newest]);

  const resize = (next: number) => {
    const fitted = fit(next);
    setHeight(fitted);
    storeConsoleHeight(fitted);
  };
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = {
      ArrowUp: STEP_PX,
      ArrowDown: -STEP_PX,
      PageUp: STEP_PX * 4,
      PageDown: -STEP_PX * 4,
      Home: tallest() - height,
      End: MIN_PX - height,
    };
    const move = moves[event.key];
    if (move === undefined) return;
    event.preventDefault();
    resize(height + move);
  };
  const onDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current) setHeight(fit(drag.current.height + drag.current.y - event.clientY));
  };
  const endDrag = () => {
    if (!drag.current) return;
    drag.current = null;
    storeConsoleHeight(height);
  };

  const counts = { warn: 0, error: 0 };
  for (const entry of view.entries) if (entry.severity !== "info") counts[entry.severity] += 1;

  return (
    <section className="devconsole" aria-label="Dev console" data-state={open ? "open" : "closed"}>
      {open && (
        // The window splitter pattern: a focusable separator, which ARIA counts as a widget and this rule doesn't.
        // eslint-disable-next-line jsx-a11y-x/no-noninteractive-element-interactions
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize the console"
          aria-valuemin={MIN_PX}
          aria-valuemax={tallest()}
          aria-valuenow={height}
          // eslint-disable-next-line jsx-a11y-x/no-noninteractive-tabindex
          tabIndex={0}
          className="console-grip"
          onKeyDown={onKey}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            drag.current = { y: event.clientY, height };
          }}
          onPointerMove={onDrag}
          onPointerUp={endDrag}
          onLostPointerCapture={endDrag}
        />
      )}
      <div className="console-strip">
        <SquareTerminal className="size-4 shrink-0 text-subtle" aria-hidden="true" />
        <h2 className="console-title">Console</h2>
        <p className="console-counts">
          <span>{view.entries.length === 1 ? "1 event" : `${view.entries.length} events`}</span>
          {counts.warn > 0 && (
            <span className="text-warning">{`${counts.warn} ${counts.warn === 1 ? "warning" : "warnings"}`}</span>
          )}
          {counts.error > 0 && (
            <span className="text-danger">{`${counts.error} ${counts.error === 1 ? "error" : "errors"}`}</span>
          )}
        </p>
        <div className="console-actions">
          {/* On a phone the two show their icons only, and keep their names. */}
          {open && (
            <button
              type="button"
              className="console-button"
              aria-label="Clear"
              onClick={() => {
                log.clear();
              }}
            >
              <Eraser aria-hidden="true" />
              <span className="label">Clear</span>
            </button>
          )}
          {open && (
            <button
              type="button"
              className="console-button"
              aria-label="Follow latest"
              aria-pressed={follow}
              onClick={() => {
                setFollow(!follow);
              }}
            >
              <ArrowDownToLine aria-hidden="true" />
              <span className="label">Follow latest</span>
            </button>
          )}
          <Hint label={open ? "Fold the console" : "Open the console"}>
            <button
              type="button"
              className="console-icon"
              aria-label={open ? "Fold the console" : "Open the console"}
              aria-expanded={open}
              aria-controls="console-body"
              onClick={() => {
                setOpen(!open);
              }}
            >
              {open ? <ChevronDown aria-hidden="true" /> : <ChevronUp aria-hidden="true" />}
            </button>
          </Hint>
        </div>
      </div>
      <div id="console-body" className="console-body" hidden={!open}>
        <div className="console-tools">
          <select
            aria-label="Request"
            value={request}
            onChange={(event) => {
              setRequest(event.currentTarget.value);
            }}
          >
            <option value="all">All requests</option>
            {[...view.turns].map(([turn, info]) => (
              <option key={turn} value={String(turn)}>
                {requestLabel(turn, info)}
              </option>
            ))}
          </select>
          <select
            aria-label="Event type"
            value={type}
            onChange={(event) => {
              setType(event.currentTarget.value);
            }}
          >
            <option value="all">All events</option>
            {EVENT_TYPES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <select
            aria-label="Level"
            value={level}
            onChange={(event) => {
              setLevel(event.currentTarget.value);
            }}
          >
            {LEVELS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            type="search"
            aria-label="Search the events"
            placeholder="Search"
            value={search}
            onChange={(event) => {
              setSearch(event.currentTarget.value);
            }}
          />
        </div>
        {shown.length ? (
          <ol ref={list} className="console-rows" aria-label="Events">
            {shown.map((entry) => (
              <Row key={entry.seq} entry={entry} request={requestOf(entry, view.turns)} />
            ))}
          </ol>
        ) : (
          <p className="console-empty">
            {view.entries.length
              ? "No events match these filters."
              : "No events yet. Ask a question, and each event the server sends for it shows here as it arrives."}
          </p>
        )}
      </div>
    </section>
  );
}
