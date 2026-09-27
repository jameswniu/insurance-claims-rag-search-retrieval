"""The README's eval comparison, docs/figures/eval-comparison.svg: four checks, dev beside held-out, each a rate with
its Wilson interval drawn on the whole scale from none to all.

Every number and bar is read from evals/report.json as it is drawn. The interval ends are the report's own, never
worked out again from a rounded rate, and a missing key or an invalid interval stops the drawing.
"""

from __future__ import annotations

try:
    from tools import figures as f
except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
    import figures as f  # type: ignore[import-not-found, no-redef]

OUT = f.FIGURES / "eval-comparison.svg"
HEIGHT = 624

# The light palette the README's other figures share.
CANVAS, PRIMARY, SECONDARY, BORDER = "#FFFFFF", "#202B36", "#435363", "#D1D9E0"
DEV_INK, HELD_INK = "#5D6B79", "#245B85"

M = 48
RIGHT = f.WIDTH - M
NAME = "Dev and held-out"
SUBTITLE = "No API key · Points are rates, bars are Wilson intervals."
FOOTER = "Dev shaped the rules. Held-out cases were reserved."

# Each check by its row label and its path under a split. The same path is read from dev and from held-out.
ROWS = (
    ("Routing", "routing.accuracy"),
    ("Refusals", "refusal.recall"),
    ("SQL results", "sql.execution_accuracy"),
    ("Cited answers", "answers.grounded"),
)
ROW_TOPS, ROW_H = (176, 264, 352, 440), 88
LABEL_END = 336

# A plot per split: its heading, where it starts, the split it reads, its colour and whether its point is hollow.
PLOT_W = 344
PLOTS = (("Dev", 360, "dev", DEV_INK, True), ("Held-out", 784, "heldout", HELD_INK, False))
HEADING_Y, COUNT_DY, TRACK_DY, CAP, AXIS_Y = 146, 30, 62, 14, 550


def count_label(r: f.Rate) -> str:
    return f"{r.hits}/{r.n} · {100 * r.value:.1f}%"


def said(r: f.Rate) -> str:
    """The same rate as a screen reader hears it."""
    return f"{r.hits} of {r.n} ({100 * r.value:.1f}%, interval {100 * r.low:.1f}% to {100 * r.high:.1f}%)"


def rates(report: f.Report) -> list[tuple[str, f.Rate, f.Rate]]:
    """Each row's label with its dev and held-out rates, checked by f.rate: hits within n, value inside its interval."""
    return [(label, f.rate(report, f"dev.{path}"), f.rate(report, f"heldout.{path}")) for label, path in ROWS]


def plot(left: int, top: int, r: f.Rate, ink: str, hollow: bool) -> list[str]:
    """One rate on its row: the count above, the full track, the interval with its end caps, and the point."""
    y, right, half = top + TRACK_DY, left + PLOT_W, CAP // 2
    low, high, at = (left + PLOT_W * v for v in (r.low, r.high, r.value))
    cap = f'stroke="{ink}" stroke-width="3"'
    if hollow:
        point = f'<circle cx="{at:.1f}" cy="{y}" r="7" fill="{CANVAS}" stroke="{ink}" stroke-width="3"/>'
    else:
        point = f'<circle cx="{at:.1f}" cy="{y}" r="8" fill="{ink}"/>'
    return [
        f.fitted(left, top + COUNT_DY, count_label(r), 26, PRIMARY, left, right),
        f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="{BORDER}" stroke-width="2"/>',
        f'<line x1="{low:.1f}" y1="{y}" x2="{high:.1f}" y2="{y}" stroke="{ink}" stroke-width="5"/>',
        *(f'<line x1="{end:.1f}" y1="{y - half}" x2="{end:.1f}" y2="{y + half}" {cap}/>' for end in (low, high)),
        point,
    ]


def draw(report: f.Report) -> str:
    rows = rates(report)
    if len(rows) != len(ROW_TOPS) or ROW_TOPS[-1] + TRACK_DY + CAP > AXIS_Y - 24:
        raise SystemExit("the rows don't match their tops, or the last one runs into the axis labels")
    parts = [
        "<style>text{font-variant-numeric:tabular-nums}</style>",
        f.fitted(M, 60, NAME, 40, PRIMARY, M, RIGHT, bold=True),
        f.fitted(M, 100, SUBTITLE, 26, SECONDARY, M, RIGHT),
        f.fitted(M, 584, FOOTER, 26, SECONDARY, M, RIGHT),
    ]
    for heading, left, _, _, _ in PLOTS:
        right = left + PLOT_W
        parts.append(f.fitted(left + PLOT_W / 2, HEADING_Y, heading, 28, PRIMARY, left, right, True, "middle"))
        parts.append(f.fitted(left, AXIS_Y, "None", 24, SECONDARY, left, right))
        parts.append(f.fitted(right, AXIS_Y, "All", 24, SECONDARY, left, right, anchor="end"))
    for (label, dev, held), top in zip(rows, ROW_TOPS, strict=True):
        parts.append(f.fitted(M, top + 50, label, 28, PRIMARY, M, LABEL_END, bold=True))
        for (_, left, _, ink, hollow), r in zip(PLOTS, (dev, held), strict=True):
            parts += plot(left, top, r, ink, hollow)
    parts.append(f.frame(HEIGHT, BORDER))
    title = f"{NAME}, eval results with no API key"
    lines = [f"{label}: dev {said(dev)}, held-out {said(held)}." for label, dev, held in rows]
    description = f"{NAME} with no API key, each check a rate with its Wilson interval. {' '.join(lines)} {FOOTER}"
    return f.document(title, description, HEIGHT, parts)
