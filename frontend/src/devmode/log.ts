import { useSyncExternalStore } from "react";

import { capture, captureClient, type Captured, type ClientKind } from "@/devmode/capture";

// The console's memory: the events of this page's questions, newest last, for the user asking now. It holds at most
// LOG_LIMIT events, dropping the oldest, and remembers a question only while one of its events is kept or it is still
// streaming, and never more than TURN_LIMIT of them. It lives only in this tab and empties when the user changes;
// events still arriving for the user before are dropped.

export const LOG_LIMIT = 500;
export const TURN_LIMIT = 100;

// The events after which a question's stream is over.
const ENDS: ReadonlySet<string> = new Set(["done", "error", "client"]);

export interface LogEntry extends Captured {
  seq: number;
  /** When the browser received it, in epoch milliseconds. */
  at: number;
  /** The question's number on this page, which groups its events until the server's request id arrives. */
  turn: number | null;
}

export interface TurnInfo {
  question: string;
  /** performance.now() when it was sent. */
  startedAt: number;
  requestId: string | null;
  /** Whether its stream has ended, with a done, an error or a failure the browser saw. */
  finished: boolean;
}

export interface LogView {
  entries: readonly LogEntry[];
  turns: ReadonlyMap<number, TurnInfo>;
}

export interface DevLog {
  subscribe: (listener: () => void) => () => void;
  view: () => LogView;
  /** Which identity the log belongs to. A different one empties it and drops what is still arriving for the last. */
  scope: (owner: string) => void;
  /** The current identity's number, which each question keeps so its late events can be told apart. */
  epoch: () => number;
  /** Empties the list and forgets every question, as a change of user does. */
  reset: () => void;
  /** Empties the list and forgets finished questions. One still streaming keeps its group, so its next events show. */
  clear: () => void;
  begin: (turn: number, question: string) => number;
  event: (epoch: number, turn: number, type: string, payload: unknown) => void;
  client: (epoch: number, turn: number | null, kind: ClientKind, message: string, status?: number) => void;
}

export function createDevLog(
  limit = LOG_LIMIT,
  now = () => performance.now(),
  clock = () => Date.now(),
  turnLimit = TURN_LIMIT,
): DevLog {
  let entries: LogEntry[] = [];
  let turns = new Map<number, TurnInfo>();
  let owner: string | null = null;
  let epoch = 0;
  let seq = 0;
  let view: LogView = { entries, turns };
  const listeners = new Set<() => void>();

  const publish = () => {
    view = { entries: [...entries], turns: new Map(turns) };
    for (const listener of listeners) listener();
  };

  // Forgets each finished question none of whose events are kept, then the oldest past the cap, finished ones first.
  // A Map keeps insertion order, so the first keys are the oldest questions.
  const prune = () => {
    const kept = new Set(entries.map((entry) => entry.turn));
    for (const [turn, info] of turns) {
      if (info.finished && !kept.has(turn)) turns.delete(turn);
    }
    for (const [turn, info] of turns) {
      if (turns.size <= turnLimit) break;
      if (info.finished) turns.delete(turn);
    }
    for (const turn of turns.keys()) {
      if (turns.size <= turnLimit) break;
      turns.delete(turn);
    }
  };

  const add = (turn: number | null, found: Captured) => {
    entries.push({ ...found, seq: ++seq, at: clock(), turn });
    if (entries.length > limit) entries.splice(0, entries.length - limit);
    const info = turn === null ? undefined : turns.get(turn);
    if (turn !== null && info) {
      turns.set(turn, {
        ...info,
        requestId: found.requestId ?? info.requestId,
        finished: info.finished || ENDS.has(found.type),
      });
    }
    prune();
    publish();
  };

  const reset = () => {
    epoch += 1;
    entries = [];
    turns = new Map();
    publish();
  };

  return {
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    view: () => view,
    scope: (next) => {
      if (next === owner) return;
      owner = next;
      reset();
    },
    epoch: () => epoch,
    reset,
    clear: () => {
      entries = [];
      prune();
      publish();
    },
    begin: (turn, question) => {
      turns.set(turn, { question, startedAt: now(), requestId: null, finished: false });
      prune();
      publish();
      return epoch;
    },
    event: (at, turn, type, payload) => {
      const info = turns.get(turn);
      if (at !== epoch || !info) return;
      const found = capture(type, payload, now() - info.startedAt);
      if (found) add(turn, found);
    },
    client: (at, turn, kind, message, status) => {
      if (at !== epoch) return;
      add(turn, captureClient(kind, message, status));
    },
  };
}

/** The browser's clock when an event arrived, to the millisecond. */
export function clock(at: number): string {
  const time = new Date(at);
  const pad = (value: number, width = 2) => String(value).padStart(width, "0");
  return `${pad(time.getHours())}:${pad(time.getMinutes())}:${pad(time.getSeconds())}.${pad(time.getMilliseconds(), 3)}`;
}

/** The page's one log, which the chat records into and the console reads. */
export const devLog = createDevLog();

export function useDevLog(log: DevLog = devLog): LogView {
  return useSyncExternalStore(log.subscribe, log.view);
}

/**
 * Records the page's own script errors into the log while mounted: the message only, clipped, never a stack or a file.
 * Returns the function that stops it.
 */
export function watchScriptErrors(log: DevLog = devLog): () => void {
  const onError = (event: ErrorEvent) => {
    log.client(log.epoch(), null, "script", event.message || "A script error was reported.");
  };
  const onRejection = (event: PromiseRejectionEvent) => {
    const reason: unknown = event.reason;
    const said = reason instanceof Error ? `${reason.name}: ${reason.message}` : "A promise was rejected.";
    log.client(log.epoch(), null, "script", said);
  };
  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}
