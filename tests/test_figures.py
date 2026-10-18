"""The result figures: same-size canvases so they line up, nothing clipped or overprinted, honest axes, and the page structure."""
import itertools
import re

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("matplotlib")

from boltz2nb import analysis
from boltz2nb.ui import figures
from boltz2nb.ui.results import render_figures


@pytest.fixture(scope="module")
def job(example_pred_dir):
    return analysis.load_job(example_pred_dir)


class Measured:
    """A figure as it is drawn: the figure, the renderer of a real draw and every piece of text that is painted, with its extent."""

    def __init__(self, fig):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(fig)
        canvas.draw()                           # constrained layout (legends, colour bars) only resolves when the figure is drawn
        self.fig, self.renderer = fig, canvas.get_renderer()
        self.texts = self._painted_texts()

    def _painted_texts(self):
        """Tick labels outside the axis limits stay in matplotlib's tick lists but are never painted, so they are left out."""
        found = []

        def add(t):
            if t is not None and t.get_visible() and t.get_text().strip():
                box = t.get_window_extent(self.renderer)
                if box.width > 0:
                    found.append((t.get_text(), box))

        for ax in self.fig.axes:
            for text in (ax.title, ax._left_title, ax._right_title, ax.xaxis.label, ax.yaxis.label, *ax.texts):
                add(text)
            for axis in (ax.xaxis, ax.yaxis):
                lo, hi = sorted(axis.get_view_interval())
                for tick, loc in zip(axis.get_major_ticks(), axis.get_majorticklocs()):
                    if lo - 1e-9 <= loc <= hi + 1e-9:
                        add(tick.label1)
        for legend in self.fig.legends:
            for t in legend.get_texts():
                add(t)
        return found


@pytest.fixture
def captured(monkeypatch):
    """Measure every figure just before it is saved (the draw functions close theirs afterwards)."""
    kept = []
    original = figures.save_figure

    def spy(fig, path, *a, **k):
        kept.append(Measured(fig))
        return original(fig, path, *a, **k)

    monkeypatch.setattr(figures, "save_figure", spy)
    return kept


def size(path):
    return Image.open(path).size


def test_pae_and_plddt_are_drawn_at_the_same_height_and_the_pair_at_the_same_size(job, tmp_path):
    pae = analysis.plot_pae(job.best, tmp_path / "pae.png")
    plddt = analysis.plot_plddt(job.best, tmp_path / "plddt.png")
    aff = analysis.plot_affinity_card(job, tmp_path / "aff.png")
    assert size(pae)[1] == size(plddt)[1], "a sample's PAE and pLDDT must be equally tall so a row of the two lines up"
    assert size(pae)[0] / size(plddt)[0] == pytest.approx(figures.PAE_SIZE[0] / figures.PLDDT_SIZE[0], abs=0.01)
    assert size(aff) == tuple(round(v * 150) for v in figures.PAIR_SIZE)


def test_figures_of_one_kind_have_identical_pixel_sizes_whatever_the_data(job, tmp_path):
    """No tight cropping: a different tick label or a wider axis must not change the canvas."""
    sizes = {size(analysis.plot_plddt(job.best, tmp_path / f"{i}.png")) for i in range(2)}
    short = figures.draw_plddt(np.linspace(40, 99, 30), [("A", 0, 29)], 3, tmp_path / "short.png")
    low = figures.draw_plddt(np.full(300, 12.0), [("A", 0, 299)], 4, tmp_path / "low.png")
    assert len(sizes | {size(short), size(low)}) == 1


def test_ensemble_and_affinity_are_the_same_size(job, tmp_path):
    rows = [{"model": i, "confidence_score": 0.9 - 0.05 * i, "ptm": 0.9, "iptm": 0.85, "ligand_iptm": 0.8} for i in range(4)]
    ens = figures.draw_ensemble(rows, tmp_path / "ens.png")
    aff = analysis.plot_affinity_card(job, tmp_path / "aff.png")
    assert size(ens) == size(aff)


@pytest.mark.parametrize("which", ["plddt", "pae", "affinity", "ensemble", "ensemble5"])
def test_nothing_is_clipped_and_no_two_labels_overprint(job, tmp_path, captured, which):
    rows = [{"model": i, "confidence_score": 0.91 - 0.03 * i, "ptm": 0.93, "iptm": 0.88, "ligand_iptm": 0.86} for i in range(5)]
    {"plddt": lambda: analysis.plot_plddt(job.best, tmp_path / "a.png"),
     "pae": lambda: analysis.plot_pae(job.best, tmp_path / "a.png"),
     "affinity": lambda: analysis.plot_affinity_card(job, tmp_path / "a.png"),
     "ensemble": lambda: figures.draw_ensemble(rows[:3], tmp_path / "a.png"),
     "ensemble5": lambda: figures.draw_ensemble(rows, tmp_path / "a.png")}[which]()
    fig_box = captured[-1].fig.bbox
    items = captured[-1].texts
    assert items
    for label, box in items:
        assert box.x0 >= fig_box.x0 - 1 and box.x1 <= fig_box.x1 + 1 and box.y0 >= fig_box.y0 - 1 and box.y1 <= fig_box.y1 + 1, \
            f"{which}: '{label}' is cut off by the edge of the figure"
    for (a, ba), (b, bb) in itertools.combinations(items, 2):
        if ba.overlaps(bb):
            inter = (min(ba.x1, bb.x1) - max(ba.x0, bb.x0)) * (min(ba.y1, bb.y1) - max(ba.y0, bb.y0))
            assert inter < 4, f"{which}: '{a}' overprints '{b}'"


