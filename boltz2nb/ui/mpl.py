"""Matplotlib look that matches the notebook UI (brand palette, quiet axes, AlphaFold confidence bands)."""
from __future__ import annotations

import io
from contextlib import contextmanager
from pathlib import Path

INK, INK2, MUTED = "#0E1B32", "#3D4C68", "#586784"
GRID, AXIS = "#E4EAF5", "#C5CEDF"
INDIGO, PERI, CYAN = "#3B4FD6", "#7C8CFF", "#63E6FF"
TEAL, VIOLET, AMBER = "#08756A", "#7A3FD1", "#A94E08"
OK, WARN, ERR = "#0B7A52", "#B8860B", "#B3263F"
BANDS = [(90, 100, "#0053D6"), (70, 90, "#65CBF3"), (50, 70, "#FFDB13"), (0, 50, "#FF7D45")]
SERIES = [INDIGO, PERI, "#2E9BD6", TEAL, VIOLET, AMBER]


def _font_family() -> list[str]:
    """Inter if it is installed, else DejaVu Sans; never name a missing family (matplotlib warns per glyph run)."""
    try:
        from matplotlib import font_manager
        have = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:  # noqa: BLE001
        have = set()
    fam = [f for f in ("Inter", "DejaVu Sans") if f in have]
    return fam or ["sans-serif"]


def rc() -> dict:
    return {
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "font.family": _font_family(), "font.size": 10.5, "text.color": INK,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.titleweight": "bold",
        "axes.titlesize": 12.5, "axes.titlelocation": "left", "axes.titlepad": 12, "axes.labelsize": 10.5,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 1.0,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
        "axes.grid": False, "grid.color": GRID, "grid.linewidth": 0.8,
        "legend.frameon": False, "legend.fontsize": 9, "legend.labelcolor": INK2,
        "figure.dpi": 100, "savefig.dpi": 150, "lines.solid_capstyle": "round",
    }


@contextmanager
def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with plt.rc_context(rc()):
        yield plt


def save_figure(fig, path, tight: bool = False) -> None:
    """Save as an optimised 256-colour PNG (about half the size of RGB, visually identical for these charts).

    The canvas is kept as drawn (``tight=False``) so that figures of one kind have identical pixel sizes and line up on the page."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight" if tight else None)
    data = buf.getvalue()
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        out = io.BytesIO()
        im.save(out, "PNG", optimize=True)
        data = out.getvalue()
    except Exception:  # noqa: BLE001 - Pillow missing/old: keep the plain PNG
        pass
    Path(path).write_bytes(data)
