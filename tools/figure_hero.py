"""The README's opening, docs/figures/hero.svg: what the app is, four measured results and the stages of a question.

Every number on it is read from evals/report.json as it is drawn, and a missing key or an invalid rate stops it."""

from __future__ import annotations

import math
from dataclasses import dataclass

try:
    from tools import figures as f
except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
    import figures as f  # type: ignore[import-not-found, no-redef]

OUT = f.FIGURES / "hero.svg"
HEIGHT = 528

CANVAS, PANEL, TINT, BORDER = "#141A21", "#1D252E", "#25394A", "#43515F"  # fixed dark, the app's Dev mode palette
PRIMARY, SECONDARY, ACCENT = "#E9EEF3", "#BCC7D2", "#8CB4DF"

M = 48
RIGHT = f.WIDTH - M
KICKER = "Home insurance · Synthetic data"
NAME = "Claims Q&A"
SUBTITLE = "Ask about claims, policies and scanned forms."
RESULTS = "Eval results · No API key"
FOOTER = "Queries use the asker's Postgres login under row-level security."

# The table mark at the upper right, drawn from rules only: its frame, two row rules and one column rule.
MARK_X, MARK_Y, MARK_W, MARK_H = 1032, 64, 120, 100
MARK_ROWS, MARK_COLUMN = (96, 130), 1072

# Tiles share the row from M to RIGHT, each as wide as its longest line plus padding. Four equal tiles can't hold
# "34 held-out answers" at 26 units, and text is never shrunk to fit, so a longer line widens its own tile.
TILE_Y, TILE_H, GAP, PAD = 238, 160, 16, 16
VALUE_Y, CAPTION_Y, CONTEXT_Y = 296, 342, 376
VALUE, CAPTION, CONTEXT = 56, 28, 26

PILL_Y, PILL_H, PILL_BASE, PILL_TEXT = 424, 44, 454, 26
PILLS: tuple[tuple[str, int, int], ...] = (("Gate", 48, 144), ("Route", 208, 152), ("Query or search", 376, 312))
PILLS += (("Verify", 704, 208), ("Stream", 928, 224))
HIGHLIGHT = "Verify"


@dataclass(frozen=True)
class Tile:
    """One result: its value, what it counts, what it was counted over, and the same said as a sentence."""

    value: str
    caption: str
    context: str
    said: str


def tiles(report: f.Report) -> list[Tile]:
    """The four results, bound to the report. No count is typed here."""
    leaks, runs = f.count(report, "dev.permissions.leaks"), f.count(report, "dev.permissions.runs")
    harmful = f.count(report, "shared.hostile_sql.harmful")
    executions = f.count(report, "shared.hostile_sql.executions")
    caught, planted = f.count(report, "shared.verifier.caught"), f.count(report, "shared.verifier.planted")
    wrong = f.rate(report, "heldout.abstention.wrong_answer")
    if harmful > executions or caught > planted:
        raise SystemExit("evals/report.json counts more harmful executions or caught errors than it ran or planted")
    held, sql = f"{wrong.n} held-out answers", f"{harmful} harmful SQL executions in {executions}"
    return [
        Tile(str(leaks), "Leaks found", f"{runs} dev runs", f"{leaks} leaks found in {runs} dev runs"),
        Tile(str(harmful), "Harmful SQL", f"{executions} executions", sql),
        Tile(f"{caught}/{planted}", "Errors caught", "Planted errors", f"{caught} of {planted} planted errors caught"),
        Tile(str(wrong.hits), "Wrong answers", held, f"{wrong.hits} wrong answers in {held}"),
    ]


def widths(row: list[Tile]) -> list[int]:
    """Each tile's longest line measured, plus padding, with the spare width given to the narrowest tile first."""
    needs = [
        math.ceil(max(f.width(t.value, VALUE, True), f.width(t.caption, CAPTION, True), f.width(t.context, CONTEXT)))
        + 2 * PAD
        for t in row
    ]
    room = RIGHT - M - GAP * (len(row) - 1)
    if sum(needs) > room:
        raise SystemExit(f"the tiles need {sum(needs)} units and the row holds {room}")
    out = list(needs)
    for _ in range(room - sum(needs)):
        out[out.index(min(out))] += 1
    return out


