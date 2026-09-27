"""The middle level, docs/figures/system-paths.svg: the steps inside each path, the verifier's checks, and what live
mode adds."""

from __future__ import annotations

try:
    from tools import figures as f
except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
    import figures as f  # type: ignore[import-not-found, no-redef]

OUT = f.FIGURES / "system-paths.svg"
TITLE = "System paths, mid level: the steps inside each path"
DESCRIPTION = (
    "Four columns show each path's steps. Lookup reads one claim row or its scanned form, checks a scan's total "
    "against payments, and answers a hidden claim as a missing one. Figures fill a typed query from the semantic "
    "layer, check the period against the data, compile SQL through an AST allow-list and run it on the asker's login. "
    "Documents read the policy edition in force on the loss date, fuse full-text and vector search, rerank, and cite "
    "a chunk for every line. Why fetches both periods, splits the change by driver with a sandbox template, finds a "
    "memo or bulletin from within 92 days, and builds its sentences from the rows. The verifier traces figures and "
    "citations and checks comparative words. Live mode adds a fast model, a main model, an orchestrator with three "
    "tools and a Gemini checker."
)

M, INSET = 16, 14
COLUMN_W, BOX_H, GAP = 270, 72, 24
LANES = (
    (("Lookup", "one claim by id"), [
        ("Claim number", "from the question"),
        ("Claim row", "or its scan fields"),
        ("Scan total", "matched to paid"),
        ("Hidden claim", "reads as missing"),
    ]),
    (("Figures", "typed query to SQL"), [
        ("Typed query", "semantic layer"),
        ("Period check", "inside the data"),
        ("Compiled SQL", "AST allow-list"),
        ("Asker's login", "4 s, 500 rows"),
    ]),
    (("Documents", "hybrid, reranked"), [
        ("Policy edition", "on the loss date"),
        ("Two searches", "full text, vectors"),
        ("Fused, reranked", "RRF, cross-encoder"),
        ("Cited lines", "each names a chunk"),
    ]),
    (("Why", "drivers + memos"), [
        ("Both periods", "this vs the last"),
        ("Driver split", "sandbox template"),
        ("Memo, bulletin", "within 92 days"),
        ("Sentences", "built from rows"),
    ]),
)  # fmt: skip
CHECKS = (
    ("Figures", "traced to rows or", "sandbox output"),
    ("Citations", "retrieved for you,", "in your regions"),
    ("Wording", "rose, highest and", "doubled must hold"),
    ("One retry", "for live writers,", "then failures cut"),
)
LIVE = (
    ("Fast model", "claude-haiku-4-5", "routes, and fills", "a typed query"),
    ("Main model", "claude-sonnet-5", "writes cited", "document answers"),
    ("Orchestrator", "query_metric", "analyze", "find_documents"),
    ("Checker", "gemini-3.8-flash", "or the fast model,", "reads cited lines"),
)


def columns() -> list[float]:
    inner = f.WIDTH - 2 * (M + INSET)
    gap = (inner - 4 * COLUMN_W) / 3
    return [M + INSET + i * (COLUMN_W + gap) for i in range(4)]


def draw() -> str:
    xs = columns()
    parts: list[str] = []
    boxes: list[f.Box] = []
    last_bottom = 0.0
    for x, (head, steps) in zip(xs, LANES, strict=True):
        header = f.Box(x, M, COLUMN_W, BOX_H, head, f.BLUE_BG, f.BLUE_EDGE)
        column = [header]
        for i, lines in enumerate(steps):
            column.append(f.Box(x, header.bottom + GAP + i * (BOX_H + GAP), COLUMN_W, BOX_H, lines))
        parts += [f.path([(a.cx, a.bottom), (b.cx, b.y)]) for a, b in zip(column, column[1:], strict=False)]
        boxes += column
        last_bottom = max(last_bottom, column[-1].bottom)

    check_y = last_bottom + 36
    parts += f.group(M, check_y, f.WIDTH - 2 * M, 168, "Verifier, on every sentence of every answer")
    for x, check in zip(xs, CHECKS, strict=True):
        boxes.append(f.Box(x, check_y + 44, COLUMN_W, 108, check, f.GREEN_BG, f.GREEN_EDGE))
    parts += [f.path([(x + COLUMN_W / 2, last_bottom), (x + COLUMN_W / 2, check_y)]) for x in xs]

    live_y = check_y + 168 + 36
    parts += f.group(M, live_y, f.WIDTH - 2 * M, 196, "Live mode, when LLM_BACKEND names a backend")
    for x, part in zip(xs, LIVE, strict=True):
        mono = frozenset({1, 2, 3}) if part[0] == "Orchestrator" else frozenset({1})
        boxes.append(f.Box(x, live_y + 44, COLUMN_W, 136, part, mono=mono))
    parts += [part for box in boxes for part in box.svg()]
    return f.document(TITLE, DESCRIPTION, live_y + 196 + M, parts)
