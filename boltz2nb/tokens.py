"""Map Boltz tokens to structure elements.

Boltz-2 tokenisation (``boltz/data/tokenize/boltz2.py``): one token per standard
polymer residue; non-standard residues (PTMs) and every non-polymer (ligand)
heavy atom are tokenised per atom.  Boltz's PDB writer emits polymer chains as
``ATOM`` records (modified residues included, under their CCD name) and only
non-polymer chains as ``HETATM``, so the hetero flag alone cannot be used.

The ``plddt_*.npz`` and ``pae_*.npz`` files are indexed by token in the same
chain order as the written structure.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

STANDARD_PROTEIN = {"ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS",
                    "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL", "UNK"}
STANDARD_DNA = {"DA", "DC", "DG", "DT", "DN"}
STANDARD_RNA = {"A", "C", "G", "U", "N"}
STANDARD = STANDARD_PROTEIN | STANDARD_DNA | STANDARD_RNA


@dataclass(frozen=True)
class Token:
    index: int
    chain_id: str
    kind: str          # "residue" | "atom"
    resname: str
    resseq: int
    atom_name: str | None = None


def _load_structure(path: Path | str):
    from Bio.PDB import MMCIFParser, PDBParser
    path = Path(path)
    if path.suffix.lower() in (".cif", ".mmcif"):
        return MMCIFParser(QUIET=True).get_structure("model", str(path))
    return PDBParser(QUIET=True).get_structure("model", str(path))


def token_layout(structure_path: Path | str) -> list[Token]:
    """Enumerate tokens in Boltz order from a written model (PDB or mmCIF)."""
    structure = _load_structure(structure_path)
    model = next(iter(structure))
    tokens: list[Token] = []
    for chain in model:
        for residue in chain:
            hetflag, resseq, _ = residue.id
            resname = residue.get_resname().strip()
            is_polymer_residue = hetflag == " " and resname in STANDARD
            if is_polymer_residue:
                tokens.append(Token(len(tokens), chain.id, "residue", resname, resseq))
            else:
                for atom in residue:
                    if atom.element == "H":
                        continue
                    tokens.append(Token(len(tokens), chain.id, "atom", resname, resseq, atom.get_id()))
    return tokens


def chain_indices(tokens: Sequence[Token]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for t in tokens:
        out.setdefault(t.chain_id, []).append(t.index)
    return out


def chain_kinds(tokens: Sequence[Token]) -> dict[str, str]:
    """'protein' | 'dna' | 'rna' | 'ligand' per chain, by majority of residue names."""
    kinds: dict[str, str] = {}
    for cid, idx in chain_indices(tokens).items():
        names = {tokens[i].resname for i in idx}
        res_tokens = [tokens[i] for i in idx if tokens[i].kind == "residue"]
        if not res_tokens:
            kinds[cid] = "ligand"
        elif names & STANDARD_DNA:
            kinds[cid] = "dna"
        elif names & STANDARD_RNA and not names & STANDARD_PROTEIN:
            kinds[cid] = "rna"
        else:
            kinds[cid] = "protein"
    return kinds


def check_token_count(tokens: Sequence[Token], n_expected: int) -> None:
    if len(tokens) != n_expected:
        raise ValueError(
            f"Token layout derived from the structure has {len(tokens)} tokens but the confidence "
            f"arrays have {n_expected}. The structure and the NPZ files do not belong to the same model.")
