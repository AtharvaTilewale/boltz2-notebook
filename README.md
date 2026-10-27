<div align="center">

<img src="assets/boltz2-wordmark-horizontal-dark.svg" alt="Boltz2-Notebook" width="520">

### Biomolecular structure and binding-affinity prediction with Boltz-2, in your browser

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/Boltz2.ipynb)
[![bioRxiv](https://img.shields.io/badge/bioRxiv-10.64898%2F2026.09.18.752645-b31b1b)](https://doi.org/10.64898/2026.09.18.752645)
[![CI](https://github.com/AtharvaTilewale/boltz2-notebook/actions/workflows/ci.yml/badge.svg)](https://github.com/AtharvaTilewale/boltz2-notebook/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-5A6985)](LICENSE)
![Python 3.10 to 3.13](https://img.shields.io/badge/Python-3.10%E2%80%933.13-3B4FD6?logo=python&logoColor=white)

[Website](https://atharvatilewale.github.io/boltz2-notebook/) · [Guide](https://atharvatilewale.github.io/boltz2-notebook/docs/use-cases.html) · [FAQ](https://atharvatilewale.github.io/boltz2-notebook/docs/faq.html) · [Paper](https://doi.org/10.64898/2026.09.18.752645) · [Report an issue](https://github.com/AtharvaTilewale/boltz2-notebook/issues)

</div>

---

**Boltz2-Notebook** puts [Boltz-2](https://github.com/jwohlwend/boltz) behind a guided form in Google Colab. Describe your molecules (proteins, DNA, RNA
and small-molecule ligands), press run, and get a predicted 3-D structure with confidence scores, a binding-affinity estimate and a self-contained
report. No installation, no command line, no YAML to write. The same code also runs on your own Linux machine.

## Quick start

1. **Open the [default notebook in Colab](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/Boltz2.ipynb)** and choose *Runtime ▸ Change runtime type ▸ T4 GPU*.
2. Run **Install** and **Download model weights**, once per session (about 6 GB of model files).
3. Run **Generate Parameters**, describe your system in the form and press **Save configuration**.
4. Run **Run Boltz2 Engine** (2 to 10 minutes on a T4), then **Analyse Results** for the plots, the 3-D viewer and the HTML report.

## Choose a notebook

| Notebook | Use it for | Status | |
|:--|:--|:--|:--|
| **Advanced** (default) | Everything: proteins, DNA/RNA, ligands, templates, constraints, covalent bonds, modified residues, custom MSA | ![Stable](https://img.shields.io/badge/Stable-Default-green) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/Boltz2.ipynb) |
| **Standard** | Proteins and small-molecule ligands, with a shorter form | ![Stable](https://img.shields.io/badge/Stable-Mature-green) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v1/Boltz2_v1.0.0.ipynb) |
| **Batch** | Screening many inputs from a CSV or FASTA file, with ranking | ![Experimental](https://img.shields.io/badge/Pre--release-Experimental-orange) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/batch/Boltz2_Batch_v1_beta.ipynb) |

Not sure? Start with **Advanced**: it does everything the Standard notebook does. The Batch notebook has its own [guide](batch/README.md).

<details>
<summary><b>Feature comparison</b></summary>

| Feature | Advanced | Standard | Batch |
|:--|:--:|:--:|:--:|
| Proteins and multi-chain complexes | ✅ | ✅ | ✅ |
| Small-molecule ligands (SMILES or CCD code) | ✅ | ✅ | ✅ |
| Binding affinity | ✅ | ✅ | ✅ |
| DNA and RNA | ✅ | – | ✅ |
| Uploaded MSA (`.a3m`) | ✅ | ✅ | ✅ |
| Structural templates | ✅ | – | ✅ |
| Covalent bonds, pocket and contact constraints | ✅ | – | – |
| Modified residues, cyclic peptides | ✅ | – | – |
| Import chains and ligands from a PDB or mmCIF file | ✅ | ✅ | – |
| Many jobs from a CSV or FASTA file, with ranking | – | – | ✅ |
| 3-D viewer and HTML report per job | ✅ | ✅ | summary table |

</details>

## What you get

| Input builder | Live run panel |
|:--|:--|
| ![Input builder with a protein, a ligand with its 2-D drawing, and the live summary](assets/ui/input-builder.png) | ![Run panel with phase tracker, timer and log, while running and after a failure](assets/ui/run-panel.png) |
| **Result card** | **Run settings** |
| ![Result card with confidence scores and the binding-affinity summary](assets/ui/result-card.png) | ![Quality presets and run settings](assets/ui/run-settings.png) |

- **A guided form** that checks your input as you type: sequences, chain IDs, SMILES (with a 2-D drawing) and CCD codes, with a live summary and YAML preview.
- **Confidence scores** that are easy to read: per-residue pLDDT, the predicted aligned error (PAE) with chain-to-chain blocks, ipTM and interface summaries.
- **Binding affinity** for small-molecule ligands: the probability that the ligand binds, and the predicted IC50 in µM and nM, with pIC50 and an approximate ΔG.
- **Several samples per job** if you want them, with the spread across samples reported.
- **A self-contained HTML report** for each job: figures, the 3-D structure, tables and everything needed to reproduce the run.
- **Clear failures:** when a run fails, the notebook names the likely cause and how to fix it.
- **Light and dark themes**, and a layout that works on screens from 360 px wide.

## Reading the results

| Quantity | What it means |
|:--|:--|
| **pLDDT** (0 to 100) | Confidence per residue: above 90 very high, 70 to 90 high, 50 to 70 low, below 50 very low. Ligands and modified residues get one value per heavy atom. |
| **PAE** (Å) | Expected position error between two residues. It is asymmetric (row: aligned residue, column: scored residue); blocks between two chains show how confident the interface is. |
| **Confidence score, pTM, ipTM** | Boltz's ranking metrics. Sample 0 is the best-ranked sample. |
| **Binding probability** | How likely the ligand is a binder. Use it to separate binders from decoys. |
| **Predicted affinity** | log10 of the IC50 in µM: −2 is about 10 nM, 0 is 1 µM, 1 is 10 µM. Use it to rank close analogues, not to compare unrelated compounds. Meaningful for small molecules only. |

## Requirements

- A Google account and a **GPU runtime** in Colab (T4 or better; use an L4 or A100 for large complexes).
- About **6 GB** of model files are downloaded once per session.
- The notebook installs the engine for you: `boltz 2.2.1` on Python 3.10 to 3.12, and the `boltz-community 2.10.12` fork on Python 3.13 runtimes, where the official package is not available yet.
- Protein sequences are sent to the ColabFold MSA server to build alignments, unless you upload your own MSA or choose single-sequence mode.

## Troubleshooting

| Problem | What to do |
|:--|:--|
| **CUDA out of memory** | Lower *Max MSA sequences* (for example 256), use 1 sample, or switch to an L4 or A100 runtime. |
| **MSA server failed or timed out** | Try again later, upload an `.a3m` file, or choose single-sequence mode. |
| **Invalid SMILES or unknown CCD code** | The form checks both while you type; fix the entry it marks. |
| **A template cannot be read** | Use the template's `.cif` file, or a `.pdb` file with SEQRES records (files written by Boltz itself have none). The form warns about this when you upload. |
| **Low pLDDT everywhere** | Often a disordered region or single-sequence mode: provide an MSA or a template. |

Every failed run shows a likely cause and a fix. For an analysis that does not line up with the predicted files, run `python -m boltz2nb.doctor /content/boltz_data/<job>` and include its output in an [issue](https://github.com/AtharvaTilewale/boltz2-notebook/issues).

## Privacy

Your inputs stay in your Colab runtime, except for the MSA request (your protein sequences go to the ColabFold server), the check of CCD codes with the PDB,
and usage reports, which help improve the tool and contain no personal data. Usage reports are on by default: untick `SEND_USAGE_STATS` in the first cell to
turn them off. See [PRIVACY.md](docs/PRIVACY.md) for details.

## Run it on your own machine

<details>
<summary><b>Install and run without Colab</b></summary>

```bash
git clone https://github.com/AtharvaTilewale/boltz2-notebook && cd boltz2-notebook
pip install -e ".[ligand,viewer]" "boltz[cuda]==2.2.1"
export BOLTZ2NB_BASE_DIR=$PWD/boltz_data      # where params.yaml, run_params.txt and the results live
python - <<'PY'
from boltz2nb.yaml_builder import build_yaml, write_yaml, simple_spec
from boltz2nb.run_params import serialize_run_params, DEFAULTS
write_yaml(build_yaml(simple_spec("MKTAYIAKQRQISFVKSHFSRQLEERLGL", ligand_smiles="CC(=O)Oc1ccccc1C(=O)O", affinity=True)), "boltz_data/params.yaml")
open("boltz_data/run_params.txt", "w").write(serialize_run_params(dict(DEFAULTS, job_name="demo")))
PY
python scripts/common/Boltz_Run.py && python scripts/common/analysis.py   # the report is written to boltz_data/demo/analysis/
```

</details>

<details>
<summary><b>Run settings and their defaults</b></summary>

| Setting | Default | Range | Meaning |
|:--|:--|:--|:--|
| Recycling steps | 3 | 1 to 20 | Refinement passes of the trunk |
| Sampling steps | 200 | 10 to 1000 | Diffusion steps per sample |
| Diffusion samples | 1 | 1 to 25 | Structures per job; 3 or more give a spread estimate |
| Step scale | 1.638 | 0.5 to 5 | Lower values give more diverse samples |
| Max MSA sequences | 8192 | 1 to 16384 | Depth cap of the alignment |
| Subsample MSA | on, 1024 | | Faster and lighter on memory |
| MSA pairing | greedy | greedy, complete | How chains of a complex are paired |
| Steering potentials | off | | Physics-based potentials during sampling |

The **Fast** preset uses 2 recycling steps, 50 sampling steps and an MSA depth of 256; **Scientific** uses 5 recycling steps, 5 samples and the steering potentials.

</details>

<details>
<summary><b>How it works</b></summary>

The notebooks are thin shells. Cell 1 clones a pinned release tag of this repository and installs the `boltz2nb` package and the Boltz engine; the other
cells run three scripts that call into the package:

| Cell | Script | What it does |
|:--|:--|:--|
| Generate Parameters | `scripts/v1` or `scripts/v2/param_gen.py` | The input builder; writes `params.yaml` and `run_params.txt` |
| Run Boltz2 Engine | `scripts/common/Boltz_Run.py` | Builds the `boltz predict` command, shows live progress and the result card; never overwrites an existing job folder |
| Analyse Results | `scripts/common/analysis.py` | Maps confidence values to residues, computes interface and ensemble statistics, writes `analysis/<job>_report.html` and `summary.json` |

Each job folder also keeps `boltz.log`, `status.json` and `run_context.json` (engine, PyTorch and CUDA versions, GPU, the exact command and the input).
The package, its tests and the release process are described in [CONTRIBUTING.md](CONTRIBUTING.md).

</details>

## Documentation

- [Use cases](https://atharvatilewale.github.io/boltz2-notebook/docs/use-cases.html) and [FAQ](https://atharvatilewale.github.io/boltz2-notebook/docs/faq.html) on the website
- [Batch guide](batch/README.md): high-throughput screens from CSV or FASTA
- [Changelog](releases/CHANGELOG.md) and [version table](releases/version_table.md)
- [Privacy](docs/PRIVACY.md) and, for maintainers, [receiving usage reports](docs/TELEMETRY.md)
- [Contributing](CONTRIBUTING.md) and the [verification log](docs/VERIFICATION.md)

## Citation

If Boltz2-Notebook helps your work, please cite the preprint, and Boltz-2 for the model:

```bibtex
@article{Tilewale2026.09.18.752645,
  author    = {Tilewale, Atharva and Patel, Dhaval},
  title     = {Boltz2-Notebook: An Interactive Google Colab Platform for Diffusion-Based
               Biomolecular Structure and Binding Affinity Prediction using the Boltz2 model},
  journal   = {bioRxiv},
  year      = {2026},
  doi       = {10.64898/2026.09.18.752645},
  url       = {https://www.biorxiv.org/content/early/2026/09/24/2026.09.18.752645},
  publisher = {Cold Spring Harbor Laboratory}
}

@article{Passaro2025,
  author  = {Passaro, Saro and Corso, Gabriele and Wohlwend, Jeremy and others},
  title   = {Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction},
  journal = {bioRxiv},
  year    = {2025},
  doi     = {10.1101/2025.06.14.659707}
}

@article{Wohlwend2024,
  author  = {Wohlwend, Jeremy and Corso, Gabriele and Passaro, Saro and others},
  title   = {Boltz-1: Democratizing Biomolecular Interaction Modeling},
  journal = {bioRxiv},
  year    = {2024},
  doi     = {10.1101/2024.11.19.624167}
}
```

## Authors and acknowledgements

Developed by [Atharva Tilewale](https://github.com/AtharvaTilewale) and Dr. Dhaval Patel at Gujarat Biotechnology University.
Built on [Boltz](https://github.com/jwohlwend/boltz) by Wohlwend, Corso, Passaro and colleagues, and on [boltz-community](https://github.com/Novel-Therapeutics/boltz-community) for Python 3.13 runtimes.
Alignments come from the [ColabFold](https://github.com/sokrypton/ColabFold) MSA server.

Questions and ideas are welcome in [Discussions](https://github.com/AtharvaTilewale/boltz2-notebook/discussions); bugs go to [Issues](https://github.com/AtharvaTilewale/boltz2-notebook/issues).
Released under the [MIT License](LICENSE).

---

**Version:** 2.1.2 · [Changelog](releases/CHANGELOG.md)
