"""The result figures: pLDDT, PAE, affinity and per-sample confidence.

Every figure of a kind is drawn on the same canvas and saved without cropping, so the images line up when the report puts them side
by side: a sample's PAE map and pLDDT trace have the same height, and the affinity and per-sample figures have the same size. Sizes
are chosen for the way the page shows them (about 65 % scale in a two-column row), so the text stays readable at that size.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .mpl import AXIS, BANDS, ERR, GRID, INDIGO, INK, INK2, MUTED, OK, PERI, SERIES, WARN, save_figure, style

HEIGHT = 4.2                    # inches: PAE and pLDDT share it, so a row of the two is exactly as tall on both sides
PAE_SIZE = (4.6, HEIGHT)
PLDDT_SIZE = (6.0, HEIGHT)
PAIR_SIZE = (5.3, 3.4)          # affinity and per-sample confidence
BAND_NAMES = {90: "Very high (>90)", 70: "Confident (70-90)", 50: "Low (50-70)", 0: "Very low (<50)"}


def _axis_floor(lowest: float) -> float:
    """Where the pLDDT axis starts: just below the data (never above 50 so the low bands stay visible when something dips)."""
    return float(max(0, min(50, 10 * math.floor((lowest - 4) / 10))))


def draw_plddt(plddt: Sequence[float], bounds: Sequence[tuple[str, int, int]], sample: Any, out_path: Path | str) -> Path:
    """Per-token pLDDT as one clean line over tinted confidence bands, with the chains marked along the top."""
    from matplotlib.patches import Patch

    y = np.asarray(plddt, dtype=float)
    x = np.arange(len(y))
    floor = _axis_floor(float(np.nanmin(y)) if len(y) else 0.0)
    with style() as plt:
        fig, ax = plt.subplots(figsize=PLDDT_SIZE, layout="constrained")
        for lo, hi, c in BANDS:
            if hi > floor:
                ax.axhspan(max(lo, floor), hi, color=c, alpha=0.16, lw=0, zorder=0)
        for edge in (50, 70, 90):
            if edge > floor:
                ax.axhline(edge, color="white", lw=1.0, zorder=1)
        ax.plot(x, y, color=INDIGO, lw=1.6, zorder=3, solid_joinstyle="round")
        for cid, start, end in bounds:
            if start > 0:
                ax.axvline(start - 0.5, color=MUTED, lw=0.9, ls=(0, (3, 3)), zorder=2)
            ax.text((start + end) / 2, 1.02, cid, ha="center", va="bottom", fontsize=9.5, fontweight="bold", color=INDIGO,
                    transform=ax.get_xaxis_transform(), bbox={"boxstyle": "round,pad=0.25", "fc": "#E9ECFD", "ec": "none"})
        ax.set_xlim(0, max(len(y) - 1, 1))
        ax.set_ylim(floor, 100)
        ax.set_yticks([t for t in (0, 20, 40, 50, 60, 70, 80, 90, 100) if t >= floor and (t in (50, 70, 90, 100) or t == floor)])
        ax.set_xlabel("Token")
        ax.set_ylabel("pLDDT")
        ax.set_title(f"Per-token confidence \u00b7 sample {sample}", pad=24)
        ax.margins(x=0)
        handles = [Patch(fc=c, alpha=0.5, ec="none", label=BAND_NAMES[lo]) for lo, hi, c in BANDS if hi > floor]
        fig.legend(handles=handles, loc="outside lower center", ncol=len(handles), fontsize=8.5, handlelength=1.1, columnspacing=1.2)
        save_figure(fig, out_path)
        plt.close(fig)
    return Path(out_path)


def draw_pae(pae: np.ndarray, bounds: Sequence[tuple[str, int, int]], sample: Any, out_path: Path | str, vmax: float = 32.0) -> Path:
    """The PAE matrix as Boltz writes it (asymmetric), on a fixed 0-32 A scale, chain boundaries ruled."""
    with style() as plt:
        fig, ax = plt.subplots(figsize=PAE_SIZE, layout="constrained")
        im = ax.imshow(pae, cmap="Greens_r", vmin=0, vmax=vmax, origin="upper", interpolation="none", aspect="equal")
        for _cid, start, _end in bounds:
            if start > 0:
                ax.axhline(start - 0.5, color=INK, lw=0.8)
                ax.axvline(start - 0.5, color=INK, lw=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(True)
        ticks = [(s + e) / 2 for _, s, e in bounds]
        ax.set_xticks(ticks, [c for c, _, _ in bounds])
        ax.set_yticks(ticks, [c for c, _, _ in bounds])
        ax.set_xlabel("Scored token")
        ax.set_ylabel("Aligned token")
        ax.set_title(f"Predicted aligned error \u00b7 sample {sample}", pad=24)
        cb = fig.colorbar(im, ax=ax, shrink=0.82, aspect=26, pad=0.03, ticks=[0, 8, 16, 24, 32])
        cb.set_label("PAE (\u00c5)")
        cb.outline.set_edgecolor(AXIS)
        save_figure(fig, out_path)
        plt.close(fig)
    return Path(out_path)


def draw_affinity(prob: float, ic50_text: str, log10_ic50: float, members: Sequence[tuple[str, float]], out_path: Path | str) -> Path:
    """Binding probability as a ring and the predicted log10 IC50 (ensemble and each member) as bars, one baseline for both."""
    with style() as plt:
        fig, (ring, bars) = plt.subplots(1, 2, figsize=PAIR_SIZE, layout="constrained", gridspec_kw={"width_ratios": [1.0, 1.45]})
        color = OK if prob >= 0.75 else WARN if prob >= 0.4 else ERR
        ring.pie([prob, 1 - prob], colors=[color, GRID], startangle=90, counterclock=False, wedgeprops={"width": 0.27, "edgecolor": "white"})
        ring.set_aspect("equal", adjustable="datalim")           # keep the axes box full-size so both titles share a baseline
        ring.text(0, 0.06, f"{prob * 100:.0f}%", ha="center", va="center", fontsize=19, fontweight="bold", color=INK)
        ring.text(0, -0.3, "binder", ha="center", va="center", fontsize=9, color=MUTED)
        ring.set_title("Binding probability", loc="center", pad=14, fontsize=11.5)
        labels = ["ensemble"] + [name for name, _ in members]
        values = [log10_ic50] + [v for _, v in members]
        ypos = np.arange(len(values))
        bars.barh(ypos, values, color=[INDIGO] + [PERI] * len(members), height=0.5)
        bars.set_yticks(ypos, labels)
        bars.invert_yaxis()
        bars.axvline(0, color=AXIS, lw=1)
        span = max(abs(v) for v in values) or 1.0
        for i, v in enumerate(values):       # always to the right of zero: a negative bar leaves that side free (left would meet the labels)
            bars.text(max(v, 0) + 0.04 * span, i, f"{v:.2f}", va="center", ha="left", fontsize=9, color=INK2)
        lo, hi = min(min(values), 0), max(max(values), 0)
        bars.set_xlim(lo - 0.1 * span, hi + 0.2 * span)
        bars.set_xlabel("log10 IC50 (\u00b5M), lower = tighter")
        bars.set_title(f"Predicted IC50 \u2248 {ic50_text}", pad=14, fontsize=11.5)
        bars.tick_params(axis="y", length=0)
        save_figure(fig, out_path)
        plt.close(fig)
    return Path(out_path)


def draw_ensemble(rows: Sequence[dict[str, Any]], out_path: Path | str) -> Path:
    """Confidence metrics per sample as dots on an axis that starts just below the lowest value (bars from 0 hide the differences)."""
    keys = [k for k in ("confidence_score", "ptm", "iptm", "ligand_iptm") if any(r.get(k) is not None for r in rows)]
    markers = ["o", "s", "D", "^"]
    allv = [r[k] for r in rows for k in keys if r.get(k) is not None]
    floor = max(0.0, math.floor((min(allv) - 0.06) * 20) / 20)
    with style() as plt:
        fig, ax = plt.subplots(figsize=PAIR_SIZE, layout="constrained")
        x = np.arange(len(rows))
        ax.set_axisbelow(True)
        ax.yaxis.grid(True)
        # one dot per metric, side by side inside each sample: metrics that are equal (a confidence score that equals iptm, say)
        # must not hide each other
        ms = 7.5 if len(rows) <= 6 else 6.0
        unit_pt = 0.8 * PAIR_SIZE[0] * 72 / len(rows)                   # width of one sample slot in points
        step = min((ms + 2.5) / unit_pt, 0.8 / max(len(keys) - 1, 1))
        for i, k in enumerate(keys):
            vals = [r.get(k) if r.get(k) is not None else np.nan for r in rows]
            offset = (i - (len(keys) - 1) / 2) * step
            ax.plot(x + offset, vals, ls="none", marker=markers[i % 4], ms=ms, color=SERIES[i % len(SERIES)], mec="white", mew=0.9,
                    label=k.replace("_", " "), zorder=3)
        ax.set_xticks(x, [f"sample {r['model']}" for r in rows])
        ax.set_xlim(-0.5, len(rows) - 0.5)
        ax.set_ylim(floor, 1.0 + 0.02)
        ax.set_ylabel("score")
        ax.set_title("Confidence per sample", pad=14)
        ax.tick_params(axis="x", length=0)
        fig.legend(*ax.get_legend_handles_labels(), loc="outside lower center", ncol=len(keys), fontsize=8.5, handlelength=1.0,
                   columnspacing=1.0)
        save_figure(fig, out_path)
        plt.close(fig)
    return Path(out_path)
