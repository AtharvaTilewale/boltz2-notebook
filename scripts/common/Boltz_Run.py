# @title Boltz2 Engine
# ruff: noqa: E402
"""Run `boltz predict` for the job described by run_params.txt + params.yaml."""
import json
import os
from pathlib import Path

import yaml

try:
    from IPython.display import HTML, display
except ImportError:  # plain Python: print a short notice instead of rich HTML
    class HTML(str):  # noqa: N801
        pass

    def display(obj):
        print(f"[HTML output suppressed outside IPython: {len(str(obj))} chars]")

# --- refresh stale boltz2nb (the same block is in every notebook script; the check itself is boltz2nb/_build.py) ---
# Cell 1 can update the clone under a running kernel; modules imported from the older copy would then be mixed with this newer script.
def _refresh_stale_boltz2nb():
    import importlib.util
    import sys
    from pathlib import Path

    loaded = sys.modules.get("boltz2nb")
    if loaded is None or not getattr(loaded, "__file__", None):
        return
    build_file = Path(loaded.__file__).parent / "_build.py"
    if build_file.exists():
        spec = importlib.util.spec_from_file_location("_boltz2nb_build", build_file)
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        build.drop_stale_modules(loaded)


_refresh_stale_boltz2nb()
del _refresh_stale_boltz2nb
# --- end refresh ---

from boltz2nb import telemetry
from boltz2nb.analysis import load_job, summary_dict
from boltz2nb.diagnostics import diagnose_failure
from boltz2nb.install import engine_version
from boltz2nb.paths import base_dir, find_predictions_dir
from boltz2nb.report import structure_text
from boltz2nb.run_params import load_run_params, validate_run_params
from boltz2nb.runner import build_boltz_cmd, capture_run_context, run_boltz, unique_output_dir, write_json
from boltz2nb.ui.live import LivePanel, RunState
from boltz2nb.ui.results import render_result_card
from boltz2nb.yaml_builder import dump_yaml, yaml_has_explicit_msa


