"""Batch orchestration: manifests, validation, execution, metrics, export.

Public functions keep the names used by ``batch/Boltz2_Batch_v1_beta.ipynb``;
``scripts/batch_utils.py`` re-exports them for backward compatibility.
"""
from __future__ import annotations

import csv
import json
import os
import re
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from . import __version__
from .analysis import load_job
from .diagnostics import diagnose_failure
from .paths import find_predictions_dir
from .run_params import DEFAULTS, apply_profile
from .runner import build_boltz_cmd, capture_run_context, run_boltz
from .yaml_builder import SpecError, build_yaml, dump_yaml, pop_warnings, simple_spec, yaml_has_explicit_msa

WORK_ROOT = Path(os.environ.get("BOLTZ2NB_BATCH_ROOT", "/content/boltz_batch"))
SUBDIRS = ("inputs", "uploads", "manifests", "jobs", "yaml_jobs", "summaries", "exports", "logs")
JOB_STATES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED")
REQUIRED_CSV = ("job_name", "protein_sequence")
OPTIONAL_CSV = ("ligand_smiles", "ligand_ccd", "binder", "dna_sequence", "rna_sequence", "msa_mode", "msa_path",
                "template_file", "template_chain_id", "template_id", "affinity", "notes")


def set_work_root(path: Path | str) -> Path:
    global WORK_ROOT
    WORK_ROOT = Path(path)
    return WORK_ROOT


def ensure_workspace() -> Path:
    for d in SUBDIRS:
        (WORK_ROOT / d).mkdir(parents=True, exist_ok=True)
    return WORK_ROOT


MAX_JOB_NAME = 80   # job names become folder and file names; keep well under the 255-byte filesystem limit


def slugify(name: str) -> str:
    """A job name that is safe as a folder name: ASCII letters, digits, ``_ . -``; never empty; never longer than MAX_JOB_NAME."""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name).strip()).strip("_.")
    return (s[:MAX_JOB_NAME].rstrip("_.") or "job") if s else "job"


def clean_sequence(seq: str) -> str:
    return re.sub(r"\s+", "", str(seq or "")).upper()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


# ----------------------------------------------------------------- inputs
def make_example_csv(path: Path | None = None) -> Path:
    ensure_workspace()
    path = path or WORK_ROOT / "inputs" / "example_batch.csv"
    rows = [
        {"job_name": "apo_example", "protein_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
         "ligand_smiles": "", "ligand_ccd": "", "binder": "", "msa_mode": "server", "affinity": "false"},
        {"job_name": "holo_example", "protein_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
         "ligand_smiles": "CC(=O)Oc1ccccc1C(=O)O", "ligand_ccd": "", "binder": "B", "msa_mode": "server", "affinity": "true"},
        {"job_name": "dimer_example", "protein_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGL:MKTAYIAKQRQISFVKSHFSRQLEERLGL",
         "ligand_smiles": "", "ligand_ccd": "", "binder": "", "msa_mode": "server", "affinity": "false"},
    ]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


def discover_uploads() -> dict[str, list[str]]:
    ensure_workspace()
    inv: dict[str, list[str]] = {}
    for sub in ("inputs", "inputs/tables", "inputs/yamls", "inputs/templates", "inputs/msas", "uploads", "yaml_jobs"):
        d = WORK_ROOT / sub
        if d.exists():
            files = sorted(str(f.relative_to(WORK_ROOT)) for f in d.iterdir() if f.is_file())
            if files:
                inv[sub] = files
    return inv


def save_uploaded_file(name: str, content: bytes, category: str = "uploads") -> str:
    ensure_workspace()
    sub = {"tables": "inputs/tables", "yamls": "inputs/yamls", "templates": "inputs/templates",
           "msas": "inputs/msas"}.get(category, "uploads")
    dest = WORK_ROOT / sub / Path(name).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content if isinstance(content, (bytes, bytearray)) else str(content).encode())
    return str(dest)


def default_run_params() -> dict[str, Any]:
    p = dict(DEFAULTS)
    p.update({"skip_completed": True, "retry_failed": False, "continue_on_error": True})
    return p


