# Tutorial

## 1. Check the analysis stack without a GPU

```bash
pip install -e ".[ligand]"
python tutorial/analyse_example.py
```

This assembles the example Boltz-2 output shipped in `assets/` (a 585-residue protein with a 23-heavy-atom
ligand) and writes `tutorial/output/prot_lig/analysis/prot_lig_report.html`. Expected console output:

```
chain A  protein  tokens= 585 mean pLDDT=93.8  Very high confidence
chain B  ligand   tokens=  23 mean pLDDT=59.5  Low confidence
interface PAE (Å): {'A-B': 14.2}
affinity: p(binder)=0.38  log10 IC50=0.44  IC50=2.77 µM  spread=1.07
```

Open the report: the PAE heat-map is the raw asymmetric matrix (rows = aligned token, columns = scored
token) on a fixed 0-32 Å scale with the ligand block in the lower right.

## 2. A first prediction in Colab

1. Open the V2 notebook from the README and run **Cell 1** (keep `NOTEBOOK_VERSION` at the release tag).
2. Run **Cell 2** once per runtime (downloads ~6 GB of weights).
3. In **Generate Parameters** paste a protein sequence, add a ligand by SMILES, tick *Predict affinity*,
   click *Save*, then set a job name and *Save run parameters*. The status line shows RDKit's formula
   and molecular weight for the ligand - a quick check that the SMILES is what you meant.
4. **Run Boltz2 Engine** streams the log; a T4 needs 2-5 min for a 300-residue protein with one ligand.
5. **Analyse Results** writes `analysis/<job>_report.html` and `summary.json` next to the predictions and
   shows the report inline. Use the binding probability for binder/decoy decisions and the IC50 only to
   rank close analogues; set `diffusion_samples ≥ 3` to see the spread of the confidence metrics.
6. **Copy to Drive** / **Download zip** export the whole job folder (models, NPZ/JSON, log,
   `run_context.json`, report).

## 3. Reproducing a run

`run_context.json` records the engine and torch versions, GPU, the exact command and the input YAML.
Re-running with the same YAML, `--seed` (set `seed` in `run_params.txt`) and engine version reproduces
the prediction up to GPU non-determinism.
