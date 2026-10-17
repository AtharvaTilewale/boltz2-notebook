# @title Boltz2 Engine
"""Run `boltz predict` for the job described by run_params.txt + params.yaml."""
import json
import os
import re
import sys
import time
from pathlib import Path

import yaml

try:
    from IPython.display import HTML, display
except ImportError:  # plain Python: print a short notice instead of rich HTML
    class HTML(str):  # noqa: N801
        pass

    def display(obj):
        print(f"[HTML output suppressed outside IPython: {len(str(obj))} chars]")

from boltz2nb import telemetry
from boltz2nb.analysis import load_job, summary_dict
from boltz2nb.diagnostics import diagnose_failure
from boltz2nb.install import engine_version
from boltz2nb.paths import base_dir, find_predictions_dir
from boltz2nb.run_params import load_run_params, validate_run_params
from boltz2nb.runner import build_boltz_cmd, capture_run_context, run_boltz, unique_output_dir, write_json
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
print(f"[i] Engine: {engine_version()} | GPU: {run_context.get('gpu_name', 'none')}")
print(f"[i] Command: {' '.join(cmd)}")
print(f"[i] Live log: {output_dir / 'boltz.log'}")

# ---- 6. run with live output ---------------------------------------------------------------
_progress_re = re.compile(r"(\d+%\|)|(it/s\])|(s/it\])")
_last = {"t": time.time(), "line": ""}


def on_line(line: str):
    line = line.rstrip()
    if not line:
        return
    if _progress_re.search(line):           # tqdm bars: keep only the most recent one on screen
        sys.stdout.write("\r" + line[-110:].ljust(110)); sys.stdout.flush()
        _last["line"] = line
        return
    sys.stdout.write("\r" + " " * 110 + "\r")
    print(line[:400])


t0 = time.time()
result = run_boltz(cmd, output_dir / "boltz.log", on_line=on_line)
print()
elapsed = result["runtime_sec"]
telemetry.send("run_finished" if result["return_code"] == 0 else "run_failed", engine=engine_version())

# ---- 7. outcome ------------------------------------------------------------------------------
status = {"job_name": job_name, "output_dir": str(output_dir), "return_code": result["return_code"],
          "runtime_sec": elapsed, "command": cmd}
if result["return_code"] != 0:
    diag = diagnose_failure(Path(result["log_path"]).read_text())
    status.update({"status": "FAILED", **diag})
    write_json(output_dir / "status.json", status)
    (BASE / "last_job.json").write_text(json.dumps(status, indent=2))
    print(f"[{Color.RED}✘{Color.RESET}] Boltz2 failed after {elapsed:.0f} s (exit code {result['return_code']}).")
    print(f"{Color.YELLOW}Likely cause:{Color.RESET} {diag['likely_cause']}\n{Color.YELLOW}Suggested fix:{Color.RESET} {diag['suggested_fix']}")
    display(HTML(f"<details open><summary>Log tail</summary><pre style='max-height:360px;overflow:auto;font-size:.85em'>{result['tail']}</pre></details>"))
else:
    pred_dir = find_predictions_dir(output_dir)
    if pred_dir is None:
        raise RuntimeError("Boltz exited normally but no predictions directory was found.")
    if msa_cache_dir and use_server:
        stored = msa_cache.store(job_yaml, output_dir, msa_cache_dir)
        if stored:
            print(f"[i] MSA cache: stored {len(stored)} new MSA file(s).")
    job = load_job(pred_dir)
    summary = summary_dict(job)
    status.update({"status": "COMPLETED", "predictions_dir": str(pred_dir), "n_models": len(job.models)})
    write_json(output_dir / "status.json", status)
    (BASE / "last_job.json").write_text(json.dumps(status, indent=2))
    print(f"[{Color.GREEN}✔{Color.RESET}] Boltz2 finished in {elapsed:.0f} s - {len(job.models)} model(s) in {pred_dir}")

    best = job.best
    rows = "".join(
        f"<tr><td>{r['model']}</td><td>{r['confidence_score']:.3f}</td><td>{(r['ptm'] or 0):.3f}</td>"
        f"<td>{(r['iptm'] or 0):.3f}</td><td>{r['mean_plddt']:.1f}</td></tr>"
        for r in summary["models"] if r.get("confidence_score") is not None)
    chain_rows = "".join(f"<tr><td>{c['chain_id']}</td><td>{c['kind']}</td><td>{c['n_tokens']}</td>"
                         f"<td>{c['mean_plddt']:.1f}</td><td>{c['assessment']}</td></tr>" for c in summary["chains"])
    aff_html = ""
    if summary["affinity"]:
        a = summary["affinity"]
        aff_html = (f"<p><b>Affinity:</b> binding probability {a['binding_probability']:.2f} ({a['probability_class']}); "
                    f"log10 IC50(µM) = {a['log10_ic50_um']:.2f} → IC50 ≈ {a['ic50']} ({a['potency_class']}).</p>")
    pdb_js = json.dumps(best.structure_path.read_text()) if best.structure_path.suffix == ".pdb" else "null"
    css = ("<style>.bz{font-family:Roboto,Arial,sans-serif;border:1px solid #e0e0e0;border-radius:10px;padding:16px;margin:8px}"
           ".bz table{border-collapse:collapse;margin:6px 0}.bz td,.bz th{border:1px solid #e5e7eb;padding:4px 10px;font-size:.9em}"
           ".bz h2{color:#145abe;margin:4px 0 8px}.bz .row{display:flex;gap:16px;flex-wrap:wrap}"
           "#bzv{width:620px;height:460px;position:relative;border:1px solid #e0e0e0;border-radius:8px}</style>")
    html = f"""{css}<div class="bz"><h2>Boltz2 results: <code>{job_name}</code></h2>
    <div class="row"><div><b>Per-sample scores</b><table><tr><th>model</th><th>confidence</th><th>pTM</th><th>ipTM</th><th>mean pLDDT</th></tr>{rows}</table>
    <b>Chains (model {best.model_id})</b><table><tr><th>chain</th><th>kind</th><th>tokens</th><th>mean pLDDT</th><th>assessment</th></tr>{chain_rows}</table>{aff_html}
    <p style="font-size:.85em;color:#555">Run the <b>Analyse Results</b> cell for PAE/pLDDT plots, ensemble statistics and the downloadable HTML report.</p></div>
    <div><div id="bzv"></div><div style="font-size:.8em;color:#555">cartoon coloured by pLDDT (red 50 → blue 90); ligands as sticks</div></div></div></div>
    <script src="https://3Dmol.org/build/3Dmol-min.js"></script><script>
    (function(){{const pdb={pdb_js}; if(!pdb) return; const el=document.getElementById('bzv');
    const v=$3Dmol.createViewer(el,{{backgroundColor:'white'}}); v.addModel(pdb,'pdb');
    v.setStyle({{}},{{cartoon:{{colorscheme:{{prop:'b',gradient:'roygb',min:50,max:90}}}}}});
    v.addStyle({{hetflag:true}},{{stick:{{}}}}); v.zoomTo(); v.render();}})();</script>"""
    display(HTML(html))