def apply_run_profile(profile: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    p = apply_profile(profile, overrides)
    p.update({k: v for k, v in default_run_params().items() if k not in p})
    return p


def normalize_run_params(run_params: dict[str, Any]) -> dict[str, Any]:
    p = default_run_params()
    p.update(run_params or {})
    if str(p.get("output_format", "pdb")).lower() in ("cif", "mmcif"):
        p["output_format"] = "mmcif"
    else:
        p["output_format"] = "pdb"
    return p


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def build_yaml_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """CSV row -> Boltz schema dict (raises SpecError on bad input)."""
    def get(k, default=""):
        v = row.get(k, default)
        return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()

    protein_chains = [clean_sequence(s) for s in get("protein_sequence").split(":") if clean_sequence(s)]
    if not protein_chains and not get("dna_sequence") and not get("rna_sequence"):
        raise SpecError("protein_sequence (or dna_sequence / rna_sequence) is required.")
    dna = [clean_sequence(s) for s in get("dna_sequence").split(":") if clean_sequence(s)]
    rna = [clean_sequence(s) for s in get("rna_sequence").split(":") if clean_sequence(s)]
    smiles, ccd = get("ligand_smiles"), get("ligand_ccd")
    msa_mode = (get("msa_mode") or "server").lower()
    msa_path = get("msa_path")
    msa = msa_path or ("empty" if msa_mode == "none" else None)
    affinity = _truthy(get("affinity")) or (bool(get("binder")) and (bool(smiles) or bool(ccd)) and get("affinity") == "")
    payload = simple_spec(protein_chains, ligand_smiles=smiles or None, ligand_ccd=ccd or None,
                          affinity=affinity, msa=msa, dna=dna or None, rna=rna or None)
    binder = get("binder").upper()
    if binder and payload["sequences"] and payload["sequences"][-1]["type"] == "ligand":
        payload["sequences"][-1]["data"]["id"] = [binder]
        if affinity:
            payload["properties"]["affinity_binder"] = binder
    template_file = get("template_file")
    if template_file:
        payload["templates"] = [{"path": resolve_upload(template_file), "chain_id": get("template_chain_id"),
                                 "template_id": get("template_id")}]
    doc = build_yaml(payload)
    pop_warnings(doc)
    return doc


def resolve_upload(name: str) -> str:
    """Accept absolute paths or bare filenames placed in uploads/ or inputs/."""
    p = Path(name)
    if p.is_absolute() and p.exists():
        return str(p)
    for sub in ("uploads", "inputs", "inputs/templates", "inputs/msas", "inputs/tables", "inputs/yamls"):
        cand = WORK_ROOT / sub / p.name
        if cand.exists():
            return str(cand)
    return str(p)


def _split_fasta_chain_sequences(text: str) -> list[str]:
    return [clean_sequence(s) for s in text.split(":") if clean_sequence(s)]


def build_manifest_from_fasta(fasta_path: str, manifest_name: str = "fasta_manifest") -> Path:
    from Bio import SeqIO
    ensure_workspace()
    rows = []
    for rec in SeqIO.parse(fasta_path, "fasta"):
        chains = _split_fasta_chain_sequences(str(rec.seq))
        rows.append({"job_name": slugify(rec.id), "protein_sequence": ":".join(chains), "msa_mode": "server"})
    return _write_manifest(rows, manifest_name, source="fasta")


def build_manifest_from_csv(csv_path: str, manifest_name: str = "batch_manifest") -> Path:
    ensure_workspace()
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    missing = [c for c in REQUIRED_CSV if c not in df.columns]
    if missing:
        raise SpecError(f"CSV is missing required column(s): {missing}")
    return _write_manifest(df.to_dict("records"), manifest_name, source="csv")


def build_manifest_from_yaml_dir(yaml_dir: str, manifest_name: str = "yaml_manifest") -> Path:
    ensure_workspace()
    rows = []
    for f in sorted(Path(yaml_dir).glob("*.y*ml")):
        rows.append({"job_name": slugify(f.stem), "yaml_source": str(f)})
    return _write_manifest(rows, manifest_name, source="yaml")


def extract_yaml_zip(zip_path: str) -> list[str]:
    ensure_workspace()
    dest = WORK_ROOT / "yaml_jobs"
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.lower().endswith((".yaml", ".yml")) and not n.startswith("__MACOSX")]
        for n in names:
            (dest / Path(n).name).write_bytes(z.read(n))
    return [str(dest / Path(n).name) for n in names]


