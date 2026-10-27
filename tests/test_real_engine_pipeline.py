"""The notebooks' cells run against the real Boltz-2 engine (CPU, tiny settings) - opt-in, never part of the normal run.

    BOLTZ2NB_REAL_ENGINE=1 BOLTZ_CACHE=/path/with/weights pytest tests/test_real_engine_pipeline.py -s

The official ``boltz`` package (``torch`` included) must be installed in the interpreter that runs pytest, with its ``boltz``
executable on PATH, and ``BOLTZ_CACHE`` must hold the Boltz-2 weights and CCD (``mols/``; the first run of the warm-up cell
downloads about 6 GB there). Everything else is what ``tests/test_notebooks_offline.py`` does: ``/content`` is a sandbox, the
clone is this working tree, ``google.colab`` is a stub. The MSA server is not used (``msa: empty``), so no network is needed
once the weights are present. Two diffusion samples at 20 sampling steps keep a run to a few minutes without a GPU.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
from pathlib import Path

import pytest

pytest.importorskip("IPython", reason="the notebook cells run inside an IPython shell")

from test_notebooks_offline import ASPIRIN, ASSETS, SEQ, Runner, call  # noqa: E402  (tests/ is on sys.path; no package)
from test_telemetry import collector, keys  # noqa: E402,F401  (fixtures: a local collecting web app and a key pair)

CACHE = Path(os.environ.get("BOLTZ_CACHE", Path.home() / ".boltz"))
pytestmark = pytest.mark.skipif(
    os.environ.get("BOLTZ2NB_REAL_ENGINE") != "1" or shutil.which("boltz") is None or not (CACHE / "mols").is_dir(),
    reason="opt-in: set BOLTZ2NB_REAL_ENGINE=1 with the boltz executable on PATH and the weights in BOLTZ_CACHE")

CPU_WARMUP = {'"--recycling_steps", "1", "--override"]': '"--recycling_steps", "1", "--override", "--num_workers", "0", "--accelerator", "cpu"]'}


@pytest.fixture
def real(tmp_path, monkeypatch):
    monkeypatch.setenv("BOLTZ_CACHE", str(CACHE))
    r = Runner(tmp_path, monkeypatch, real_engine=True)
    yield r
    r.close()


@pytest.mark.parametrize("notebook,scripts,fmt", [
    ("Boltz2.ipynb", "v2", "pdb"),                       # the default notebook
    ("Boltz2.ipynb", "v2", "mmcif"),                     # the structure format that once hit a stale-module error
    ("colab/v1/Boltz2_v1.0.0.ipynb", "v1", "pdb"),       # the Standard notebook
])
def test_real_protein_ligand_affinity(real, notebook, scripts, fmt, monkeypatch, collector, keys):  # noqa: F811
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", collector.url)                                 # usage reports ticked, aimed at a local collector
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    c = real.content
    out = real.run(notebook, 1, {"SEND_USAGE_STATS": True})                                  # Cell 1
    assert "Boltz engine already installed" in out and "All setup steps completed" in out, out[-1500:]
    out = real.run(notebook, 2, replace=CPU_WARMUP)                                          # Cell 2: warm-up on the real engine
    assert "Boltz2 ready" in out, out[-1500:]
    real.run(notebook, 3)                                                                    # Cell 3: the form
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": SEQ, "msa": "empty"}},
                             {"type": "ligand", "data": {"id": ["B"], "smiles": ASPIRIN}}],
               "templates": [], "constraints": {"bonds": [], "pockets": [], "contacts": []}, "properties": {"affinity_binder": "B"}}
    assert call(real.colab, "save_params", payload)["status"] == "ok"
    from boltz2nb.run_params import DEFAULTS, serialize_run_params
    job_name = f"real_{scripts}_{fmt}"
    content = serialize_run_params(dict(DEFAULTS, job_name=job_name, diffusion_samples=2, sampling_steps=20, recycling_steps=1,
                                        accelerator="cpu", num_workers=0, max_parallel_samples=1, output_format=fmt))
    assert call(real.colab, "save_run_params", {"filename": "run_params.txt", "content": content})["status"] == "ok"

    out = real.run(notebook, 4)                                                              # Cell 4: the real engine
    job = c / "boltz_data" / job_name
    status = json.loads((job / "status.json").read_text())
    assert status["status"].lower() == "completed", (status, out[-2000:])
    suffix = ".cif" if fmt == "mmcif" else ".pdb"
    models = sorted(job.rglob(f"{job_name}_model_*{suffix}"))
    assert len(models) == 2, [p.name for p in job.rglob("*model*")]
    for i in range(2):
        conf = json.loads(next(job.rglob(f"confidence_{job_name}_model_{i}.json")).read_text())
        assert 0 <= conf["confidence_score"] <= 1 and 0 <= conf["complex_plddt"] <= 1
        assert next(job.rglob(f"plddt_{job_name}_model_{i}.npz")) and next(job.rglob(f"pae_{job_name}_model_{i}.npz"))
    aff = json.loads(next(job.rglob(f"affinity_{job_name}.json")).read_text())
    assert "affinity_pred_value" in aff and "affinity_probability_binary" in aff

    out = real.run(notebook, 5)                                                              # Cell 5: analysis
    reports = [p for p in job.rglob("*.html")]
    assert reports, out[-2000:]
    html = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in reports)
    assert "bz-" in html and ("ATOM" in html or "data_" in html), "the report carries no structure for the viewer"
    assert "IC50" in html or "ic50" in html.lower(), "no affinity section in the report"
    summaries = list(job.rglob("summary.json"))
    assert summaries, [p.name for p in job.rglob("*.json")]
    summary = json.loads(summaries[0].read_text())
    assert len(summary.get("chains", [])) == 2 or "chains" in summary
    pngs = [p for p in job.rglob("*.png")]
    assert pngs, "no figures written"

    reports = collector.reports(keys["private"])                                              # what the maintainer would receive
    assert [r["event"] for r in reports] == ["boltz setup", "job started", "job succeeded"], [r["event"] for r in reports]
    started, ended = reports[1], reports[2]
    assert started["job_name"] == ended["job_name"] == job_name and (started["n_chains"], started["n_ligand_chains"], started["polymer_residues"]) == (2, 1, len(SEQ))
    assert started["params"]["output_format"] == fmt and started["params"]["sampling_steps"] == 20 and started["params"]["accelerator"] == "cpu"
    assert ended["runtime_sec"] > 60 and "log_tail" not in ended
    assert SEQ not in json.dumps(reports) and ASPIRIN not in json.dumps(reports)
    assert [json.loads(ln)["event"] for ln in (job / "usage_reports.jsonl").read_text().splitlines()] == ["job started", "job succeeded"]


def test_real_template_boltz_cannot_read_is_warned_about_and_explained(real):
    """A structure written by Boltz (no SEQRES records) as a template: the engine skips the input and exits 0. The form warns beforehand and the run
    cell says what happened instead of 'wrote no predictions directory, try another seed'."""
    notebook = "Boltz2.ipynb"
    real.run(notebook, 1)
    real.run(notebook, 2, replace=CPU_WARMUP)
    real.run(notebook, 3)
    up = call(real.colab, "save_uploaded_file", "template", "prediction.pdb", base64.b64encode((ASSETS / "pdb" / "prot_lig.pdb").read_bytes()).decode())
    assert up["status"] == "ok", up
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": SEQ, "msa": "empty"}}], "constraints": {"bonds": [], "pockets": [], "contacts": []},
               "templates": [{"path": up["path"], "chain_id": ["A"]}], "properties": {}}
    saved = call(real.colab, "save_params", payload)
    assert saved["status"] == "ok" and any("no SEQRES" in w for w in saved["warnings"]), saved
    from boltz2nb.run_params import DEFAULTS, serialize_run_params
    content = serialize_run_params(dict(DEFAULTS, job_name="bad_template", diffusion_samples=1, sampling_steps=20, recycling_steps=1, accelerator="cpu", num_workers=0))
    assert call(real.colab, "save_run_params", {"filename": "run_params.txt", "content": content})["status"] == "ok"

    out = real.run(notebook, 4, allow_failure_report=True)      # %run prints the script's RuntimeError and stops "Run all" at this cell; it does not raise out of it
    assert "no predictions directory was found: A template file could not be read by Boltz." in out, out[-1500:]
    job = real.content / "boltz_data" / "bad_template"
    status = json.loads((job / "status.json").read_text())
    assert status["status"] == "FAILED" and status["return_code"] == 0, status
    assert status["likely_cause"] == "A template file could not be read by Boltz." and "SEQRES" in status["suggested_fix"], status
    assert "Failed to process" in (job / "boltz.log").read_text() and "different seed" not in out


def test_real_failed_job_report_is_sealed_and_masked(real, monkeypatch, collector, keys):  # noqa: F811
    """Usage reports ticked, a real engine failure: what the collector decrypts is the real log tail with its paths masked, and the run settings as numbers."""
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", collector.url)
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    notebook = "Boltz2.ipynb"
    real.run(notebook, 1, {"SEND_USAGE_STATS": True})
    real.run(notebook, 2, replace=CPU_WARMUP)
    real.run(notebook, 3)
    up = call(real.colab, "save_uploaded_file", "template", "prediction.pdb", base64.b64encode((ASSETS / "pdb" / "prot_lig.pdb").read_bytes()).decode())
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": SEQ, "msa": "empty"}}], "constraints": {"bonds": [], "pockets": [], "contacts": []},
               "templates": [{"path": up["path"], "chain_id": ["A"]}], "properties": {}}
    assert call(real.colab, "save_params", payload)["status"] == "ok"
    from boltz2nb.run_params import DEFAULTS, serialize_run_params
    content = serialize_run_params(dict(DEFAULTS, job_name="private_target_x", diffusion_samples=1, sampling_steps=20, recycling_steps=1, accelerator="cpu", num_workers=0))
    assert call(real.colab, "save_run_params", {"filename": "run_params.txt", "content": content})["status"] == "ok"
    real.run(notebook, 4, allow_failure_report=True)

    reports = collector.reports(keys["private"])
    assert [r["event"] for r in reports] == ["boltz setup", "job started", "job failed"], [r["event"] for r in reports]
    started, failed = reports[1], reports[2]
    assert started["job_name"] == "private_target_x" and started["n_chains"] == 1 and started["polymer_residues"] == len(SEQ) and started["n_ligand_chains"] == 0
    assert started["params"]["accelerator"] == "cpu" and started["params"]["sampling_steps"] == 20 and "job_name" not in started["params"]
    assert failed["likely_cause"] == "A template file could not be read by Boltz." and failed["return_code"] == 0
    tail = failed["log_tail"]
    assert "Failed to process" in tail and "IndexError: list index out of range" in tail and "boltz/data/parse/mmcif.py" in tail
    for private in ("/home/", str(real.sandbox), "/content", SEQ):
        assert private not in tail, private
    assert SEQ not in json.dumps(reports)
