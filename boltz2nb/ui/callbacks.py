"""Python side of the input builder: every function the browser form can call.

Each callback takes JSON-compatible arguments and returns a JSON-compatible dict with a
``status`` of ``"ok"`` or ``"error"``.  They are plain functions so tests can call them
directly or through the browser harness.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from ..ligand import depict_svg, describe_smiles
from ..paths import base_dir, ensure_dirs, upload_dir
from ..pdb_import import parse_structure_text
from ..run_params import parse_run_params_text, validate_run_params
from ..yaml_builder import SpecError, build_yaml, dump_yaml, pop_warnings, spec_summary, write_yaml
from .theme import set_theme

LARGE_COMPLEX_RESIDUES = 1500  # same threshold as the batch preflight


def _build(payload: dict[str, Any]) -> dict[str, Any]:
    doc = build_yaml(payload)
    warnings = pop_warnings(doc)
    info = spec_summary(doc)
    notes: list[str] = []
    if info["single_sequence_chains"]:
        notes.append(f"{info['single_sequence_chains']} protein chain(s) run in single-sequence mode (lower accuracy).")
    for s in doc["sequences"]:
        if "ligand" in s and s["ligand"].get("smiles"):
            d = describe_smiles(s["ligand"]["smiles"])
            if d.get("valid"):
                notes.append(f"Ligand {s['ligand']['id'][0]}: {d['formula']}, MW {d['mol_weight']}, {d['heavy_atoms']} heavy atoms.")
            if d.get("message"):
                warnings.append(d["message"])
    if info["polymer_residues"] > LARGE_COMPLEX_RESIDUES:
        warnings.append(f"{info['polymer_residues']} polymer residues: this is likely to exceed the memory of a T4 GPU. "
                        "Use the Fast preset or a larger GPU.")
    return {"doc": doc, "summary": info, "notes": notes, "warnings": warnings}


def preview_params(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the form state and return the YAML that would be written (nothing is saved)."""
    try:
        r = _build(payload)
        return {"status": "ok", "yaml": dump_yaml(r["doc"]), "summary": r["summary"],
                "notes": r["notes"], "warnings": r["warnings"]}
    except SpecError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"{type(e).__name__}: {e}"}


def save_params(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        r = _build(payload)
        ensure_dirs()
        path = write_yaml(r["doc"], base_dir() / "params.yaml")
        return {"status": "ok", "filename": str(path), "yaml": dump_yaml(r["doc"]), "summary": r["summary"],
                "notes": r["notes"], "warnings": r["warnings"]}
    except SpecError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"{type(e).__name__}: {e}"}


def save_run_params(data: dict[str, Any]) -> dict[str, Any]:
    try:
        content = str(data.get("content", ""))
        problems = validate_run_params({**parse_run_params_text(content)})
        if problems:
            return {"status": "error", "message": " ".join(problems)}
        name = Path(str(data.get("filename", "run_params.txt"))).name
        ensure_dirs()
        (base_dir() / name).write_text(content.strip() + "\n")
        return {"status": "ok", "filename": name}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": str(e)}


def save_uploaded_file(file_kind: str, filename: str, content_b64: str) -> dict[str, Any]:
    try:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(str(filename)).name) or "upload"
        allowed = {".pdb", ".cif", ".mmcif"} if file_kind == "template" else {".a3m", ".csv"}
        if file_kind not in ("template", "msa"):
            return {"status": "error", "message": f"Unsupported upload kind: {file_kind}."}
        if Path(safe).suffix.lower() not in allowed:
            return {"status": "error", "message": f"{file_kind} must be one of {sorted(allowed)}."}
        ensure_dirs()
        dest = upload_dir("templates" if file_kind == "template" else "msas") / safe
        raw = content_b64.split(",", 1)[1] if "," in content_b64 else content_b64
        dest.write_bytes(base64.b64decode(raw))
        return {"status": "ok", "path": str(dest), "name": safe, "size": dest.stat().st_size}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": str(e)}


def describe_ligand(data: dict[str, Any]) -> dict[str, Any]:
    """Live ligand feedback: validity, properties and a 2-D depiction for SMILES."""
    kind = str(data.get("kind", "smiles")).lower()
    value = str(data.get("value", "")).strip()
    if not value:
        return {"status": "ok", "valid": None}
    if kind == "ccd":
        ok = bool(re.fullmatch(r"[A-Za-z0-9]{1,5}", value))
        return {"status": "ok", "valid": ok, "kind": "ccd",
                "message": "" if ok else "CCD codes are 1-5 letters or digits (for example SAH, ATP, HEM)."}
    d = describe_smiles(value)
    out = {"status": "ok", "kind": "smiles", **d}
    if d.get("valid"):
        out["svg"] = depict_svg(value, 280, 200)
    return out


def process_pdb_upload(data: dict[str, Any]) -> dict[str, Any]:
    return parse_structure_text(str(data.get("pdb_content", "")), str(data.get("filename", "")))


def save_theme(theme: str) -> dict[str, Any]:
    """The colour theme chosen with the switch; panels drawn later (run panel, result card, report) start in it."""
    try:
        return {"status": "ok", "theme": set_theme(theme)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}


CALLBACKS = {
    "preview_params": preview_params,
    "save_params": save_params,
    "save_run_params": save_run_params,
    "save_uploaded_file": save_uploaded_file,
    "describe_ligand": describe_ligand,
    "process_pdb_upload": process_pdb_upload,
    "set_theme": save_theme,
}


def register_callbacks(output: Any = None) -> bool:
    """Register every callback with ``google.colab.output``; returns False outside Colab."""
    if output is None:
        try:
            from google.colab import output  # type: ignore[no-redef]
        except Exception:  # noqa: BLE001
            return False
    for name, fn in CALLBACKS.items():
        output.register_callback(name, fn)
    return True
