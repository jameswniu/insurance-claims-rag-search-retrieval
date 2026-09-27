import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ChatPage } from "@/chat/ChatPage";
import DashboardPage from "@/dashboard/DashboardPage";
import type { SessionView } from "@/lib/types";
import { dana, figures, streamOf } from "@/test/fixtures";
import { fakeServer, json, renderWithQueries } from "@/test/server";

const demo: SessionView = {
  me: dana,
  demo: true,
  users: [{ user_id: "dana", name: "Dana Reyes", title: "Claims adjuster, West" }],
};
const QUESTION = "How much did we pay on hail claims in Colorado in Q2 2025?";
const root = document.documentElement;

const streamed = (events: [string, unknown][]) => () =>
  new Response(streamOf(events), { headers: { "Content-Type": "text/event-stream" } });

/** The chat page in dev mode, with one question asked and its reply coming from reply. */
async function askInDevMode(reply: () => Response) {
  window.localStorage.setItem("claims-qa:dev-mode", "on");
  fakeServer({ "GET /api/session": () => json(demo), "POST /ask": reply });
  renderWithQueries(<ChatPage />);
  await userEvent.type(await screen.findByRole("textbox", { name: "Your question" }), `${QUESTION}{Enter}`);
  return screen.getByRole("region", { name: "Dev console" });
}

const rowsIn = (panel: HTMLElement) => within(panel).queryAllByRole("listitem");
const cell = (row: HTMLElement | undefined, name: string) => row?.querySelector(`.${name}`)?.textContent;