def create_job_record(job_name: str, yaml_path: str, source: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    job_id = slugify(job_name)
    job_dir = WORK_ROOT / "jobs" / f"job_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    rec = {"job_id": job_id, "job_name": job_name, "yaml_path": yaml_path, "source": source,
           "job_dir": str(job_dir), "output_dir": str(job_dir / "output"),
           "stdout_log": str(job_dir / "boltz.log"), "stderr_log": str(job_dir / "boltz.log"),
           "status_file": str(job_dir / "status.json"),
           "status": "PENDING", "created_at": now_iso(), "validation": ""}
    rec.update(extra or {})
    write_json(job_dir / "status.json", rec)
    return rec


def _write_manifest(rows: list[dict[str, Any]], manifest_name: str, source: str) -> Path:
    records = []
    seen = set()
    for row in rows:
        name = slugify(row.get("job_name", "")) or f"job_{len(records) + 1}"
        if name in seen:
            raise SpecError(f"Duplicate job_name '{name}' in input.")
        seen.add(name)
        job_dir = WORK_ROOT / "jobs" / f"job_{name}"
        job_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = job_dir / f"{name}.yaml"
        validation = ""
        try:
            if source == "yaml":
                doc = yaml.safe_load(Path(row["yaml_source"]).read_text())
                yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False))
            else:
                doc = build_yaml_from_row(row)
                yaml_path.write_text(dump_yaml(doc))
        except (SpecError, Exception) as e:  # noqa: BLE001
            validation = f"{type(e).__name__}: {e}"
        extra = {k: row.get(k, "") for k in ("msa_mode", "notes", "binder")}
        extra["validation"] = validation
        if validation:
            extra["status"] = "FAILED"
            extra["diagnostic"] = {"likely_cause": "Input validation failed.", "suggested_fix": validation}
        records.append(create_job_record(name, str(yaml_path), source, extra))
    path = WORK_ROOT / "manifests" / f"{manifest_name}.csv"
    pd.DataFrame(records).to_csv(path, index=False)
    return path


# ----------------------------------------------------------------- validation
def validate_yaml_job(yaml_path: str) -> list[str]:
    problems: list[str] = []
    try:
        doc = yaml.safe_load(Path(yaml_path).read_text())
    except Exception as e:  # noqa: BLE001
        return [f"YAML parse error: {e}"]
    if not isinstance(doc, dict) or "sequences" not in doc:
        return ["YAML has no 'sequences' key."]
    ids = []
    for s in doc.get("sequences", []):
        if not isinstance(s, dict) or len(s) != 1:
            problems.append("Each sequence entry must have exactly one entity key.")
            continue
        (etype, body), = s.items()
        cid = body.get("id")
        cids = cid if isinstance(cid, list) else [cid]
        ids.extend(cids)
        if etype in ("protein", "dna", "rna") and not body.get("sequence"):
            problems.append(f"{etype} {cids} has no sequence.")
        if etype == "ligand" and bool(body.get("smiles")) == bool(body.get("ccd")):
            problems.append(f"ligand {cids} needs exactly one of smiles/ccd.")
        msa = body.get("msa")
        if msa and msa != "empty" and not Path(str(msa)).exists():
            problems.append(f"MSA file not found: {msa}")
    if len(ids) != len(set(ids)):
        problems.append("Duplicate chain IDs.")
    for t in doc.get("templates", []) or []:
        p = t.get("cif") or t.get("pdb")
        if p and not Path(p).exists():
            problems.append(f"Template file not found: {p}")
    for prop in doc.get("properties", []) or []:
        binder = (prop.get("affinity") or {}).get("binder")
        if binder and binder not in ids:
            problems.append(f"Affinity binder {binder} is not a chain.")
    return problems


