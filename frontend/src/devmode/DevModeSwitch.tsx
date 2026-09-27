import { useDevMode } from "@/devmode/mode";
import { cn } from "@/lib/cn";

/** The header's switch between the light page and dev mode, which is dark and opens the console on the chat page. */
export function DevModeSwitch({ className }: { className?: string }) {
  const { on, setOn } = useDevMode();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => {
        setOn(!on);
      }}
      className={cn("mode-switch", className)}
    >
      <span aria-hidden="true" className="track">
        <span className="thumb" />
      </span>
      Dev mode
    </button>
  );
}
