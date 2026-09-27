"""Draws the three architecture figures in docs/figures. Run `uv run python tools/figures.py`, and add --check to fail
when a file on disk is stale.

system-map.svg is the top level, a question end to end. system-paths.svg is the middle, what each path does inside.
system-runtime.svg is the bottom, what runs where. Each figure lives in its own module beside this one, which holds
the pieces they share: the palette, the boxes, the connectors and the guards.

Every label is measured before it is drawn. GitHub shows a README image in a column about 837 px wide, so a
1200-unit figure is scaled by about 0.7 and a 23-unit font lands near 16 px, which is still readable at 75%.
"""

from __future__ import annotations

import html
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
MIN_FONT = 23
BODY, TITLE = 23, 26
PAD = 14
STEP = 32
WIDTH = 1200

INK, MUTED, EDGE = "#1f2328", "#59636e", "#d1d9e0"
CANVAS, SUBTLE = "#ffffff", "#f6f8fa"
BLUE_BG, BLUE_EDGE = "#ddf4ff", "#54aeff"
GREEN_BG, GREEN_EDGE = "#dafbe1", "#4ac26b"
GROUP_BG = "#fbfcfd"

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


@dataclass(frozen=True)
class Box:
    """A rounded box with a bold title and smaller lines under it. Lines listed in mono are code identifiers."""

    x: float
    y: float
    w: float
    h: float
    lines: tuple[str, ...]
    fill: str = SUBTLE
    edge: str = EDGE
    mono: frozenset[int] = field(default_factory=frozenset)

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
            out.append(text(self.cx, top + i * STEP, line, size, INK if bold else MUTED, bold, mono=mono))
        return out


def group(x: float, y: float, w: float, h: float, name: str, name_x: float | None = None) -> list[str]:
    """A light frame around boxes that belong together, named at its top left, or centred on name_x."""
    if width(name, BODY, bold=True) > w - 36:
        raise SystemExit(f"{name!r} doesn't fit its group")
    at, anchor = (x + 18, "start") if name_x is None else (name_x, "middle")
    return [
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="14" fill="{GROUP_BG}" '
        f'stroke="{EDGE}" stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round"/>',
        text(at, y + 31, name, BODY, MUTED, bold=True, anchor=anchor),
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
    return f'<path d="{d}" fill="none" stroke="{MUTED}" stroke-width="2"{dash}{head}/>'


def label(
    x: float, y: float, s: str, anchor: str = "middle", lo: float = 0, hi: float = WIDTH, mono: bool = False
) -> str:
    """A muted note on the canvas, which must sit between lo and hi."""
    need = width(s, BODY, mono=mono)
    left = x - need if anchor == "end" else x - need / 2 if anchor == "middle" else x
    if left < lo or left + need > hi:
        raise SystemExit(f"{s!r} runs from {left:.0f} to {left + need:.0f}, outside {lo:.0f} to {hi:.0f}")
    return text(x, y, s, BODY, MUTED, anchor=anchor, mono=mono)


def document(title: str, description: str, height: float, parts: Iterable[str]) -> str:
    """The figure as a file: its title and description for screen readers, the arrowhead and the white canvas."""
    for words in (title, description):
        if BANNED.search(words):
            raise SystemExit(f"{words!r} carries a dash, an arrow or a banned word")
    defs = (
        '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker></defs>'
    )
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height:.0f}" width="{WIDTH}" '
            f'height="{height:.0f}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{html.escape(title)}</title>',
            f'<desc id="desc">{html.escape(description)}</desc>',
            defs,
            f'<rect width="{WIDTH}" height="{height:.0f}" fill="{CANVAS}"/>',
            *parts,
            "</svg>",
            "",
        ]
    )


def drawn() -> dict[Path, str]:
    """Every figure, by the file it is written to."""
    try:
        from tools import figure_paths, figure_runtime, figure_top
    except ModuleNotFoundError:  # run as a script from tools/, where the repository root may not be on the path
        import figure_paths  # type: ignore[import-not-found, no-redef]
        import figure_runtime  # type: ignore[import-not-found, no-redef]
        import figure_top  # type: ignore[import-not-found, no-redef]
    return {module.OUT: module.draw() for module in (figure_top, figure_paths, figure_runtime)}


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
