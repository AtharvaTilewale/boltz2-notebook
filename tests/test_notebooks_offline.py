"""Run every notebook's code cells, in order, the way Colab would - offline.

``/content`` is redirected to a sandbox, the repository clone is a copy of this working tree, ``google.colab`` is a stub
that records what the cells asked of it (Drive mounts, downloads, uploads, registered callbacks), and ``boltz`` is the fake
executable from the other tests. A cell's ``# @param`` form values can be set per run, as a user would in Colab.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("IPython", reason="the notebook cells run inside an IPython shell")

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SEQ = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDG"
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"

FAKE_BOLTZ = '''#!{python}
import json, pathlib, shutil, sys
args = sys.argv[1:]
assert args[0] == "predict", args
yaml_path = pathlib.Path(args[1]); out = pathlib.Path(args[args.index("--out_dir") + 1]); name = yaml_path.stem
n = int(args[args.index("--diffusion_samples") + 1]) if "--diffusion_samples" in args else 1
print("Checking input data.", flush=True)
if "--use_msa_server" in args:
    print("Calling MSA server for target 0 with 1 sequences", flush=True)
print("Running structure prediction for 1 input.", flush=True)
text = yaml_path.read_text()
if "FAILME" in text:
    print("torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.50 GiB", flush=True); sys.exit(1)
d = out / ("boltz_results_" + name) / "predictions" / name
d.mkdir(parents=True, exist_ok=True)
a = pathlib.Path({assets!r})
for i in range(n):
    shutil.copy(a / "pdb" / "prot_lig.pdb", d / f"{{name}}_model_{{i}}.pdb")
    shutil.copy(a / "pred_data" / "plddt.npz", d / f"plddt_{{name}}_model_{{i}}.npz")
    shutil.copy(a / "pred_data" / "pae.npz", d / f"pae_{{name}}_model_{{i}}.npz")
    (d / f"confidence_{{name}}_model_{{i}}.json").write_text(json.dumps({{"confidence_score": 0.9 - 0.05 * i, "ptm": 0.9, "iptm": 0.8,
        "ligand_iptm": 0.8, "protein_iptm": 0.0, "complex_plddt": 0.92, "complex_iplddt": 0.9, "complex_pde": 1.1, "complex_ipde": 1.5,
        "chains_ptm": {{"0": 0.9, "1": 0.8}}, "pair_chains_iptm": {{"0": {{"0": 0.9, "1": 0.8}}, "1": {{"0": 0.8, "1": 0.8}}}}}}))
if "properties" in text or "affinity" in text:
    shutil.copy(a / "pred_data" / "affinity.json", d / f"affinity_{{name}}.json")
    print("Predicting property: affinity", flush=True)
print("Boltz fake run complete", flush=True)
'''


class ColabStub:
    """Stands in for ``google.colab``: records every call the notebooks make."""

    def __init__(self, content: Path):
        self.content = content
        self.callbacks: dict[str, object] = {}
        self.downloads: list[str] = []
        self.mounts: list[str] = []
        self.uploads: dict[str, bytes] = {}
        stub = self
        google = types.ModuleType("google")
        colab = types.ModuleType("google.colab")
        output = types.ModuleType("google.colab.output")
        files = types.ModuleType("google.colab.files")
        drive = types.ModuleType("google.colab.drive")
        output.register_callback = lambda name, fn: stub.callbacks.__setitem__(name, fn)
        output.eval_js = lambda *a, **k: None
        files.download = lambda path: stub.downloads.append(str(path))
        files.upload = lambda: dict(stub.uploads)

        def mount(path, force_remount=False):
            stub.mounts.append(path)
            (Path(path) / "MyDrive").mkdir(parents=True, exist_ok=True)

        drive.mount = mount
        colab.output, colab.files, colab.drive = output, files, drive
        google.colab = colab
        self.modules = {"google": google, "google.colab": colab, "google.colab.output": output, "google.colab.files": files, "google.colab.drive": drive}


STUB_TORCH = """# stand-in for the real package: enough for the setup checks and the GPU banner
__version__ = "0.0-stub"
class _Props:
    total_memory = 16e9
class cuda:
    @staticmethod
    def is_available(): return False
    @staticmethod
    def get_device_name(i=0): return "stub"
    @staticmethod
    def get_device_properties(i=0): return _Props()
