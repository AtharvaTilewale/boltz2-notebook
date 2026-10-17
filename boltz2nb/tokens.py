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


class LayoutMismatch(ValueError):
    """Raised when no known token layout matches the confidence array length."""


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


def _enumerate(structure_path: Path | str, mode: str) -> list[Token]:
    """Enumerate tokens under one of the known layout conventions.

    ``atomised``      Boltz-2 default: one token per polymer residue, one per heavy atom
                      of every non-polymer / non-standard residue.
    ``atomised_std``  like ``atomised`` but modified residues written as ATOM records
                      (PTMs under their CCD name) count as a single token.
    ``atomised_all``  like ``atomised`` but hydrogens present in the file also count.
    ``residue``       one token per residue, ligands included.
    """
    structure = _load_structure(structure_path)
    model = next(iter(structure))
    tokens: list[Token] = []
    for chain in model:
        for residue in chain:
            hetflag, resseq, _ = residue.id
            resname = residue.get_resname().strip()
            is_het = hetflag != " "
            if mode == "residue":
                atomise = False
            elif mode == "atomised_std":
                atomise = is_het
            else:
                atomise = is_het or resname not in STANDARD
            if not atomise:
                tokens.append(Token(len(tokens), chain.id, "residue", resname, resseq))
            else:
                for atom in residue:
                    if mode != "atomised_all" and atom.element == "H":
                        continue
                    tokens.append(Token(len(tokens), chain.id, "atom", resname, resseq, atom.get_id()))
    return tokens


LAYOUTS = ("atomised", "atomised_std", "atomised_all", "residue")
LAYOUT_LABELS = {
    "atomised": "residue, or heavy atom for ligands and modified residues",
    "atomised_std": "residue, or heavy atom for ligands",
    "atomised_all": "residue, or atom (hydrogens included) for ligands",
    "residue": "residue (ligands counted once)",
}


def token_layout(structure_path: Path | str, mode: str = "atomised") -> list[Token]:
    """Enumerate tokens in Boltz order from a written model (PDB or mmCIF)."""
    return _enumerate(structure_path, mode)


def layout_counts(structure_path: Path | str) -> dict[str, int]:
    """Token count under each known convention - used for diagnostics."""
    return {mode: len(_enumerate(structure_path, mode)) for mode in LAYOUTS}


def resolve_layout(structure_path: Path | str, n_expected: int) -> tuple[list[Token], str]:
    """Pick the layout whose token count matches the confidence arrays.

    Boltz 2.2.x writes one value per token (``atomised``); forks and future releases
    may differ, so the convention is matched against the array length instead of
    assumed, and the one that was used is reported alongside the tokens.
    """
    counts: dict[str, int] = {}
    for mode in LAYOUTS:
        tokens = _enumerate(structure_path, mode)
        counts[mode] = len(tokens)
        if len(tokens) == n_expected:
            return tokens, mode
    raise LayoutMismatch(
        f"The confidence arrays have {n_expected} entries, which matches none of the token layouts "
        f"derivable from {Path(structure_path).name} ({counts}). Per-token analysis (pLDDT, PAE) is "
        "not possible for this model; ranking metrics and affinity are unaffected.")


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
