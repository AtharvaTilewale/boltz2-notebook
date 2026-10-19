"""Ligand helpers: SMILES validation and properties, CCD-code lookup and 2-D depiction (RDKit optional).

SMILES are checked in two stages. Plain-Python checks catch the usual typing slips (spaces, unbalanced brackets, a ring that is opened
and never closed) with a message that names the problem and works without RDKit; RDKit then parses and sanitises the molecule and
supplies the chemistry errors (valence, aromaticity).

A CCD code is checked against the wwPDB Chemical Component Dictionary through the public RCSB data API. Boltz stops with a
traceback on a code that is not in the dictionary, so this saves a run. When the service cannot be reached the answer is
"unknown" (never "invalid"): the format is still checked and the run is not blocked. Setting ``BOLTZ2NB_OFFLINE=1`` skips the lookup
(the code you type is the only thing the check sends to the service).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

CCD_RE = re.compile(r"[A-Z0-9]{1,5}")
RCSB_CHEMCOMP = "https://data.rcsb.org/rest/v1/core/chemcomp/{code}"
SMILES_CHARS = re.compile(r"[A-Za-z0-9@+\-\[\]()=#$:/\\.%*]+")
MAX_SMILES_LENGTH = 2000

_ccd_cache: dict[str, dict[str, Any]] = {}


# ------------------------------------------------------------------------------------------------- SMILES
def smiles_syntax_problem(smiles: str) -> str:
    """A plain-language problem with the SMILES text, or '' when nothing is wrong that can be seen without chemistry."""
    s = smiles
    if not s.strip():
        return "Enter a SMILES string."
    if len(s) > MAX_SMILES_LENGTH:
        return f"This SMILES is {len(s)} characters long; the limit is {MAX_SMILES_LENGTH}."
    if re.search(r"\s", s.strip()):
        return "A SMILES cannot contain spaces. Remove the spaces (or anything written after the SMILES, such as a name)."
    s = s.strip()
    bad = sorted({c for c in s if not SMILES_CHARS.fullmatch(c)})
    if bad:
        return "These characters are not allowed in a SMILES: " + " ".join(repr(c) for c in bad) + "."
    depth, ring_open, i, n = 0, {}, 0, len(s)
    while i < n:
        c = s[i]
        if c == "[":
            j = s.find("]", i)
            if j < 0:
                return "A square bracket '[' is never closed with ']'."
            if "[" in s[i + 1:j]:
                return "Square brackets cannot be nested."
            i = j
        elif c == "]":
            return "A closing bracket ']' has no matching '['."
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0:
                return "A closing parenthesis ')' has no matching '('."
        elif c.isdigit() or c == "%":
            if c == "%":
                label = s[i + 1:i + 3]
                if len(label) < 2 or not label.isdigit():
                    return "A ring label that starts with '%' needs two digits, for example %10."
                label = "%" + label
                i += 2
            else:
                label = c
            ring_open[label] = not ring_open.get(label, False)
        i += 1
    if depth > 0:
        return "A parenthesis '(' is never closed with ')'."
    left = sorted(k for k, v in ring_open.items() if v)
    if left:
        return f"Ring label {left[0]} is opened but never closed (ring labels come in pairs)."
    return ""


def _rdkit():
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    except Exception:  # noqa: BLE001
        return None
    RDLogger.DisableLog("rdApp.*")
    return Chem, Crippen, Descriptors, rdMolDescriptors


def describe_smiles(smiles: str) -> dict[str, Any]:
    smiles = smiles.strip()
    problem = smiles_syntax_problem(smiles)
    if problem:
        return {"valid": False, "message": problem}
    kit = _rdkit()
    if kit is None:
        return {"valid": None, "message": "RDKit is not installed in this runtime, so the SMILES cannot be checked or drawn. "
                                          "Run the setup cell again (it installs RDKit)."}
    Chem, Crippen, Descriptors, rdMolDescriptors = kit
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return {"valid": False, "message": "This is not a valid SMILES: check the atom symbols (organic atoms are written B C N O P S F Cl Br I, "
                                           "anything else goes in square brackets) and the bond symbols."}
    try:
        Chem.SanitizeMol(mol)
    except Exception as exc:  # noqa: BLE001  (RDKit raises several exception types)
        why = str(exc).strip().splitlines()[0] if str(exc).strip() else "the molecule is chemically impossible"
        return {"valid": False, "message": f"The SMILES reads, but the molecule is chemically invalid: {why}."}
    if mol.GetNumHeavyAtoms() == 0:
        return {"valid": False, "message": "This SMILES has no heavy atoms."}
    fragments = len(Chem.GetMolFrags(mol))
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
        "n_fragments": fragments,
        "message": "" if fragments == 1 else "SMILES contains several fragments (salt/counter-ion?); Boltz expects one molecule.",
    }


def depict_svg(smiles: str, width: int = 320, height: int = 240) -> str | None:
    kit = _rdkit()
    if kit is None:
        return None
    Chem = kit[0]
    from rdkit.Chem import Draw
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    drawer = Draw.MolDraw2DSVG(width, height)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    # RDKit starts the file with an XML declaration (<?xml ... encoding='iso-8859-1'?>); inside an HTML page that is not markup
    return svg[svg.index("<svg"):] if "<svg" in svg else svg


# ------------------------------------------------------------------------------------------------- CCD codes
def _fetch_ccd_json(code: str, timeout: float) -> dict[str, Any] | None:
    """RCSB's record for a component, or None when the component does not exist. Raises on network trouble."""
    req = urllib.request.Request(RCSB_CHEMCOMP.format(code=code), headers={"Accept": "application/json", "User-Agent": "boltz2-notebook"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  (fixed https URL)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def lookup_ccd(code: str, timeout: float = 8.0, fetch: Callable[[str, float], dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Look a CCD code up. ``status`` is ``found``, ``missing`` (not in the dictionary), ``invalid`` (not even a possible code) or ``unknown``."""
    code = str(code).strip().upper()
    if not CCD_RE.fullmatch(code):
        return {"status": "invalid", "code": code}
    if code in _ccd_cache:
        return _ccd_cache[code]
    if os.environ.get("BOLTZ2NB_OFFLINE", "").strip().lower() in ("1", "true", "yes"):
        return {"status": "unknown", "code": code, "reason": "BOLTZ2NB_OFFLINE is set"}
    try:
        record = (fetch or _fetch_ccd_json)(code, timeout)
    except Exception as exc:  # noqa: BLE001  (offline, timeout, rate limit, bad JSON)
        return {"status": "unknown", "code": code, "reason": f"{type(exc).__name__}"}
    if record is None:
        out = {"status": "missing", "code": code}
    else:
        comp, desc = record.get("chem_comp") or {}, record.get("rcsb_chem_comp_descriptor") or {}
        out = {"status": "found", "code": code, "name": str(comp.get("name") or ""),
               "formula": " ".join(str(comp.get("formula") or "").split()).replace(" ", ""),
               "mol_weight": comp.get("formula_weight"), "type": comp.get("type"),
               "smiles": desc.get("SMILES_stereo") or desc.get("SMILES") or ""}
    _ccd_cache[code] = out
    return out


def clear_ccd_cache() -> None:
    _ccd_cache.clear()


def describe_ccd(code: str, **kw: Any) -> dict[str, Any]:
    """Live feedback for a CCD code: valid / invalid / unverifiable, with the component's name, formula and a 2-D drawing."""
    code = str(code).strip().upper()
    info = lookup_ccd(code, **kw)
    st = info["status"]
    if st == "invalid":
        shown = code[:12] + ("..." if len(code) > 12 else "")
        return {"valid": False, "kind": "ccd", "code": code,
                "message": f"'{shown}' is not a CCD code: codes are 1 to 5 letters or digits (for example SAH, ATP, HEM)."}
    if st == "missing":
        return {"valid": False, "kind": "ccd", "code": code,
                "message": f"{code} is not in the PDB Chemical Component Dictionary, so Boltz cannot use it. Check the code on rcsb.org/ligand, "
                           "or describe the molecule with a SMILES instead."}
    if st == "unknown":
        return {"valid": None, "kind": "ccd", "code": code,
                "message": f"The format of {code} is right, but the PDB component service could not be reached to confirm it exists. "
                           "Boltz will check it when the run starts."}
    out: dict[str, Any] = {"valid": True, "kind": "ccd", "code": code, "name": info["name"], "formula": info["formula"],
                           "mol_weight": info["mol_weight"], "component_type": info["type"], "message": ""}
    if info.get("smiles"):
        try:
            out["svg"] = depict_svg(info["smiles"], 280, 200)
        except Exception:  # noqa: BLE001  (organometallic SMILES that RDKit rejects: the drawing is a courtesy)
            out["svg"] = None
    return out
