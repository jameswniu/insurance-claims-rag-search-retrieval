"""The low level, docs/figures/system-runtime.svg: the compose services, the database logins and what each may read,
the sandbox job's limits, and the telemetry."""

from __future__ import annotations

try:
    from tools import figures as f
except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
    import figures as f  # type: ignore[import-not-found, no-redef]

OUT = f.FIGURES / "system-runtime.svg"
TITLE = "System runtime, low level: what runs where"
DESCRIPTION = (
    "Five compose services: init bootstraps the database once, db is Postgres 17 with pgvector, app is the FastAPI "
    "app on port 8000, sandboxd holds the Docker socket and starts one sandbox container per job. In Postgres, four "
    "adjuster logins share chat_adjuster, the supervisor has chat_supervisor and the analyst chat_analyst. Adjusters "
    "and the supervisor read through forced row security keyed on session_user and security_invoker views. The "
    "analyst reads only agg.metric, which runs as agg_owner and withholds cells under 10 claims or where one claim is "
    "over half. Each sandbox job has no network, a read-only root, uid 65534, 512 MB, one CPU, 64 processes, 10 "
    "seconds and 1 MiB of output. Telemetry is OpenTelemetry spans, request and audit rows, and the operator dashboard."
)

M, INSET, HEAD = 16, 14, 44
X0 = M + INSET
INNER = f.WIDTH - 2 * X0

ADJUSTERS = ("Adjusters", "u_adj_north", "u_adj_south", "u_adj_east", "u_adj_west")
ROW_SECURITY = ("Row security", "forced, every table", "visible_regions()", "session_user")
METRIC = ("agg.metric()", "runs as agg_owner,", "withholds cells", "under 10 claims or", "one claim over half")
TELEMETRY = ("Spans and logs", "OpenTelemetry, OTLP", "request, audit rows", "operator dashboard")


def spread(widths: tuple[float, ...]) -> list[float]:
    """The x of each box, left to right across the frame with equal gaps."""
    gap = (INNER - sum(widths)) / (len(widths) - 1)
    xs, x = [], float(X0)
    for w in widths:
        xs.append(x)
        x += w + gap
    return xs


def centred(x: float, cy: float, w: float, lines: tuple[str, ...], mono: frozenset[int] = frozenset()) -> f.Box:
    """A box as tall as its lines need, centred on cy, so the connector into it runs straight across."""
    h = f.STEP * len(lines) + 8 if len(lines) > 2 else 72
    return f.Box(x, cy - h / 2, w, h, lines, mono=mono)


def services(y: float) -> tuple[list[str], list[f.Box]]:
    widths = (202.0,) * 5
    xs = spread(widths)
    named = [
        ("init", "one-shot", "bootstrap"),
        ("db", "Postgres 17", "and pgvector"),
        ("app", "FastAPI app", "port 8000"),
        ("sandboxd", "holds the", "Docker socket"),
        ("sandbox", "one container", "per job"),
    ]
    boxes = [
        f.Box(x, y + HEAD, w, 108, lines, mono=frozenset({0})) for x, w, lines in zip(xs, widths, named, strict=True)
    ]
    init, db, app, daemon, job = boxes
    mid = init.cy
    parts = [
        *f.group(M, y, f.WIDTH - 2 * M, HEAD + 108 + 16, "Compose services, on an internal backend network"),
        f.path([(init.right, mid), (db.x, mid)]),
        f.path([(app.x, mid), (db.right, mid)]),
        f.path([(app.right, mid), (daemon.x, mid)]),
        f.path([(daemon.right, mid), (job.x, mid)]),
    ]
    return parts, boxes


def database(y: float) -> tuple[list[str], list[f.Box]]:
    x1, x2, x3, x4 = spread((210, 270, 290, 260))
    top = y + HEAD
    adjusters = f.Box(x1, top, 210, 168, ADJUSTERS, mono=frozenset({1, 2, 3, 4}))
    supervisor = f.Box(x1, top + 184, 210, 72, ("Supervisor", "u_supervisor"), mono=frozenset({1}))
    analyst = f.Box(x1, top + 304, 210, 72, ("Analyst", "u_analyst"), mono=frozenset({1}))
    adj_group = centred(
        x2, adjusters.cy, 270, ("chat_adjuster", "core and rag,", "no PII columns"), mono=frozenset({0})
    )
    sup_group = centred(x2, supervisor.cy, 270, ("chat_supervisor", "same grants"), mono=frozenset({0}))
    ana_group = centred(x2, analyst.cy, 270, ("chat_analyst", "no claim rows"), mono=frozenset({0}))
    rows = f.Box(x3, top + 20, 290, 216, ROW_SECURITY, mono=frozenset({2, 3}))
    metric = centred(x3, analyst.cy, 290, METRIC, mono=frozenset({0}))
    views = centred(x4, rows.cy, 260, ("Views", "security_invoker", "so RLS applies"), mono=frozenset({1}))
    tables = centred(x4, metric.cy, 260, ("Core tables", "claims, payments,", "premium, policies"))
    if metric.y < rows.bottom + 16 or metric.bottom > top + 424:
        raise SystemExit("the analyst's row has run into its neighbours")
    parts = [
        *f.group(M, y, f.WIDTH - 2 * M, HEAD + 424 + 16, "Postgres logins, read-only with a 4 s statement timeout"),
        *[
            f.path([(a.right, a.cy), (b.x, a.cy)])
            for a, b in ((adjusters, adj_group), (supervisor, sup_group), (analyst, ana_group))
        ],
        f.path([(adj_group.right, adj_group.cy), (rows.x, adj_group.cy)]),
        f.path([(sup_group.right, sup_group.cy), (rows.x, sup_group.cy)]),
        f.path([(ana_group.right, ana_group.cy), (metric.x, ana_group.cy)]),
        f.path([(rows.right, views.cy), (views.x, views.cy)]),
        f.path([(views.cx, views.bottom), (views.cx, tables.y)]),
        f.path([(metric.right, tables.cy), (tables.x, tables.cy)]),
    ]
    boxes = [adjusters, supervisor, analyst, adj_group, sup_group, ana_group, rows, metric, views, tables]
    return parts, boxes


def limits(y: float) -> tuple[list[str], list[f.Box]]:
    job_w = 740
    xs = [X0 + i * (224 + 20) for i in range(3)]
    named = [
        ("Isolation", "no network", "read-only root", "uid 65534"),
        ("Resources", "512 MB memory", "1 CPU", "64 processes"),
        ("Time, output", "10 s, killed", "1 MiB output", "2 jobs a login"),
    ]
    boxes = [f.Box(x, y + HEAD, 224, 136, lines) for x, lines in zip(xs, named, strict=True)]
    tel_x = M + job_w + 20
    boxes.append(f.Box(tel_x + INSET, y + HEAD, f.WIDTH - M - tel_x - 2 * INSET, 136, TELEMETRY))
    parts = [
        *f.group(M, y, job_w, HEAD + 136 + 16, "Each sandbox job"),
        *f.group(tel_x, y, f.WIDTH - M - tel_x, HEAD + 136 + 16, "Telemetry"),
    ]
    return parts, boxes


def draw() -> str:
    parts: list[str] = []
    boxes: list[f.Box] = []
    y = float(M)
    for band, height in ((services, HEAD + 108 + 16), (database, HEAD + 424 + 16), (limits, HEAD + 136 + 16)):
        drawn, placed = band(y)
        parts += drawn
        boxes += placed
        y += height + 36
    parts += [part for box in boxes for part in box.svg()]
    return f.document(TITLE, DESCRIPTION, y - 36 + M, parts)
