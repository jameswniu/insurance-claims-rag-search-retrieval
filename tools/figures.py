"""Draws the five figures in docs/figures. Run `uv run python tools/figures.py`, and add --check to fail when a file
on disk is stale.

hero.svg opens the README with four measured results, and eval-comparison.svg sets dev against held-out. Both read
every number they show from evals/report.json when they are drawn, and stop on a missing key or an invalid interval.

system-map.svg is the top level, a question end to end. system-paths.svg is the middle, what each path does inside.
system-runtime.svg is the bottom, what runs where. Each figure lives in its own module beside this one, which holds
the pieces they share: the palette, the boxes, the connectors and the guards.

Every label is measured before it is drawn. GitHub shows a README image in a column about 837 px wide, so a
1200-unit figure is scaled by about 0.7 and a 23-unit font lands near 16 px, which is still readable at 75%.
"""

from __future__ import annotations

import html
import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"
REPORT = ROOT / "evals" / "report.json"
Report = dict[str, Any]

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
MIN_FONT = 23
BODY, TITLE = 23, 26
PAD = 14
STEP = 32
WIDTH = 1200

# One dark palette for every figure: charcoal surfaces, steel blue for the repo, a color per path, green for checks.
CANVAS, PANEL, NODE_BG, GROUP_BG = "#10161D", "#18212B", "#1D2733", "#141B23"
EDGE, CONNECTOR, TINT, BADGE_BLUE = "#475569", "#7B8492", "#25394A", "#365C7D"
PRIMARY, SECONDARY, MUTED = "#E9EEF3", "#BCC7D2", "#94A3B8"
ACCENT = LOOKUP = "#8CB4DF"
# FIGURES already names the folder the files are written to, so the figures path color takes a suffix.
FIGURES_EDGE, DOCUMENTS, WHY = "#79B8C8", "#B4A7D6", "#C5BBA4"
SUCCESS, GREEN_BG, WARNING = "#74C3A1", "#172D27", "#E5B567"

INK = PRIMARY
SUBTLE = NODE_BG
BLUE_BG = NODE_BG
BLUE_EDGE = LOOKUP
GREEN_EDGE = SUCCESS
PATH_EDGES = (LOOKUP, FIGURES_EDGE, DOCUMENTS, WHY)

# What a label may not carry: dashes and arrows are drawn as lines, never typed, and these words say nothing. The
# marks are built from their code points, so this file holds none of them.
_MARKS = "".join(chr(c) for c in (*range(0x2012, 0x2016), *range(0x2190, 0x2200), *range(0x27F5, 0x2800)))
_ENTITIES = ("rarr", "larr", "harr", "mdash", "ndash")
_TYPED = ("-" * 2, "-" + ">", "<" + "-", *(f"&{name};" for name in _ENTITIES))
_WORDS = ("production-grade", "showcase", r"\blocks\b", "source of truth", "golden")
BANNED = re.compile("|".join([f"[{re.escape(_MARKS)}]", *map(re.escape, _TYPED), *_WORDS]), re.IGNORECASE)


def width(text: str, size: int, bold: bool = False, mono: bool = False) -> float:
    """A deliberately generous estimate for a proportional sans face, or a monospaced one."""
    return len(text) * size * (0.62 if bold or mono else 0.58)


def text(
    x: float, y: float, s: str, size: int, fill: str, bold: bool = False, anchor: str = "middle", mono: bool = False
) -> str:
    if size < MIN_FONT:
        raise SystemExit(f"{s!r} is set at {size}, under the {MIN_FONT}-unit floor")
    if BANNED.search(s):
        raise SystemExit(f"{s!r} carries a dash, an arrow or a banned word")
    weight = ' font-weight="600"' if bold else ""
    return (
        f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-family="{MONO if mono else SANS}" '
        f'font-size="{size}"{weight} fill="{fill}">{html.escape(s)}</text>'
    )