"""


class Runner:
    def __init__(self, tmp_path: Path, monkeypatch, real_engine: bool = False):
        self.sandbox = tmp_path
        self.content = tmp_path / "content"
        self.content.mkdir()
        # The engine is never installed here: a stub ``torch`` and ``boltz`` (importable in this process and in the
        # subprocess the setup cell spawns to verify the installation) make the cells take their "already installed" path.
        # With ``real_engine`` the installed ``torch`` / ``boltz`` and the ``boltz`` executable on PATH are used as they are.
        if not real_engine:
            stubs = tmp_path / "stubs"
            (stubs / "boltz").mkdir(parents=True)
            (stubs / "boltz" / "__init__.py").write_text('__version__ = "0.0-stub"\n')
            (stubs / "torch.py").write_text(STUB_TORCH)
            monkeypatch.setenv("PYTHONPATH", f"{stubs}{os.pathsep}{os.environ.get('PYTHONPATH', '')}".rstrip(os.pathsep))
            for name in ("torch", "boltz"):
                monkeypatch.delitem(sys.modules, name, raising=False)
            sys.path.insert(0, str(stubs))
            monkeypatch.setattr(sys, "path", list(sys.path))
        self.colab = ColabStub(self.content)
        for name, mod in self.colab.modules.items():
            monkeypatch.setitem(sys.modules, name, mod)
        # the "clone": this working tree, so uncommitted changes are what gets tested
        repo = self.content / "boltz2-notebook"
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
                                 capture_output=True, text=True, check=True).stdout.split("\n")
        for rel in tracked:
            if rel and (ROOT / rel).is_file():
                dst = repo / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, dst)
        self.repo = repo
        # fake engine
        if not real_engine:
            bindir = tmp_path / "bin"
            bindir.mkdir()
            exe = bindir / "boltz"
            exe.write_text(FAKE_BOLTZ.format(python=sys.executable, assets=str(ASSETS)))
            exe.chmod(0o755)
            monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("MPLBACKEND", "Agg")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home").mkdir()
        for var in ("BOLTZ2NB_BASE_DIR", "BOLTZ2NB_REPO_DIR", "BOLTZ2NB_JOB_OUTPUT_DIR", "BOLTZ2NB_MSA_CACHE", "BOLTZ2NB_BATCH_ROOT", "FORCE_REINSTALL",
                    "BOLTZ2NB_SEND_USAGE_STATS"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.chdir(tmp_path)
        # a fresh IPython shell with a display publisher that records outputs
        from IPython.core.displaypub import CapturingDisplayPublisher
        from IPython.core.interactiveshell import InteractiveShell
        InteractiveShell.clear_instance()
        self.shell = InteractiveShell.instance()
        self.shell.display_pub = CapturingDisplayPublisher()
        self.shell.user_ns.clear()
        self.shell.user_ns.update({"__name__": "__main__", "__builtins__": __builtins__})
        self.outputs: list[str] = []

    def close(self):
        from IPython.core.interactiveshell import InteractiveShell
        InteractiveShell.clear_instance()

    def rewrite(self, src: str, params: dict | None = None) -> str:
        src = src.replace("/content", str(self.content))
        # pip installs are not performed (the working tree is importable; the engine is stubbed): the call becomes a no-op
        src = src.replace('"-m", "pip", "install"', '"-c", "pass", "--"')
        for key, value in (params or {}).items():
            replacement = f"{key} = {value!r}" + r"\1"
            src, n = re.subn(rf"^{key} = .*?(\s*#\s*@param.*)$", replacement, src, flags=re.M)
            assert n == 1, f"form field {key} not found exactly once"
        return src

    def run(self, notebook: str, index: int, params: dict | None = None, expect_error: str | None = None, allow_failure_report: bool = False,
            replace: dict[str, str] | None = None) -> str:
        cells = json.loads((ROOT / notebook).read_text(encoding="utf-8"))["cells"]
        cell = cells[index]
        assert cell["cell_type"] == "code", (notebook, index)
        src = self.rewrite("".join(cell["source"]), params)
        for before, after in (replace or {}).items():
            assert src.count(before) == 1, f"{before!r} not found exactly once in cell {index} of {notebook}"
            src = src.replace(before, after)
        buf = io.StringIO()
        self.shell.display_pub.outputs.clear()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result = self.shell.run_cell(src, store_history=False)
        out = buf.getvalue()
        self.outputs.append(out)
        displayed = "\n".join(str(o.get("data", {}).get("text/html", "")) for o in self.shell.display_pub.outputs)
        self.last_html = displayed
        err = result.error_in_exec or result.error_before_exec
        if expect_error:
            assert err is not None and expect_error in f"{type(err).__name__}: {err}", f"cell {index} of {notebook} should have failed with {expect_error!r}; got {err!r}\n{out[-1500:]}"
            return out
        assert err is None, f"cell {index} of {notebook} raised {type(err).__name__}: {err}\n--- output ---\n{out[-3000:]}"
        clean = re.sub(r"\x1b\[[0-9;]*m", "", out)
        bad = [] if allow_failure_report else [ln for ln in clean.splitlines() if re.search(r"\[✘\]|Traceback|failed:|Setup finished with errors", ln)]
        assert not bad, f"cell {index} of {notebook} reported a failure:\n" + "\n".join(bad[:6]) + "\n--- output ---\n" + clean[-3000:]
        return clean


@pytest.fixture
def runner(tmp_path, monkeypatch):
    r = Runner(tmp_path, monkeypatch)
    yield r
    r.close()


def call(colab: ColabStub, name: str, *args):
    """Invoke a registered callback and read the answer the way the page does: the notebook's display of the return value."""
    from IPython.core.formatters import DisplayFormatter
    data, _ = DisplayFormatter().format(colab.callbacks[name](*args))
    assert "application/json" in data, f"{name} would reach the page as {sorted(data)}, not as parsed JSON"
    return data["application/json"]


