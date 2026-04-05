# Boltz2-Notebook

Boltz2-Notebook is a simple Google Colab notebook project for protein, ligand, and biomolecular structure prediction using the Boltz2 model. It helps you prepare input data, run predictions, view the results, and save outputs without needing a full local setup.

## What It Is

This notebook gives you a guided workflow for Boltz2. It handles setup, input preparation, prediction, and result analysis in one place.

## Main Features

- Automatic environment setup for Colab or Linux
- GPU check before running the notebook
- YAML input generation for Boltz2 jobs
- MSA download and validation
- Structure prediction for protein and ligand systems
- Confidence and error output such as pLDDT and PAE
- 3D structure visualization
- Google Drive export
- ZIP download of results

## What It Can Be Used For

- Predicting protein-ligand complexes
- Estimating binding affinity
- Visualizing predicted molecular structures
- Testing simple biomolecular modeling workflows in Colab
- Saving results for later review or local analysis

## Versions

### V1.0.0

The first public version focuses on the core workflow:

- Basic protein-ligand prediction
- Affinity prediction
- Structure and interaction visualization
- Google Drive saving
- ZIP export of results

### V2.0.0 Beta

The beta version adds more advanced input and modeling support:

- Advanced modeling panel
- Template upload for `.cif` and `.pdb` files
- Explicit template chain mapping
- Covalent ligand bond builder
- Pocket conditioning builder
- Contact conditioning builder
- Modified residue editor
- Custom or precomputed MSA upload
- Warning for single-sequence mode when MSA is empty
- DNA and RNA chain support
- Cyclic polymer toggle
- Expanded YAML writing for protein, DNA, RNA, ligands, constraints, templates, and advanced properties

## Notebook Files

- [Current notebook](Boltz2.ipynb)
- [V1 notebook](notebooks/v1/Boltz2_v1.0.0.ipynb)
- [V2 beta notebook](notebooks/v2/Boltz2_V2.0.0_beta.ipynb)

## Short Summary

If you want a quick way to run Boltz2 in Colab, this repo provides a clean notebook workflow for prediction, analysis, visualization, and result export. V2 beta adds more control for advanced biomolecular inputs and constraints.
