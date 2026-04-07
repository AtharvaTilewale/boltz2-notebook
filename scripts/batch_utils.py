from __future__ import annotations
import os, re, json, glob, zipfile, hashlib, subprocess, time, traceback
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import yaml
from Bio import SeqIO

WORK_ROOT = Path("/content/boltz_batch")
NOTEBOOK_VERSION = "1.0.1"
DIRS = {
    "inputs": WORK_ROOT / "inputs",
    "tables": WORK_ROOT / "inputs" / "tables",
    "yamls": WORK_ROOT / "inputs" / "yamls",
    "templates": WORK_ROOT / "inputs" / "templates",
    "msas": WORK_ROOT / "inputs" / "msas",
    "uploads": WORK_ROOT / "uploads",
    "jobs": WORK_ROOT / "jobs",
    "manifests": WORK_ROOT / "manifests",
    "summaries": WORK_ROOT / "summaries",
    "exports": WORK_ROOT / "exports",
    "logs": WORK_ROOT / "logs",
}
for p in DIRS.values():
    p.mkdir(parents=True, exist_ok=True)

AA_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYXBZUOJ*-]+$", re.I)
METRIC_DIRECTION = {
    "affinity_pred_value": "asc",
    "complex_pde": "asc",
    "complex_ipde": "asc",
    "affinity_probability_binary": "desc",
    "confidence_score": "desc",
    "ptm": "desc",
    "iptm": "desc",
    "complex_plddt": "desc",
    "complex_iplddt": "desc",
    "plddt": "desc",
}

def slugify(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name).strip())
    name = re.sub(r"_+", "_", name).strip("._")
    return name or "job"

def clean_sequence(seq: str) -> str:
    return re.sub(r"\s+", "", str(seq or "")).upper()

def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def _coerce_float(val: Any) -> Optional[float]:
    try:
        if val is None or val == "":
            return None
        return float(val)
    except Exception:
        return None

def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)

def read_json(path: Path, default=None):
    if not Path(path).exists():
        return {} if default is None else default
    with open(path) as fh:
        return json.load(fh)

def discover_uploads() -> Dict[str, List[str]]:
    return {
        "csv": sorted(str(p) for p in DIRS["tables"].glob("*.csv")),
        "fasta": sorted(str(p) for ext in ("*.fa", "*.fasta", "*.faa") for p in DIRS["tables"].glob(ext)),
        "yaml": sorted(str(p) for p in DIRS["yamls"].glob("*.yaml")),
        "zip": sorted(str(p) for p in DIRS["uploads"].glob("*.zip")),
        "template": sorted(str(p) for p in DIRS["templates"].glob("*")),
        "msa": sorted(str(p) for p in DIRS["msas"].glob("*")),
    }

def save_uploaded_file(name: str, content: bytes, category: str = "uploads") -> str:
    if category not in DIRS:
        raise KeyError(f"Unknown category: {category}")
    path = DIRS[category] / Path(name).name
    with open(path, "wb") as fh:
        fh.write(content)
    return str(path)

