# Boltz2 Notebook - Advanced Biomolecular Structure Prediction & Affinity Analysis

Boltz2-Notebook provides interactive Jupyter notebooks for AI-powered molecular structure prediction, enabling you to prepare inputs, run predictions, visualize results, and export outputs—all without local installation.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python)
![CUDA](https://img.shields.io/badge/CUDA-Enabled-green?logo=nvidia)
![Boltz2](https://img.shields.io/badge/Model-Boltz2-purple)
![Platform](https://img.shields.io/badge/Platform-Colab%20|%20Linux-lightgrey?logo=googlecolab)
![License](https://img.shields.io/badge/License-MIT-orange)
![Status](https://img.shields.io/badge/Status-Active-success)

</div>

---

## Available Notebooks

| Notebook | Status | Features | Best For | Link |
|----------|--------|----------|----------|------|
| **V2.0.0** | ![Beta](https://img.shields.io/badge/Beta-Latest-blue) | Multi-entity support, Advanced constraints, Template guidance, Affinity prediction, Cyclic peptides, PTMs | Production & Research | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v2/Boltz2_V2.0.0_beta.ipynb) |
| **V1.0.0** | ![Stable](https://img.shields.io/badge/Stable-Mature-green) | Multi-chain protein prediction, Protein-ligand binding, Affinity analysis, 3D visualization | Standard predictions | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v1/Boltz2_v1.0.0.ipynb) |
| **Batch v1.0.0** | ![Pre-release](https://img.shields.io/badge/Pre--release-Experimental-orange) | Batch processing, CSV/FASTA inputs, High-throughput screening, Result ranking, Manifest validation | Large-scale screening | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/batch/Boltz2_Batch_v1_beta.ipynb) 

### Feature Comparison

| Feature | V1.0.0 | V2.0.0 | Batch |
|---------|--------|--------|-------|
| Single protein prediction | ✅ | ✅ | ✅ |
| Protein-ligand binding | ✅ | ✅ | ✅ |
| Multi-chain complexes | ✅ | ✅ | ❌ |
| DNA/RNA support | ❌ | ✅ | ❌ |
| Template guidance | ✅ | ✅ | ✅ |
| Cyclic peptides | ❌ | ✅ | ❌ |
| MSA upload | ❌ | ✅ | ❌ |
| Modified residues | ❌ | ✅ | ❌ |
| Custom constraints | ❌ | ✅ | ❌ |
| Covalent bonds | ❌ | ✅ | ❌ |
| Affinity prediction | ✅ | ✅ | ✅ |
| PTM support | ❌ | ✅ | ❌ |
| Batch processing | ❌ | ❌ | ✅ |
| CSV input | ❌ | ❌ | ✅ |
| 3D visualization | ✅ | ✅ | ✅ |

### Notebook Selection Guide

- **Standard research?** → Use **V1.0.0** (protein-ligand, templates)
- **Advanced needs?** → Use **V2.0.0** (latest, multi-entity, constraints)
- **Large-scale screening?** → Use **Batch v1.0.0** (high-throughput)

---

## Quick Start - Open in Google Colab

Click the button below to launch the latest Boltz2 Notebook in Google Colab:

**Boltz2-Notebook V2.0.0**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v2/Boltz2_V2.0.0_beta.ipynb)

> **Note:** Google Colab provides free GPU access (T4 GPU). For best performance, select GPU runtime: `Runtime → Change runtime type → GPU`

---

## Overview

**Boltz2-Notebook V2.0.0** is an advanced interactive Google Colab platform for:

- **Diffusion-based protein structure prediction**
- **Protein-ligand binding affinity estimation**
- **Multi-chain complex modeling** (proteins, DNA, RNA)
- **Structure-guided design** (templates, constraints)
- **Binding pocket prediction & contact conditioning**
- **Interactive 3D visualization** with confidence metrics
- **Automated analysis** (pLDDT, PAE, affinity scoring)

This notebook eliminates the need for local GPU setup or command-line configuration, providing a fully guided workflow from input to publication-ready results.

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

---

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
```

---

## Usage Examples

### Example 1: Simple Protein Prediction (Apo Structure)

**Input:** Single protein sequence only
```
Sequence: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
Expected time: 2-5 minutes on T4 GPU
Output: PDB file + confidence plots
```

**Steps:**
1. Fill protein sequence field
2. Run param_gen (Step 2)
3. Run Boltz_Run (Step 3)
4. View results in analysis (Step 4)

---

### Example 2: Protein-Ligand Complex with Affinity

**Input:**
- Protein: Kinase sequence
- Ligand: Drug molecule (SMILES)
- Affinity target: Kinase chain

**Configuration:**
```
Protein: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
Ligand SMILES: CC(=O)Oc1ccccc1C(=O)O
Ligand Chain: B
Binder (for affinity): B
```

**Expected Output:**
- Complex structure (protein + ligand)
- Binding pocket visualization
- Affinity score + probability
- Hit discovery dashboard

---

### Example 3: Template-Guided Variant Modeling

**Input:**
- Parent protein sequence (known structure)
- Variant sequence (mutations)
- Template: PDB file of parent

**Configuration:**
```
Template: parent_structure.pdb
Template Chain: A
Protein Sequence: [parent with specific mutations]
```

**Benefit:** Faster convergence, higher confidence in conserved regions

**Time:** Faster than ab initio prediction

---

### Example 4: Multi-Chain Complex (Antibody-Antigen)

**Input:**
```
Chain A: Antibody light chain (120 residues)
Chain B: Antibody heavy chain (150 residues)
Chain C: Antigen protein (300 residues)
```

**Configuration:**
- Define 3 protein entities
- Specify contact constraints (antibody-antigen interface)
- Run prediction

**Output:**
- Full complex structure
- Interface pLDDT/PAE
- Contact residues highlighted


---

### Example 5: Post-Translational Modifications

**Input:**
```
Protein: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
Modifications:
  - Position 5: Phosphotyrosine (PTR)
  - Position 10: Hydroxyproline (HYP)
```

**Expected:** Structure with PTMs properly modeled in local geometry

---

### Example 6: Cyclic Peptide Prediction

**Input:**
```
Sequence: ACDEFGHIKLMNPQRSTVWY
Cyclic: True
```

**Effect:** Treats C-terminus connected to N-terminus for cyclic constraint

---

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

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| **"CUDA out of memory"** | Sequence too long | Reduce max_msa_seqs to 256, use fast profile |
| **"MSA generation failed"** | Internet/server issue | Use custom MSA file instead of server |
| **"Invalid SMILES"** | Bad ligand format | Validate SMILES at chemspider.com |
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

## Citation

If you use this notebook, please cite:

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

## Credits

- **Notebook Developer:** Atharva Tilewale & Dr. Dhaval Patel
- **Institution:** Gujarat Biotechnology University
- **GitHub:** [boltz2-notebook](https://github.com/AtharvaTilewale/boltz2-notebook)
- **Boltz2 Authors:** [Original Repository](https://github.com/jwohlwend/boltz)

---

## Version History & Changelog

For detailed feature comparisons and release notes:
- **[Version Table](releases/version_table.md)** — Quick feature comparison
- **[Changelog](releases/CHANGELOG.md)** — Complete release history

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

## Support & Contribution

For issues, feature requests, or contributions, please refer to the GitHub repository issues and discussions.

---

**Last Updated:** April 2026  
**Version:** 2.0.0  
**Status:** ✅ Production Ready