describe("the dev console", () => {
  it("docks under the composer and lists each event of an answer as it arrived", async () => {
    const panel = await askInDevMode(streamed(figures));
    await waitFor(() => {
      expect(rowsIn(panel)).toHaveLength(figures.length);
    });
    expect(root).toHaveAttribute("data-mode", "dev");
    expect(root.style.getPropertyValue("--console-h")).toBe("280px");
    const rows = rowsIn(panel);
    expect(rows.map((row) => cell(row, "kind"))).toEqual(figures.map(([type]) => type));
    // Once the done arrives, every row of the question carries the server's request id.
    expect(rows.map((row) => cell(row, "request"))).toEqual(rows.map(() => "5b0c1f3e"));
    const done = rows.at(-1);
    expect(cell(done, "level")).toBe("INFO");
    expect(cell(done, "summary")).toBe("route=quantitative outcome=answer total_ms=61.5");
    expect(cell(done, "when")).toMatch(/^\d\d:\d\d:\d\d\.\d{3}$/);

    const line = within(done!).getByRole("button");
    await userEvent.click(line);
    expect(line).toHaveAttribute("aria-expanded", "true");
    expect(done?.querySelector("pre.console-detail")?.textContent).toContain('"route": "quantitative"');

    // In dev mode the answer's footer names its request and route too.
    const footer = document.querySelector(".turn .footer");
    expect(footer).toHaveTextContent("Request 5b0c1f3e");
    expect(footer).toHaveTextContent("Route quantitative");
  });

  it("filters by request, event type, level and text, and clears", async () => {
    const panel = await askInDevMode(streamed(figures));
    await waitFor(() => {
      expect(rowsIn(panel)).toHaveLength(figures.length);
    });
    const request = within(panel).getByRole("combobox", { name: "Request" });
    expect(
      within(request).getByRole("option", { name: /^5b0c1f3e: How much did we pay on hail claims in Co…$/ }),
    ).toBeInTheDocument();
    await userEvent.selectOptions(request, "1");
    expect(rowsIn(panel)).toHaveLength(figures.length);

    const type = within(panel).getByRole("combobox", { name: "Event type" });
    await userEvent.selectOptions(type, "stage");
    expect(rowsIn(panel).map((row) => cell(row, "kind"))).toEqual(["stage", "stage", "stage"]);
    await userEvent.selectOptions(type, "all");

    await userEvent.type(within(panel).getByRole("searchbox", { name: "Search the events" }), "sem.v_payments_net");
    expect(rowsIn(panel).map((row) => cell(row, "summary")?.split(" ")[0])).toEqual(["kind=sql"]);
    await userEvent.clear(within(panel).getByRole("searchbox", { name: "Search the events" }));

    await userEvent.selectOptions(within(panel).getByRole("combobox", { name: "Level" }), "Errors only");
    expect(rowsIn(panel)).toHaveLength(0);
    expect(within(panel).getByText("No events match these filters.")).toBeVisible();
    await userEvent.selectOptions(within(panel).getByRole("combobox", { name: "Level" }), "All levels");

    const follow = within(panel).getByRole("button", { name: "Follow latest" });
    expect(follow).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(follow);
    expect(follow).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(within(panel).getByRole("button", { name: "Clear" }));
    expect(rowsIn(panel)).toHaveLength(0);
    expect(within(panel).getByText(/^No events yet\./)).toBeVisible();
  });

  it("records a request the server turned away, in its own words, grouped by the question", async () => {
    const said = "You have asked 20 questions in the last minute. Wait 3 seconds and try again.";
    const panel = await askInDevMode(() => new Response(said, { status: 429 }));
    await waitFor(() => {
      expect(rowsIn(panel)).toHaveLength(1);
    });
    const [row] = rowsIn(panel);
    expect(cell(row, "kind")).toBe("client");
    expect(cell(row, "level")).toBe("ERROR");
    expect(cell(row, "request")).toBe("turn 1");
    // The line clips a long value, and the row opens to the whole of it.
    expect(cell(row, "summary")).toMatch(
      /^kind=http status=429 message="You have asked 20 questions in the last minute\./,
    );
    await userEvent.click(within(row!).getByRole("button"));
    expect(row?.querySelector("pre.console-detail")?.textContent).toContain(said);
  });

  it("records a stream that ends early, one that can't be read, and the page's own script errors", async () => {
    const panel = await askInDevMode(streamed(figures.slice(0, 3)));
    await waitFor(() => {
      expect(rowsIn(panel).map((row) => cell(row, "summary")?.split(" ")[0])).toContain("kind=premature_close");
    });
    act(() => {
      window.dispatchEvent(new ErrorEvent("error", { message: "boom" }));
    });
    await waitFor(() => {
      expect(rowsIn(panel).map((row) => cell(row, "summary"))).toContain("kind=script message=boom");
    });
    const scripted = rowsIn(panel).find((row) => cell(row, "summary") === "kind=script message=boom");
    expect(cell(scripted, "request")).toBe("page");
  });

  it("names a stream it could not read", async () => {
    const panel = await askInDevMode(() => new Response('event: stage\ndata: {"name": \n\n'));
    await waitFor(() => {
      expect(rowsIn(panel).map((row) => cell(row, "summary")?.split(" ")[0])).toEqual(["kind=parse"]);
    });
  });

  it("folds to a strip, resizes from the keyboard, remembers its height, and goes when dev mode does", async () => {
    window.localStorage.setItem("claims-qa:dev-mode", "on");
    fakeServer({ "GET /api/session": () => json(demo) });
    renderWithQueries(<ChatPage />);
    const panel = await screen.findByRole("region", { name: "Dev console" });
    expect(within(panel).getByText(/^No events yet\./)).toBeVisible();
    const grip = within(panel).getByRole("separator", { name: "Resize the console" });
    expect(grip).toHaveAttribute("aria-valuenow", "280");
    grip.focus();
    await userEvent.keyboard("{ArrowUp}");
    expect(grip).toHaveAttribute("aria-valuenow", "304");
    expect(window.localStorage.getItem("claims-qa:console-height")).toBe("304");
    expect(root.style.getPropertyValue("--console-h")).toBe("304px");

    await userEvent.click(within(panel).getByRole("button", { name: "Fold the console" }));
    expect(root.style.getPropertyValue("--console-h")).toBe("36px");
    expect(within(panel).queryByRole("separator")).toBeNull();
    await userEvent.click(within(panel).getByRole("button", { name: "Open the console" }));
    expect(root.style.getPropertyValue("--console-h")).toBe("304px");

    await userEvent.click(screen.getByRole("switch", { name: "Dev mode" }));
    expect(screen.queryByRole("region", { name: "Dev console" })).toBeNull();
    expect(root).not.toHaveAttribute("data-mode");
    expect(root.style.getPropertyValue("--console-h")).toBe("");
  });

  it("gives the dashboard the switch and the dark theme, and no console", async () => {
    window.localStorage.setItem("claims-qa:dev-mode", "on");
    fakeServer({
      "GET /api/session": () => json({ ...demo, me: { ...dana, ops: true } }),
      "GET /api/dashboard": () => new Response("The dashboard is for operators only.", { status: 403 }),
    });
    renderWithQueries(<DashboardPage />);
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByRole("switch", { name: "Dev mode" })).toHaveAttribute("aria-checked", "true");
    expect(root).toHaveAttribute("data-mode", "dev");
    expect(screen.queryByRole("region", { name: "Dev console" })).toBeNull();
  });
});