class Color:
    CYAN = "\033[96m"; GREEN = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"; RESET = "\033[0m"


BASE = base_dir()
BASE.mkdir(parents=True, exist_ok=True)
os.chdir(BASE)

# ---- 1. parameters -----------------------------------------------------------------------
params_path = BASE / "run_params.txt"
if not params_path.exists():
    raise FileNotFoundError("run_params.txt not found - save the run parameters in the 'Generate Parameters' step first.")
params = load_run_params(params_path)
problems = validate_run_params(params)
if problems:
    raise ValueError("Invalid run parameters:\n  - " + "\n  - ".join(problems))
job_name = str(params["job_name"])

# ---- 2. input YAML (re-serialised through the builder's dumper: no shell/sed step) -------
source_yaml = BASE / "params.yaml"
job_yaml = BASE / f"{job_name}.yaml"
if source_yaml.exists():
    doc = yaml.safe_load(source_yaml.read_text())
    job_yaml.write_text(dump_yaml(doc))
elif not job_yaml.exists():
    raise FileNotFoundError(f"Neither params.yaml nor {job_yaml.name} exists - run the parameter step first.")

# ---- 3. output directory: never silently overwrite ---------------------------------------
requested_dir = BASE / job_name
if requested_dir.exists() and not params.get("override"):
    output_dir = unique_output_dir(requested_dir)
    print(f"{Color.YELLOW}[i] {requested_dir.name} already exists; writing to {output_dir.name} instead "
          f"(tick 'override' in the parameters to reuse the folder).{Color.RESET}")
else:
    output_dir = requested_dir
output_dir.mkdir(parents=True, exist_ok=True)
job_output_dir = output_dir  # used by the Drive/zip cells

# ---- 4. optional MSA cache (set BOLTZ2NB_MSA_CACHE, e.g. to a Drive folder) --------------
msa_cache_dir = os.environ.get("BOLTZ2NB_MSA_CACHE")
if msa_cache_dir:
    from boltz2nb import msa_cache
    applied, notes = msa_cache.apply_cache(job_yaml, msa_cache_dir)
    for n in notes:
        print(f"[i] MSA cache: {n}")

# ---- 5. command ---------------------------------------------------------------------------
use_server = not yaml_has_explicit_msa(job_yaml.read_text())
cmd = build_boltz_cmd(job_yaml, output_dir, params, use_msa_server=use_server)
run_context = capture_run_context(params, cmd, job_yaml)
write_json(output_dir / "run_context.json", run_context)

state = RunState(job_name=job_name, has_affinity="affinity" in job_yaml.read_text(), msa_server=use_server,
                 gpu=run_context.get("gpu_name") or "", engine=engine_version() or "", samples=int(params["diffusion_samples"]),
                 command=" ".join(cmd))
panel = LivePanel(state)
if not panel.rich:  # plain Python / terminal: keep the old, explicit console header
    print(f"[i] Engine: {engine_version()} | GPU: {run_context.get('gpu_name', 'none')}")
    print(f"[i] Command: {' '.join(cmd)}")
print(f"[i] Live log: {output_dir / 'boltz.log'}")

# ---- 6. run with live output ---------------------------------------------------------------
# Usage report (docs/PRIVACY.md): job name, number of chains and residues, run settings. Never sequences, ligands or modifications.
# Silent: a copy of what was sent is kept in usage_reports.jsonl in the job folder.
_usage_copy = output_dir / "usage_reports.jsonl"
telemetry.job_started(job_yaml.read_text(), params, engine=engine_version() or "", copy_to=_usage_copy)
panel.start()
result = run_boltz(cmd, output_dir / "boltz.log", on_line=panel.feed)
elapsed = result["runtime_sec"]


def _report_end(ok, **details):
    telemetry.job_ended(ok, job_name, elapsed, engine_version() or "", _usage_copy, **details)

# ---- 7. outcome ------------------------------------------------------------------------------
status = {"job_name": job_name, "output_dir": str(output_dir), "return_code": result["return_code"],
          "runtime_sec": elapsed, "command": cmd}
if result["return_code"] != 0:
    _log = Path(result["log_path"]).read_text()
    diag = diagnose_failure(_log)
    _report_end(False, return_code=result["return_code"], likely_cause=diag["likely_cause"], log_text=_log)
    status.update({"status": "FAILED", **diag})
    write_json(output_dir / "status.json", status)
    (BASE / "last_job.json").write_text(json.dumps(status, indent=2))
    for line in str(result.get("tail", "")).splitlines()[-14:]:
        state.lines.append(line)            # the panel's log shows the real tail, not just the last streamed lines
    panel.finish(False, diag["likely_cause"], diag["suggested_fix"])
    print(f"Boltz-2 failed after {elapsed:.0f} s (exit code {result['return_code']}). Full log: {result['log_path']}")
else:
    pred_dir = find_predictions_dir(output_dir)
    if pred_dir is None:
        # Boltz skips an input it cannot process and still exits with code 0; its log says why.
        _log = Path(result["log_path"]).read_text()
        diag = diagnose_failure(_log)
        if diag["likely_cause"] == "Unrecognised error.":
            diag = {"likely_cause": "Boltz exited normally but wrote no predictions directory.",
                    "suggested_fix": "Open the log above; re-run with a different seed or fewer tokens."}
        _report_end(False, return_code=0, likely_cause=diag["likely_cause"], log_text=_log)
        status.update({"status": "FAILED", **diag})
        write_json(output_dir / "status.json", status)
        (BASE / "last_job.json").write_text(json.dumps(status, indent=2))
        for line in str(result.get("tail", "")).splitlines()[-14:]:
            state.lines.append(line)
        panel.finish(False, diag["likely_cause"], diag["suggested_fix"])
        raise RuntimeError("Boltz exited normally but no predictions directory was found: " + diag["likely_cause"])
    if msa_cache_dir and use_server:
        stored = msa_cache.store(job_yaml, output_dir, msa_cache_dir)
        if stored:
            print(f"[i] MSA cache: stored {len(stored)} new MSA file(s).")
    job = load_job(pred_dir)
    summary = summary_dict(job)
    _report_end(True)
    status.update({"status": "COMPLETED", "predictions_dir": str(pred_dir), "n_models": len(job.models)})
    write_json(output_dir / "status.json", status)
    (BASE / "last_job.json").write_text(json.dumps(status, indent=2))
    panel.finish(True)
    best = job.best
    pdb_text, structure_format = structure_text(job)
    display(HTML(render_result_card(summary, pdb_text, run_context, runtime=elapsed, structure_format=structure_format)))
    print(f"[ok] {len(job.models)} model(s) in {pred_dir}")
