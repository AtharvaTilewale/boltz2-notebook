"""Run panel log parser, result renderers and figure helpers (no browser needed)."""
import io
import logging
import re
import time
import warnings

import pytest

from boltz2nb.ui import live, results
from boltz2nb.ui.live import LivePanel, RunState, render_live

# Lines copied from a real Colab run (boltz-community 2.10.12, T4)
COLAB_LOG = [
    "Checking input data.",
    "Calling MSA server for target 0 with 1 sequences",
    "Running structure prediction for 1 input.",
    "Predicting \x1b[38;2;98;6;224m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m \x1b[35m1/1\x1b[0m \x1b[36m0:00:35\x1b[0m",
    "Predicting property: affinity",
    "100%|██████████| 1/1 [06:14<00:00, 374.2s/it]",
]


def test_phases_advance_in_order_and_never_go_back():
    s = RunState(has_affinity=True)
    seen = []
    for line in COLAB_LOG:
        s.feed(line)
        seen.append(s.phase)
    assert seen == ["prepare", "msa", "fold", "fold", "affinity", "affinity"]
    s.feed("Checking input data.")                      # a late, earlier-phase line must not rewind the tracker
    assert s.phase == "affinity"


def test_progress_bars_become_numbers_not_log_lines():
    s = RunState()
    s.feed("Running structure prediction for 1 input.")
    s.feed(COLAB_LOG[3])
    assert s.progress == 1.0 and "━" not in "".join(s.lines)
    s.feed("42%|████      | 21/50 [00:10<00:14, 2.1it/s]")
    assert s.progress == pytest.approx(0.42)
    assert all("it/s" not in line for line in s.lines)
    s.feed("Predicting \u2501\u2501\u2501\u2501\u2501 3/12 0:00:01")
    assert s.progress == pytest.approx(0.25)


def test_ansi_is_stripped_and_duplicates_collapsed():
    s = RunState()
    s.feed("\x1b[31mWarning: something\x1b[0m")
    s.feed("Warning: something")
    s.feed("\r")
    assert list(s.lines) == ["Warning: something"]


def test_long_lines_are_truncated_and_history_is_bounded():
    s = RunState()
    s.feed("x" * 500)
    assert len(s.lines[-1]) <= 220
    for i in range(50):
        s.feed(f"line {i}")
    assert len(s.lines) == 14 and s.lines[-1] == "line 49"


def test_phase_list_depends_on_the_job():
    assert [k for k, _ in RunState(has_affinity=True, msa_server=True).phases()] == ["prepare", "msa", "fold", "affinity", "finish"]
    assert [k for k, _ in RunState(has_affinity=False, msa_server=False).phases()] == ["prepare", "fold", "finish"]


def test_finish_states():
    ok = RunState()
    ok.feed("Running structure prediction")
    ok.finish(True)
    assert ok.status == "completed" and ok.phase == "finish" and ok.progress == 1.0 and ok.elapsed() >= 0
    bad = RunState()
    bad.finish(False, "GPU ran out of memory.", "Use fewer samples.")
    assert bad.status == "failed" and bad.cause.startswith("GPU")


def test_render_live_states():
    s = RunState(job_name="<script>alert(1)</script>", gpu="T4", engine="boltz 2.2.1", command="boltz predict a.yaml")
    s.started = time.time() - 75
    s.feed("Running structure prediction for 1 input.")
    html_ = render_live(s)
    assert "<script>alert(1)" not in html_ and "&lt;script&gt;" in html_            # job names are escaped
    assert "bz-spin" in html_ and 'data-bz-e0="7' in html_ and "1:1" in html_ and "boltz predict a.yaml" in html_
    assert "<style>" in html_ and "<style>" not in render_live(s, standalone_css=False)
    s.finish(False, "Out of memory.", "Fewer samples.")
    failed = render_live(s)
    assert "bz-alert--err" in failed and "Out of memory." in failed and "Fewer samples." in failed and "bz-spin" not in failed.split("</ol>")[1]
    ok = RunState()
    ok.finish(True)
    done = render_live(ok)
    tracker = done.split('<ol class="bz-phases">')[1].split("</ol>")[0]
    assert "Completed" in done and tracker.count('data-state="done"') == len(ok.phases())


def test_live_panel_prints_in_plain_python(capsys):
    p = LivePanel(RunState(job_name="j"))
    assert not p.rich
    p.start()
    for line in COLAB_LOG:
        p.feed(line)
    p.finish(False, "Out of memory.", "Fewer samples.")
    out = capsys.readouterr().out
    assert "Calling MSA server" in out and "━" not in out and "it/s" not in out
    assert "[failed] j" in out and "Likely cause: Out of memory." in out


