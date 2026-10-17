import sys
from pathlib import Path

import pandas as pd
import pytest

from boltz2nb import batch, msa_cache
from boltz2nb.run_params import apply_profile


@pytest.fixture(autouse=True)
def work_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_FOR_FAKE", sys.executable)
    batch.set_work_root(tmp_path / "boltz_batch")
    batch.ensure_workspace()
    return batch.WORK_ROOT


def write_csv(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_csv_manifest_and_validation(tmp_path):
    csv = write_csv(tmp_path / "in.csv", [
        {"job_name": "apo", "protein_sequence": "MKTAYIAK"},
        {"job_name": "holo", "protein_sequence": "MKTAYIAK", "ligand_smiles": "CC(=O)Oc1ccccc1C(=O)O", "binder": "L"},
        {"job_name": "complex", "protein_sequence": "MKTAYIAK:MKTAYIAK", "dna_sequence": "ACGT", "msa_mode": "none"},
        {"job_name": "bad", "protein_sequence": "MKT1"},
    ])
    m = batch.build_manifest_from_csv(str(csv))
    df = pd.read_csv(m, dtype=str).fillna("")
    assert list(df["job_name"]) == ["apo", "holo", "complex", "bad"]
    assert df.loc[3, "status"] == "FAILED" and "invalid characters" in df.loc[3, "validation"]
    holo = (Path(df.loc[1, "yaml_path"])).read_text()
    assert "id: [L]" in holo and "affinity" in holo and "binder: L" in holo
    cx = (Path(df.loc[2, "yaml_path"])).read_text()
    assert cx.count("protein:") == 2 and "dna:" in cx and "msa: empty" in cx
    rep = batch.validate_manifest(str(m))
    assert rep["valid"].tolist() == [True, True, True, False]
    pre = batch.preflight_manifest(str(m))
    assert "single-sequence" in pre.loc[2, "warnings"]


def test_fasta_manifest(tmp_path):
    fa = tmp_path / "s.fasta"
    fa.write_text(">p1 desc\nMKTAYIAK\n>p2\nMKTAY:IAKQ\n")
    m = batch.build_manifest_from_fasta(str(fa))
    df = pd.read_csv(m, dtype=str)
    assert list(df["job_name"]) == ["p1", "p2"] and df["validation"].isna().all()


def test_run_manifest_with_fake_boltz(tmp_path, fake_boltz):
    csv = write_csv(tmp_path / "in.csv", [
        {"job_name": "ok1", "protein_sequence": "MKTAYIAK", "ligand_smiles": "c1ccccc1O", "binder": "B", "affinity": "true"},
        {"job_name": "boom", "protein_sequence": "MKTFAILMEAK"},
        {"job_name": "ok2", "protein_sequence": "MKTAYIAK", "msa_mode": "none"},
    ])
    m = batch.build_manifest_from_csv(str(csv))
    params = apply_profile("fast", {"diffusion_samples": 2})
    df = batch.run_manifest(str(m), params, verbose=False)
    st = dict(zip(df["job_name"], df["status"]))
    assert st == {"ok1": "COMPLETED", "boom": "FAILED", "ok2": "COMPLETED"}
    summ = batch.summarize_manifest(str(m))
    ok1 = summ[summ.job_name == "ok1"].iloc[0]
    assert ok1["n_models"] == 2 and ok1["affinity_probability_binary"] == pytest.approx(0.379, abs=1e-3)
    assert ok1["ic50_um"] == pytest.approx(2.77, abs=0.01)
    ranked = batch.rank_results(summ, metric="affinity_probability_binary")
    assert list(ranked["job_name"]) == ["ok1"]
    ranked = batch.rank_results(summ, metric="confidence_score")
    assert set(ranked["job_name"]) == {"ok1", "ok2"}
    diag = batch.failure_diagnostics_table(str(m))
    assert diag.iloc[0]["job_name"] == "boom" and "memory" in diag.iloc[0]["likely_cause"]
    # resume: completed jobs are skipped, failed retried only when asked
    df2 = batch.run_manifest(str(m), dict(params, retry_failed=False), verbose=False)
    assert dict(zip(df2["job_name"], df2["status"]))["boom"] == "FAILED"
    ctx = batch.read_json(Path(df.loc[0, "job_dir"]) / "run_context.json")
    assert ctx["command"][0] == "boltz" and "--use_msa_server" in ctx["command"]
    ctx2 = batch.read_json(Path(df.loc[2, "job_dir"]) / "run_context.json")
    assert "--use_msa_server" not in ctx2["command"]
    z = batch.create_export_zip(str(m))
    assert z.exists() and z.stat().st_size > 0
    assert batch.manifest_overview(str(m))["COMPLETED"] == 2


def test_msa_cache_roundtrip(tmp_path, fake_boltz):
    from boltz2nb.runner import build_boltz_cmd, run_boltz
    from boltz2nb.yaml_builder import build_yaml, dump_yaml, simple_spec
    cache = tmp_path / "msa_cache"
    y = tmp_path / "j.yaml"
    y.write_text(dump_yaml(build_yaml(simple_spec(["MKTAYIAK", "PEPTIDE"]))))
    applied, msg = msa_cache.apply_cache(y, cache)
    assert not applied and "2/2" in msg[0]
    out = tmp_path / "out"
    run_boltz(build_boltz_cmd(y, out, {}), tmp_path / "log")
    stored = msa_cache.store(y, out, cache)
    assert len(stored) == 2
    applied, msg = msa_cache.apply_cache(y, cache)
    assert applied and "msa:" in y.read_text()
    cmd = build_boltz_cmd(y, out, {})
    assert "--use_msa_server" not in cmd


def test_notebook_contract_columns(tmp_path, fake_boltz):
    csv = write_csv(tmp_path / "in.csv", [
        {"job_name": "a", "protein_sequence": "MKTAYIAK"},
        {"job_name": "bad", "protein_sequence": "MKTAYIAK", "ligand_smiles": "C1CC", "binder": "B"},
    ])
    m = batch.build_manifest_from_csv(str(csv))
    df = pd.read_csv(m, dtype=str).fillna("")
    assert {"status_file", "stdout_log", "stderr_log", "yaml_path", "job_dir"} <= set(df.columns)
    val = batch.validate_manifest(str(m))
    assert list(val.columns) == ["job_name", "valid", "issue_count", "problems"]
    pre = batch.preflight_manifest(str(m), batch.apply_run_profile("fast", {"output_format": "cif"}))
    assert {"issue_count", "warning_count", "ready_to_run"} <= set(pre.columns)
    assert pre["ready_to_run"].tolist() == [True, False] or pre["ready_to_run"].tolist() == [True, True]
    params = batch.apply_run_profile("balanced")
    params.update({"output_format": "cif", "skip_completed": True, "retry_failed": False})
    res = batch.run_manifest(str(m), params, verbose=False)
    assert dict(zip(res["job_name"], res["status"]))["a"] == "COMPLETED"
    ctx = batch.read_json(Path(res.loc[0, "job_dir"]) / "run_context.json")
    assert ctx["command"][ctx["command"].index("--output_format") + 1] == "mmcif"
    summ = batch.summarize_manifest(str(m))
    assert {"rank_metric", "rank_direction", "model_format", "model_path"} <= set(summ.columns)
    assert summ["rank_metric"].iloc[0] in ("iptm", "confidence_score")
    assert len(batch.rank_results(summ, metric="auto", status_filter="ALL")) >= 1
    assert batch.discover_uploads() == {} or isinstance(batch.discover_uploads(), dict)
    p = batch.save_uploaded_file("x.csv", b"job_name\n", category="tables")
    assert Path(p).exists() and "inputs/tables" in p
    diag = batch.failure_diagnostics_table(str(m))
    assert "bad" in diag["job_name"].tolist()


def test_shim_reexports():
    import importlib.util
    spec = importlib.util.spec_from_file_location("Batch_Utils", Path(__file__).resolve().parents[1] / "scripts" / "batch_utils.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("run_manifest", "apply_run_profile", "discover_uploads", "save_uploaded_file", "capture_run_context",
                 "build_manifest_from_fasta", "create_export_zip", "failure_diagnostics_table"):
        assert callable(getattr(mod, name)), name


def test_job_names_from_headers_are_safe_folder_names(tmp_path):
    """A FASTA header can be arbitrarily long; the job name becomes a folder, so it must stay within filesystem limits."""
    from boltz2nb.batch import MAX_JOB_NAME, build_manifest_from_fasta, slugify

    assert len(slugify("x" * 500)) == MAX_JOB_NAME
    assert slugify("../etc/passwd") == "etc_passwd" and slugify("..") == "job" and slugify("") == "job"
    assert slugify(">sp|P1|ONE first") == "sp_P1_ONE_first"
    f = tmp_path / "long.fasta"
    f.write_text(">" + "h" * 400 + "\nMKTAYIAK\n")
    import pandas as pd
    df = pd.read_csv(build_manifest_from_fasta(str(f), "m"))     # used to raise OSError: File name too long
    assert len(df) == 1 and len(df.iloc[0]["job_name"]) <= MAX_JOB_NAME
