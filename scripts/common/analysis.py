# @title Analyse Results
"""Confidence / affinity analysis and HTML report for the last (or a chosen) job."""
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

from boltz2nb.analysis import load_job
from boltz2nb.ligand import depict_svg
from boltz2nb.paths import base_dir, find_predictions_dir
from boltz2nb.report import write_report

BASE = base_dir()
# Which job?  Explicit JOB_OUTPUT_DIR env/global wins, then the last run, then run_params.txt.
_target = os.environ.get("BOLTZ2NB_JOB_OUTPUT_DIR") or globals().get("job_output_dir")
if not _target and (BASE / "last_job.json").exists():
    _target = json.loads((BASE / "last_job.json").read_text()).get("output_dir")
if not _target:
    from boltz2nb.run_params import load_run_params
    _target = BASE / str(load_run_params(BASE / "run_params.txt")["job_name"])
output_dir = Path(_target)
pred_dir = find_predictions_dir(output_dir)
if pred_dir is None:
    raise FileNotFoundError(f"No Boltz predictions under {output_dir}. Did the run succeed?")

job = load_job(pred_dir)
run_context = None
ctx_path = output_dir / "run_context.json"
if ctx_path.exists():
    run_context = json.loads(ctx_path.read_text())

ligand_svg = None
try:
    doc = yaml.safe_load(run_context["input_yaml"]) if run_context and run_context.get("input_yaml") else None
    if doc:
        for s_ in doc.get("sequences", []):
            if "ligand" in s_ and s_["ligand"].get("smiles"):
                ligand_svg = depict_svg(s_["ligand"]["smiles"])
                break
except Exception:  # noqa: BLE001
    pass

runtime = None
if (output_dir / "status.json").exists():
    runtime = json.loads((output_dir / "status.json").read_text()).get("runtime_sec")

out = write_report(job, output_dir / "analysis", run_context=run_context, ligand_svg=ligand_svg, runtime=runtime)
job_name = job.job_name
report_path = Path(out["report"])
display(HTML(out["fragment"]))
print(f"[ok] Report: {report_path}")
