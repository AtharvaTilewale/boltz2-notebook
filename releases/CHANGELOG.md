# Changelog

## v2.0.1 (Latest)
- Migrated engine to `boltz-community` with full Python 3.13 support
- Removed Google Drive cache in favor of fast local NVMe SSD storage (`/root/.boltz`)
- Eliminated 30+ minute source build times on Python 3.13 using PyPI binary wheels and `uv`
- Fixed CCD dataset re-downloading on every run (boltz-community #633)
- Relaxed dependency constraints (numpy>=1.26, fairscale removed)


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