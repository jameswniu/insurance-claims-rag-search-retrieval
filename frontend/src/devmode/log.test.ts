import { describe, expect, it } from "vitest";

import { createDevLog } from "@/devmode/log";
import { figures, HAIL_SQL, policy, split, why } from "@/test/fixtures";

/** A log on a clock that moves 5 ms per reading, so arrival times are known. */
function testLog(limit?: number) {
  let tick = 0;
  return createDevLog(
    limit,
    () => (tick += 5),
    () => 1_700_000_000_000 + tick,
  );
}

describe("the console's log", () => {
  it("keeps each kind of event as it arrived, with the fields the console shows", () => {
    const log = testLog();
    log.scope("dana");
    const epoch = log.begin(1, "How much did we pay on hail claims in Colorado in Q2 2025?");
    const events: [string, unknown][] = [
      ...figures,
      ["evidence", { kind: "chunks", payload: (policy[1]?.[1] as { payload: unknown }).payload }],
      ["evidence", { kind: "scan", payload: [{ doc_id: "scan-7", field: "total", value: "412.50", flagged: true }] }],
      ["evidence", { kind: "sandbox", payload: [split] }],
      ["refused", { reason: "write", message: "I only read data." }],
      ["clarify", { question: "For which period?", options: ["year to date", "Q2 2025"] }],
      ["out_of_data", { message: "2022 is before my data starts.", covered: "January 2024 to June 2026" }],
      ["error", { message: "Something went wrong on our side.", request_id: "5b0c1f3e-0000" }],
    ];
    for (const [type, data] of events) log.event(epoch, 1, type, data);
    log.client(epoch, 1, "http", "You have asked 20 questions in the last minute.", 429);
    log.client(epoch, 1, "parse", "An event's data was not JSON.");
    log.client(epoch, 1, "connection", "TypeError: the connection dropped.");
    log.client(epoch, 1, "cancelled", "The request was stopped.");
    log.client(epoch, 1, "premature_close", "The stream ended before a done or an error event.");

    const { entries, turns } = log.view();
    expect(new Set(entries.map((entry) => entry.type))).toEqual(
      new Set(["stage", "evidence", "answer", "done", "refused", "clarify", "out_of_data", "error", "client"]),
    );
    const find = (type: string, start = "") =>
      entries.find((entry) => entry.type === type && entry.summary.startsWith(start));
    // A stage says the server's time for it apart from when the browser got it, counted from the question.
    expect(find("stage", "name=sql")?.summary).toBe("name=sql server_ms=38.4 arrived_ms=10");
    expect(find("evidence", "kind=sql")?.detail).toEqual({
      kind: "sql",
      sql: HAIL_SQL,
      params: ["2025-04-01", "2025-06-30", ["CO"], ["hail"]],
    });
    expect(find("evidence", "kind=rows")?.summary).toBe("kind=rows rows=1");
    expect(find("evidence", "kind=chunks")?.summary).toBe("kind=chunks passages=2");
    expect(find("evidence", "kind=scan")?.summary).toBe("kind=scan fields=1 flagged=1");
    expect(find("evidence", "kind=sandbox")?.detail).toMatchObject({ runs: [{ delta_total: 1200000 }] });
    expect(find("answer")?.summary).toBe("kept=1 cut=0 citations=0 chars=57");
    expect(find("done")?.summary).toBe("route=quantitative outcome=answer total_ms=61.5");
    expect(find("refused")).toMatchObject({
      severity: "warn",
      detail: { reason: "write", message: "I only read data." },
    });
    expect(find("clarify")?.detail).toEqual({ question: "For which period?", options: ["year to date", "Q2 2025"] });
    expect(find("out_of_data")?.severity).toBe("warn");
    expect(find("error")).toMatchObject({
      severity: "error",
      detail: { message: "Something went wrong on our side." },
    });
    expect(find("client", "kind=http")?.summary).toBe(
      'kind=http status=429 message="You have asked 20 questions in the last minute."',
    );
    expect(entries.filter((entry) => entry.type === "client").map((entry) => entry.severity)).toEqual([
      "error",
      "error",
      "error",
      "warn",
      "error",
    ]);
    // Every event is stamped with the browser's clock, and the question's group takes the id the done brought.
    expect(entries.every((entry) => entry.at > 1_700_000_000_000 && entry.turn === 1)).toBe(true);
    expect(turns.get(1)?.requestId).toBe("5b0c1f3e-0000");
  });

  it("names the request once its done arrives, grouping its events by the question until then", () => {
    const log = testLog();
    const epoch = log.begin(3, "Why were paid losses in the West so high in Q2 2025?");
    for (const [type, data] of why.slice(0, 3)) log.event(epoch, 3, type, data);
    expect(log.view().turns.get(3)?.requestId).toBeNull();
    for (const [type, data] of why.slice(3)) log.event(epoch, 3, type, data);
    expect(log.view().turns.get(3)?.requestId).toBe("9d0c1f3e-2a47-4c1d-9e8f-0a1b2c3d4e5f");
  });

  it("holds at most its limit, dropping the oldest", () => {
    const log = testLog(5);
    const epoch = log.begin(1, "q");
    for (let n = 0; n < 8; n += 1) log.event(epoch, 1, "stage", { name: `step_${n}`, ms: n });
    const { entries } = log.view();
    expect(entries).toHaveLength(5);
    expect(entries.map((entry) => entry.summary.split(" ")[0])).toEqual([
      "name=step_3",
      "name=step_4",
      "name=step_5",
      "name=step_6",
      "name=step_7",
    ]);
  });

  it("empties when the user changes, and drops what still arrives for the user before", () => {
    const log = testLog();
    log.scope("dana");
    const danas = log.begin(1, "How much did we pay?");
    log.event(danas, 1, "stage", { name: "route", ms: 4 });
    log.scope("dana");
    expect(log.view().entries).toHaveLength(1);

    log.scope("omar");
    expect(log.view().entries).toHaveLength(0);
    expect(log.view().turns.size).toBe(0);
    log.begin(1, "How many open claims?");
    log.event(danas, 1, "done", { request_id: "late", outcome: "answer" });
    log.client(danas, 1, "cancelled", "The request was stopped.");
    expect(log.view().entries).toHaveLength(0);
  });

  it("clears the list but keeps a question still streaming in its group", () => {
    const log = testLog();
    const epoch = log.begin(1, "q");
    log.event(epoch, 1, "stage", { name: "route", ms: 4 });
    log.clear();
    expect(log.view().entries).toHaveLength(0);
    log.event(epoch, 1, "done", { request_id: "abc12345-0000", route: "lookup", outcome: "answer", total_ms: 9 });
    expect(log.view().entries).toHaveLength(1);
    expect(log.view().turns.get(1)?.requestId).toBe("abc12345-0000");
  });

  it("never keeps what the console must not show", () => {
    const log = testLog();
    const epoch = log.begin(1, "q");
    const secrets = ["Traceback (most recent call last)", "Bearer eyJhbGciOi", "hunter2", "sess=0xdeadbeef"];
    const noise = {
      trace: secrets[0],
      headers: { authorization: secrets[1], cookie: secrets[3] },
      password: secrets[2],
    };
    log.event(epoch, 1, "stage", { name: "route", ms: 4, ...noise });
    log.event(epoch, 1, "evidence", { kind: "sql", payload: { sql: "SELECT 1", params: [], ...noise }, ...noise });
    log.event(epoch, 1, "evidence", {
      kind: "chunks",
      payload: [{ chunk_id: "c1", body: "Flood is excluded.", ...noise }],
    });
    log.event(epoch, 1, "evidence", {
      kind: "sandbox",
      payload: [{ delta_total: 1, count_effect: 1, mean_effect: 0, ...noise }],
    });
    log.event(epoch, 1, "evidence", { kind: "embedding", payload: { vector: [0.1], ...noise } });
    log.event(epoch, 1, "answer", {
      text: "Paid $10.",
      claims_kept: [{ text: "Paid $10.", citations: [], ...noise }],
      claims_cut: [{ text: "The words of a cut claim", citations: ["secret-doc#1"] }],
      could_not_confirm: ["One figure did not match."],
      ...noise,
    });
    log.event(epoch, 1, "live", { fallback: "the model timed out", retried: true });
    log.event(epoch, 1, "error", { message: "Something went wrong.", stage: "sql", ...noise });
    log.event(epoch, 1, "done", { request_id: "r1", route: "lookup", outcome: "answer", ...noise });
    log.event(epoch, 1, "surprise", { ...noise });

    const kept = JSON.stringify(log.view().entries);
    for (const secret of [...secrets, "The words of a cut claim", "secret-doc", "the model timed out", "0.1"]) {
      expect(kept).not.toContain(secret);
    }
    for (const name of ["trace", "headers", "authorization", "cookie", "password", "vector", "retried"]) {
      expect(kept).not.toContain(`"${name}"`);
    }
    expect(log.view().entries.some((entry) => entry.summary.includes("live"))).toBe(false);
    const answer = log.view().entries.find((entry) => entry.type === "answer");
    expect(answer?.detail.claims_cut).toBe(1);
    expect(answer?.severity).toBe("warn");
  });

  it("forgets a finished question once none of its events are kept", () => {
    const log = testLog(3);
    const first = log.begin(1, "How much did we pay on hail claims in Colorado in Q2 2025?");
    log.event(first, 1, "done", { request_id: "r1", route: "quantitative", outcome: "answer", total_ms: 9 });
    const second = log.begin(2, "Is flood damage covered?");
    for (let n = 0; n < 3; n += 1) log.event(second, 2, "stage", { name: `step_${n}`, ms: n });
    expect([...log.view().turns.keys()]).toEqual([2]);
  });

  it("forgets finished questions when cleared, keeping one still streaming", () => {
    const log = testLog();
    const epoch = log.begin(1, "q1");
    log.event(epoch, 1, "done", { request_id: "r1", route: "lookup", outcome: "answer", total_ms: 9 });
    log.begin(2, "q2");
    log.event(epoch, 2, "stage", { name: "route", ms: 4 });
    log.clear();
    expect([...log.view().turns.keys()]).toEqual([2]);
  });

  it("remembers at most its cap of questions, dropping finished ones first", () => {
    let tick = 0;
    const log = createDevLog(
      500,
      () => (tick += 5),
      () => 1_700_000_000_000 + tick,
      3,
    );
    const epoch = log.begin(1, "q1");
    log.event(epoch, 1, "done", { request_id: "r1", route: "lookup", outcome: "answer", total_ms: 9 });
    for (const turn of [2, 3, 4]) log.begin(turn, `q${turn}`);
    expect([...log.view().turns.keys()]).toEqual([2, 3, 4]);
    log.begin(5, "q5");
    expect([...log.view().turns.keys()]).toEqual([3, 4, 5]);
  });
});
