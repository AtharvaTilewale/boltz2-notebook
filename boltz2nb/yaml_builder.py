"""Build and validate Boltz input YAML from the GUI payload or a Python dict.

Payload shape (what ``param_gen.py``'s JavaScript sends)::

    {"sequences": [{"type": "protein"|"dna"|"rna"|"ligand", "data": {...}}, ...],
     "constraints": {"bonds": [...], "pockets": [...], "contacts": [...]},
     "templates": [{"path": ..., "chain_id": [...], "template_id": [...], "force": bool, "threshold": float}],
     "properties": {"affinity_binder": "B"}}

The output follows the Boltz schema documented at
https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .ligand import CCD_RE

PROTEIN_ALPHABET = set("ACDEFGHIKLMNPQRSTVWYX")
DNA_ALPHABET = set("ACGTN")
RNA_ALPHABET = set("ACGUN")
ALPHABETS = {"protein": PROTEIN_ALPHABET, "dna": DNA_ALPHABET, "rna": RNA_ALPHABET}
POLYMER_TYPES = ("protein", "dna", "rna")


class SpecError(ValueError):
    """Raised when the user specification cannot become a valid Boltz input."""


# ---------------------------------------------------------------- YAML dumper
class IdList(list):
    """Chain-id lists are emitted in flow style: ``id: [A, B]``."""


class QuotedString(str):
    """SMILES are always single-quoted so YAML never mis-parses ``#``/``:``."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(IdList, lambda d, data: d.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True))
_Dumper.add_representer(QuotedString, lambda d, data: d.represent_scalar("tag:yaml.org,2002:str", data, style="'"))
_Dumper.add_representer(str, lambda d, data: d.represent_scalar("tag:yaml.org,2002:str", data))


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, default_flow_style=False, indent=2, width=10_000)


# ---------------------------------------------------------------- cleaning
def clean_ids(values) -> IdList:
    if isinstance(values, str):
        values = values.split(",")
    return IdList(str(v).strip().upper().replace(" ", "") for v in values if str(v).strip())


def clean_token_list(values) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    return [str(v).strip() for v in values if str(v).strip()]


def clean_sequence(seq) -> str:
    return re.sub(r"\s+", "", str(seq or "")).upper()


def _ref(value):
    """Residue references may be integers (index) or strings (atom name for ligands)."""
    s = str(value).strip()
    try:
        return int(s)
    except ValueError:
        return s


def smiles_is_valid(smiles: str) -> tuple[bool, str]:
    """Validate SMILES (text checks always, chemistry with RDKit when available); (True, '') when RDKit is missing and the text is fine."""
    from .ligand import describe_smiles
    d = describe_smiles(smiles)
    if d["valid"] is False:
        return False, f"Ligand SMILES '{smiles}': {d['message']}"
    return True, ""


