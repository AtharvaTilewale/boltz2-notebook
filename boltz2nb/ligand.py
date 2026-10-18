"""Ligand helpers (RDKit optional): validation, properties and 2-D depiction."""
from __future__ import annotations

from typing import Any


def describe_smiles(smiles: str) -> dict[str, Any]:
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    except Exception:
        return {"valid": None, "message": "RDKit not installed; SMILES not checked."}
    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"valid": False, "message": "RDKit could not parse this SMILES."}
    return {
        "valid": True,
        "canonical_smiles": Chem.MolToSmiles(mol),
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "mol_weight": round(Descriptors.MolWt(mol), 2),
        "clogp": round(Crippen.MolLogP(mol), 2),
        "hbd": rdMolDescriptors.CalcNumHBD(mol),
        "hba": rdMolDescriptors.CalcNumHBA(mol),
        "rotatable_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "n_fragments": len(Chem.GetMolFrags(mol)),
        "message": "" if len(Chem.GetMolFrags(mol)) == 1 else "SMILES contains several fragments (salt/counter-ion?); Boltz expects one molecule.",
    }


def depict_svg(smiles: str, width: int = 320, height: int = 240) -> str | None:
    try:
        from rdkit import Chem
        from rdkit.Chem import Draw
    except Exception:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    drawer = Draw.MolDraw2DSVG(width, height)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    # RDKit starts the file with an XML declaration (<?xml ... encoding='iso-8859-1'?>); inside an HTML page that is not markup
    return svg[svg.index("<svg"):] if "<svg" in svg else svg
