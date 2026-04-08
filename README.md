# Boltz2-Notebook

**Streamlined Boltz2 protein and biomolecular structure prediction in Google Colab.** 

Boltz2-Notebook provides interactive Jupyter notebooks for AI-powered molecular structure prediction, enabling you to prepare inputs, run predictions, visualize results, and export outputs—all without local installation.

---

## Quick Start

### Choose Your Notebook

| Notebook | Best For | Status |
|----------|----------|--------|
| [**Latest Release**](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/Boltz2.ipynb) | General protein-ligand prediction | Current |
| [**V1 (Stable)**](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v1/Boltz2_v1.0.0.ipynb) | Core workflow, proven stability | Stable |
| [**V2 (Beta)**](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/colab/v2/Boltz2_V2.0.0_beta.ipynb) | Advanced modeling, custom MSA, DNA/RNA | Beta |
| [**Batch Processing**](https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/batch/Boltz2_Batch_v1_beta.ipynb) | Multiple predictions at once | Beta |

👉 **[View all versions and release notes →](releases/version_table.md)**

---

## Features

**Core Capabilities**
- Automatic environment setup for Colab and Linux
- GPU verification before prediction
- Flexible biomolecular input handling (proteins, ligands, DNA/RNA)
- Interactive YAML input generation
- MSA download and validation

**Results & Analysis**
- Structure prediction with confidence metrics (pLDDT, PAE)
- Interactive 3D visualization
- Protein-ligand complex analysis
- Binding affinity estimation

**Workflow**
- Google Drive integration for saving results
- ZIP export of all outputs
- Batch prediction support (local scripts available)

---

## Use Cases

- **Structure Prediction**: Predict protein-ligand and protein-protein complexes
- **Binding Analysis**: Estimate binding affinities and interaction sites
- **Visualization**: Inspect predicted structures and confidence scores
- **Batch Processing**: Automate predictions on multiple inputs locally
- **Colab Workflows**: Test biomolecular workflows in cloud notebooks

---

## Repository Structure

```
Boltz2-Notebook/
├── Boltz2.ipynb              # Main notebook (current version)
├── colab/                    # Version-specific notebooks
│   ├── v1/Boltz2_v1.0.0.ipynb
│   └── v2/Boltz2_V2.0.0_beta.ipynb
├── scripts/                  # Utility modules used by notebooks
│   ├── batch_utils.py
│   ├── v1/                   # V1 utilities (analysis.py, param_gen.py, setup.py)
│   └── v2/                   # V2 utilities (analysis.py, param_gen.py, setup.py)
├── batch/                    # Batch processing notebooks
├── notebooks/                # Additional utility notebooks
├── assets/                   # Sample data and predictions
└── releases/                 # Version history and changelog
    ├── version_table.md      # Complete version comparison
    └── CHANGELOG.md          # Release notes
```

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
