# Verification log (v2.1.0)

| What | How | Result |
|---|---|---|
| Unit suite | `pytest` without a browser (168 tests, no GPU) | pass |
| Browser suite | `pytest tests/ui` in headless Firefox 157 (64 tests): real form + real callbacks, both RPC shapes, validation, FASTA, PDB import, uploads, presets, theme, no horizontal overflow at 360 / 414 / 768 / 1024 / 1280 px in light and dark, accessible names, phone header layout; run panel, result card and report at four widths | pass (230 passed, 6 skipped with everything installed) |
| Notebook cells end to end | `tests/test_run_scripts.py`: `Boltz_Run.py` then `analysis.py` against a fake `boltz` executable that prints real-style log lines and writes real prediction files - success, out-of-memory failure, existing job folder kept, and the IPython display path (CSS sent once, refreshes carry only the panel) | pass |
| Wheel contents | `tests/test_packaging.py` builds the wheel, checks every asset is inside, installs it to an empty directory and renders the form | pass |
| Colour contrast | `tests/ui/test_theme_contrast.py` (WCAG ratios for every text / control colour pair, light and dark) | pass |
| Visual review | screenshots of every step and state at 360 / 820 / 1280 px, light and dark, reviewed by eye | issues found and fixed (see below) |
| Lint | `ruff check boltz2nb tests scripts/common scripts/batch_utils.py tools tutorial` | clean |
| Notebook cells | `tools/check_notebooks.py` (compile + `%run` targets) | pass |
| Generated YAML vs engine schema | `tests/test_engine_schema.py` - protein+ligand+affinity, DNA/RNA multichain, PTM + CCD ligand + pocket/contact constraints, cyclic peptide, parsed by `boltz.data.parse.schema.parse_boltz_schema` with the real CCD cache | pass |
| Full pipeline, official engine | `boltz 2.2.1`, 43-aa protein + aspirin, affinity, `diffusion_samples 2`, through `scripts/v2/Boltz_Run.py` then `scripts/v2/analysis.py` | 565 s (CPU); 43 + 13 tokens mapped, interface PAE 7.2/6.2 Å, confidence 0.747/0.706, IC50 ≈ 44 µM; report + summary.json + plots written |
| Full pipeline, community engine | `boltz-community 2.10.12`, same input | analysed identically (`atomised` layout, 43 + 13 tokens, IC50 ≈ 32 µM) |
| Failure path | OOM on a 4 GB GPU | correct diagnosis ("GPU ran out of memory" + fix), `status.json` written, log preserved |
| Parameter GUI backends (v1 and v2 dialects) | callbacks driven directly with a stubbed `google.colab.output`: valid payload, bad SMILES, affinity on a protein chain, constraint referencing an unknown chain, PTM position out of range, invalid DNA alphabet, out-of-range sampling_steps, obsolete `unpaired_paired` strategy, template/MSA uploads with extension checks | all accepted/rejected as intended; `params.yaml` and `run_params.txt` correct |
| Real Colab, Python 3.13 runtime, T4 | V2 notebook, protein + ligand with affinity and MSA server | Cell 1 selected `boltz-community 2.10.12` (official wheels need < 3.13); MSA server, structure (35 s) and affinity (12 s) succeeded; analysis initially stopped on a token-layout mismatch (29 structure tokens vs 20 array entries), which is why layout resolution and the metrics-only fallback were added |

Defects the browser and visual checks found in the new interface before release: chain-ID placeholder crashed form start-up;
the Balanced preset was never recognised because the slider snapped 1.638 to 1.65; a pocket's residue box and the contact list shared a
selector so new contacts landed inside the pocket; the save-time job-name error was hidden again by the next quiet validation; the Save
button threw after a successful save; result tables overflowed on phones; the phone phase tracker misaligned. (Narrow-width checks were
first run in a 500 px window by mistake; they now use an exact-width iframe and assert the viewport.)

Not yet verified: the new interface inside a real Colab output frame (theme inheritance, Google Fonts loading, WebGL rendering of the
3-D viewer - tested only against a stub because headless Firefox here has no WebGL), the `browser-ui` GitHub Actions job, Google Drive
export in a live session, and the batch notebook on Colab. The static website and the batch notebook tables were not redesigned.
