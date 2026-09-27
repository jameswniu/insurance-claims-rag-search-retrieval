"""The top level, docs/figures/system-map.svg: one question from the browser to its answer, and what it touches."""

from __future__ import annotations

try:
    from tools import figures as f
except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
    import figures as f  # type: ignore[import-not-found, no-redef]

OUT = f.FIGURES / "system-map.svg"
TITLE = "System map, top level: one question end to end"
DESCRIPTION = (
    "The browser posts a question to the FastAPI app, where the gate refuses injection and off-topic questions and the "
    "keyword router asks back, says the period is outside the data, or picks the lookup, figures, documents or why "
    "path. Every path reads Postgres as the asker's own login, and the why path also runs a sandbox job. The verifier "
    "checks numbers and citations before the answer and its evidence stream back as server-sent events. Ingest loads "
    "documents, notes and scans into Postgres, and each request is logged for the operator dashboard."
)

M, INSET = 16, 14
TOP, APP_Y, LANES_Y = 16, 150, 196
LANE_H, LANE_GAP = 84, 14
# Gate, router, paths, verifier and answer, left to right inside the app's frame, with equal gaps between them.
WIDTHS = (162, 206, 270, 180, 190)


def columns() -> list[float]:
    inner = f.WIDTH - 2 * (M + INSET)
    gap = (inner - sum(WIDTHS)) / (len(WIDTHS) - 1)
    xs, x = [], float(M + INSET)
    for w in WIDTHS:
        xs.append(x)
        x += w + gap
    return xs


def draw() -> str:
    gx, rx, lx, vx, ax = columns()
    gw, rw, lw, vw, aw = WIDTHS
    heads = [
        ("Lookup", "one claim by id"),
        ("Figures", "typed query to SQL"),
        ("Documents", "hybrid, reranked"),
        ("Why", "drivers + memos"),
    ]
    # Each path keeps one color, in its outline and its heading.
    lanes = [
        f.Box(lx, LANES_Y + i * (LANE_H + LANE_GAP), lw, LANE_H, lines, f.NODE_BG, edge, title_fill=edge)
        for i, (lines, edge) in enumerate(zip(heads, f.PATH_EDGES, strict=True))
    ]
    mid = (lanes[0].cy + lanes[-1].cy) / 2
    lanes_bottom = lanes[-1].bottom
    gate = f.Box(gx, mid - 40, gw, 80, ("Gate",))
    router = f.Box(rx, mid - 40, rw, 80, ("Router", "keyword rules"))
    verifier = f.Box(
        vx, mid - 55, vw, 110, ("Verifier", "numbers and", "citations"), f.GREEN_BG, f.SUCCESS, title_fill=f.SUCCESS
    )
    answer = f.Box(ax, mid - 40, aw, 80, ("Answer", "and evidence"))
    refused = f.Box(gx, lanes_bottom - 108, gw, 108, ("Refused", "injection,", "off-topic"))
    clarify = f.Box(rx, lanes_bottom - 108, rw, 108, ("Clarify", "one question,", "with options"))
    outside = f.Box(rx, LANES_Y, rw, 108, ("Out of data", "Jan 2024 to", "Jun 2026"))
    browser = f.Box(M, TOP, f.WIDTH - 2 * M, 76, ("Browser", "React chat page, reads the answer as it streams"))
    app_bottom = lanes_bottom + 20

    row = app_bottom + 56
    ingest = f.Box(M, row, 270, 110, ("Ingest", "docs, notes, scans", "mask, screen, OCR"))
    postgres = f.Box(400, row, 290, 110, ("Postgres", "claims and chunks", "row-level security"))
    sandbox = f.Box(730, row, 176, 110, ("Sandbox", "no network,", "10 s a job"))
    telemetry = f.Box(answer.cx - 108, row, 216, 110, ("Telemetry", "request log", "and spans"))
    dashboard = f.Box(telemetry.x, telemetry.bottom + 50, 216, 80, ("Dashboard", "operators only"))
    if telemetry.right > f.WIDTH - M or not lanes[0].x < postgres.cx < lanes[0].right:
        raise SystemExit("the bottom row has drifted out from under the columns it hangs from")

    bus_in, bus_out = (router.right + lx) / 2, (lanes[0].right + vx) / 2
    turn = (app_bottom + row) / 2
    why_x = lanes[-1].right - 30
    parts = [
        *f.group(M, APP_Y, f.WIDTH - 2 * M, app_bottom - APP_Y, "FastAPI app", name_x=lanes[0].cx),
        f.path([(gate.cx, browser.bottom), (gate.cx, gate.y)]),
        f.label(gate.cx + 14, (browser.bottom + APP_Y) / 2 + 8, "POST /ask", anchor="start", mono=True),
        f.path([(answer.cx, answer.y), (answer.cx, browser.bottom)]),
        f.label(answer.cx - 14, (browser.bottom + APP_Y) / 2 + 8, "server-sent events", anchor="end"),
        f.path([(gate.right, mid), (router.x, mid)]),
        f.path([(gate.cx, gate.bottom), (gate.cx, refused.y)]),
        f.path([(router.cx, router.bottom), (router.cx, clarify.y)]),
        f.path([(router.cx, router.y), (router.cx, outside.bottom)]),
        f.path([(router.right, mid), (bus_in, mid)], arrow=False),
        f.path([(bus_in, lanes[0].cy), (bus_in, lanes[-1].cy)], arrow=False),
        *[f.path([(bus_in, lane.cy), (lane.x, lane.cy)]) for lane in lanes],
        *[f.path([(lane.right, lane.cy), (bus_out, lane.cy)], arrow=False) for lane in lanes],
        f.path([(bus_out, lanes[0].cy), (bus_out, lanes[-1].cy)], arrow=False),
        f.path([(bus_out, mid), (verifier.x, mid)]),
        f.path([(verifier.right, mid), (answer.x, mid)]),
        f.path([(answer.cx, answer.bottom), (answer.cx, telemetry.y)]),
        f.path([(telemetry.cx, telemetry.bottom), (telemetry.cx, dashboard.y)]),
        f.path([(ingest.right, ingest.cy), (postgres.x, ingest.cy)]),
        f.path([(postgres.cx, lanes_bottom), (postgres.cx, postgres.y)], dashed=True),
        f.label(postgres.cx - 14, turn + 8, "as the asker's own login", anchor="end", lo=M),
        f.path([(why_x, lanes_bottom), (why_x, turn), (sandbox.cx, turn), (sandbox.cx, sandbox.y)], dashed=True),
    ]
    boxes = [browser, gate, router, outside, clarify, refused, *lanes, verifier, answer]
    boxes += [ingest, postgres, sandbox, telemetry, dashboard]
    parts += [part for box in boxes for part in box.svg()]
    return f.document(TITLE, DESCRIPTION, dashboard.bottom + M + 8, parts)