def user_fills_the_form(colab: ColabStub, job_name: str, affinity: bool = True):
    """What the browser form sends when the user clicks Save: the same callbacks, the same payloads."""
    cb = colab.callbacks
    assert {"preview_params", "save_params", "save_run_params"} <= set(cb), sorted(cb)
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": SEQ, "msa": "server"}},
                             {"type": "ligand", "data": {"id": ["B"], "smiles": ASPIRIN}}],
               "templates": [], "constraints": {"bonds": [], "pockets": [], "contacts": []},
               "properties": {"affinity_binder": "B"} if affinity else {}}
    preview = call(colab, "preview_params", payload)
    assert preview["status"] == "ok", preview
    saved = call(colab, "save_params", payload)
    assert saved["status"] == "ok", saved
    from boltz2nb.run_params import DEFAULTS, serialize_run_params
    content = serialize_run_params(dict(DEFAULTS, job_name=job_name, diffusion_samples=2, sampling_steps=50, recycling_steps=1, max_msa_seqs=256))
    run = call(colab, "save_run_params", {"filename": "run_params.txt", "content": content})
    assert run["status"] == "ok", run
    return saved, run


@pytest.mark.parametrize("notebook,scripts", [("Boltz2.ipynb", "v2"), ("colab/v1/Boltz2_v1.0.0.ipynb", "v1"), ("colab/v2/Boltz2_V2.0.0.ipynb", "v2")])
def test_main_notebook_end_to_end(runner, notebook, scripts):
    c = runner.content
    out = runner.run(notebook, 1, {"USE_DRIVE_MSA_CACHE": True})                 # Cell 1: setup (+ Drive MSA cache)
    assert "Using the notebook code already present" in out and "Notebook scripts staged" in out and "All setup steps completed" in out
    assert (c / "boltz_data" / "scripts" / scripts / "param_gen.py").is_file() and (c / "boltz_data" / "VERSION").is_file()
    assert runner.colab.mounts == [str(c / "drive")] and (c / "drive/MyDrive/Boltz2_Results/msa_cache").is_dir()

    out = runner.run(notebook, 2)                                                 # Cell 2: warm-up
    assert "Boltz2 ready" in out and (c / "boltz_data" / "warmup").is_dir()

    runner.run(notebook, 3)                                                       # Cell 3: the input builder
    assert 'id="bz-root-' in runner.last_html and 'data-theme="light"' in runner.last_html
    saved, run = user_fills_the_form(runner.colab, "demo_job")
    assert (c / "boltz_data" / "params.yaml").is_file() and (c / "boltz_data" / "run_params.txt").is_file()

    out = runner.run(notebook, 4)                                                 # Cell 4: the engine
    job = c / "boltz_data" / "demo_job"
    assert job.is_dir(), out
    status = json.loads((job / "status.json").read_text())
    assert status["status"].lower() == "completed", status
    assert (job / "run_context.json").is_file() and (c / "boltz_data" / "last_job.json").is_file()
    assert "bz-live" in runner.last_html

    out = runner.run(notebook, 5)                                                 # Cell 5: analysis
    report = list(job.rglob("*.html"))
    assert report, out
    assert "bz-report" in runner.last_html or "bz-res" in runner.last_html
    assert any(p.suffix == ".png" for p in job.rglob("*")), "no figures written"

    out = runner.run(notebook, 6)                                                 # Cell 6: copy to Drive
    assert (c / "drive/MyDrive/Boltz2_Results/demo_job/status.json").is_file(), out
    out = runner.run(notebook, 6)                                                 # again: the existing copy is kept
    assert len(list((c / "drive/MyDrive/Boltz2_Results").glob("demo_job*"))) == 2

    out = runner.run(notebook, 7)                                                 # Cell 7: download zip
    assert runner.colab.downloads and runner.colab.downloads[-1].endswith("demo_job.zip") and Path(runner.colab.downloads[-1]).is_file()