def fitted(
    x: float, y: float, s: str, size: int, fill: str, lo: float, hi: float, bold: bool = False, anchor: str = "start"
) -> str:
    """Text measured against the span it has to stay inside, lo to hi, before it is drawn. It is never shrunk."""
    need = width(s, size, bold)
    left = x - need if anchor == "end" else x - need / 2 if anchor == "middle" else x
    if left < lo or left + need > hi:
        raise SystemExit(f"{s!r} at {size} runs from {left:.0f} to {left + need:.0f}, outside {lo:.0f} to {hi:.0f}")
    return text(x, y, s, size, fill, bold, anchor)


@dataclass(frozen=True)
class Rate:
    """A rate from evals/report.json: hits of n, its value, and its Wilson interval from low to high."""

    hits: int
    n: int
    value: float
    low: float
    high: float


def need(report: Report, path: str) -> Any:
    """The value at a dotted path in the report. A figure never draws a default, so a missing key stops it."""
    node: Any = report
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            raise SystemExit(f"evals/report.json has no {path}")
        node = node[key]
    return node


def count(report: Report, path: str) -> int:
    value = need(report, path)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SystemExit(f"evals/report.json holds {value!r} at {path}, not a count")
    return value


def rate(report: Report, path: str) -> Rate:
    """A rate with every part checked: n above 0, hits within n, the value equal to hits over n, inside its interval."""
    hits, n = count(report, f"{path}.hits"), count(report, f"{path}.n")
    value, low, high = (need(report, f"{path}.{key}") for key in ("value", "low", "high"))
    if any(isinstance(v, bool) or not isinstance(v, int | float) for v in (value, low, high)):
        raise SystemExit(f"evals/report.json has a value or bound at {path} that is not a number")
    if not (n > 0 and hits <= n and 0 <= low <= value <= high <= 1 and abs(value - hits / n) < 1e-3):
        raise SystemExit(f"evals/report.json has an invalid rate at {path}: {hits} of {n}, {value} in {low} to {high}")
    return Rate(hits, n, float(value), float(low), float(high))


@dataclass(frozen=True)
class Box:
    """A rounded box with a bold title and smaller lines under it. Lines listed in mono are code identifiers.
    title_fill colors the title, and line_fills colors a line by its index, ahead of title_fill."""

    x: float
    y: float
    w: float
    h: float
    lines: tuple[str, ...]
    fill: str = SUBTLE
    edge: str = EDGE
    mono: frozenset[int] = field(default_factory=frozenset)
    title_fill: str | None = None
    line_fills: Mapping[int, str] = field(default_factory=dict, hash=False)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def svg(self) -> list[str]:
        out = [
            f'<rect x="{self.x:.0f}" y="{self.y:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" rx="10" '
            f'fill="{self.fill}" stroke="{self.edge}" stroke-width="2"/>'
        ]
        if STEP * len(self.lines) + 8 > self.h:
            raise SystemExit(f"{self.lines[0]!r} has {len(self.lines)} lines in a {self.h:.0f}-unit box")
        top = self.cy - STEP * (len(self.lines) - 1) / 2 + 8
        for i, line in enumerate(self.lines):
            bold, mono = i == 0, i in self.mono
            size = TITLE if bold else BODY
            need = width(line, size, bold, mono)
            if need > self.w - 2 * PAD:
                raise SystemExit(f"{line!r} needs {need:.0f} units in a {self.w:.0f}-unit box")
            ink = self.line_fills.get(i, (self.title_fill or PRIMARY) if bold else SECONDARY)
            out.append(text(self.cx, top + i * STEP, line, size, ink, bold, mono=mono))
        return out


def group(x: float, y: float, w: float, h: float, name: str, name_x: float | None = None) -> list[str]:
    """A light frame around boxes that belong together, named at its top left, or centred on name_x."""
    if width(name, BODY, bold=True) > w - 36:
        raise SystemExit(f"{name!r} doesn't fit its group")
    at, anchor = (x + 18, "start") if name_x is None else (name_x, "middle")
    return [
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="14" fill="{GROUP_BG}" '
        f'stroke="{EDGE}" stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round"/>',
        text(at, y + 31, name, BODY, SECONDARY, bold=True, anchor=anchor),
    ]