def tile(x: int, w: int, t: Tile) -> list[str]:
    """A panel with the value on top, then what it counts, then what it was counted over, each measured inside it."""
    lo, hi, cx = x + PAD, x + w - PAD, x + w / 2
    return [
        f'<rect x="{x}" y="{TILE_Y}" width="{w}" height="{TILE_H}" fill="{PANEL}" stroke="{BORDER}" stroke-width="2"/>',
        f.fitted(cx, VALUE_Y, t.value, VALUE, ACCENT, lo, hi, bold=True, anchor="middle"),
        f.fitted(cx, CAPTION_Y, t.caption, CAPTION, PRIMARY, lo, hi, bold=True, anchor="middle"),
        f.fitted(cx, CONTEXT_Y, t.context, CONTEXT, SECONDARY, lo, hi, anchor="middle"),
    ]


def pills() -> list[str]:
    """The stages a question passes, left to right with empty gaps, the verifier filled in."""
    out: list[str] = []
    for (name, x, w), after in zip(PILLS, [*PILLS[1:], ("", RIGHT + GAP, 0)], strict=True):
        if x + w + GAP > after[1]:
            raise SystemExit(f"the {name} pill runs into the next one or past the margin")
        fill, edge, ink = (ACCENT, ACCENT, CANVAS) if name == HIGHLIGHT else (PANEL, BORDER, SECONDARY)
        shape, r = f'x="{x}" y="{PILL_Y}" width="{w}" height="{PILL_H}"', PILL_H // 2
        out.append(f'<rect {shape} rx="{r}" fill="{fill}" stroke="{edge}" stroke-width="2"/>')
        out.append(f.fitted(x + w / 2, PILL_BASE, name, PILL_TEXT, ink, x + r, x + w - r, True, "middle"))
    return out


def mark() -> list[str]:
    """A small table at the upper right: its middle row tinted, two row rules, one column rule, and no text."""
    right, bottom, (top, low) = MARK_X + MARK_W, MARK_Y + MARK_H, MARK_ROWS
    rule = f'stroke="{ACCENT}" stroke-width="2"'
    return [
        f'<rect x="{MARK_X}" y="{top}" width="{MARK_W}" height="{low - top}" fill="{TINT}"/>',
        *(f'<line x1="{MARK_X}" y1="{y}" x2="{right}" y2="{y}" {rule}/>' for y in MARK_ROWS),
        f'<line x1="{MARK_COLUMN}" y1="{MARK_Y}" x2="{MARK_COLUMN}" y2="{bottom}" {rule}/>',
        f'<rect x="{MARK_X}" y="{MARK_Y}" width="{MARK_W}" height="{MARK_H}" fill="none" {rule}/>',
    ]


def header() -> list[str]:
    """The copy down the left. The kicker, name and subtitle share rows with the table mark, so they end before it."""
    beside = MARK_X - 24
    return [
        f.fitted(M, 60, KICKER, 26, ACCENT, M, beside, bold=True),
        f.fitted(M, 128, NAME, 64, PRIMARY, M, beside, bold=True),
        f.fitted(M, 174, SUBTITLE, 28, SECONDARY, M, beside),
        f.fitted(M, 218, RESULTS, 26, SECONDARY, M, RIGHT),
        f.fitted(M, 506, FOOTER, 26, SECONDARY, M, RIGHT),
    ]


def draw(report: f.Report) -> str:
    row = tiles(report)
    parts = ["<style>text{font-variant-numeric:tabular-nums}</style>", *header(), *mark()]
    x = M
    for t, w in zip(row, widths(row), strict=True):
        parts += tile(x, w, t)
        x += w + GAP
    parts += [*pills(), f.frame(HEIGHT, BORDER), f'<rect width="{f.WIDTH}" height="4" fill="{ACCENT}"/>']
    description = (
        f"{NAME} answers questions about claims, policies and scanned forms for a made-up home insurer, on synthetic "
        f"data. Eval results with no API key: {', '.join(t.said for t in row)}. A question passes these stages in "
        f"order: {', '.join(name for name, _, _ in PILLS)}. {FOOTER}"
    )
    return f.document(f"{NAME}, eval results with no API key", description, HEIGHT, parts, canvas=CANVAS)
