# Changelog

## v2.1.0 (unreleased)

### Fixed
- **PAE heat-maps were wrong.** The per-chain PAE plot drew `P + P.T - diag(P)`, which roughly doubles every
  off-diagonal value (the shipped example differs from its transpose by up to 24 Å). PAE is now plotted
  as the asymmetric matrix Boltz writes, on a fixed 0-32 Å scale, for the full complex with chain boundaries.
- **Affinity units.** `affinity_pred_value` is log10(IC50 in µM), not kcal/mol. Reports now show
  log10 IC50, IC50 in nM/µM, pIC50, an approximate ΔG, and consistent potency classes
  (the old code used `< -2 / < -1.5 / < 1` while the README said `< -1.0`).
- **Token ↔ residue mapping.** Modified residues (PTMs) and ligands are tokenised per heavy atom by Boltz;
  the previous residue-counting mapping shifted every pLDDT/PAE index after a PTM. Token layout is now
  derived from the written structure and checked against the NPZ length.
- `msa_pairing_strategy` default `unpaired_paired` was not a Boltz-2 option (`greedy`/`complete` only).
- Runner defaults (`step_scale 10.0`, `max_msa_seqs 254`, `sampling_steps 50`) disagreed with the docs; one
  `DEFAULTS` table is now shared by the GUI, the runner and the batch engine.
- `subsample_msa` / `num_subsampled_msa` from the GUI were silently ignored; they are passed through.
- The `--output_format cif` choice in the batch notebook (invalid for Boltz) is normalised to `mmcif`.
- Python 3.13 Colab runtimes: official `boltz` wheels require `<3.13`; the installer now selects
  `boltz-community` on 3.13+ automatically instead of failing.
- Results folders and Drive folders are no longer deleted before a run; a timestamp suffix is used.
- Removed the `sed`/`shell=True` YAML rewrite; the builder emits plain scalars.
- `batch/README.md` linked to `Batch/` (wrong case) and non-existent files.

### Changed (privacy)
- Removed the hidden telemetry that authenticated the Colab user with Google OAuth and posted their
  e-mail address and name to a Google Apps Script endpoint (XOR-obfuscated URL in v1).
  Usage statistics are now **opt-in** (`SEND_USAGE_STATS` in Cell 1), anonymous (version strings and a
  random session id only) and documented in `docs/PRIVACY.md`.

### Added
- Token-layout resolution: the convention used by the confidence arrays is matched against the
  structure (`atomised`, `atomised_std`, `atomised_all`, `residue`) instead of assumed, so output
  from the community fork and future engine versions is handled. If nothing matches, the report is
  still produced from the ranking metrics and affinity, with the per-token section marked unavailable
  instead of the analysis failing (found by a real Colab run on `boltz-community 2.10.12`).
- `python -m boltz2nb.doctor <job dir>` prints engine version, array lengths, per-convention token
  counts and the matching layout - enough to diagnose an output mismatch without sharing sequences.
- Affinity files are discovered as `affinity_<job>*.json`, covering the community fork's per-binder
  naming (`affinity_<job>_<chain>.json`).
- `boltz2nb` Python package: all logic moved out of the notebooks into testable modules
  (`yaml_builder`, `run_params`, `runner`, `tokens`, `analysis`, `report`, `batch`, `diagnostics`,
  `msa_cache`, `ligand`, `telemetry`, `install`). 40+ unit tests, GitHub Actions CI on Python 3.10-3.13,
  plus optional tests that validate generated YAML with Boltz's own schema parser.
- Pinned engine (`boltz[cuda]==2.2.1` / `boltz-community[cuda]==2.10.12`) and pinned notebook code
  (`NOTEBOOK_VERSION` tag in Cell 1 with fallback to `main`).
- Live streaming of the Boltz log during a run; failure diagnostics with a likely cause and a fix.
- `run_context.json` provenance (engine/torch/CUDA versions, GPU, full command, input YAML + SHA-1) per job.
- Ensemble statistics across diffusion samples (mean ± SD of confidence, ipTM, pLDDT, interface PAE,
  affinity ensemble-member spread) and a per-sample table in the result card.
- Inter-chain PAE summary for complexes.
- Standalone HTML report per job (`analysis/<job>_report.html`) with embedded figures, 3-D viewer,
  metrics tables and provenance; `summary.json` alongside.
- RDKit SMILES validation and 2-D depiction with basic properties in the parameter step and report.
- Optional Drive-backed MSA cache keyed by sequence hash (`USE_DRIVE_MSA_CACHE`).
- Batch mode: multi-chain proteins, `dna_sequence` / `rna_sequence` / `affinity` CSV columns,
  ensemble metrics and interface PAE in the summary, `metric="auto"` ranking.
- Input validation in the builder: alphabets per polymer type, duplicate chain IDs, constraint/template
  references to unknown chains, affinity binder must be a ligand, PTM positions within the chain.
- The scripts run outside Colab (`BOLTZ2NB_BASE_DIR`, guarded `google.colab` imports).

## v2.0.0
- Advanced Modeling panel
- Template upload for .cif / .pdb
- Explicit template chain mapping
- Covalent ligand bond builder
- Pocket conditioning builder
- Contact conditioning builder
- Modified residue editor
- Custom/precomputed MSA upload
- Single-sequence mode warning for msa: empty
- DNA/RNA chain support
- Cyclic polymer toggle
- YAML writer now supports protein, dna, rna, ligand, constraints, templates, and advanced properties

## v1.0.0
- Initial public notebook release
- Basic protein-ligand prediction
- Affinity prediction workflow
- Visualization of predicted structures and interactions
- G-Drive integration for saving and sharing results
- Zip file export of all outputs for easy download and local analysis
