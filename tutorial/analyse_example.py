"""Build the analysis report from the shipped example outputs - no GPU or Boltz install needed.

    pip install -e ".[ligand]"
    python tutorial/analyse_example.py            # writes tutorial/output/

Expected values (from assets/pred_data + assets/pdb/prot_lig.pdb):
    chain A (protein, 585 tokens)  mean pLDDT 93.8
    chain B (ligand,  23 tokens)   mean pLDDT 59.5
    affinity: binding probability 0.38, log10 IC50(µM) 0.44 -> IC50 ~ 2.8 µM, ensemble spread 1.07 log units
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from boltz2nb.analysis import load_job  # noqa: E402
from boltz2nb.report import write_report  # noqa: E402

job = "prot_lig"
out = ROOT / "tutorial" / "output"
pred = out / job / f"boltz_results_{job}" / "predictions" / job
pred.mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT / "assets/pdb/prot_lig.pdb", pred / f"{job}_model_0.pdb")
shutil.copy(ROOT / "assets/pred_data/plddt.npz", pred / f"plddt_{job}_model_0.npz")
shutil.copy(ROOT / "assets/pred_data/pae.npz", pred / f"pae_{job}_model_0.npz")
shutil.copy(ROOT / "assets/pred_data/affinity.json", pred / f"affinity_{job}.json")

result = load_job(pred)
files = write_report(result, out / job / "analysis")
summary = json.loads(Path(files["summary"]).read_text())
for c in summary["chains"]:
    print(f"chain {c['chain_id']:2s} {c['kind']:8s} tokens={c['n_tokens']:4d} mean pLDDT={c['mean_plddt']:.1f}  {c['assessment']}")
print("interface PAE (Å):", {k: round(v, 1) for k, v in summary["interface_pae"].items()})
a = summary["affinity"]
print(f"affinity: p(binder)={a['binding_probability']:.2f}  log10 IC50={a['log10_ic50_um']:.2f}  IC50={a['ic50']}  spread={a['member_spread']:.2f}")
print("report:", files["report"])
