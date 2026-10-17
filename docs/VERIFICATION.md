# Verification log (v2.1.0)

| What | How | Result |
|---|---|---|
| Unit suite | `pytest` (46 tests, no GPU) | pass |
| Lint | `ruff check boltz2nb tests scripts/common tutorial` | clean |
| Notebook cells | `tools/check_notebooks.py` (compile + `%run` targets) | pass |
| Generated YAML vs engine schema | `tests/test_engine_schema.py` - protein+ligand+affinity, DNA/RNA multichain, PTM + CCD ligand + pocket/contact constraints, cyclic peptide, parsed by `boltz.data.parse.schema.parse_boltz_schema` with the real CCD cache | pass |
| Full pipeline, official engine | `boltz 2.2.1`, 43-aa protein + aspirin, affinity, `diffusion_samples 2`, through `scripts/v2/Boltz_Run.py` then `scripts/v2/analysis.py` | 565 s (CPU); 43 + 13 tokens mapped, interface PAE 7.2/6.2 Å, confidence 0.747/0.706, IC50 ≈ 44 µM; report + summary.json + plots written |
| Full pipeline, community engine | `boltz-community 2.10.12`, same input | analysed identically (`atomised` layout, 43 + 13 tokens, IC50 ≈ 32 µM) |
| Failure path | OOM on a 4 GB GPU | correct diagnosis ("GPU ran out of memory" + fix), `status.json` written, log preserved |
| Parameter GUI backends (v1 and v2 dialects) | callbacks driven directly with a stubbed `google.colab.output`: valid payload, bad SMILES, affinity on a protein chain, constraint referencing an unknown chain, PTM position out of range, invalid DNA alphabet, out-of-range sampling_steps, obsolete `unpaired_paired` strategy, template/MSA uploads with extension checks | all accepted/rejected as intended; `params.yaml` and `run_params.txt` correct |
| Real Colab, Python 3.13 runtime, T4 | V2 notebook, protein + ligand with affinity and MSA server | Cell 1 selected `boltz-community 2.10.12` (official wheels need < 3.13); MSA server, structure (35 s) and affinity (12 s) succeeded; analysis initially stopped on a token-layout mismatch (29 structure tokens vs 20 array entries), which is why layout resolution and the metrics-only fallback were added |

Not yet verified: the in-browser HTML forms (JavaScript interaction), Google Drive export in a live
session, and the batch notebook on Colab.