def path(points: Iterable[tuple[float, float]], dashed: bool = False, arrow: bool = True) -> str:
    """A connector through the points, straight across or straight down between each pair."""
    pts = list(points)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        if x1 != x2 and y1 != y2:
            raise SystemExit(f"the connector from {(x1, y1)} to {(x2, y2)} is neither across nor down")
    d = " ".join(f"{'M' if i == 0 else 'L'}{x:.0f},{y:.0f}" for i, (x, y) in enumerate(pts))
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    head = ' marker-end="url(#head)"' if arrow else ""
    return f'<path d="{d}" fill="none" stroke="{CONNECTOR}" stroke-width="2"{dash}{head}/>'


def label(
    x: float, y: float, s: str, anchor: str = "middle", lo: float = 0, hi: float = WIDTH, mono: bool = False
) -> str:
    """A muted note on the canvas, which must sit between lo and hi."""
    need = width(s, BODY, mono=mono)
    left = x - need if anchor == "end" else x - need / 2 if anchor == "middle" else x
    if left < lo or left + need > hi:
        raise SystemExit(f"{s!r} runs from {left:.0f} to {left + need:.0f}, outside {lo:.0f} to {hi:.0f}")
    return text(x, y, s, BODY, MUTED, anchor=anchor, mono=mono)


def frame(height: float, edge: str) -> str:
    """A square two-unit border just inside the canvas."""
    size = f'width="{WIDTH - 2}" height="{height - 2:.0f}"'
    return f'<rect x="1" y="1" {size} fill="none" stroke="{edge}" stroke-width="2"/>'


def document(title: str, description: str, height: float, parts: Iterable[str], canvas: str = CANVAS) -> str:
    """The figure as a file: its title and description for screen readers, the arrowhead, the canvas and its frame.
    The frame goes under the parts, so anything drawn on the edge, like the hero's top stripe, stays on top."""
    for words in (title, description):
        if BANNED.search(words):
            raise SystemExit(f"{words!r} carries a dash, an arrow or a banned word")
    defs = (
        '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{CONNECTOR}"/></marker></defs>'
    )
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height:.0f}" width="{WIDTH}" '
            f'height="{height:.0f}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{html.escape(title)}</title>',
            f'<desc id="desc">{html.escape(description)}</desc>',
            defs,
            f'<rect width="{WIDTH}" height="{height:.0f}" fill="{canvas}"/>',
            frame(height, EDGE),
            *parts,
            "</svg>",
            "",
        ]
    )


def drawn() -> dict[Path, str]:
    """Every figure, by the file it is written to. The hero and the eval comparison read evals/report.json, which
    is loaded once for both."""
    try:
        from tools import figure_evidence, figure_hero, figure_paths, figure_runtime, figure_top
    except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
        import figure_evidence  # type: ignore[import-not-found, no-redef]
        import figure_hero  # type: ignore[import-not-found, no-redef]
        import figure_paths  # type: ignore[import-not-found, no-redef]
        import figure_runtime  # type: ignore[import-not-found, no-redef]
        import figure_top  # type: ignore[import-not-found, no-redef]
    report: Report = json.loads(REPORT.read_text())
    figures = {module.OUT: module.draw(report) for module in (figure_hero, figure_evidence)}
    return figures | {module.OUT: module.draw() for module in (figure_top, figure_paths, figure_runtime)}


def main() -> None:
    figures = drawn()
    if "--check" in sys.argv:
        stale = [out.relative_to(ROOT) for out, svg in figures.items() if not out.exists() or out.read_text() != svg]
        if stale:
            raise SystemExit(f"{', '.join(map(str, stale))} stale; run uv run python tools/figures.py")
        return
    FIGURES.mkdir(parents=True, exist_ok=True)
    for out, svg in figures.items():
        out.write_text(svg)
        print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
