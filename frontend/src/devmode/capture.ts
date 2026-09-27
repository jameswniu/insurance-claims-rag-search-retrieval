import { asText } from "@/lib/text";

// What the console keeps of each stream event, taken as it arrives, before the page turns it into a reply. Every kind
// keeps only the fields named here, clipped to a size, so the console never holds more than the server sent this user,
// and never anything it doesn't show: no headers, no credentials, no traces, and no words of a cut claim, only the
// count. The server never sends its live events, and one that arrived would be dropped here too.

export type Severity = "info" | "warn" | "error";
export type EventType =
  "stage" | "evidence" | "answer" | "refused" | "clarify" | "out_of_data" | "error" | "done" | "client";
export type ClientKind = "http" | "parse" | "connection" | "cancelled" | "premature_close" | "script";

export const EVENT_TYPES: readonly EventType[] = [
  "stage",
  "evidence",
  "answer",
  "refused",
  "clarify",
  "out_of_data",
  "error",
  "done",
  "client",
];

/** One event as the console keeps it. */
export interface Captured {
  type: EventType;
  severity: Severity;
  /** The fields that matter, on one line, as name=value. */
  summary: string;
  /** The allowlisted fields, for the row's expanded view. */
  detail: Record<string, unknown>;
  /** The server's id for the request, from the events that carry it. */
  requestId?: string;
}

const MAX_TEXT = 2000;
const MAX_ITEMS = 50;
const MAX_DEPTH = 4;
const SUMMARY_TEXT = 72;
const CLIENT_TEXT = 300;

const CHUNK_KEYS = [
  "chunk_id",
  "doc_id",
  "anchor",
  "title",
  "header",
  "section",
  "kind",
  "edition",
  "region",
  "claim_id",
  "score",
  "rerank_score",
  "similarity",
  "lexical_rank",
  "vector_rank",
  "quarantined",
  "body",
  "text",
  "snippet",
];
const SCAN_KEYS = ["doc_id", "title", "field", "value", "confidence", "bbox", "flagged", "flag_reason"];
const SPLIT_KEYS = [
  "group",
  "n_base",
  "n_current",
  "total_base",
  "total_current",
  "mean_base",
  "mean_current",
  "delta_total",
  "count_effect",
  "mean_effect",
  "share",
];
const WARN_OUTCOMES = new Set(["not_found", "not_allowed", "out_of_data", "refused"]);
const ERROR_OUTCOMES = new Set(["error", "timeout", "unavailable"]);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const listOf = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

/** A copy of a value, clipped: long text cut, long lists cut short, and nesting stopped four levels down. */
export function clip(value: unknown, depth = 0): unknown {
  if (value === null || typeof value === "boolean" || typeof value === "number") return value;
  if (typeof value === "string") {
    return value.length > MAX_TEXT
      ? `${value.slice(0, MAX_TEXT)}… (${value.length - MAX_TEXT} more characters)`
      : value;
  }
  if (depth >= MAX_DEPTH) return "…";
  if (Array.isArray(value)) {
    const kept = value.slice(0, MAX_ITEMS).map((item) => clip(item, depth + 1));
    return value.length > MAX_ITEMS ? [...kept, `… ${value.length - MAX_ITEMS} more`] : kept;
  }
  if (isRecord(value))
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clip(item, depth + 1)]));
  return asText(value);
}

/** Only the named fields of a record, each clipped. */
function pick(value: unknown, keys: readonly string[]): Record<string, unknown> {
  const found = isRecord(value) ? value : {};
  return Object.fromEntries(keys.filter((key) => found[key] !== undefined).map((key) => [key, clip(found[key], 1)]));
}

function field(name: string, value: unknown): string {
  const text = asText(value);
  const short = text.length > SUMMARY_TEXT ? `${text.slice(0, SUMMARY_TEXT)}…` : text;
  return /^[\w.:/-]+$/.test(short) ? `${name}=${short}` : `${name}=${JSON.stringify(short)}`;
}

function line(fields: [string, unknown][]): string {
  return fields
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([name, value]) => field(name, value))
    .join(" ");
}

