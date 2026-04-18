# Boltz2-Notebook

**AI-powered biomolecular structure prediction and binding affinity analysis** — Interactive Jupyter notebooks for protein structure prediction, protein-ligand binding, and multi-entity complex modeling using the Boltz2 diffusion model. No local GPU installation required.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python)
![CUDA](https://img.shields.io/badge/CUDA-Enabled-green?logo=nvidia)
![Boltz2](https://img.shields.io/badge/Model-Boltz2-purple)
![Platform](https://img.shields.io/badge/Platform-Colab%20|%20Linux-lightgrey?logo=googlecolab)
![License](https://img.shields.io/badge/License-MIT-orange)
![Status](https://img.shields.io/badge/Status-Production-success)

</div>

---

## Quick Start

**Launch in Google Colab (Free GPU):**

| Version | Features | Status | Link |
|---------|----------|--------|------|
| **V2.0.0** | Multi-entity support, DNA/RNA, Advanced constraints, Cyclic peptides, PTMs | Latest | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v2/Boltz2_V2.0.0_beta.ipynb) |
| **V1.0.0** | Multi-chain proteins, Protein-ligand binding, Affinity analysis | Stable | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v1/Boltz2_v1.0.0.ipynb) |
| **Batch v1.0** | Batch processing, CSV/FASTA inputs, High-throughput screening | Experimental | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/batch/Boltz2_Batch_v1_beta.ipynb) |

---

## Key Features

- **Protein Structure Prediction** — Diffusion-based AI modeling for single proteins and multi-chain complexes
- **Protein-Ligand Binding** — Predict and score molecular interactions with affinity estimation
- **Multi-Entity Support** — Handle proteins, DNA/RNA, ligands, and custom modifications simultaneously
- **Advanced Constraints** — Covalent bonds, binding pocket conditioning, contact constraints, template guidance
- **Confidence Metrics** — Per-residue confidence (pLDDT), Predicted Aligned Error (PAE), affinity predictions
- **Interactive Visualization** — 3D structure viewer with confidence overlays and binding analysis dashboard
- **GPU Acceleration** — CUDA-enabled with free T4 GPU access in Google Colab
- **Zero Installation** — Runs entirely in Google Colab (no local GPU setup required)

---

## Feature Comparison

| Feature | V1.0.0 | V2.0.0 | Batch |
|---------|:------:|:------:|:-----:|
| Single protein prediction | ✅ | ✅ | ✅ |
| Protein-ligand binding | ✅ | ✅ | ✅ |
| Multi-chain complexes | ✅ | ✅ | ❌ |
| DNA/RNA support | ❌ | ✅ | ❌ |
| Template guidance | ✅ | ✅ | ✅ |
| Custom MSA upload | ❌ | ✅ | ❌ |
| Post-translational modifications | ❌ | ✅ | ❌ |
| Custom constraints | ❌ | ✅ | ❌ |
| Covalent bonds | ❌ | ✅ | ❌ |
| Cyclic peptides | ❌ | ✅ | ❌ |
| Affinity prediction | ✅ | ✅ | ✅ |
| Batch processing | ❌ | ❌ | ✅ |
| CSV/FASTA input | ❌ | ❌ | ✅ |
| 3D visualization | ✅ | ✅ | ✅ |

### Notebook Selection Guide

- **New users or standard predictions?** → Use **V1.0.0** (stable, battle-tested)
- **Advanced modeling needs?** → Use **V2.0.0** (latest features, DNA/RNA, constraints)
- **Large-scale screening?** → Use **Batch v1.0** (automated high-throughput)

---

## Available Notebooks

| Notebook | Status | Best For |
|----------|--------|----------|
| [V2.0.0](colab/v2/Boltz2_V2.0.0_beta.ipynb) | ![Beta](https://img.shields.io/badge/Beta-Latest-blue) | Advanced modeling, multi-entity complexes, structure-guided design |
| [V1.0.0](colab/v1/Boltz2_v1.0.0.ipynb) | ![Stable](https://img.shields.io/badge/Stable-Proven-green) | Production predictions, protein-ligand binding, standard analysis |
| [Batch v1.0](batch/Boltz2_Batch_v1_beta.ipynb) | ![Pre-release](https://img.shields.io/badge/Pre--release-Early-orange) | High-throughput screening, batch processing, automation |
| [Parameter Generator](notebooks/Boltz2_paramgen.ipynb) | Utility | Custom configuration and input building |

---

## Workflow

```
Input Definition → Parameter Generation → Structure Prediction → Analysis & Visualization
   (Sequences         (params.yaml +        (MSA generation +     (pLDDT, PAE,
    Ligands,          run_params.txt)       Boltz2 diffusion)      Affinity scoring)
    Constraints)
```

**Typical Time:** 2-10 minutes on T4 GPU (depending on complexity)

---

## Usage Examples

### Basic Protein Structure
```
Input: Single protein sequence
Output: PDB file + confidence metrics
Time: ~2-5 min
```

### Protein-Ligand Complex with Affinity
```
Input: Protein sequence + ligand SMILES
Output: Complex structure + binding affinity + hit discovery dashboard
Time: ~3-7 min
```

### Multi-Chain Complex (e.g., Antibody-Antigen)
```
Input: 2-3 protein sequences
Output: Full complex structure + interface metrics (PAE, pLDDT)
Time: ~5-10 min
```

### Template-Guided Modeling
```
Input: Protein variant + reference PDB template
Output: Faster convergence + higher confidence in conserved regions
Time: ~2-5 min
```

---

## Advanced Features (V2.0.0+)

### Supported Entity Types
- **Proteins** — Standard amino acids + post-translational modifications (PTMs)
- **DNA/RNA** — Nucleic acid sequences
- **Ligands** — SMILES notation or PDB CCD codes
- **Cyclic Chains** — N- and C-terminus covalently linked

### Constraint Types
- **Covalent Bonds** — Custom disulfide bonds or linkers
- **Binding Pockets** — Distance constraints on active sites
- **Contact Constraints** — Force proximity between residue pairs
- **Template Guidance** — Structure-based modeling with PDB/CIF references

### Affinity Predictions
- Binding probability (0-1 scale)
- Predicted binding affinity (kcal/mol)
- Hit discovery ranking dashboard

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| **CUDA out of memory** | Sequence too long | Reduce `max_msa_seqs` to 256 or use fast profile |
| **MSA generation failed** | Server/connectivity issue | Use custom MSA file instead of online server |
| **Invalid SMILES** | Malformed ligand notation | Validate SMILES syntax at ChemSpider |
| **Low pLDDT throughout** | Novel/ambiguous structure | Try template guidance or increase recycling steps |
| **Model file not generated** | Boltz2 execution error | Check output logs and verify params.yaml |

---

## Documentation

- **[Version Table](releases/version_table.md)** — Feature comparison across releases
- **[Changelog](releases/CHANGELOG.md)** — Complete release history
- **[Batch README](batch/README.md)** — High-throughput batch processing guide

---

## Citation

If you use Boltz2-Notebook, please cite:

```bibtex
@article{Passaro2025,
  title={Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction},
  author={Passaro, S. and Corso, G. and Wohlwend, J. and others},
  journal={bioRxiv},
  year={2025}
}

@article{Wohlwend2024,
  title={Boltz-1: Democratizing Biomolecular Interaction Modeling},
  author={Wohlwend, J. and Corso, G. and Passaro, S. and others},
  journal={bioRxiv},
  year={2024}
}
```

---

## Credits & Links

- **Notebook:** [Atharva Tilewale](https://github.com/AtharvaTilewale) & Dr. Dhaval Patel (Gujarat Biotechnology University)
- **Boltz2 Model:** [Original Repository](https://github.com/jwohlwend/boltz)
- **License:** MIT

---

## Getting Help

- **Issues & Bugs:** [GitHub Issues](https://github.com/AtharvaTilewale/boltz2-notebook/issues)
- **Feature Requests:** [GitHub Discussions](https://github.com/AtharvaTilewale/boltz2-notebook/discussions)
- **Questions:** See the [Q&A Documentation](docs/) or open a discussion

---

**Last Updated:** April 2026 | **Version:** 2.0.0 | **Status:** ✅ Production Ready