# ---------------------------------------------------------------- building
def build_sequences(raw_sequences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in raw_sequences:
        etype = str(entry.get("type", "")).lower()
        item = entry.get("data", {}) or {}
        ids = clean_ids(item.get("id", []))
        if not ids:
            raise SpecError(f"{etype or 'entity'} entry is missing a chain ID.")
        if etype in POLYMER_TYPES:
            seq = clean_sequence(item.get("sequence", ""))
            if not seq:
                raise SpecError(f"{etype} chain {list(ids)} has an empty sequence.")
            bad = sorted(set(seq) - ALPHABETS[etype])
            if bad:
                raise SpecError(f"{etype} chain {list(ids)} contains invalid characters: {''.join(bad)}.")
            poly: dict[str, Any] = {"id": ids, "sequence": seq}
            msa = item.get("msa")
            if etype == "protein" and msa not in (None, ""):
                poly["msa"] = str(msa).strip()
            mods = []
            for mod in item.get("modifications", []) or []:
                pos, ccd = mod.get("position"), str(mod.get("ccd", "")).strip().upper()
                if pos in (None, "") or not ccd:
                    continue
                pos = int(pos)
                if not (1 <= pos <= len(seq)):
                    raise SpecError(f"Modification position {pos} is outside chain {list(ids)} (length {len(seq)}).")
                mods.append({"position": pos, "ccd": ccd})
            if mods:
                poly["modifications"] = mods
            if item.get("cyclic"):
                poly["cyclic"] = True
            out.append({etype: poly})
        elif etype == "ligand":
            lig: dict[str, Any] = {"id": ids}
            ccd = str(item.get("ccd", "")).strip().upper()
            smiles = str(item.get("smiles", "")).strip()
            if bool(ccd) == bool(smiles):
                raise SpecError(f"Ligand {list(ids)} must have exactly one of CCD code or SMILES.")
            if ccd:
                if not CCD_RE.fullmatch(ccd):
                    raise SpecError(f"Ligand {list(ids)}: '{ccd}' is not a CCD code (1 to 5 letters or digits, for example SAH, ATP, HEM).")
                lig["ccd"] = ccd
            else:
                ok, msg = smiles_is_valid(smiles)
                if not ok:
                    raise SpecError(msg)
                lig["smiles"] = QuotedString(smiles)
            out.append({"ligand": lig})
        else:
            raise SpecError(f"Unsupported entity type: {etype!r}.")
    return out


def _all_chain_ids(sequences: list[dict[str, Any]]) -> dict[str, str]:
    """Map chain id -> entity type; raises on duplicates."""
    seen: dict[str, str] = {}
    for s in sequences:
        (etype, body), = s.items()
        for cid in body["id"]:
            if cid in seen:
                raise SpecError(f"Chain ID '{cid}' is used more than once.")
            seen[cid] = etype
    return seen


def build_constraints(raw: dict[str, Any], chains: dict[str, str]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []

    def check_chain(cid: str, where: str):
        if cid not in chains:
            raise SpecError(f"{where} references unknown chain '{cid}'. Known chains: {sorted(chains)}.")

    for b in raw.get("bonds", []) or []:
        a1 = [str(b.get("chain1", "")).strip().upper(), int(b.get("res1", 1) or 1), str(b.get("atom1", "")).strip()]
        a2 = [str(b.get("chain2", "")).strip().upper(), int(b.get("res2", 1) or 1), str(b.get("atom2", "")).strip()]
        if not (a1[0] and a1[2] and a2[0] and a2[2]):
            continue
        check_chain(a1[0], "Bond"); check_chain(a2[0], "Bond")
        constraints.append({"bond": {"atom1": a1, "atom2": a2}})

    for p in raw.get("pockets", []) or []:
        binder = str(p.get("binder", "")).strip().upper()
        contacts = []
        for tok in p.get("contacts", []) or []:
            chain, ref = str(tok.get("chain", "")).strip().upper(), str(tok.get("ref", "")).strip()
            if chain and ref:
                check_chain(chain, "Pocket contact")
                contacts.append([chain, _ref(ref)])
        if not (binder and contacts):
            continue
        check_chain(binder, "Pocket binder")
        d: dict[str, Any] = {"binder": binder, "contacts": contacts}
        if p.get("max_distance") not in (None, "", 0):
            d["max_distance"] = float(p["max_distance"])
        if p.get("force"):
            d["force"] = True
        constraints.append({"pocket": d})

    for c in raw.get("contacts", []) or []:
        ch1, r1 = str(c.get("chain1", "")).strip().upper(), str(c.get("ref1", "")).strip()
        ch2, r2 = str(c.get("chain2", "")).strip().upper(), str(c.get("ref2", "")).strip()
        if not (ch1 and r1 and ch2 and r2):
            continue
        check_chain(ch1, "Contact"); check_chain(ch2, "Contact")
        d = {"token1": [ch1, _ref(r1)], "token2": [ch2, _ref(r2)]}
        if c.get("max_distance") not in (None, "", 0):
            d["max_distance"] = float(c["max_distance"])
        if c.get("force"):
            d["force"] = True
        constraints.append({"contact": d})
    return constraints


_BOLTZ_LIGAND = re.compile(r"LIG\d?")        # how Boltz labels a ligand it writes (LIG in a .pdb, LIG1 in a .cif): not in the Chemical Component Dictionary


def template_file_warnings(path: str, template_ids: list[str]) -> list[str]:
    """What a quick look at a template file shows will make Boltz stop (found with boltz 2.2.1; nothing is rejected, the engine decides).

    Boltz skips an input it cannot read and exits normally, so without this the first sign would be a finished run without a structure.
    """
    file = Path(path)
    if not file.is_file():
        return []
    try:
        text = file.read_bytes()[:20_000_000].decode("utf-8", errors="ignore")
    except OSError:
        return []
    name, found = file.name, []
    if file.suffix.lower() == ".pdb":
        if not any(line.startswith("SEQRES") for line in text.splitlines()):
            found.append(f"Template {name} has no SEQRES records. Boltz reads a .pdb template's sequence from them and stops without them "
                         "(structures written by Boltz have none): use the .cif file instead.")
        if any(re.fullmatch(r"[A-Za-z]", t) for t in template_ids):
            found.append(f"Template {name}: Boltz names the chains of a .pdb template A1, B1, ... so a template chain such as 'A' is not found. "
                         "Leave the template chain empty to use every protein chain, or use the .cif file (its chains keep the names A, B, ...).")
        ligand = any(_BOLTZ_LIGAND.fullmatch(line[17:20].strip()) for line in text.splitlines() if line.startswith("HETATM"))
    else:
        ligand = any(_BOLTZ_LIGAND.fullmatch(word) for line in text.splitlines() for word in line.split())
    if ligand:
        found.append(f"Template {name} contains a ligand named LIG or LIG1, which is how Boltz labels a ligand it writes. Boltz cannot read such a ligand "
                     "back (it is not in the Chemical Component Dictionary): remove its HETATM records, or use a protein-only structure.")
    return found


def build_templates(raw: list[dict[str, Any]], chains: dict[str, str], warnings: list[str] | None = None) -> list[dict[str, Any]]:
    templates = []
    for t in raw or []:
        path = str(t.get("path", "")).strip()
        if not path:
            continue
        ext = Path(path).suffix.lower()
        if ext == ".cif" or ext == ".mmcif":
            tmpl: dict[str, Any] = {"cif": path}
        elif ext == ".pdb":
            tmpl = {"pdb": path}
        else:
            raise SpecError(f"Template '{path}' must be a .pdb, .cif or .mmcif file.")
        chain_ids = clean_token_list(t.get("chain_id", []))
        template_ids = clean_token_list(t.get("template_id", []))
        for cid in chain_ids:
            if cid.upper() not in chains:
                raise SpecError(f"Template chain_id '{cid}' does not match any input chain.")
            if chains[cid.upper()] != "protein":
                raise SpecError(f"Templates are only supported for protein chains (chain '{cid}').")
        if chain_ids:
            tmpl["chain_id"] = [c.upper() for c in chain_ids] if len(chain_ids) > 1 else chain_ids[0].upper()
        if template_ids:
            tmpl["template_id"] = template_ids if len(template_ids) > 1 else template_ids[0]
        if warnings is not None:
            warnings.extend(template_file_warnings(path, template_ids))
        if t.get("force"):
            tmpl["force"] = True
            if t.get("threshold") not in (None, ""):
                tmpl["threshold"] = float(t["threshold"])
        templates.append(tmpl)
    return templates


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept both GUI payload dialects and return the typed (v2) form.

    v1 sends Boltz-shaped entries ``{"protein": {...}}`` / ``{"ligand": {...}}`` and
    ``properties: [{"affinity": {"binder": "B"}}]``; v2 sends ``{"type": ..., "data": ...}``
    and ``properties: {"affinity_binder": "B"}``.
    """
    if not isinstance(payload, dict) or "sequences" not in payload:
        raise SpecError('Invalid data structure: "sequences" key missing.')
    out = dict(payload)
    seqs = []
    for entry in payload.get("sequences", []) or []:
        if isinstance(entry, dict) and "type" in entry and "data" in entry:
            seqs.append(entry)
        elif isinstance(entry, dict) and len(entry) == 1:
            (etype, body), = entry.items()
            seqs.append({"type": etype, "data": dict(body or {})})
        else:
            raise SpecError(f"Unrecognised sequence entry: {entry!r}")
    out["sequences"] = seqs
    props = payload.get("properties")
    if isinstance(props, list):
        binder = None
        for item in props:
            if isinstance(item, dict) and "affinity" in item:
                binder = (item["affinity"] or {}).get("binder")
        out["properties"] = {"affinity_binder": binder} if binder else {}
    elif props is None:
        out["properties"] = {}
    out.setdefault("constraints", {})
    out.setdefault("templates", [])
    return out


def build_yaml(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the GUI payload (either dialect) into a Boltz schema dict (raises SpecError)."""
    payload = normalize_payload(payload)
    data: dict[str, Any] = {"version": 1}
    data["sequences"] = build_sequences(payload.get("sequences", []))
    if not data["sequences"]:
        raise SpecError("At least one entity is required.")
    chains = _all_chain_ids(data["sequences"])

    constraints = build_constraints(payload.get("constraints", {}) or {}, chains)
    if constraints:
        data["constraints"] = constraints
    template_warnings: list[str] = []
    templates = build_templates(payload.get("templates", []) or [], chains, template_warnings)
    if templates:
        data["templates"] = templates
    if template_warnings:
        data.setdefault("_warnings", []).extend(template_warnings)

    binder = (payload.get("properties", {}) or {}).get("affinity_binder")
    if binder:
        binder = str(binder).strip().upper()
        if binder not in chains:
            raise SpecError(f"Affinity binder '{binder}' is not a defined chain.")
        if chains[binder] != "ligand":
            raise SpecError("Boltz-2 affinity is only defined for small-molecule ligand chains, "
                            f"but '{binder}' is a {chains[binder]} chain.")
        ligands = [c for c, t in chains.items() if t == "ligand"]
        data["properties"] = [{"affinity": {"binder": binder}}]
        if len(ligands) > 1:
            data.setdefault("_warnings", []).append(
                "Boltz-2 affinity was trained on single-ligand complexes; results with several "
                "ligand chains are less reliable.")
    return data


def pop_warnings(data: dict[str, Any]) -> list[str]:
    return data.pop("_warnings", [])


def spec_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Small description used by the GUI status line and the report."""
    kinds: dict[str, int] = {}
    n_polymer_residues = 0
    for s in data["sequences"]:
        (etype, body), = s.items()
        kinds[etype] = kinds.get(etype, 0) + len(body["id"])
        if etype in POLYMER_TYPES:
            n_polymer_residues += len(body["sequence"]) * len(body["id"])
    return {
        "entities": kinds,
        "polymer_residues": n_polymer_residues,
        "has_affinity": "properties" in data,
        "n_constraints": len(data.get("constraints", [])),
        "n_templates": len(data.get("templates", [])),
        "single_sequence_chains": sum(1 for s in data["sequences"] if "protein" in s and s["protein"].get("msa") == "empty"),
    }


def write_yaml(data: dict[str, Any], path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data))
    return path


def yaml_has_explicit_msa(yaml_text: str) -> bool:
    return bool(re.search(r"^[ \t]*msa\s*:", yaml_text, flags=re.MULTILINE))


def simple_spec(protein: str | list[str], ligand_smiles: str | None = None, ligand_ccd: str | None = None,
                affinity: bool = False, msa: str | None = None,
                dna: list[str] | None = None, rna: list[str] | None = None) -> dict[str, Any]:
    """Programmatic helper to create a payload without the GUI (used by batch mode)."""
    chains = [protein] if isinstance(protein, str) else list(protein)
    ids = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    seqs = []
    for seq in chains:
        d: dict[str, Any] = {"id": [next(ids)], "sequence": seq}
        if msa:
            d["msa"] = msa
        seqs.append({"type": "protein", "data": d})
    for seq in dna or []:
        seqs.append({"type": "dna", "data": {"id": [next(ids)], "sequence": seq}})
    for seq in rna or []:
        seqs.append({"type": "rna", "data": {"id": [next(ids)], "sequence": seq}})
    binder = None
    if ligand_smiles or ligand_ccd:
        binder = next(ids)
        seqs.append({"type": "ligand", "data": {"id": [binder], "smiles": ligand_smiles or "", "ccd": ligand_ccd or ""}})
    payload: dict[str, Any] = {"sequences": seqs, "constraints": {}, "templates": [], "properties": {}}
    if affinity and binder:
        payload["properties"]["affinity_binder"] = binder
    return payload
