"""Run the notebook cells (scripts/common/Boltz_Run.py, analysis.py) end to end against a fake ``boltz`` executable.

The fake prints the same kinds of log lines a real run does (plain lines, rich progress bars, tqdm bars) and writes real
prediction files from ``assets/``, so the live panel, result card, status files and report generation are all exercised.
"""
import json
import os
import runpy
import stat
import sys
from pathlib import Path

import pytest

from boltz2nb.run_params import DEFAULTS, serialize_run_params
from boltz2nb.yaml_builder import build_yaml, simple_spec, write_yaml

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

FAKE = '''#!{python}
import json, pathlib, shutil, sys, time
args = sys.argv[1:]
yaml_path = pathlib.Path(args[1]); out = pathlib.Path(args[args.index("--out_dir") + 1]); name = yaml_path.stem
print("Checking input data.", flush=True)
if "--use_msa_server" in args:
    print("Calling MSA server for target 0 with 1 sequences", flush=True)
print("Running structure prediction for 1 input.", flush=True)
print("Predicting \\x1b[35m1/1\\x1b[0m \\u2501\\u2501\\u2501\\u2501 0:00:01", flush=True)
if {fail!r}:
    print("torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.50 GiB", flush=True)
    sys.exit(1)
if {skip!r}:      # what boltz really does with an input it cannot parse: log it, skip it, exit 0, write nothing
    print("Found explicit empty MSA for some proteins, will run these in single sequence mode.", flush=True)
    print("Failed to process " + name + ".yaml. Skipping. Error: unsupported residue letter Z at position 12.", flush=True)
    sys.exit(0)
d = out / ("boltz_results_" + name) / "predictions" / name
d.mkdir(parents=True)
a = pathlib.Path({assets!r})
shutil.copy(a / "pdb" / "prot_lig.pdb", d / (name + "_model_0.pdb"))
shutil.copy(a / "pred_data" / "plddt.npz", d / ("plddt_" + name + "_model_0.npz"))
shutil.copy(a / "pred_data" / "pae.npz", d / ("pae_" + name + "_model_0.npz"))
shutil.copy(a / "pred_data" / "affinity.json", d / ("affinity_" + name + ".json"))
(d / ("confidence_" + name + "_model_0.json")).write_text(json.dumps({{"confidence_score": 0.9, "ptm": 0.9, "iptm": 0.8, "complex_plddt": 0.92}}))
print("Predicting property: affinity", flush=True)
print("100%|##########| 1/1 [00:01<00:00, 1.0s/it]", flush=True)
'''


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    base = tmp_path / "boltz_data"
    base.mkdir()
    write_yaml(build_yaml(simple_spec("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDG", ligand_smiles="CC(=O)Oc1ccccc1C(=O)O", affinity=True)), base / "params.yaml")
    (base / "run_params.txt").write_text(serialize_run_params(dict(DEFAULTS, job_name="demo", diffusion_samples=1)))
    monkeypatch.setenv("BOLTZ2NB_BASE_DIR", str(base))
    monkeypatch.delenv("BOLTZ2NB_JOB_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("BOLTZ2NB_MSA_CACHE", raising=False)
    monkeypatch.chdir(tmp_path)
    return base


def install_fake_boltz(tmp_path, monkeypatch, fail=False, skip=False):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    exe = bindir / "boltz"
    exe.write_text(FAKE.format(python=sys.executable, fail=fail, skip=skip, assets=str(ASSETS)))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")


def test_successful_run_then_analysis_in_plain_python(workspace, tmp_path, monkeypatch, capsys):
    install_fake_boltz(tmp_path, monkeypatch)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    out = capsys.readouterr().out
    assert "Calling MSA server" in out and "━" not in out and "[ok] 1 model(s)" in out        # bars are not echoed line by line
    status = json.loads((workspace / "demo" / "status.json").read_text())
    assert status["status"] == "COMPLETED" and status["n_models"] == 1 and status["return_code"] == 0
    assert json.loads((workspace / "last_job.json").read_text())["status"] == "COMPLETED"
    assert (workspace / "demo" / "run_context.json").exists() and (workspace / "demo" / "boltz.log").exists()

    g = runpy.run_path(str(ROOT / "scripts" / "common" / "analysis.py"))
    report = Path(g["out"]["report"])
    html = report.read_text()
    assert report.name == "demo_report.html" and 'class="bz-aff-v">2.77 µM<' in html and "$3Dmol.createViewer" in html
    frag = g["out"]["fragment"]
    assert "Saved files" in frag and "$3Dmol.createViewer" in frag and 'class="bz-viewer"' in frag   # Analyse Results shows the 3-D viewer too
    assert "ATOM  " in frag and "too large to show" not in frag
    assert json.loads((workspace / "demo" / "analysis" / "summary.json").read_text())["best_model"] == 0


def test_failed_run_reports_cause_and_fix(workspace, tmp_path, monkeypatch, capsys):
    install_fake_boltz(tmp_path, monkeypatch, fail=True)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    out = capsys.readouterr().out
    assert "[failed] demo" in out and "GPU ran out of memory" in out and "Boltz-2 failed after" in out
    status = json.loads((workspace / "demo" / "status.json").read_text())
    assert status["status"] == "FAILED" and "memory" in status["likely_cause"].lower() and status["suggested_fix"]
    assert json.loads((workspace / "last_job.json").read_text())["status"] == "FAILED"


def test_input_skipped_by_boltz_is_reported_as_failed_with_the_reason(workspace, tmp_path, monkeypatch, capsys):
    install_fake_boltz(tmp_path, monkeypatch, skip=True)
    with pytest.raises(RuntimeError, match="no predictions directory"):
        runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    out = capsys.readouterr().out
    assert "[failed] demo" in out and "skipped it" in out and "unsupported residue letter Z" in out and "different seed" not in out
    status = json.loads((workspace / "demo" / "status.json").read_text())
    assert status["status"] == "FAILED" and status["return_code"] == 0 and "skipped" in status["likely_cause"]
    assert json.loads((workspace / "last_job.json").read_text())["status"] == "FAILED"          # the analysis cell must not pick up an older job


def test_existing_job_folder_is_never_overwritten(workspace, tmp_path, monkeypatch, capsys):
    (workspace / "demo").mkdir()
    (workspace / "demo" / "keep.txt").write_text("precious")
    install_fake_boltz(tmp_path, monkeypatch)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    assert (workspace / "demo" / "keep.txt").read_text() == "precious"
    assert "already exists" in capsys.readouterr().out
    assert any(p.name.startswith("demo_") and (p / "status.json").exists() for p in workspace.iterdir() if p.is_dir())


def test_rich_display_path(workspace, tmp_path, monkeypatch):
    """With an IPython shell the panel streams updates to one display handle and the result card is displayed at the end."""
    pytest.importorskip("IPython")
    import IPython
    import IPython.display as ipd

    shown, updates = [], []

    class Handle:
        def update(self, obj):
            updates.append(str(getattr(obj, "data", obj)))

    def fake_display(obj, display_id=None, **kw):
        shown.append(str(getattr(obj, "data", obj)))
        return Handle() if display_id else None

    monkeypatch.setattr(IPython, "get_ipython", lambda: object())
    monkeypatch.setattr(ipd, "display", fake_display)
    install_fake_boltz(tmp_path, monkeypatch)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    assert shown[0].lstrip().startswith("<link") or "<style>" in shown[0]               # design system sent once, first
    assert sum("<style>" in s for s in shown + updates) == 2                            # ...plus once more inside the result card
    assert updates and "Completed" in updates[-1] and "Running" in "".join(updates)
    assert "Results" in shown[-1] and 'class="bz-aff-v"' in shown[-1] and "3Dmol.org" in shown[-1]
    assert max(len(u) for u in updates) < 20000                                         # refreshes carry the panel only, not the CSS


def test_a_structure_too_large_for_the_notebook_is_left_to_the_html_report(example_pred_dir, tmp_path, monkeypatch):
    from boltz2nb import report
    from boltz2nb.analysis import load_job
    job = load_job(example_pred_dir)
    monkeypatch.setattr(report, "INLINE_STRUCTURE_MAX_BYTES", 10)
    out = report.write_report(job, tmp_path / "analysis")
    assert 'class="bz-viewer"' not in out["fragment"] and "too large to show inside the notebook" in out["fragment"]
    assert 'class="bz-viewer"' in Path(out["report"]).read_text()                   # the HTML report keeps it