def test_fmt_time():
    assert live._fmt_time(5) == "0:05" and live._fmt_time(125) == "2:05" and live._fmt_time(3725) == "1:02:05"


# ------------------------------------------------------------------------------------------------ results
def test_tones():
    assert [results.tone_confidence(v) for v in (0.95, 0.6, 0.2, None)] == ["ok", "warn", "err", None]
    assert [results.tone_pae(v) for v in (3, 8, 15, None)] == ["ok", "warn", "err", None]
    assert results.tone_plddt(95) == "ok" and results.tone_plddt(30) == "err"


@pytest.fixture()
def summary(example_pred_dir):
    from boltz2nb.analysis import load_job, summary_dict
    job = load_job(example_pred_dir)
    return summary_dict(job), job.best.structure_path.read_text()


def test_result_card_contents(summary):
    s, pdb = summary
    html_ = results.render_result_card(s, pdb, {"engine": "boltz 2.2.1", "gpu_name": "T4"}, runtime=95, uid="abc")
    assert 'class="bz-aff-v">2.77 µM<' in html_ and "boltz 2.2.1" in html_ and "1:35" in html_
    assert html_.count('id="v-abc"') == 1 and "3Dmol.org" in html_
    assert html_.index("Structure") < html_.index("Chains")                     # the 3-D view comes before the tables


def test_result_card_without_affinity_or_structure(summary):
    s, _ = summary
    s = dict(s, affinity=None)
    html_ = results.render_result_card(s, None, None, uid="x")
    assert 'class="bz-aff-v"' not in html_ and "3Dmol" not in html_ and "Structure" not in html_


def test_result_card_shows_layout_notes_and_escapes(summary):
    s, pdb = summary
    s = dict(s, layout_notes=["Token layout <b>mismatch</b>"], job_name="<img src=x>")
    html_ = results.render_result_card(s, pdb, None)
    assert "<b>mismatch</b>" not in html_ and "&lt;b&gt;mismatch" in html_ and "<img src=x>" not in html_


def test_only_documented_external_hosts(summary):
    s, pdb = summary
    html_ = results.render_result_card(s, pdb, None) + render_live(RunState())
    hosts = set(re.findall(r'(?:src|href)="https?://([^/"]+)', html_))
    assert hosts <= {"cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"}, hosts
    assert "3dmol@2.5.5" in html_, "the viewer library must be pinned to a version"


def test_report_fragment_and_document(summary):
    s, pdb = summary
    frag = results.render_report_fragment(s, {"models": {}, "affinity": None}, pdb, None, files=[("report", "/tmp/r.html")])
    assert "Saved files" in frag and "/tmp/r.html" in frag and "<!doctype" not in frag
    doc = results.render_report_document(s, {"models": {0: {"plddt": "AAAA"}}}, pdb, None)
    assert doc.startswith("<!doctype html>") and 'name="viewport"' in doc and "data:image/png;base64,AAAA" in doc
    assert "<style>" in doc and doc.count("<style>") == 1                      # CSS is not duplicated inside the body fragment


# ------------------------------------------------------------------------------------------------ figures
def test_figure_font_never_names_a_missing_family(caplog):
    from boltz2nb.ui import mpl
    fam = mpl._font_family()
    assert fam and all(f in {"Inter", "DejaVu Sans", "sans-serif"} for f in fam)
    with caplog.at_level(logging.WARNING, logger="matplotlib.font_manager"), warnings.catch_warnings():
        warnings.simplefilter("error")
        with mpl.style() as plt:
            fig, ax = plt.subplots()
            ax.set_title("pLDDT")
            ax.text(0.5, 0.5, "label", fontweight="bold")
            fig.canvas.draw()
            plt.close(fig)
    assert not [r for r in caplog.records if "findfont" in r.getMessage()]


def test_save_figure_writes_a_smaller_valid_png(tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    from boltz2nb.ui import mpl
    with mpl.style() as plt:
        fig, ax = plt.subplots()
        ax.imshow([[i * j for i in range(60)] for j in range(60)], cmap="Greens_r")
        plain = io.BytesIO()
        fig.savefig(plain, format="png", bbox_inches="tight")
        mpl.save_figure(fig, tmp_path / "f.png")
        plt.close(fig)
    out = tmp_path / "f.png"
    im = PIL.open(out)
    assert im.format == "PNG" and im.mode == "P" and out.stat().st_size < len(plain.getvalue())
