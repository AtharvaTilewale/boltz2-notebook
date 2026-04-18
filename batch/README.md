# Boltz2 Batch Notebook - User Guide

## Overview

The **Boltz2 Batch Notebook** is a comprehensive tool for running batch protein structure predictions using the Boltz2 AI model. It automates the processing of multiple protein sequences, ligands, and templates in a streamlined 7-step workflow.

This notebook is designed for:
- High-throughput protein structure prediction
- Protein-ligand binding predictions
- Template-guided structure modeling
- Large-scale screening and analysis

---

## Key Features

### 1. **Environment Setup & Workspace Bootstrap**
- Automatic installation of all dependencies (Boltz2, PyTorch, CUDA support)
- Optional Google Drive integration for persistent storage
- Workspace initialization with organized folder structure
- CUDA/GPU detection and configuration

### 2. **Flexible Input Handling**
The notebook supports **4 input modes**:
- **CSV Mode** - Tabular format (one row = one job)
- **FASTA Mode** - Protein sequence files
- **YAML ZIP Mode** - Compressed archive of YAML job files
- **YAML Folder Mode** - Directory with pre-uploaded YAML files

### 3. **Intelligent Manifest Builder**
- Validates input data structure
- Supports multi-chain protein sequences (separated by `:`)
- Handles optional ligands (SMILES or CCD code)
- Manages MSA settings and template files
- Auto-resolves file paths from runtime or Drive storage

### 4. **Pre-Flight Validation & Configuration**
- Validates all job specifications before execution
- Configurable run profiles:
  - **Fast** - Quick sanity checks (fewer recycling steps)
  - **Balanced** - Default trade-off between speed and quality
  - **Scientific** - High-quality production runs
- Output format selection (PDB, MMCIF, or CIF)
- Job filtering options (skip completed, retry failed)

### 5. **Batch Execution Engine**
- Launch new batch runs or resume interrupted sessions
- Live progress tracking and verbose updates
- Automatic job queuing and dependency management
- Support for GPU acceleration

### 6. **Results Analysis & Visualization**
- **Summarize Results** - Generate ranking by quality metrics
- **Interactive 3D Viewer** - Browse structures with PyMol visualization
- **Log Inspection** - Detailed failure diagnostics and troubleshooting
- **Metrics Support**: Affinity probability, confidence scores, pLDDT, pAE, pTM

### 7. **Export & Archival**
- Package all predictions, logs, and manifests into single ZIP
- Automatic Drive export (when configured)
- One-click download of complete run artifacts
- Preserves full audit trail

---

## Input Format Reference

### CSV Mode (Recommended for Users)

**Required Columns:**
| Column | Description | Example |
|--------|-------------|---------|
| `job_name` | Unique identifier for the job | `protein_001` |
| `protein_sequence` | Protein sequence in 1-letter code | `MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ` |

**Optional Columns:**
| Column | Description | Example | Notes |
|--------|-------------|---------|-------|
| `ligand_smiles` | Small molecule SMILES string | `CC(=O)Oc1ccccc1C(=O)O` | Use for small molecules |
| `ligand_ccd` | CCD code from PDB | `HEM` | Alternative to SMILES |
| `binder` | Ligand chain ID | `B` | Required if ligand is provided |
| `protein_id` | Custom protein identifier | `P123` | Optional metadata |
| `ligand_id` | Custom ligand identifier | `L456` | Optional metadata |
| `msa_mode` | MSA strategy | `server` or `none` | Default: `server` |
| `msa_path` | Path to MSA file | `/path/to/msa.a3m` | A3M format |
| `template_file` | Structure template file | `/path/to/template.pdb` | PDB, CIF, or MMCIF |
| `template_chain_id` | Chain to use from template | `A` | If template has multiple chains |
| `template_id` | Custom template identifier | `T789` | Optional |
| `notes` | User notes | `High priority screening` | Optional metadata |

**Example CSV:**
```csv
job_name,protein_sequence,ligand_smiles,binder,msa_mode
apo_1,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,,,server
holo_2,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,CC(=O)Oc1ccccc1C(=O)O,B,server
```

### FASTA Mode