@pytest.mark.parametrize("nb", ["Boltz2.ipynb", "colab/v1/Boltz2_v1.0.0.ipynb"])
def test_main_notebook_failed_run_is_reported_not_raised(runner, nb):
    runner.run(nb, 1)
    runner.run(nb, 3)
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTAYIAKQFAILMEKQRQISFVKSHFSRQLEERLG", "msa": "empty"}}],
               "templates": [], "constraints": {"bonds": [], "pockets": [], "contacts": []}, "properties": {}}
    assert call(runner.colab, "save_params", payload)["status"] == "ok"
    from boltz2nb.run_params import DEFAULTS, serialize_run_params
    assert call(runner.colab, "save_run_params", {"filename": "run_params.txt", "content": serialize_run_params(dict(DEFAULTS, job_name="oom_job", diffusion_samples=1))})["status"] == "ok"
    # make the fake engine fail: it fails on any YAML that mentions FAILME
    p = runner.content / "boltz_data" / "params.yaml"
    p.write_text(p.read_text() + "\n# FAILME\n")
    out = runner.run(nb, 4, allow_failure_report=True)
    assert "Boltz-2 failed" in out
    status = json.loads((runner.content / "boltz_data" / "oom_job" / "status.json").read_text())
    assert status["status"].lower() == "failed" and "memory" in json.dumps(status).lower(), status
    assert "bz-alert--err" in runner.last_html or "GPU ran out of memory" in out


def test_paramgen_notebook(runner):
    nb = "notebooks/Boltz2_paramgen.ipynb"
    out = runner.run(nb, 1)
    runner.run(nb, 2)
    assert 'id="bz-root-' in runner.last_html, out
    user_fills_the_form(runner.colab, "pg_job")
    runner.run(nb, 3)
    assert len(runner.colab.downloads) >= 2 and all(Path(p).is_file() for p in runner.colab.downloads), runner.colab.downloads


def test_batch_notebook_end_to_end(runner):
    pytest.importorskip("ipywidgets", reason="the batch notebook's viewer step uses ipywidgets")
    pytest.importorskip("py3Dmol", reason="the batch notebook's viewer step uses py3Dmol")
    nb = "batch/Boltz2_Batch_v1_beta.ipynb"
    c = runner.content
    fasta = runner.sandbox / "jobs.fasta"
    fasta.write_text(f">job_one\n{SEQ}\n>job_two\n{SEQ[:30]}:{SEQ[10:40]}\n>job_fail\nFAILME{SEQ}\n")
    out = runner.run(nb, 1, {"MOUNT_DRIVE": True})
    assert "Workspace ready" in out and (c / "boltz_batch" / "Batch_Utils.py").is_file()
    out = runner.run(nb, 2, {"INPUT_MODE": "fasta", "FASTA_PATH": str(fasta), "UPLOAD_FILES": False})
    manifests = list((c / "boltz_batch" / "manifests").glob("*.csv"))
    assert manifests, out
    out = runner.run(nb, 3)
    out = runner.run(nb, 4)
    jobs = c / "boltz_batch" / "jobs"
    statuses = {p.parent.name: json.loads(p.read_text()).get("status") for p in jobs.rglob("status.json")}
    assert statuses and set(statuses.values()) <= {"COMPLETED", "FAILED", "completed", "failed"}, (statuses, out[-2000:])
    out = runner.run(nb, 5)
    assert list((c / "boltz_batch" / "summaries").glob("*.csv")), out
    out = runner.run(nb, 6)
    out = runner.run(nb, 7)
    out = runner.run(nb, 8)
    exports = list((c / "boltz_batch" / "exports").glob("*.zip"))
    assert exports and runner.colab.downloads, out
