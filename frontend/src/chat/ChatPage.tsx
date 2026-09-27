import { useEffect, useState } from "react";

import { Composer } from "@/chat/Composer";
import { Intro } from "@/chat/Intro";
import { TurnView } from "@/chat/TurnView";
import { useChat } from "@/chat/useChat";
import { IdentityPicker } from "@/components/Identity";
import { ErrorPanel, Skeleton } from "@/components/StatePanels";
import { TopBar } from "@/components/TopBar";
import { DevConsole } from "@/devmode/DevConsole";
import { devLog, watchScriptErrors } from "@/devmode/log";
import { useDevMode } from "@/devmode/mode";
import { useSession } from "@/session";

/**
 * The chat page: who is asking in the header, the thread, and the question box under it. In dev mode the console
 * docks under the box, and each answer's footer names its request and route.
 */
export function ChatPage() {
  const session = useSession();
  const me = session.data?.me;
  const owner = me?.user_id ?? null;
  const { turns, busy, ask, stop } = useChat(owner);
  const dev = useDevMode().on;
  const [draft, setDraft] = useState("");
  const [focusKey, setFocusKey] = useState(0);
  const fill = (text: string) => {
    setDraft(text);
    setFocusKey((key) => key + 1);
  };

  // The console's log belongs to whoever is asking, and records this page's script errors while it is open.
  useEffect(() => {
    if (owner) devLog.scope(owner);
  }, [owner]);
  useEffect(() => watchScriptErrors(), []);

  return (
    <>
      <a
        href="#q"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-sm font-medium shadow-md focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to the question box
      </a>
      <TopBar page="chat" ops={me?.ops ?? false} identity={session.data && <IdentityPicker session={session.data} />} />
      <main id="thread" className="thread mx-auto w-full max-w-[768px] px-4 pt-8 sm:px-6">
        {session.isError ? (
          <ErrorPanel error={session.error} />
        ) : !me ? (
          <div className="space-y-4 pt-10" aria-busy="true">
            <Skeleton className="h-9 w-3/4" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-2/3" />
          </div>
        ) : turns.length === 0 ? (
          <Intro me={me} onPick={fill} />
        ) : (
          turns.map((turn) => <TurnView key={turn.id} turn={turn} me={me} onFill={fill} dev={dev} />)
        )}
      </main>
      {me && (
        <Composer
          value={draft}
          onChange={setDraft}
          onAsk={(question) => void ask(question)}
          onStop={stop}
          busy={busy}
          focusKey={focusKey}
        />
      )}
      {me && dev && <DevConsole />}
    </>
  );
}