function tidy(text: string): string {
  const flat = text
    .replace(/\p{Cc}+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length > CLIENT_TEXT ? `${flat.slice(0, CLIENT_TEXT)}…` : flat;
}

function evidence(data: Record<string, unknown>): Captured {
  const kind = asText(data.kind);
  const payload = data.payload;
  const found = isRecord(payload) ? payload : {};
  let detail: Record<string, unknown> = {};
  let facts: [string, unknown][];
  if (kind === "sql") {
    detail = typeof payload === "string" ? { sql: clip(payload, 1) } : pick(payload, ["sql", "params", "role"]);
    const sql = typeof payload === "string" ? payload : asText(found.sql);
    facts = [
      ["params", Array.isArray(found.params) ? found.params.length : undefined],
      ["role", found.role],
      ["sql", sql],
    ];
  } else if (kind === "rows") {
    const rows = Array.isArray(payload) ? payload : listOf(found.rows);
    detail = { ...pick(payload, ["row_count", "truncated", "columns"]), rows: clip(rows, 1) };
    facts = [
      ["rows", typeof found.row_count === "number" ? found.row_count : rows.length],
      ["truncated", found.truncated === true ? "true" : undefined],
    ];
  } else if (kind === "chunks") {
    const chunks = Array.isArray(payload) ? payload : listOf(found.chunks ?? found.hits);
    detail = { chunks: chunks.slice(0, MAX_ITEMS).map((chunk) => pick(chunk, CHUNK_KEYS)) };
    facts = [["passages", chunks.length]];
  } else if (kind === "scan") {
    const fields = Array.isArray(payload) ? payload : listOf(found.fields);
    detail = { fields: fields.slice(0, MAX_ITEMS).map((item) => pick(item, SCAN_KEYS)) };
    facts = [
      ["fields", fields.length],
      ["flagged", fields.filter((item) => isRecord(item) && item.flagged === true).length || undefined],
    ];
  } else if (kind === "sandbox") {
    const runs = listOf(payload).slice(0, MAX_ITEMS);
    detail = {
      runs: runs.map((run) => {
        const groups = isRecord(run) && Array.isArray(run.groups) ? run.groups : null;
        const kept = pick(run, SPLIT_KEYS);
        return groups ? { ...kept, groups: groups.slice(0, MAX_ITEMS).map((group) => pick(group, SPLIT_KEYS)) } : kept;
      }),
    };
    facts = [["runs", runs.length]];
  } else {
    facts = [["payload", "not kept"]];
  }
  return { type: "evidence", severity: "info", summary: line([["kind", kind], ...facts]), detail: { kind, ...detail } };
}

function answer(data: Record<string, unknown>): Captured {
  const kept = listOf(data.claims_kept)
    .slice(0, MAX_ITEMS)
    .map((claim) => (typeof claim === "string" ? clip(claim, 1) : pick(claim, ["text", "citations"])));
  // Only the count of cut claims: their words never reach the page, whatever shape the count arrives in.
  const raw = data.claims_cut;
  const cut = typeof raw === "number" ? raw : Array.isArray(raw) ? raw.length : 0;
  const reasons = Array.isArray(data.could_not_confirm)
    ? data.could_not_confirm.slice(0, MAX_ITEMS).map((reason) => clip(asText(reason), 1))
    : data.could_not_confirm === true;
  const citations = listOf(data.citations)
    .slice(0, MAX_ITEMS)
    .map((source) => pick(source, CHUNK_KEYS));
  const text = asText(data.text);
  const flagged = cut > 0 || reasons === true || (Array.isArray(reasons) && reasons.length > 0);
  return {
    type: "answer",
    severity: flagged ? "warn" : "info",
    summary: line([
      ["kept", kept.length],
      ["cut", cut],
      ["citations", citations.length],
      ["chars", text.length],
    ]),
    detail: { text: clip(text, 1), citations, claims_kept: kept, claims_cut: cut, could_not_confirm: reasons },
  };
}

function done(data: Record<string, unknown>): Captured {
  const detail = pick(data, ["request_id", "route", "outcome", "total_ms", "claim_ids", "doc_ids"]);
  const outcome = asText(data.outcome);
  const claims = listOf(data.claim_ids).length;
  const docs = listOf(data.doc_ids).length;
  return {
    type: "done",
    severity: ERROR_OUTCOMES.has(outcome) ? "error" : WARN_OUTCOMES.has(outcome) ? "warn" : "info",
    summary: line([
      ["route", data.route],
      ["outcome", outcome],
      ["total_ms", data.total_ms],
      ["claims", claims || undefined],
      ["docs", docs || undefined],
    ]),
    detail,
    ...(typeof data.request_id === "string" ? { requestId: data.request_id } : {}),
  };
}

/**
 * What the console keeps of one stream event, or null for an event it never shows. arrivedMs is when it arrived,
 * counted from when the question was sent, so a stage's arrival reads apart from the server's own time for it.
 */
export function capture(type: string, payload: unknown, arrivedMs: number): Captured | null {
  const data = isRecord(payload) ? payload : {};
  switch (type) {
    case "stage": {
      const detail = { name: asText(data.name), server_ms: Number(data.ms) || 0, arrived_ms: Math.round(arrivedMs) };
      const summary = line([
        ["name", detail.name],
        ["server_ms", detail.server_ms],
        ["arrived_ms", detail.arrived_ms],
      ]);
      return { type, severity: "info", summary, detail };
    }
    case "evidence":
      return evidence(data);
    case "answer":
      return answer(data);
    case "refused": {
      const detail = pick(data, ["reason", "message"]);
      return {
        type,
        severity: "warn",
        summary: line([
          ["reason", data.reason],
          ["message", data.message],
        ]),
        detail,
      };
    }
    case "clarify": {
      const question = asText(data.question ?? data.message);
      const options = listOf(data.options);
      const detail = { question: clip(question, 1), options: clip(options, 1) };
      return {
        type,
        severity: "info",
        summary: line([
          ["question", question],
          ["options", options.length],
        ]),
        detail,
      };
    }
    case "out_of_data": {
      const detail = pick(data, ["message", "covered"]);
      return {
        type,
        severity: "warn",
        summary: line([
          ["covered", data.covered],
          ["message", data.message],
        ]),
        detail,
      };
    }
    case "error": {
      const detail = pick(data, ["message", "stage", "request_id"]);
      const summary = line([
        ["message", data.message],
        ["stage", data.stage],
      ]);
      const requestId = typeof data.request_id === "string" ? { requestId: data.request_id } : {};
      return { type, severity: "error", summary, detail, ...requestId };
    }
    case "done":
      return done(data);
    case "live":
      return null;
    default:
      // The page ends an answer on a kind it doesn't know, so the console shows it as an error, without its fields.
      return {
        type: "error",
        severity: "error",
        summary: line([["unknown_event", type]]),
        detail: { event: tidy(type) },
      };
  }
}

/** A failure on the page's side of a request: what went wrong, in the page's own words or the server's sentence. */
export function captureClient(kind: ClientKind, message: string, status?: number): Captured {
  const detail = { kind, ...(status === undefined ? {} : { status }), message: tidy(message) };
  return {
    type: "client",
    severity: kind === "cancelled" ? "warn" : "error",
    summary: line([
      ["kind", kind],
      ["status", status],
      ["message", detail.message],
    ]),
    detail,
  };
}