def test_plddt_axis_starts_just_below_the_data_and_keeps_the_low_bands_visible():
    assert figures._axis_floor(92.0) == 50 and figures._axis_floor(61.0) == 50     # never starts above 50: the low bands stay in view
    assert figures._axis_floor(48.0) == 40                                          # a dip below 50 shows the 'very low' band
    assert figures._axis_floor(12.0) == 0 and figures._axis_floor(0.0) == 0


def test_plddt_does_not_waste_half_the_plot_on_empty_range(job, tmp_path, captured):
    analysis.plot_plddt(job.best, tmp_path / "p.png")
    ax = captured[-1].fig.axes[0]
    lo, hi = ax.get_ylim()
    assert lo >= 30 and hi == 100, (lo, hi)
    assert float(np.min(job.best.plddt)) >= lo


def test_ensemble_axis_is_zoomed_not_bars_from_zero(tmp_path, captured):
    rows = [{"model": i, "confidence_score": 0.88 + 0.01 * i, "ptm": 0.9, "iptm": 0.86, "ligand_iptm": 0.84} for i in range(3)]
    figures.draw_ensemble(rows, tmp_path / "e.png")
    lo, hi = captured[-1].fig.axes[0].get_ylim()
    assert 0.7 <= lo <= 0.8 and hi > 1.0
    assert not captured[-1].fig.axes[0].patches, "bars from zero would hide the differences between samples"


def test_affinity_value_labels_do_not_sit_on_the_bar_names(job, tmp_path, captured):
    """A negative log10 IC50 used to put its label over the 'member 1' tick label."""
    analysis.plot_affinity_card(job, tmp_path / "a.png")
    bars = captured[-1].fig.axes[1]
    renderer = captured[-1].renderer
    names = [t.get_window_extent(renderer) for t in bars.get_yticklabels()]
    values = [t.get_window_extent(renderer) for t in bars.texts]
    assert values and not any(v.overlaps(n) for v in values for n in names)


# --------------------------------------------------------------------------------------------- page structure
def b64(n=2):
    import base64
    import io
    buf = io.BytesIO()
    Image.new("RGB", (n, n), "white").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


SUMMARY = {"best_model": 0, "models": [{"model": 0, "confidence_score": 0.91, "mean_plddt": 92.5},
                                       {"model": 1, "confidence_score": 0.88, "mean_plddt": 91.0}]}


def test_each_sample_gets_one_row_with_pae_then_plddt_and_the_extras_get_an_even_row():
    fig = {"models": {0: {"pae": b64(), "plddt": b64()}, 1: {"pae": b64(), "plddt": b64()}}, "ensemble": b64(), "affinity": b64()}
    html = render_figures(SUMMARY, fig)
    rows = re.findall(r'<div class="bz-figrow ([^"]+)">', html)
    assert rows == ["bz-figrow--pae", "bz-figrow--pae", "bz-figrow--even"]
    assert html.index("Sample 0") < html.index("Sample 1") and html.count('class="bz-chip bz-chip--primary"') == 1
    first_row = html.split('bz-figrow--pae">')[1].split("</figure>")[0]
    assert "Predicted aligned error" in first_row, "the PAE map comes first (left), the pLDDT trace second"
    assert "confidence 0.910" in html and "mean pLDDT 92.5" in html


def test_a_single_sample_has_no_best_chip_and_a_lone_extra_is_not_stretched():
    html = render_figures({"best_model": 0, "models": [{"model": 0, "confidence_score": 0.9}]},
                          {"models": {0: {"pae": b64(), "plddt": None}}, "affinity": b64()})
    assert "bz-chip--primary" not in html
    assert re.findall(r'<div class="bz-figrow ([^"]+)">', html) == ["bz-figrow--one", "bz-figrow--one"]


def test_no_figures_no_section():
    assert render_figures({"models": []}, {"models": {}}) == ""
    assert render_figures({"models": []}, {"models": {0: {"pae": None, "plddt": None}}, "ensemble": None, "affinity": None}) == ""


@pytest.mark.parametrize("n_samples", [1, 3, 5, 8])
def test_ensemble_metrics_with_equal_values_do_not_hide_each_other(tmp_path, captured, n_samples):
    """A confidence score that equals iptm used to sit exactly under it and vanish: every dot must stay visible."""
    rows = [{"model": i, "confidence_score": 0.88, "ptm": 0.88, "iptm": 0.88, "ligand_iptm": 0.88} for i in range(n_samples)]
    figures.draw_ensemble(rows, tmp_path / "e.png")
    m = captured[-1]
    ax = m.fig.axes[0]
    for sample in range(n_samples):
        pts = [ax.transData.transform((line.get_xdata()[sample], line.get_ydata()[sample])) for line in ax.lines]
        size = ax.lines[0].get_markersize() * m.fig.dpi / 72
        for a in range(len(pts)):
            for b in range(a + 1, len(pts)):
                gap = float(((pts[a] - pts[b]) ** 2).sum() ** 0.5)
                assert gap >= size, f"sample {sample}: two metrics are drawn {gap:.1f}px apart, markers are {size:.1f}px wide"

