"""Read chains and ligand components out of a PDB or mmCIF file for the input builder.

Only the first model is used.  Sequences are built from the residues that are actually
present in the file (unresolved residues are not invented), modified residues map to their
parent where that is unambiguous (MSE -> M), and chains with an identical sequence are
grouped into one entity so a homo-oligomer becomes ``id: [A, B]``.
"""
from __future__ import annotations

from collections import OrderedDict
from io import StringIO
from typing import Any

AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
       "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
       "TYR": "Y", "VAL": "V", "MSE": "M"}
DNA3 = {"DA": "A", "DC": "C", "DG": "G", "DT": "T"}
RNA3 = {"A": "A", "C": "C", "G": "G", "U": "U"}
WATER = {"HOH", "WAT", "DOD", "H2O"}
MAX_CHARS = 40_000_000


def _parser(filename: str):
    from Bio.PDB import MMCIFParser, PDBParser
    name = (filename or "").lower()
    return MMCIFParser(QUIET=True) if name.endswith((".cif", ".mmcif")) else PDBParser(QUIET=True)


def _kind_of(resname: str, hetflag: str) -> str | None:
    r = resname.strip().upper()
    if r in AA3:
        return "protein"
    if r in DNA3:
        return "dna"
    if r in RNA3 and hetflag == " ":
        return "rna"
    return None


def parse_structure_text(text: str, filename: str = "") -> dict[str, Any]:
    if not text or not text.strip():
        return {"status": "error", "message": "The file is empty.",
                "hint": "Choose a PDB (.pdb/.ent) or mmCIF (.cif) file."}
    if len(text) > MAX_CHARS:
        return {"status": "error", "message": "The file is too large to import in the browser.",
                "hint": "Extract the chains you need and upload that smaller file."}
    try:
        structure = _parser(filename).get_structure("upload", StringIO(text))
        model = next(iter(structure))
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"Could not read the structure: {exc}",
                "hint": "Check that this is a valid PDB or mmCIF file."}

    chains: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ligands: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for chain in model:
        cid = (chain.id or "A").strip() or "A"
        letters: list[str] = []
        kinds: list[str] = []
        for res in chain:
            hetflag, _, _ = res.id
            resname = res.get_resname().strip().upper()
            kind = _kind_of(resname, hetflag)
            if kind is not None:
                table = {"protein": AA3, "dna": DNA3, "rna": RNA3}[kind]
                letters.append(table[resname])
                kinds.append(kind)
            elif hetflag.startswith("H") and resname not in WATER:
                entry = ligands.setdefault(resname, {"ccd": resname, "chains": [], "copies": 0, "atoms": 0})
                if cid not in entry["chains"]:
                    entry["chains"].append(cid)
                entry["copies"] += 1
                entry["atoms"] = max(entry["atoms"], len([a for a in res if a.element != "H"]))
        if letters:
            kind = max(set(kinds), key=kinds.count)
            chains[cid] = {"sequence": "".join(letters), "length": len(letters), "kind": kind}

    if not chains:
        return {"status": "error",
                "message": "No protein, DNA or RNA chains with standard residues were found.",
                "hint": "The file may only contain ligands/ions or non-standard residues."}

    groups: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
    for cid, c in chains.items():
        groups.setdefault((c["kind"], c["sequence"]), []).append(cid)
    entities = [{"kind": k, "sequence": s, "length": len(s), "ids": ids} for (k, s), ids in groups.items()]
    lig = []
    for entry in ligands.values():
        entry["ion"] = entry["atoms"] <= 1
        lig.append(entry)
    return {"status": "ok", "filename": filename, "chains": chains, "entities": entities, "ligands": lig}
