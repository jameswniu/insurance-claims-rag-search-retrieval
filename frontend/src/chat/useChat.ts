import { useCallback, useEffect, useRef, useState } from "react";

import { applyEvent, closes, finish, newTurn, withNotice, type Turn } from "@/chat/turn";
import { devLog, type DevLog } from "@/devmode/log";
import { askQuestion } from "@/lib/api";
import { readEvents } from "@/lib/sse";

/**
 * The thread: every question asked on this page, its answer as it streams, and a way to stop the one in flight. Each
 * event goes to the dev console's log as it is read, before it becomes part of a reply, and so does each failure on
 * the page's side. A change of user stops the question in flight.
 */
export function useChat(owner: string | null = null, log: DevLog = devLog) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef<AbortController | null>(null);
  const asked = useRef(0);

  useEffect(
    () => () => {
      inFlight.current?.abort();
    },
    [owner],
  );

  const ask = useCallback(
    async (question: string) => {
      const id = ++asked.current;
      const update = (change: (turn: Turn) => Turn) => {
        setTurns((all) => all.map((turn) => (turn.id === id ? change(turn) : turn)));
      };
      setTurns((all) => [...all, newTurn(id, question, performance.now())]);
      const epoch = log.begin(id, question);
      const controller = new AbortController();
      inFlight.current = controller;
      setBusy(true);
      try {
        const response = await askQuestion(question, controller.signal);
        if (!response.ok || !response.body) {
          const said = (await response.text()) || `The server answered ${response.status}.`;
          log.client(epoch, id, "http", said, response.status);
          update((turn) => ({ ...withNotice(turn, "error", "Not sent", said), ended: true }));
          return;
        }
        let ended = false;
        for await (const [type, data] of readEvents(response.body)) {
          log.event(epoch, id, type, data);
          ended ||= closes(type);
          update((turn) => applyEvent(turn, type, data));
        }
        if (!ended) {
          log.client(epoch, id, "premature_close", "The stream ended before a done or an error event.");
          update((turn) => withNotice(turn, "error", "Stopped early", "The answer ended before it finished."));
        }
      } catch (error) {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
          log.client(epoch, id, "cancelled", "The request was stopped before the answer finished.");
          update((turn) => withNotice(turn, "outside", "Stopped", "You stopped this answer."));
        } else {
          if (error instanceof SyntaxError) {
            log.client(epoch, id, "parse", "An event's data was not JSON, so the rest of the stream was not read.");
          } else {
            const name = error instanceof Error ? error.name : "Error";
            log.client(epoch, id, "connection", `${name}: the connection dropped before the answer finished.`);
          }
          update((turn) =>
            withNotice(turn, "error", "Connection lost", "The connection dropped before the answer finished."),
          );
        }
      } finally {
        inFlight.current = null;
        setBusy(false);
        update((turn) => finish(turn, performance.now()));
      }
    },
    [log],
  );

  const stop = useCallback(() => {
    inFlight.current?.abort();
  }, []);

  return { turns, busy, ask, stop };
}