def make_example_csv() -> Path:
    path = DIRS["tables"] / "batch_input_template.csv"
    rows = [
        {
            "job_name": "demo_protein_only",
            "protein_sequence": "MSEQNNTEMTFQIQRIYTKDISFEAPNAPHVFQKDWLDN",
            "ligand_smiles": "",
            "ligand_ccd": "",
            "protein_id": "A",
            "ligand_id": "B",
            "binder": "",
            "msa_mode": "server",
            "msa_path": "",
            "template_file": "",
            "template_chain_id": "",
            "template_id": "",
            "notes": "protein-only example",
        },
        {
            "job_name": "demo_protein_ligand",
            "protein_sequence": "MSEQNNTEMTFQIQRIYTKDISFEAPNAPHVFQKDWLDN",
            "ligand_smiles": "CCO",
            "ligand_ccd": "",
            "protein_id": "A",
            "ligand_id": "B",
            "binder": "B",
            "msa_mode": "server",
            "msa_path": "",
            "template_file": "",
            "template_chain_id": "",
            "template_id": "",
            "notes": "protein-ligand example",
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path

def extract_yaml_zip(zip_path: str) -> List[str]:
    zip_path = Path(zip_path)
    target = DIRS["yamls"] / zip_path.stem
    target.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".yaml") or name.lower().endswith(".yml"):
                base = Path(name).name
                out = target / base
                with open(out, "wb") as fh:
                    fh.write(zf.read(name))
                extracted.append(str(out))
    return sorted(extracted)

def _protein_chain_ids(count: int) -> List[str]:
    alphabet = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    ids = []
    for i in range(count):
        ids.append(alphabet[i] if i < len(alphabet) else f"CHAIN{i+1}")
    return ids

def _split_fasta_chain_sequences(seq_text: str) -> List[str]:
    parts = [clean_sequence(x) for x in str(seq_text).split(":")]
    chains = [p for p in parts if p]
    if not chains:
        raise ValueError("FASTA sequence is empty")
    for chain in chains:
        if not AA_RE.match(chain):
            raise ValueError("FASTA sequence contains unsupported characters")
    return chains

def build_manifest_from_fasta(fasta_path: str, manifest_name: str = "fasta_manifest") -> Path:
    fasta_path = Path(fasta_path)
    records = []
    seen = set()
    parsed_records = list(SeqIO.parse(str(fasta_path), "fasta"))
    if not parsed_records:
        raise ValueError("No FASTA records found")

    for idx, rec in enumerate(parsed_records):
        header = str(getattr(rec, "description", "")).strip()
        base_job_name = slugify(header or f"job_{idx+1}")
        chain_sequences = _split_fasta_chain_sequences(str(rec.seq))
        chain_ids = _protein_chain_ids(len(chain_sequences))

        payload = {
            "version": 1,
            "sequences": [
                {"protein": {"id": [chain_id], "sequence": chain_seq}}
                for chain_id, chain_seq in zip(chain_ids, chain_sequences)
            ],
        }

        yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        signature = sha1_text(yaml_text)
        dedup_note = "duplicate_content" if signature in seen else ""
        seen.add(signature)

        yaml_path = DIRS["yamls"] / f"{base_job_name}.yaml"
        with open(yaml_path, "w") as fh:
            fh.write(yaml_text)

        extra = {
            "mode": "fasta",
            "row_index": int(idx),
            "protein_length": int(sum(len(x) for x in chain_sequences)),
            "chain_count": int(len(chain_sequences)),
            "has_ligand": False,
            "binder": "",
            "msa_mode": "server",
            "duplicate_flag": dedup_note,
            "notes": "fasta_protein_only",
            "fasta_header": header,
        }
        records.append(create_job_record(base_job_name, str(yaml_path), str(fasta_path), extra=extra))

    manifest = pd.DataFrame(records)
    out = DIRS["manifests"] / f"{slugify(manifest_name)}.csv"
    manifest.to_csv(out, index=False)
    return out

def build_yaml_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    protein_sequence = clean_sequence(row.get("protein_sequence", ""))
    if not protein_sequence:
        raise ValueError("protein_sequence is required")
    if not AA_RE.match(protein_sequence):
        raise ValueError("protein_sequence contains unsupported characters")

    protein_id = str(row.get("protein_id", "A")).strip() or "A"
    ligand_id = str(row.get("ligand_id", "B")).strip() or "B"
    ligand_smiles = str(row.get("ligand_smiles", "")).strip()
    ligand_ccd = str(row.get("ligand_ccd", "")).strip().upper()
    binder = str(row.get("binder", "")).strip().upper()
    msa_mode = str(row.get("msa_mode", "server")).strip().lower()
    msa_path = str(row.get("msa_path", "")).strip()

    protein_payload = {"id": [protein_id], "sequence": protein_sequence}
    if msa_path:
        protein_payload["msa"] = msa_path
    elif msa_mode == "none":
        protein_payload["msa"] = "empty"

    sequences = [{"protein": protein_payload}]
    if ligand_smiles or ligand_ccd:
        lig = {"id": [ligand_id]}
        if ligand_smiles and ligand_ccd:
            raise ValueError("Use either ligand_smiles or ligand_ccd, not both")
        if ligand_smiles:
            lig["smiles"] = ligand_smiles
        if ligand_ccd:
            lig["ccd"] = ligand_ccd
        sequences.append({"ligand": lig})

    payload = {"version": 1, "sequences": sequences}

    template_file = str(row.get("template_file", "")).strip()
    template_chain_id = str(row.get("template_chain_id", "")).strip()
    template_id = str(row.get("template_id", "")).strip()
    if template_file:
        ext = Path(template_file).suffix.lower()
        template_entry = {}
        if ext in {".cif", ".mmcif"}:
            template_entry["cif"] = template_file
        elif ext == ".pdb":
            template_entry["pdb"] = template_file
        else:
            raise ValueError("template_file must end with .pdb, .cif, or .mmcif")
        if template_chain_id:
            template_entry["chain_id"] = template_chain_id
        if template_id:
            template_entry["template_id"] = template_id
        payload["templates"] = [template_entry]

    if binder:
        payload["properties"] = [{"affinity": {"binder": binder}}]

    return payload

def default_run_params() -> Dict[str, Any]:
    return {
        "recycling_steps": 3,
        "sampling_steps": 200,
        "diffusion_samples": 1,
        "step_scale": 1.638,
        "max_msa_seqs": 8192,
        "msa_pairing_strategy": "greedy",
        "use_potentials": False,
        "override": False,
        "output_format": "pdb",
        "skip_completed": True,
        "retry_failed": False,
        "continue_on_error": True,
        "max_parallel_samples": 5,
    }

def apply_run_profile(profile: str) -> Dict[str, Any]:
    p = default_run_params()
    profile = (profile or "balanced").strip().lower()
    if profile == "fast":
        p.update({"sampling_steps": 50, "diffusion_samples": 1, "max_msa_seqs": 256})
    elif profile == "scientific":
        p.update({"sampling_steps": 200, "diffusion_samples": 5, "max_msa_seqs": 8192, "use_potentials": True})
    return p

def create_job_record(job_name: str, yaml_path: str, source: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    job_name = slugify(job_name)
    job_id = f"job_{sha1_text(job_name + '|' + str(yaml_path))}"
    job_dir = DIRS["jobs"] / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "job_id": job_id,
        "job_name": job_name,
        "yaml_path": str(Path(yaml_path).resolve()),
        "source": source,
        "status": "PENDING",
        "created_at": now_iso(),
        "job_dir": str(job_dir),
        "output_dir": str(job_dir / "output"),
        "stdout_log": str(job_dir / "stdout.log"),
        "stderr_log": str(job_dir / "stderr.log"),
        "status_file": str(job_dir / "status.json"),
        "runtime_sec": None,
        "return_code": None,
        "notebook_version": NOTEBOOK_VERSION,
    }
    if extra:
        metadata.update(extra)
    write_json(job_dir / "status.json", metadata)
    return metadata

def build_manifest_from_csv(csv_path: str, manifest_name: str = "batch_manifest") -> Path:
    df = pd.read_csv(csv_path).fillna("")
    records = []
    seen = set()
    for i, row in df.iterrows():
        rowd = {k: row[k] for k in df.columns}
        base_job_name = slugify(rowd.get("job_name", f"job_{i+1}"))
        yaml_data = build_yaml_from_row(rowd)
        yaml_text = yaml.safe_dump(yaml_data, sort_keys=False, allow_unicode=True)
        signature = sha1_text(yaml_text)
        dedup_note = "duplicate_content" if signature in seen else ""
        seen.add(signature)

        yaml_path = DIRS["yamls"] / f"{base_job_name}.yaml"
        with open(yaml_path, "w") as fh:
            fh.write(yaml_text)

        extra = {
            "mode": "csv",
            "row_index": int(i),
            "protein_length": len(clean_sequence(rowd.get("protein_sequence", ""))),
            "has_ligand": bool(str(rowd.get("ligand_smiles", "")).strip() or str(rowd.get("ligand_ccd", "")).strip()),
            "binder": str(rowd.get("binder", "")).strip(),
            "msa_mode": str(rowd.get("msa_mode", "server")).strip() or "server",
            "duplicate_flag": dedup_note,
            "notes": str(rowd.get("notes", "")).strip(),
        }
        records.append(create_job_record(base_job_name, str(yaml_path), str(csv_path), extra=extra))

    manifest = pd.DataFrame(records)
    out = DIRS["manifests"] / f"{slugify(manifest_name)}.csv"
    manifest.to_csv(out, index=False)
    return out

def build_manifest_from_yaml_dir(yaml_dir: str, manifest_name: str = "yaml_manifest") -> Path:
    yaml_dir = Path(yaml_dir)
    records = []
    for y in sorted(list(yaml_dir.glob("*.yaml")) + list(yaml_dir.glob("*.yml"))):
        records.append(create_job_record(y.stem, str(y), str(yaml_dir), extra={"mode": "yaml_zip"}))
    out = DIRS["manifests"] / f"{slugify(manifest_name)}.csv"
    pd.DataFrame(records).to_csv(out, index=False)
    return out

def _normalize_ids(id_value: Any) -> List[str]:
    if isinstance(id_value, list):
        return [str(x).strip() for x in id_value if str(x).strip()]
    if id_value is None:
        return []
    text = str(id_value).strip()
    return [text] if text else []

def validate_yaml_job(yaml_path: str) -> List[str]:
    issues: List[str] = []
    path = Path(yaml_path)
    if not path.exists():
        return [f"Missing YAML: {yaml_path}"]
    try:
        with open(path) as fh:
            data = yaml.safe_load(fh)
    except Exception as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["Top-level YAML must be a mapping"]
    seqs = data.get("sequences", [])
    if not isinstance(seqs, list) or not seqs:
        return ["'sequences' must be a non-empty list"]

    protein_count = 0
    ligand_ids: List[str] = []
    for entry in seqs:
        if not isinstance(entry, dict) or len(entry) != 1:
            issues.append(f"Invalid sequence entry: {entry}")
            continue
        entity, payload = next(iter(entry.items()))
        payload = payload or {}
        if entity == "protein":
            protein_count += 1
            seq = clean_sequence(payload.get("sequence", ""))
            if not seq:
                issues.append("Protein sequence empty")
            elif not AA_RE.match(seq):
                issues.append("Protein sequence contains unsupported characters")
            if len(seq) > 2500:
                issues.append("Protein longer than 2500 aa; likely memory-heavy")
            if "msa" in payload and str(payload.get("msa", "")).strip() == "":
                issues.append("Protein msa field is empty; set `msa: empty` or a valid MSA path")
        elif entity == "ligand":
            smiles = str(payload.get("smiles", "")).strip()
            ccd = str(payload.get("ccd", "")).strip()
            if bool(smiles) == bool(ccd):
                issues.append("Ligand must define exactly one of smiles or ccd")
            ligand_ids.extend(_normalize_ids(payload.get("id")))
        elif entity in {"dna", "rna"}:
            seq = clean_sequence(payload.get("sequence", ""))
            if not seq:
                issues.append(f"{entity} sequence empty")
        else:
            issues.append(f"Unsupported entity type: {entity}")

    if protein_count == 0:
        issues.append("At least one protein entry is required")

    for tmpl in data.get("templates", []) or []:
        candidate = tmpl.get("pdb") or tmpl.get("cif")
        if candidate and not Path(candidate).exists():
            issues.append(f"Template file not found: {candidate}")

    for prop in data.get("properties", []) or []:
        if "affinity" in prop:
            binder = str((prop.get("affinity") or {}).get("binder", "")).strip()
            if not binder:
                issues.append("Affinity property has empty binder")
            elif binder not in set(ligand_ids):
                issues.append(f"Affinity binder '{binder}' is not a ligand id")

    return issues

def validate_manifest(manifest_path: str) -> pd.DataFrame:
    df = pd.read_csv(manifest_path).fillna("")
    rows = []
    for _, row in df.iterrows():
        issues = validate_yaml_job(row["yaml_path"])
        job_size = "heavy" if int(row.get("protein_length", 0) or 0) > 1500 else "normal"
        rows.append({
            "job_id": row["job_id"],
            "job_name": row["job_name"],
            "yaml_path": row["yaml_path"],
            "issue_count": len(issues),
            "issues": " | ".join(issues),
            "job_size_estimate": job_size,
            "status": row.get("status", "PENDING"),
        })
    out_df = pd.DataFrame(rows)
    out_df.to_csv(DIRS["summaries"] / "validation_report.csv", index=False)
    return out_df

def preflight_manifest(manifest_path: str, run_params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    run_params = run_params or default_run_params()
    df = pd.read_csv(manifest_path).fillna("")
    rows = []
    for _, row in df.iterrows():
        issues = validate_yaml_job(row["yaml_path"])
        warnings = []
        msa_mode = str(row.get("msa_mode", "server")).strip().lower()
        if msa_mode not in {"server", "none", ""}:
            warnings.append(f"Unrecognized msa_mode={msa_mode}; expected server or none")
        if run_params.get("output_format", "pdb") not in {"pdb", "mmcif", "cif"}:
            warnings.append("output_format should be one of pdb/mmcif/cif")
        if int(run_params.get("sampling_steps", 200)) < 100:
            warnings.append("sampling_steps < 100 may reduce prediction quality")
        rows.append({
            "job_id": row["job_id"],
            "job_name": row["job_name"],
            "issue_count": len(issues),
            "warning_count": len(warnings),
            "issues": " | ".join(issues),
            "warnings": " | ".join(warnings),
            "ready_to_run": len(issues) == 0,
        })
    out = pd.DataFrame(rows)
    out.to_csv(DIRS["summaries"] / "preflight_report.csv", index=False)
    return out

def update_manifest_status(manifest_path: str) -> pd.DataFrame:
    df = pd.read_csv(manifest_path).fillna("")
    fresh = []
    for _, row in df.iterrows():
        status_file = Path(row["status_file"])
        current = read_json(status_file, default={})
        if current:
            for key, val in current.items():
                row[key] = val
        fresh.append(dict(row))
    out = pd.DataFrame(fresh)
    out.to_csv(manifest_path, index=False)
    return out

def _find_model_structure(job_output_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    patterns = [
        (str(job_output_dir / "**" / "*_model_0.pdb"), "pdb"),
        (str(job_output_dir / "**" / "*_model_0.cif"), "cif"),
        (str(job_output_dir / "**" / "*_model_0.mmcif"), "cif"),
        (str(job_output_dir / "**" / "*.pdb"), "pdb"),
        (str(job_output_dir / "**" / "*.cif"), "cif"),
        (str(job_output_dir / "**" / "*.mmcif"), "cif"),
    ]
    for pat, fmt in patterns:
        found = glob.glob(pat, recursive=True)
        if found:
            return sorted(found)[0], fmt
    return None, None

def _collect_metrics(job_output_dir: Path) -> Dict[str, Any]:
    model_path, model_format = _find_model_structure(job_output_dir)
    metrics: Dict[str, Any] = {
        "model_path": model_path,
        "model_format": model_format,
        "confidence_json": None,
        "affinity_json": None,
        "confidence_score": None,
        "ptm": None,
        "iptm": None,
        "complex_plddt": None,
        "complex_iplddt": None,
        "complex_pde": None,
        "complex_ipde": None,
        "ligand_iptm": None,
        "protein_iptm": None,
        "affinity_pred_value": None,
        "affinity_probability_binary": None,
        "plddt": None,
        "affinity_score": None,
        "affinity_probability": None,
    }

    json_candidates = glob.glob(str(job_output_dir / "**" / "*.json"), recursive=True)
    for jc in json_candidates:
        name = Path(jc).name.lower()
        try:
            with open(jc) as fh:
                data = json.load(fh)
        except Exception:
            continue

        confidence_keys = {"confidence_score", "ptm", "iptm", "complex_plddt", "complex_pde"}
        affinity_keys = {"affinity_pred_value", "affinity_probability_binary"}

        if "confidence" in name or (confidence_keys & set(data.keys())):
            metrics["confidence_json"] = jc
            for key in ["confidence_score", "ptm", "iptm", "complex_plddt", "complex_iplddt", "complex_pde", "complex_ipde", "ligand_iptm", "protein_iptm", "plddt"]:
                if key in data:
                    metrics[key] = data.get(key)

        if "affinity" in name or (affinity_keys & set(data.keys())):
            metrics["affinity_json"] = jc
            if "affinity_pred_value" in data:
                metrics["affinity_pred_value"] = data.get("affinity_pred_value")
            if "affinity_probability_binary" in data:
                metrics["affinity_probability_binary"] = data.get("affinity_probability_binary")

    if metrics["plddt"] is None and metrics["complex_plddt"] is not None:
        metrics["plddt"] = metrics["complex_plddt"]
    if metrics["affinity_score"] is None and metrics["affinity_pred_value"] is not None:
        metrics["affinity_score"] = metrics["affinity_pred_value"]
    if metrics["affinity_probability"] is None and metrics["affinity_probability_binary"] is not None:
        metrics["affinity_probability"] = metrics["affinity_probability_binary"]

    return metrics

def diagnose_failure(stderr_text: str) -> Dict[str, str]:
    text = (stderr_text or "").lower()
    if not text.strip():
        return {"likely_cause": "No stderr output", "suggested_fix": "Check stdout log and job status JSON for traceback."}
    if "cuda out of memory" in text or "outofmemory" in text:
        return {"likely_cause": "GPU memory exhaustion", "suggested_fix": "Reduce sampling_steps/diffusion_samples, process fewer heavy jobs, or switch to larger GPU."}
    if "msa" in text and ("missing" in text or "not found" in text):
        return {"likely_cause": "MSA missing or inaccessible", "suggested_fix": "Use msa_mode=server or provide valid msa path in YAML/CSV."}
    if "template" in text and ("not found" in text or "missing" in text):
        return {"likely_cause": "Template file path invalid", "suggested_fix": "Upload template into inputs/templates and use absolute or correct relative path."}
    if "smiles" in text or "rdkit" in text:
        return {"likely_cause": "Ligand parsing issue", "suggested_fix": "Validate ligand_smiles syntax or switch to valid ligand_ccd."}
    return {"likely_cause": "Generic runtime failure", "suggested_fix": "Inspect stderr traceback and rerun with fewer jobs to isolate."}

def _safe_run_capture(cmd: List[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True)
        return (out.stdout or out.stderr or "").strip()
    except Exception as e:
        return f"<unavailable: {e}>"

def capture_run_context(run_params: Dict[str, Any]) -> Path:
    context = {
        "captured_at": now_iso(),
        "notebook_version": NOTEBOOK_VERSION,
        "run_params": run_params,
        "python_version": _safe_run_capture(["python", "--version"]),
        "pip_freeze_head": _safe_run_capture(["python", "-m", "pip", "freeze"]).splitlines()[:40],
        "boltz_help": _safe_run_capture(["boltz", "--help"]).splitlines()[:10],
        "boltz_git_commit": None,
    }
    git_dir = Path("/content/boltz/.git")
    if git_dir.exists():
        context["boltz_git_commit"] = _safe_run_capture(["git", "-C", "/content/boltz", "rev-parse", "HEAD"])
    out = WORK_ROOT / "run_context.json"
    write_json(out, context)
    return out

def _build_boltz_cmd(yaml_path: Path, out_dir: Path, run_params: Dict[str, Any], use_server: bool) -> List[str]:
    cmd = [
        "boltz", "predict", str(yaml_path),
        "--out_dir", str(out_dir),
        "--recycling_steps", str(run_params["recycling_steps"]),
        "--sampling_steps", str(run_params["sampling_steps"]),
        "--diffusion_samples", str(run_params["diffusion_samples"]),
        "--step_scale", str(run_params["step_scale"]),
        "--max_msa_seqs", str(run_params["max_msa_seqs"]),
        "--msa_pairing_strategy", str(run_params["msa_pairing_strategy"]),
        "--output_format", str(run_params.get("output_format", "pdb")),
    ]
    if "max_parallel_samples" in run_params:
        cmd.extend(["--max_parallel_samples", str(run_params["max_parallel_samples"])])
    if use_server:
        cmd.insert(3, "--use_msa_server")
    if bool(run_params.get("use_potentials", False)):
        cmd.append("--use_potentials")
    if bool(run_params.get("override", False)):
        cmd.append("--override")
    return cmd

def run_single_job(job: Dict[str, Any], run_params: Dict[str, Any]) -> Dict[str, Any]:
    job_dir = Path(job["job_dir"]); out_dir = Path(job["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    status = read_json(job_dir / "status.json", default=job)
    status["status"] = "RUNNING"
    status["started_at"] = now_iso()
    write_json(job_dir / "status.json", status)

    yaml_path = Path(job["yaml_path"]); yaml_text = yaml_path.read_text()
    yaml_has_explicit_msa = bool(re.search(r"^[ \t]*msa\s*:", yaml_text, flags=re.MULTILINE))
    msa_mode = str(job.get("msa_mode", "server")).lower().strip()
    use_server = (msa_mode != "none") and (not yaml_has_explicit_msa)

    cmd = _build_boltz_cmd(yaml_path, out_dir, run_params, use_server)
    status["command"] = " ".join(cmd)
    write_json(job_dir / "status.json", status)

    t0 = time.time()
    with open(job["stdout_log"], "w") as fout, open(job["stderr_log"], "w") as ferr:
        proc = subprocess.run(cmd, stdout=fout, stderr=ferr, text=True)
    runtime_sec = round(time.time() - t0, 3)

    status = read_json(job_dir / "status.json", default=job)
    status["runtime_sec"] = runtime_sec
    status["return_code"] = proc.returncode
    status["finished_at"] = now_iso()

    if proc.returncode == 0:
        status["status"] = "COMPLETED"
        status.update(_collect_metrics(out_dir))
    else:
        status["status"] = "FAILED"
        stderr_text = Path(job["stderr_log"]).read_text() if Path(job["stderr_log"]).exists() else ""
        status["diagnostic"] = diagnose_failure(stderr_text)

    write_json(job_dir / "status.json", status)
    return status

def run_manifest(manifest_path: str, run_params: Optional[Dict[str, Any]] = None, max_jobs: Optional[int] = None, verbose: bool = True) -> pd.DataFrame:
    run_params = run_params or default_run_params()
    capture_run_context(run_params)
    df = update_manifest_status(manifest_path)
    executed = 0
    refreshed_rows = []

    runnable = []
    for _, row in df.iterrows():
        status = str(row.get("status", "PENDING"))
        skip_completed = status == "COMPLETED" and bool(run_params.get("skip_completed", True))
        skip_failed = status == "FAILED" and not bool(run_params.get("retry_failed", False))
        runnable.append(not (skip_completed or skip_failed))

    planned_total = int(sum(runnable))
    if max_jobs is not None:
        planned_total = min(planned_total, int(max_jobs))

    if verbose:
        print(f"Run started: total jobs in manifest={len(df)}, runnable={planned_total}", flush=True)

    for _, row in df.iterrows():
        job = dict(row)
        current_status = str(job.get("status", "PENDING"))
        if current_status == "COMPLETED" and bool(run_params.get("skip_completed", True)):
            refreshed_rows.append(job); continue
        if current_status == "FAILED" and not bool(run_params.get("retry_failed", False)):
            refreshed_rows.append(job); continue

        if max_jobs is not None and executed >= int(max_jobs):
            refreshed_rows.append(job)
            continue

        job_name = str(job.get("job_name", job.get("job_id", "unknown_job")))
        if verbose:
            remaining_before = max(planned_total - executed, 0)
            print(f"[{executed + 1}/{planned_total}] Running job: {job_name} | remaining (incl current): {remaining_before}", flush=True)

        try:
            result = run_single_job(job, run_params)
        except Exception as e:
            result = read_json(Path(job["job_dir"]) / "status.json", default=job)
            result["status"] = "FAILED"
            result["runtime_sec"] = None
            result["return_code"] = -999
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc(limit=5)
            write_json(Path(job["job_dir"]) / "status.json", result)
            if not bool(run_params.get("continue_on_error", True)):
                refreshed_rows.append(result)
                break
        refreshed_rows.append(result)
        executed += 1

        if verbose:
            result_status = str(result.get("status", "UNKNOWN"))
            remaining_after = max(planned_total - executed, 0)
            print(f"Finished: {job_name} -> {result_status} | launched {executed}/{planned_total} | remaining {remaining_after}", flush=True)

    out = pd.DataFrame(refreshed_rows)
    out.to_csv(manifest_path, index=False)
    if verbose:
        print(f"Run complete: launched {executed} job(s)", flush=True)
    return update_manifest_status(manifest_path)

def _pick_sort_metric(df: pd.DataFrame) -> Optional[str]:
    candidates = [
        "affinity_probability_binary",
        "confidence_score",
        "iptm",
        "complex_plddt",
        "ptm",
        "affinity_pred_value",
        "complex_pde",
        "plddt",
    ]
    for col in candidates:
        if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().any():
            return col
    return None

def _sort_df_by_metric(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    if metric not in df.columns:
        return df
    temp = df.copy()
    temp[metric] = pd.to_numeric(temp[metric], errors="coerce")
    direction = METRIC_DIRECTION.get(metric, "desc")
    ascending = direction == "asc"
    return temp.sort_values(by=metric, ascending=ascending, na_position="last")

def summarize_manifest(manifest_path: str) -> pd.DataFrame:
    df = update_manifest_status(manifest_path)
    records = []
    for _, row in df.iterrows():
        status = read_json(Path(row["status_file"]), default=dict(row))
        rec = {
            "job_id": status.get("job_id"),
            "job_name": status.get("job_name"),
            "status": status.get("status"),
            "runtime_sec": status.get("runtime_sec"),
            "confidence_score": status.get("confidence_score"),
            "ptm": status.get("ptm"),
            "iptm": status.get("iptm"),
            "complex_plddt": status.get("complex_plddt"),
            "complex_pde": status.get("complex_pde"),
            "affinity_pred_value": status.get("affinity_pred_value"),
            "affinity_probability_binary": status.get("affinity_probability_binary"),
            "model_path": status.get("model_path"),
            "model_format": status.get("model_format"),
            "yaml_path": status.get("yaml_path"),
            "output_dir": status.get("output_dir"),
            "diagnostic": status.get("diagnostic"),
            "plddt": status.get("plddt"),
            "affinity_score": status.get("affinity_score"),
            "affinity_probability": status.get("affinity_probability"),
        }
        records.append(rec)

    out = pd.DataFrame(records)
    sort_col = _pick_sort_metric(out)
    if sort_col:
        out = _sort_df_by_metric(out, sort_col)
        out["rank_metric"] = sort_col
        out["rank_direction"] = METRIC_DIRECTION.get(sort_col, "desc")

    out.to_csv(DIRS["summaries"] / "batch_results_summary.csv", index=False)
    return out

def rank_results(summary_df: pd.DataFrame, top_n: int = 10, status_filter: str = "COMPLETED", metric: str = "auto") -> pd.DataFrame:
    df = summary_df.copy()
    if status_filter != "ALL" and "status" in df.columns:
        df = df[df["status"] == status_filter].copy()
    sort_col = _pick_sort_metric(df) if metric == "auto" else metric
    if sort_col:
        df = _sort_df_by_metric(df, sort_col)
        df["rank_metric"] = sort_col
        df["rank_direction"] = METRIC_DIRECTION.get(sort_col, "desc")
    return df.head(int(top_n))

def failure_diagnostics_table(manifest_path: str) -> pd.DataFrame:
    df = update_manifest_status(manifest_path)
    failed = df[df["status"] == "FAILED"].copy() if "status" in df.columns else pd.DataFrame()
    rows = []
    for _, row in failed.iterrows():
        status = read_json(Path(row["status_file"]), default={})
        diag = status.get("diagnostic", {}) if isinstance(status, dict) else {}
        rows.append({
            "job_id": row.get("job_id"),
            "job_name": row.get("job_name"),
            "likely_cause": diag.get("likely_cause", ""),
            "suggested_fix": diag.get("suggested_fix", ""),
            "stderr_log": row.get("stderr_log", ""),
        })
    out = pd.DataFrame(rows)
    out.to_csv(DIRS["summaries"] / "failure_diagnostics.csv", index=False)
    return out

def create_export_zip(manifest_path: str, export_name: str = "boltz_batch_export") -> Path:
    export_path = DIRS["exports"] / f"{slugify(export_name)}.zip"
    summary_path = DIRS["summaries"] / "batch_results_summary.csv"
    if not summary_path.exists():
        summarize_manifest(manifest_path)

    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(manifest_path, arcname=f"manifests/{Path(manifest_path).name}")
        for optional in [
            WORK_ROOT / "run_context.json",
            DIRS["summaries"] / "batch_results_summary.csv",
            DIRS["summaries"] / "validation_report.csv",
            DIRS["summaries"] / "preflight_report.csv",
            DIRS["summaries"] / "failure_diagnostics.csv",
        ]:
            if optional.exists():
                zf.write(optional, arcname=str(optional.relative_to(WORK_ROOT)))
        for job_dir in sorted(DIRS["jobs"].glob("job_*")):
            for path in job_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(WORK_ROOT)))
    return export_path

def progress_table(manifest_path: str) -> pd.DataFrame:
    df = update_manifest_status(manifest_path)
    keep = [c for c in ["job_id", "job_name", "status", "runtime_sec", "return_code", "model_path"] if c in df.columns]
    return df[keep].copy()

def manifest_overview(manifest_path: str) -> Dict[str, Any]:
    df = update_manifest_status(manifest_path)
    counts = df["status"].fillna("PENDING").value_counts().to_dict()
    return {
        "total": int(len(df)),
        "completed": int(counts.get("COMPLETED", 0)),
        "failed": int(counts.get("FAILED", 0)),
        "running": int(counts.get("RUNNING", 0)),
        "pending": int(counts.get("PENDING", 0)),
        "skipped": int(counts.get("SKIPPED", 0)),
    }
