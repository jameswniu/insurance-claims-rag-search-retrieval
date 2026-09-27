import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TopBar } from "@/components/TopBar";
import { DevModeProvider } from "@/devmode/DevModeProvider";
import { DevModeSwitch } from "@/devmode/DevModeSwitch";
import { storeConsoleHeight, storedConsoleHeight } from "@/devmode/mode";

const root = document.documentElement;

function renderSwitch() {
  return render(
    <DevModeProvider>
      <DevModeSwitch />
    </DevModeProvider>,
  );
}

/** Storage that throws on every use, as a browser that blocks site data does. */
function blockStorage() {
  const denied = () => {
    throw new DOMException("The operation is insecure.", "SecurityError");
  };
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(denied);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(denied);
}

describe("the Dev mode switch", () => {
  it("opens light even when the system prefers dark, and turns dev mode on and off, remembering it", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("dark"), media: query }));
    renderSwitch();
    const toggle = screen.getByRole("switch", { name: "Dev mode" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(root).not.toHaveAttribute("data-mode");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(root).toHaveAttribute("data-mode", "dev");
    expect(window.localStorage.getItem("claims-qa:dev-mode")).toBe("on");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(root).not.toHaveAttribute("data-mode");
    expect(window.localStorage.getItem("claims-qa:dev-mode")).toBe("off");
  });

  it("starts in dev mode when it was left on", () => {
    window.localStorage.setItem("claims-qa:dev-mode", "on");
    renderSwitch();
    expect(screen.getByRole("switch", { name: "Dev mode" })).toHaveAttribute("aria-checked", "true");
    expect(root).toHaveAttribute("data-mode", "dev");
  });

  it("still switches when storage is blocked, and forgets instead of failing", async () => {
    blockStorage();
    renderSwitch();
    const toggle = screen.getByRole("switch", { name: "Dev mode" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    await userEvent.click(toggle);
    expect(root).toHaveAttribute("data-mode", "dev");
    expect(() => {
      storeConsoleHeight(320);
    }).not.toThrow();
    expect(storedConsoleHeight()).toBeNull();
  });

  it("sits in the shared header, beside who is asking", () => {
    render(
      <DevModeProvider>
        <TopBar page="dashboard" ops identity={<span>Priya Natarajan</span>} />
      </DevModeProvider>,
    );
    const header = screen.getByRole("banner");
    const toggle = screen.getByRole("switch", { name: "Dev mode" });
    expect(header).toContainElement(toggle);
    expect(toggle.closest(".session")).toHaveTextContent("Priya Natarajan");
  });
});