- One sequence per entry (header text after `>` becomes job_name)
- Multi-chain proteins: separate chains with `:` in sequence
- No ligand support in this mode

**Example FASTA:**
```fasta
>protein_001
MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
>protein_002:chain_extension
MKTAYIAKQRQISFVK:SHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
```

### YAML Mode

Each YAML file represents one job with full specification:
```yaml
job_name: my_job
protein_sequence: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
ligand_smiles: CC(=O)Oc1ccccc1C(=O)O
binder: B
msa_mode: server
template_file: /path/to/template.pdb
template_chain_id: A
```

---

## Usage Examples

### Example 1: Protein-Only Prediction (Simplest)

**Input CSV:**
```csv
job_name,protein_sequence
kinase_1,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
kinase_2,MAGQIRTSEVNGLTLLLMEHFSNLG...
enzyme_3,MAFGTDDDQN...
```

**Steps:**
1. Run Step 1: Environment setup
2. Run Step 2: Load CSV file → Select `INPUT_MODE = "csv"`
3. Run Step 3: Choose `RUN_PROFILE = "fast"` for testing
4. Run Step 4: Launch batch
5. Run Step 5: View ranked results
6. Run Step 6A: Visualize structures
7. Run Step 7: Export as ZIP

---

### Example 2: Protein-Ligand Binding (Hit Discovery)

**Input CSV:**
```csv
job_name,protein_sequence,ligand_smiles,binder
target_bound_1,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,CC(=O)Oc1ccccc1C(=O)O,B
target_bound_2,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,CN1C=NC2=C1C(=O)N(C(=O)N2C)C,B
target_bound_3,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,Cc1ccc(S(=O)(=O)N)cc1,B
```

**Configuration:**
- Step 3: Set `RUN_PROFILE = "scientific"` for quality predictions
- Step 3: `RANK_METRIC = "affinity_probability_binary"` for hit ranking
- Step 5: Filter by `affinity_pred_value` to identify top binders

**Output:** Ranked list of best-binding compounds with predicted affinities

---

### Example 3: Template-Guided Modeling

**Prepare files:**
- `template_protein.pdb` - Reference structure
- Template folder: `/inputs/templates/`

**Input CSV:**
```csv
job_name,protein_sequence,template_file,template_chain_id
variant_1,MKTAYIAKQRQIS[variant_region]FVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,template_protein.pdb,A
variant_2,MKTAYIAKQRQIS[different_variant]FVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ,template_protein.pdb,A
```

**Process:**
1. Upload template file in Step 2
2. Select template path in CSV
3. Run with `RUN_PROFILE = "balanced"`
4. Compare predicted variants to parent structure

---

### Example 4: Multi-Chain Complex Prediction

**Input CSV:**
```csv
job_name,protein_sequence
antibody_complex,MKTAYIAKQRQISFVK:SHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
dimer,MKTAYIAKQRQ:ISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQ
```

Where `:` separates different protein chains in the complex.

**Output:** Predicted structure of multi-chain assemblies with interface predictions

---

### Example 5: Large-Scale Screening (100+ proteins)

**Setup:**
- Prepare `proteins_all.csv` with 1000 sequences
- Step 3: `RUN_PROFILE = "fast"` for efficiency
- Step 4: `MAX_JOBS_THIS_SESSION = 100` (resume later if needed)

**Workflow:**
```
Session 1: Process first 100
→ Step 4 with MAX_JOBS = 100
→ Check results in Step 5

Session 2: Resume remaining 900
→ Step 4 with RUN_MODE = "resume"
→ Automatic continuation
```

**Ranking:** 
- Step 5: `RANK_METRIC = "confidence_score"` for quality filtering
- Export top 50 for experimental validation

---

## Run Profiles Explained

| Profile | Use Case | Recycling Steps | Sampling Steps | Speed | Quality |
|---------|----------|-----------------|----------------|-------|---------|
| **Fast** | Pipeline testing, sanity checks | 2 | 100 | ⚡⚡⚡ | ⭐ |
| **Balanced** | General production use (default) | 3 | 250 | ⚡⚡ | ⭐⭐⭐ |
| **Scientific** | High-accuracy research runs | 5 | 500+ | ⚡ | ⭐⭐⭐⭐⭐ |