def validate_manifest(manifest_path: str) -> pd.DataFrame:
    df = pd.read_csv(manifest_path, dtype=str).fillna("")
    out = []
    for _, row in df.iterrows():
        probs = [row["validation"]] if row.get("validation") else validate_yaml_job(row["yaml_path"])
        out.append({"job_name": row["job_name"], "valid": not probs, "issue_count": len(probs), "problems": "; ".join(probs)})
    rep = pd.DataFrame(out, columns=["job_name", "valid", "issue_count", "problems"])
    rep.to_csv(WORK_ROOT / "summaries" / "validation_report.csv", index=False)
    return rep


def preflight_manifest(manifest_path: str, run_params: dict[str, Any] | None = None) -> pd.DataFrame:
    run_params = normalize_run_params(run_params or {})
    df = pd.read_csv(manifest_path, dtype=str).fillna("")
    rows = []
    for _, row in df.iterrows():
        warn = []
        issues = [row["validation"]] if row.get("validation") else validate_yaml_job(row["yaml_path"])
        try:
            doc = yaml.safe_load(Path(row["yaml_path"]).read_text()) or {}
        except Exception:
            doc = {}
        n_res = sum(len(s[k].get("sequence", "")) * len(s[k].get("id", []) if isinstance(s[k].get("id"), list) else [1])
                    for s in doc.get("sequences", []) for k in s if k in ("protein", "dna", "rna"))
        if n_res > 1500:
            warn.append(f"{n_res} polymer residues: likely to exceed T4 memory; use fast profile or a larger GPU.")
        if run_params.get("diffusion_samples", 1) > 1 and n_res > 800:
            warn.append("Multiple diffusion samples on a large complex - consider max_parallel_samples=1.")
        if str(row.get("msa_mode", "")).lower() == "none":
            warn.append("single-sequence mode: expect lower accuracy.")
        rows.append({"job_name": row["job_name"], "polymer_residues": n_res, "issue_count": len(issues),
                     "warning_count": len(warn), "ready_to_run": not issues, "issues": "; ".join(issues),
                     "warnings": "; ".join(warn)})
    rep = pd.DataFrame(rows, columns=["job_name", "polymer_residues", "issue_count", "warning_count", "ready_to_run", "issues", "warnings"])
    rep.to_csv(WORK_ROOT / "summaries" / "preflight_report.csv", index=False)
    return rep


# ----------------------------------------------------------------- execution
def update_manifest_status(manifest_path: str) -> pd.DataFrame:
    df = pd.read_csv(manifest_path, dtype=str).fillna("")
    rows = []
    for _, row in df.iterrows():
        status = read_json(Path(row["job_dir"]) / "status.json", default=dict(row))
        merged = dict(row)
        merged.update({k: v for k, v in status.items() if not isinstance(v, (dict, list))})
        rows.append(merged)
    out = pd.DataFrame(rows)
    out.to_csv(manifest_path, index=False)
    return out


def _collect_metrics(job_output_dir: Path) -> dict[str, Any]:
    pred = find_predictions_dir(job_output_dir)
    metrics: dict[str, Any] = {"model_path": None, "predictions_dir": str(pred) if pred else None}
    if not pred:
        return metrics
    try:
        job = load_job(pred)
    except Exception as e:  # noqa: BLE001
        metrics["metrics_error"] = str(e)
        return metrics
    best = job.best
    metrics["model_path"] = str(best.structure_path)
    metrics["model_format"] = best.structure_path.suffix.lstrip(".")
    for k in ("confidence_score", "ptm", "iptm", "ligand_iptm", "protein_iptm", "complex_plddt",
              "complex_iplddt", "complex_pde", "complex_ipde"):
        metrics[k] = best.confidence.get(k)
    metrics["mean_plddt"] = float(best.plddt.mean())
    metrics["n_models"] = len(job.models)
    ens = job.ensemble_summary()
    if "confidence_score" in ens:
        metrics["confidence_score_sd"] = ens["confidence_score"]["sd"]
    ipae = best.interface_pae()
    if ipae:
        metrics["min_interface_pae"] = min(ipae.values())
    aff = job.affinity_summary()
    if aff:
        metrics["affinity_pred_value"] = aff["log10_ic50_um"]
        metrics["affinity_probability_binary"] = aff["binding_probability"]
        metrics["ic50_um"] = aff["ic50_um"]
        metrics["affinity_member_spread"] = aff["member_spread"]
    return metrics


