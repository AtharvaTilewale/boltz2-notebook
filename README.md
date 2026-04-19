# Boltz2 Notebook - Advanced Biomolecular Structure Prediction & Affinity Analysis

![Boltz2 Notebook Banner](https://raw.githubusercontent.com/AtharvaTilewale/boltz2-notebook/main/assets/boltz2_notebook_banner.jpeg)

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


> **Note:** Google Colab provides free GPU access (T4 GPU). For best performance, select GPU runtime: `Runtime → Change runtime type → GPU`


| Version | Features | Status | Launch |
|---------|----------|--------|------|
| **V2.0.0** | Multi-entity support, DNA/RNA, Advanced constraints, Cyclic peptides, PTMs | ![Beta](https://img.shields.io/badge/Beta-Latest-blue) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v2/Boltz2_V2.0.0_beta.ipynb) |
| **V1.0.0** | Multi-chain proteins, Protein-ligand binding, Affinity analysis | ![Stable](https://img.shields.io/badge/Stable-Mature-green) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v1/Boltz2_v1.0.0.ipynb) |
| **Batch v1.0** | Batch processing, CSV/FASTA inputs, High-throughput screening | ![Pre-release](https://img.shields.io/badge/Pre--release-Experimental-orange) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/batch/Boltz2_Batch_v1_beta.ipynb) |

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
<!-- ## Available Notebooks

| Notebook | Status | Features | Best For | Link |
|----------|--------|----------|----------|------|
| **V2.0.0** | ![Beta](https://img.shields.io/badge/Beta-Latest-blue) | Multi-entity support, Advanced constraints, Template guidance, Affinity prediction, Cyclic peptides, PTMs | Production & Research | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v2/Boltz2_V2.0.0_beta.ipynb) |
| **V1.0.0** | ![Stable](https://img.shields.io/badge/Stable-Mature-green) | Multi-chain protein prediction, Protein-ligand binding, Affinity analysis, 3D visualization | Standard predictions | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v1/Boltz2_v1.0.0.ipynb) |
| **Batch v1.0.0** | ![Pre-release](https://img.shields.io/badge/Pre--release-Experimental-orange) | Batch processing, CSV/FASTA inputs, High-throughput screening, Result ranking, Manifest validation | Large-scale screening | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/batch/Boltz2_Batch_v1_beta.ipynb)  -->


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


<!-- ---

## Overview

**Boltz2-Notebook V2.0.0** is an advanced interactive Google Colab platform for:

- **Diffusion-based protein structure prediction**
- **Protein-ligand binding affinity estimation**
- **Multi-chain complex modeling** (proteins, DNA, RNA)
- **Structure-guided design** (templates, constraints)
- **Binding pocket prediction & contact conditioning**
- **Interactive 3D visualization** with confidence metrics
- **Automated analysis** (pLDDT, PAE, affinity scoring) -->

<!-- This notebook eliminates the need for local GPU setup or command-line configuration, providing a fully guided workflow from input to publication-ready results. -->

<!-- ---

## What's New in V2.0.0?

### Advanced Input Builder
- **Multi-entity support**: Proteins, DNA, RNA, and ligands in one prediction
- **Sequence modifications**: Post-translational modifications at specific residues
- **Cyclic polymers**: Support for circular protein chains
- **Custom MSA upload**: Provide pre-computed multiple sequence alignments
- **Template guidance**: Structure-based modeling with PDB/CIF templates

### Constraint System
- **Covalent bonds**: Define custom bonds between atoms
- **Pocket conditioning**: Specify binding pockets with distance constraints
- **Contact pairs**: Force proximity between specific residue pairs
- **Affinity properties**: Mark binder chains for affinity estimation

### Enhanced Analysis
- **Hit discovery dashboard**: Binding probability visualization
- **Affinity assessment**: Predicted binding strength scoring
- **Confidence metrics**: Per-residue confidence (pLDDT, PAE)
- **Color-coded results**: Interactive 3D structure visualization
- **Automated ranking**: Top predictions by quality metrics

### Performance Improvements
- **Configurable run profiles**: Fast, balanced, scientific quality modes
- **Potentials refinement**: Physics-based energy minimization (optional)
- **Multi-sample generation**: Generate multiple conformations per job
- **GPU acceleration**: Full CUDA support for speed optimization -->

---

## Architecture & Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Setup Environment & Dependencies                    │
│ - Install Boltz2, PyTorch, CUDA support                     │
│ - Initialize workspace directories                          │
│ - Google Drive integration (optional)                       │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Input Builder (param_gen.py)                        │
│ - Define protein/DNA/RNA sequences                          │
│ - Add ligands (SMILES or CCD code)                          │
│ - Upload templates & custom MSA files                       │
│ - Define constraints (bonds, pockets, contacts)             │
│ - Generate params.yaml & run_params.txt                     │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Boltz2 Execution (Boltz_Run.py)                     │
│ - MSA generation (online or pre-computed)                   │
│ - Diffusion-based structure prediction                      │
│ - Recycling steps for refinement                            │
│ - Generate PDB/CIF models                                   │
│ - Compute confidence scores                                 │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Analysis & Visualization (analysis.py)              │
│ - Extract pLDDT (per-residue confidence)                    │
│ - Extract PAE (predicted aligned error)                     │
│ - Compute affinity predictions                              │
│ - Generate confidence plots                                 │
│ - Create interactive 3D viewer                              │
│ - Display hit discovery dashboard                           │
└─────────────────────────────────────────────────────────────┘
```

**Typical Time:** 2-10 minutes on T4 GPU (depending on complexity)

---

<!-- ## Core Scripts Reference

### 1. `param_gen.py` - Parameter Generator

**Purpose:** Converts user input (proteins, ligands, constraints) into Boltz2 YAML configuration files.

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `_build_sequences()` | Validates and formats protein/DNA/RNA/ligand sequences |
| `_save_params()` | Generates `params.yaml` with YAML structure |
| `_save_run_params()` | Creates `run_params.txt` with execution settings |
| `_save_uploaded_file()` | Handles template and MSA file uploads |
| `_clean_ids()` | Sanitizes chain IDs and entity identifiers |
| `_clean_sequence()` | Normalizes protein sequences to uppercase |

**Input Data Structure:**
```python
{
    "sequences": [
        {
            "type": "protein",
            "data": {
                "id": ["A"],
                "sequence": "MKTAYIAKQRQ...",
                "msa": "/path/to/custom.a3m",  # optional
                "modifications": [
                    {"position": 5, "ccd": "PTR"},  # phosphotyrosine at pos 5
                    {"position": 10, "ccd": "HYP"}   # hydroxyproline at pos 10
                ],
                "cyclic": True  # circular protein chain
            }
        },
        {
            "type": "ligand",
            "data": {
                "id": ["B"],
                "smiles": "CC(=O)Oc1ccccc1C(=O)O"  # Aspirin
                # OR "ccd": "HEM"  # Heme (use one, not both)
            }
        }
    ],
    "constraints": {
        "bonds": [
            {
                "chain1": "A", "res1": 50, "atom1": "SG",
                "chain2": "B", "res2": 10, "atom2": "S"  # covalent bond
            }
        ],
        "pockets": [
            {
                "binder": "A",
                "contacts": [
                    {"chain": "B", "ref": "10"},  # residue 10 in chain B
                    {"chain": "B", "ref": "ARG"}  # by name (if unique)
                ],
                "max_distance": 8.0,  # Å
                "force": False
            }
        ],
        "contacts": [
            {
                "chain1": "A", "ref1": 50,
                "chain2": "B", "ref2": 20,
                "max_distance": 5.0,
                "force": True
            }
        ]
    },
    "templates": [
        {
            "path": "/path/to/template.pdb",
            "chain_id": ["A"],
            "template_id": ["template1"],
            "force": False,
            "threshold": 0.5  # confidence cutoff
        }
    ],
    "properties": {
        "affinity_binder": "B"  # chain to compute affinity for
    }
}
```

**Output Files:**
- `params.yaml` - Boltz2 configuration file
- `run_params.txt` - Execution parameters

---

### 2. `Boltz_Run.py` - Execution Engine

**Purpose:** Runs the Boltz2 prediction pipeline with loaded parameters and generates 3D structures.

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `loader()` | Displays animated CLI loading spinner |
| `parse_value()` | Converts string parameters to Python types |
| `clean_ansi_codes()` | Removes terminal color codes from output |
| `create_visualizations()` | Extracts PDB data for 3D visualization | -->

### Execution Pipeline

1. **Parameter Loading** - Reads `run_params.txt` with job settings
2. **Directory Setup** - Creates output folder structure
3. **MSA Generation** - Fetches homologous sequences (unless pre-provided)
4. **Boltz2 Command** - Constructs and runs prediction:
   ```bash
   boltz predict params.yaml \
     --out_dir job_name \
     --recycling_steps 3 \
     --sampling_steps 200 \
     --diffusion_samples 1 \
     --step_scale 1.638 \
     --max_msa_seqs 8192 \
     --msa_pairing_strategy unpaired_paired \
     --use_msa_server
   ```
5. **Output Generation** - Creates PDB/CIF files with predictions
6. **Visualization** - Extracts data for 3D rendering

### Configuration Parameters:

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `recycling_steps` | 3 | 1-10 | Model refinement iterations |
| `sampling_steps` | 200 | 50-500 | Diffusion sampling iterations |
| `diffusion_samples` | 1 | 1-10 | Number of structure samples per job |
| `step_scale` | 1.638 | 0.5-2.0 | Scaling for diffusion steps |
| `max_msa_seqs` | 8192 | 256-8192 | Max homolog sequences |
| `msa_pairing_strategy` | unpaired_paired | paired / unpaired / greedy | MSA alignment strategy |
| `use_potentials` | False | True/False | Physics-based refinement |
| `override` | False | True/False | Re-run even if output exists |

<!-- **Success Indicators:**
- ✅ Model files generated: `{job_name}_model_0.pdb`
- ✅ Confidence scores computed
- ✅ 3D coordinates written to output

**Failure Handling:**
- Detailed error logging in HTML output
- Failed job marked as non-recoverable
- Suggestions for resolution provided -->

---

<!-- ### 3. `analysis.py` - Results Analysis & Visualization

**Purpose:** Analyzes prediction results, extracts metrics, and generates confidence dashboards.

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `parse_value()` | Converts string parameters to types |
| `get_color_shade()` | Interpolates colors based on confidence values |
| `get_prob_assessment()` | Qualitative binding probability ranking |
| `get_affinity_assessment()` | Binding strength classification |
| `create_analysis_card()` | Generates hit discovery visual card |

**Analysis Metrics Extracted:**

1. **pLDDT (Per-Residue Confidence)**
   - Range: 0-100 (higher = more confident)
   - Interpretation:
     - **90-100**: Very high confidence (reliable structure)
     - **70-90**: High confidence (reliable core)
     - **50-70**: Medium confidence (may have errors)
     - **<50**: Low confidence (unreliable)

2. **PAE (Predicted Aligned Error)**
   - Range: 0-32 Å (lower = better)
   - Measures interface prediction quality
   - Used for multi-chain complex validation

3. **Affinity Predictions**
   - **Binding Probability**: 0-1 scale (0=no binding, 1=strong binding)
   - **Affinity Value**: Energy-based prediction (negative = favorable)
   - Classification:
     - **prob > 0.75**: High confidence binder
     - **prob 0.4-0.75**: Moderate confidence binder
     - **prob < 0.4**: Low confidence / likely decoy

4. **Confidence Visualizations**
   - Donut chart: Binding probability
   - Color gradient: Per-residue pLDDT
   - Heatmap: PAE matrix
   - 3D coloring: Structure colored by pLDDT -->

<!-- **Output Visualizations:**

```
┌─────────────────────────────────────┐
│  Hit Discovery Card                 │
├─────────────────────────────────────┤
│  Binding Probability: 85%           │ ← Donut chart
│  → High Confidence Binder           │
│                                     │
│  Affinity Assessment                │
│  Pred. Value: -1.8 kcal/mol         │
│  → Good Binder                      │
│                                     │
│  Structure Quality                  │
│  Avg pLDDT: 87.5                    │
│  Max PAE: 2.3 Å                     │
└─────────────────────────────────────┘
``` -->

<!-- ---

## Input Guide - Advanced Features

### Entity Types

#### **Protein Sequences**
```yaml
protein:
  id: ["A"]
  sequence: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
  msa: /path/to/alignment.a3m        # optional pre-computed MSA
  modifications:                       # optional PTMs
    - position: 5
      ccd: "PTR"                      # phosphotyrosine
    - position: 10
      ccd: "HYP"                      # hydroxyproline
  cyclic: true                        # optional circular chain
```

#### **DNA/RNA Sequences**
```yaml
dna:
  id: ["D"]
  sequence: ATGATGATGATG               # DNA sequence

rna:
  id: ["R"]
  sequence: AUGAUGAUGAUG               # RNA sequence
```

#### **Ligands (Small Molecules)**
```yaml
# Option 1: SMILES notation
ligand:
  id: ["B"]
  smiles: "CC(=O)Oc1ccccc1C(=O)O"     # Aspirin

# Option 2: PDB CCD code
ligand:
  id: ["B"]
  ccd: "HEM"                          # Heme
```

### Constraint Types

#### **Covalent Bonds**
Specify disulfide bonds, custom linkers, or covalent modifications:
```yaml
constraints:
  - bond:
      atom1: ["A", 50, "SG"]          # chain A, residue 50, atom SG
      atom2: ["B", 10, "S"]           # chain B, residue 10, atom S
```

#### **Binding Pockets**
Define active site or binding pocket regions:
```yaml
constraints:
  - pocket:
      binder: "B"                     # ligand chain
      contacts:                       # contact residues in protein
        - ["A", 50]                   # chain A, residue 50
        - ["A", 75]
      max_distance: 8.0               # Å constraint
      force: false                    # soft vs hard constraint
```

#### **Contact Constraints**
Force proximity between specific residues:
```yaml
constraints:
  - contact:
      token1: ["A", 50]               # protein residue
      token2: ["B", 20]               # ligand residue
      max_distance: 5.0               # Å
      force: true
```

### Template-Guided Modeling

Provide a reference structure to guide prediction:
```yaml
templates:
  - pdb: /path/to/reference.pdb       # reference structure
    chain_id: ["A"]                   # which chains to use
    template_id: ["ref1"]             # identifier
    force: false                      # hard vs soft constraint
    threshold: 0.5                    # confidence cutoff
```

### Affinity Targeting

Mark which chain's affinity to compute:
```yaml
properties:
  - affinity:
      binder: "B"                     # compute affinity for chain B
``` -->

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

<!-- ---

## Parameter Tuning Guide

### For Speed (Quick Testing)
```
recycling_steps: 1
sampling_steps: 50
diffusion_samples: 1
max_msa_seqs: 256
use_potentials: False
```
⏱️ **Time:** Fast | Quality: ⭐

### For Balance (Default Production)
```
recycling_steps: 3
sampling_steps: 200
diffusion_samples: 1
max_msa_seqs: 8192
use_potentials: False
```
⏱️ **Time:** Medium | Quality: ⭐⭐⭐

### For Quality (High Accuracy)
```
recycling_steps: 5
sampling_steps: 200
diffusion_samples: 5
max_msa_seqs: 8192
use_potentials: True
```
⏱️ **Time:** Slow | Quality: ⭐⭐⭐⭐⭐

---

## Interpretation Guide

### pLDDT Color Scale
- 🔵 **90-100** (Dark Blue): Very High Confidence
- 🟦 **70-90** (Light Blue): High Confidence
- 🟨 **50-70** (Yellow): Medium Confidence
- 🟥 **<50** (Red): Low Confidence

### Binding Probability (0-1 Scale)
- **≥0.75** → ✅ High confidence binder
- **0.4-0.75** → ⚠️ Moderate confidence
- **<0.4** → ❌ Likely non-binder

### Affinity Value (kcal/mol)
- **< -2.0** → Strong binder (affinity)
- **-2.0 to -1.5** → Good binder
- **-1.5 to -1.0** → Moderate binder
- **> -1.0** → Weak binder or decoy

--- -->

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| **"CUDA out of memory"** | Sequence too long | Reduce max_msa_seqs to 256, use fast profile |
| **"MSA generation failed"** | Server/connectivity issue | Use custom MSA file instead of server |
| **"Invalid SMILES"** | Malformed ligand notation | Validate SMILES at chemspider.com |
| **"No model file found"** | Boltz2 crashed | Check output logs, verify params.yaml |
| **"pLDDT all low (<50)"** | Novel/ambiguous fold | Try template guidance if available |
| **Low affinity confidence** | Complex interface | Increase sampling_steps to 500 |

---

<!-- ## File Structure

```
V2.0.0/
├── Boltz2_V2.0.0.ipynb           # Main notebook
├── README.md                       # This file
├── scripts/
│   ├── param_gen.py               # Input builder → params.yaml
│   ├── Boltz_Run.py               # Boltz2 executor
│   ├── analysis.py                # Results analyzer & visualizer
│   ├── setup.py                   # Environment setup
│   ├── dist/                      # Distribution files
│   └── __pycache__/               # Python cache
└── New Features.txt               # V2 changelog
``` -->
<!-- 
---

## Requirements

- **Python:** 3.8+
- **GPU:** NVIDIA GPU (T4 or better recommended)
- **Runtime:** Google Colab (free) or Linux with CUDA
- **Dependencies:** PyTorch, Biopython, NumPy, Matplotlib, PyYAML, py3Dmol

--- -->

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
- **License:** MIT License — See [LICENSE](LICENSE) for details.

---

## Getting Help

- **Issues & Bugs:** [GitHub Issues](https://github.com/AtharvaTilewale/boltz2-notebook/issues)
- **Feature Requests:** [GitHub Discussions](https://github.com/AtharvaTilewale/boltz2-notebook/discussions)
- **Questions:** See the [Q&A Documentation](docs/) or open a discussion

---

**Last Updated:** April 2026 | **Version:** 2.0.0 (Latest) | **Status:** ✅ Production Ready