---

## Output Metrics & Ranking

**Available Ranking Metrics:**

| Metric | Meaning | Higher is Better |
|--------|---------|------------------|
| `confidence_score` | Overall prediction confidence | Yes |
| `iptm` | Interface prediction TM-score | Yes |
| `complex_plddt` | Complex pLDDT (confidence per residue) | Yes |
| `ptm` | PAE-TM score | Yes |
| `affinity_pred_value` | Predicted binding affinity | Depends* |
| `affinity_probability_binary` | Probability of binding (0-1) | Yes |
| `complex_pde` | Complex PAE score | No |

*Lower affinity values may indicate better binding depending on energy units

## Outputs

After or during a run, the notebook can generate the following key files.

| File | Purpose |
|---|---|
| `manifests/*.csv` | Batch job registry and state |
| `jobs/job_*/status.json` | Per-job execution metadata |
| `jobs/job_*/stdout.log` | Standard output log |
| `jobs/job_*/stderr.log` | Standard error log |
| `summaries/validation_report.csv` | Structural validation results |
| `summaries/preflight_report.csv` | Readiness and warning report |
| `summaries/batch_results_summary.csv` | Final summarized results |
| `summaries/failure_diagnostics.csv` | Suggested failure causes and fixes |
| `run_context.json` | Captured environment and run parameters |
| `exports/*.zip` | Portable archive of the run |

---

## Troubleshooting

### Job Failed - How to Debug?

**Step 6B - Inspect Logs:**
1. Run Step 6B with the failed `JOB_NAME`
2. Check "Likely cause" and "Suggested fix"
3. View full STDOUT/STDERR logs

**Common Issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid protein sequence` | Unknown amino acids | Use standard 20 AAs (ACDEFGHIKLMNPQRSTVWY) |
| `SMILES parsing failed` | Bad ligand SMILES string | Validate SMILES at chemspider.com |
| `Template not found` | Wrong template file path | Use absolute paths or upload to templates folder |
| `CUDA out of memory` | Sequence too long | Use `RUN_PROFILE = "fast"` or split sequences |
| `MSA generation timeout` | Server unavailable | Set `msa_mode = "none"` or try later |

### Resume a Failed Session?

```
Step 4:
- Set RUN_MODE = "resume"
- Set RETRY_FAILED = True (in Step 3)
```

---

## Tips for Best Results

1. **Start with Fast Profile**
   - Validate your input first with `RUN_PROFILE = "fast"`
   - Then scale to "scientific" for production

2. **Use Meaningful Job Names**
   - Helps with filtering and reporting
   - Include compound IDs or variant names

3. **Leverage Templates**
   - If you have similar structures, use templates
   - Improves speed and accuracy

4. **Monitor GPU Memory**
   - Watch CUDA usage in Step 1 output
   - Reduce batch size if hitting memory limits

5. **Export Frequently**
   - Run Step 7 periodically to backup results
   - Keeps audit trail of predictions

---

## File Structure

```
Batch/
├── Boltz2_Batch_v1_beta.ipynb    (Main notebook)
├── Boltz2_Batch_v1.ipynb         (Stable version)
├── README.md                       (This file)
└── scripts/
    └── batch_utils.py             (Helper functions)
```

---

<!-- ## Requirements

- Python 3.8+
- PyTorch with CUDA support (recommended)
- 16+ GB RAM (32+ GB for scientific profile)
- Google Colab OR local GPU (highly recommended)

--- -->

## Support & Resources

- **Input Validation:** See Step 2 for manifest validation
- **Run Parameters:** See Step 3 configuration options
- **Results Export:** See Step 7 for downloading ZIP archives

For issues or feature requests, check the notebook's built-in help cells marked with `#@markdown ### Step X Help`.

---

## Version History

- **v1.0.0-beta** - Initial batch processing with 7-step workflow
- Supports: CSV, FASTA, YAML inputs
- Features: GPU acceleration, live progress, result ranking, 3D visualization

---

**Last Updated:** April 2026  
**Notebook Version:** v1.0-beta