def capture_batch_context(run_params: dict[str, Any]) -> Path:
    import platform
    import sys

    from .runner import gpu_info
    ctx = {"boltz2nb_version": __version__, "python": sys.version.split()[0], "platform": platform.platform(),
           "timestamp_utc": now_iso(), "run_params": run_params, **gpu_info()}
    path = WORK_ROOT / "run_context.json"
    write_json(path, ctx)
    return path


def run_single_job(job: dict[str, Any], run_params: dict[str, Any], on_line=None) -> dict[str, Any]:
    job_dir, out_dir = Path(job["job_dir"]), Path(job["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    status = read_json(job_dir / "status.json", default=dict(job))
    status.update({"status": "RUNNING", "started_at": now_iso()})
    write_json(job_dir / "status.json", status)
    yaml_path = Path(job["yaml_path"])
    msa_mode = str(job.get("msa_mode", "server") or "server").lower()
    use_server = (msa_mode != "none") and not yaml_has_explicit_msa(yaml_path.read_text())
    run_params = normalize_run_params(run_params)
    cmd = build_boltz_cmd(yaml_path, out_dir, run_params, use_msa_server=use_server)
    status["command"] = " ".join(cmd)
    write_json(job_dir / "status.json", status)
    write_json(job_dir / "run_context.json", capture_run_context(run_params, cmd, yaml_path))
    res = run_boltz(cmd, job_dir / "boltz.log", on_line=on_line)
    status.update({"runtime_sec": res["runtime_sec"], "return_code": res["return_code"], "finished_at": now_iso()})
    if res["return_code"] == 0:
        status["status"] = "COMPLETED"
        status.update(_collect_metrics(out_dir))
    else:
        status["status"] = "FAILED"
        status["diagnostic"] = diagnose_failure(Path(res["log_path"]).read_text())
    write_json(job_dir / "status.json", status)
    return status


def run_manifest(manifest_path: str, run_params: dict[str, Any] | None = None, max_jobs: int | None = None,
                 verbose: bool = True, on_line=None) -> pd.DataFrame:
    run_params = normalize_run_params(run_params or {})
    capture_batch_context(run_params)
    df = update_manifest_status(manifest_path)
    skip_completed = bool(run_params.get("skip_completed", True))
    retry_failed = bool(run_params.get("retry_failed", False))

    def runnable(status: str, validation: str) -> bool:
        if validation:
            return False
        if status == "COMPLETED" and skip_completed:
            return False
        if status == "FAILED" and not retry_failed:
            return False
        return True

    todo = [dict(r) for _, r in df.iterrows() if runnable(str(r.get("status", "PENDING")), str(r.get("validation", "")))]
    if max_jobs is not None:
        todo = todo[: int(max_jobs)]
    if verbose:
        print(f"Run started: {len(df)} job(s) in manifest, {len(todo)} to run", flush=True)
    for i, job in enumerate(todo, 1):
        name = job["job_name"]
        if verbose:
            print(f"[{i}/{len(todo)}] {name} ...", flush=True)
        try:
            result = run_single_job(job, run_params, on_line=on_line)
        except Exception as e:  # noqa: BLE001
            result = read_json(Path(job["job_dir"]) / "status.json", default=job)
            result.update({"status": "FAILED", "return_code": -999, "error": str(e),
                           "traceback": traceback.format_exc(limit=5)})
            write_json(Path(job["job_dir"]) / "status.json", result)
            if not bool(run_params.get("continue_on_error", True)):
                break
        if verbose:
            print(f"    -> {result.get('status')} ({result.get('runtime_sec', '?')} s)", flush=True)
    return update_manifest_status(manifest_path)


# ----------------------------------------------------------------- reporting
RANK_METRICS = {"confidence_score": False, "iptm": False, "ptm": False, "complex_plddt": False, "mean_plddt": False,
                "ligand_iptm": False, "affinity_probability_binary": False, "affinity_pred_value": True,
                "complex_pde": True, "min_interface_pae": True}  # value: ascending?


def summarize_manifest(manifest_path: str) -> pd.DataFrame:
    df = update_manifest_status(manifest_path)
    cols = ["job_name", "status", "runtime_sec", "n_models", "confidence_score", "confidence_score_sd", "ptm", "iptm",
            "ligand_iptm", "complex_plddt", "mean_plddt", "min_interface_pae", "affinity_probability_binary",
            "affinity_pred_value", "ic50_um", "affinity_member_spread", "model_path", "validation"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    if "model_format" not in df.columns:
        df["model_format"] = ""
    out = df[cols + ["model_format"]].copy()
    for c in cols[2:16]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    metric = _auto_metric(out)
    out.insert(2, "rank_metric", metric)
    out.insert(3, "rank_direction", "asc" if RANK_METRICS.get(metric, False) else "desc")
    out.to_csv(WORK_ROOT / "summaries" / "batch_results_summary.csv", index=False)
    return out


def _auto_metric(df: pd.DataFrame) -> str:
    """Affinity probability when any job has it, else interface ipTM, else confidence."""
    for m in ("affinity_probability_binary", "iptm", "confidence_score"):
        if m in df.columns and pd.to_numeric(df[m], errors="coerce").notna().any():
            return m
    return "confidence_score"


def rank_results(summary_df: pd.DataFrame, top_n: int = 10, status_filter: str = "COMPLETED",
                 metric: str = "confidence_score") -> pd.DataFrame:
    if metric in (None, "", "auto"):
        metric = _auto_metric(summary_df)
    if metric not in RANK_METRICS:
        raise ValueError(f"metric must be one of {sorted(RANK_METRICS)} or 'auto'")
    df = summary_df if status_filter in (None, "", "ALL") else summary_df[summary_df["status"] == status_filter]
    if metric not in df.columns:
        return df.head(0)
    df = df.dropna(subset=[metric])
    return df.sort_values(metric, ascending=RANK_METRICS[metric]).head(top_n).reset_index(drop=True)


def failure_diagnostics_table(manifest_path: str) -> pd.DataFrame:
    df = pd.read_csv(manifest_path, dtype=str).fillna("")
    rows = []
    for _, row in df.iterrows():
        st = read_json(Path(row["job_dir"]) / "status.json", default={})
        if st.get("status") == "FAILED" or row.get("validation"):
            d = st.get("diagnostic") or {}
            rows.append({"job_name": row["job_name"], "return_code": st.get("return_code"),
                         "likely_cause": d.get("likely_cause", ""), "suggested_fix": d.get("suggested_fix", ""),
                         "log": st.get("stdout_log", "")})
    out = pd.DataFrame(rows, columns=["job_name", "return_code", "likely_cause", "suggested_fix", "log"])
    out.to_csv(WORK_ROOT / "summaries" / "failure_diagnostics.csv", index=False)
    return out


def create_export_zip(manifest_path: str, export_name: str = "boltz_batch_export") -> Path:
    ensure_workspace()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = WORK_ROOT / "exports" / f"{export_name}_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("manifests", "jobs", "summaries"):
            for f in (WORK_ROOT / sub).rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(WORK_ROOT))
        ctx = WORK_ROOT / "run_context.json"
        if ctx.exists():
            z.write(ctx, ctx.name)
    return zip_path


def progress_table(manifest_path: str) -> pd.DataFrame:
    df = update_manifest_status(manifest_path)
    return df["status"].value_counts().rename_axis("status").reset_index(name="jobs")


def manifest_overview(manifest_path: str) -> dict[str, Any]:
    df = update_manifest_status(manifest_path)
    return {"manifest": manifest_path, "jobs": len(df), **df["status"].value_counts().to_dict()}
