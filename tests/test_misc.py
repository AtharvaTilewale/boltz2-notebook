import sys
from types import SimpleNamespace

from boltz2nb import BOLTZ_COMMUNITY_PIN, BOLTZ_OFFICIAL_PIN, telemetry
from boltz2nb.diagnostics import diagnose_failure
from boltz2nb.install import install_commands, pick_boltz_requirement, pip_fallback_command
from boltz2nb.ligand import depict_svg, describe_smiles
from boltz2nb.paths import base_dir, is_colab, predictions_dir


def test_pick_boltz_requirement():
    assert pick_boltz_requirement(SimpleNamespace(major=3, minor=12)) == BOLTZ_OFFICIAL_PIN
    assert pick_boltz_requirement(SimpleNamespace(major=3, minor=13)) == BOLTZ_COMMUNITY_PIN
    assert "==" in BOLTZ_OFFICIAL_PIN and "==" in BOLTZ_COMMUNITY_PIN
    cmds = install_commands("/usr/bin/python3", requirement="boltz[cuda]==9.9")
    assert cmds[1][:4] == ["uv", "pip", "install", "--system"] and "boltz[cuda]==9.9" in cmds[1]
    assert pip_fallback_command()[-1] == "rdkit"


def test_diagnose_failure():
    assert "memory" in diagnose_failure("torch.OutOfMemoryError: CUDA out of memory").get("likely_cause").lower()
    assert "SMILES" in diagnose_failure("ValueError: Could not parse SMILES")["likely_cause"]
    assert "ColabFold" in diagnose_failure("requests.exceptions.ConnectionError: api.colabfold.com")["likely_cause"]
    assert "Unrecognised" in diagnose_failure("something odd\nlast line")["likely_cause"]


def test_telemetry_is_off_by_default(monkeypatch):
    monkeypatch.delenv("BOLTZ2NB_SEND_USAGE_STATS", raising=False)
    assert telemetry.enabled() is False
    assert telemetry.send("setup", endpoint="http://127.0.0.1:9/never") is False
    monkeypatch.setenv("BOLTZ2NB_SEND_USAGE_STATS", "1")
    assert telemetry.enabled() is True
    assert telemetry.send("setup", endpoint="") is False  # no endpoint configured -> nothing sent
    payload = telemetry.build_payload("setup", engine="boltz 2.2.1")
    assert set(payload) <= telemetry.ALLOWED_FIELDS and not any(k in payload for k in ("email", "username", "job_name"))


def test_ligand_helpers():
    d = describe_smiles("CC(=O)Oc1ccccc1C(=O)O")
    if d["valid"] is None:
        return
    assert d["formula"] == "C9H8O4" and d["heavy_atoms"] == 13 and d["message"] == ""
    assert describe_smiles("C1CC")["valid"] is False
    assert "salt" in describe_smiles("CCN.Cl")["message"]
    assert depict_svg("c1ccccc1").startswith("<?xml")


def test_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("BOLTZ2NB_BASE_DIR", str(tmp_path))
    assert base_dir() == tmp_path
    assert predictions_dir("job1") == tmp_path / "job1" / "boltz_results_job1" / "predictions" / "job1"
    monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
    sys.modules.pop("google.colab", None)
    assert is_colab() is False


def test_doctor_report(example_pred_dir, tmp_path, capsys):
    import shutil

    import numpy as np

    from boltz2nb.doctor import main, report
    # copy: the fixture is session-scoped and other tests rely on its contents
    pred = tmp_path / "prot_lig" / "boltz_results_prot_lig" / "predictions" / "prot_lig"
    shutil.copytree(example_pred_dir, pred)
    example_pred_dir = pred
    info = report(example_pred_dir)
    m = info["models"][0]
    assert m["plddt_len"] == 608 and m["match"] == "atomised" and m["pae_shape"] == [608, 608]
    assert info["affinity_files"] == ["affinity_prot_lig.json"]
    assert main([str(example_pred_dir)]) == 0
    np.savez_compressed(example_pred_dir / "plddt_prot_lig_model_0.npz", plddt=np.full(20, 0.8))
    assert main([str(example_pred_dir)]) == 1
    assert "No known token layout matches" in capsys.readouterr().out
