import sys
from types import SimpleNamespace

from boltz2nb import BOLTZ_COMMUNITY_PIN, BOLTZ_OFFICIAL_PIN
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


# Excerpts of what boltz 2.2.1 really wrote (captured from runs on CPU); the frames and messages are verbatim.
EMPTY_MSA_WARNING = "Found explicit empty MSA for some proteins, will run these in single sequence mode. Keep in mind that the model predictions will be suboptimal without an MSA.\n"
REAL_TEMPLATE_PDB_WITHOUT_SEQRES = EMPTY_MSA_WARNING + """Traceback (most recent call last):
  File "boltz/main.py", line 551, in process_input
    target = parse_yaml(path, ccd, mol_dir, boltz2)
  File "boltz/data/parse/yaml.py", line 68, in parse_yaml
    return parse_boltz_schema(name, data, ccd, mol_dir, boltz2)
  File "boltz/data/parse/schema.py", line 1662, in parse_boltz_schema
    parsed_template = parse_pdb(
  File "boltz/data/parse/pdb.py", line 33, in parse_pdb
    return parse_mmcif(
  File "boltz/data/parse/mmcif.py", line 901, in parse_mmcif
    parsed_polymer = parse_polymer(
  File "boltz/data/parse/mmcif.py", line 588, in parse_polymer
    res_name = sequence[j]
IndexError: list index out of range
Failed to process t.yaml. Skipping. Error: list index out of range.
"""
REAL_TEMPLATE_WITH_BOLTZ_LIGAND = EMPTY_MSA_WARNING + """Traceback (most recent call last):
  File "boltz/data/parse/schema.py", line 1670, in parse_boltz_schema
    parsed_template = parse_mmcif(
  File "boltz/data/parse/mmcif.py", line 928, in parse_mmcif
    ligand_mol = get_mol(ligand.name, mols, moldir)
  File "boltz/data/mol.py", line 36, in load_molecules
    raise ValueError(msg)
ValueError: CCD component LIG1 not found!
Failed to process t.yaml. Skipping. Error: CCD component LIG1 not found!.
"""


def test_template_failures_are_named_as_template_problems_not_msa_or_ccd():
    for log in (REAL_TEMPLATE_PDB_WITHOUT_SEQRES, REAL_TEMPLATE_WITH_BOLTZ_LIGAND):
        d = diagnose_failure(log)
        assert d["likely_cause"] == "A template file could not be read by Boltz.", d
        assert "SEQRES" in d["suggested_fix"] and ".cif" in d["suggested_fix"] and "LIG1" in d["suggested_fix"]


def test_template_chain_name_error_explains_the_a1_naming():
    log = (EMPTY_MSA_WARNING + "Traceback (most recent call last):\n  File \"boltz/data/parse/schema.py\", line 1691, in parse_boltz_schema\n    raise ValueError(msg)\n"
           "ValueError: Template chain A assigned for template1UBQ is not one of the protein chains!\n"
           "Failed to process t.yaml. Skipping. Error: Template chain A assigned for template1UBQ is not one of the protein chains!.\n")
    d = diagnose_failure(log)
    assert "template chain" in d["likely_cause"].lower() and "A1" in d["suggested_fix"] and ".cif" in d["suggested_fix"], d


def test_a_chain_without_an_msa_is_not_a_failure_signature():
    # Boltz's warning for msa: empty used to make every later rule's failure read as "the MSA server failed"
    assert "memory" in diagnose_failure(EMPTY_MSA_WARNING + "torch.OutOfMemoryError: CUDA out of memory").get("likely_cause").lower()
    assert "killed" in diagnose_failure(EMPTY_MSA_WARNING + "Killed").get("likely_cause").lower()
    assert "dependency" in diagnose_failure(EMPTY_MSA_WARNING + "ModuleNotFoundError: No module named 'x'")["likely_cause"]
    assert "Unrecognised" in diagnose_failure(EMPTY_MSA_WARNING + "something odd happened")["likely_cause"]
    # real server trouble is still recognised
    for line in ("requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.colabfold.com')", "RuntimeError: MMSeqs2 API is giving errors",
                 "urllib3.exceptions.MaxRetryError: Max retries exceeded", "requests.exceptions.ReadTimeout"):
        assert "ColabFold" in diagnose_failure(EMPTY_MSA_WARNING + line)["likely_cause"], line


def test_an_input_boltz_skips_is_reported_with_the_engines_own_words():
    log = "Checking input data.\nTraceback (most recent call last):\n  File \"boltz/data/parse/yaml.py\", line 68, in parse_yaml\nKeyError: 'sequence'\nFailed to process job.yaml. Skipping. Error: 'sequence'.\n"
    d = diagnose_failure(log)
    assert d["likely_cause"] == "Boltz could not process the input and skipped it."
    assert "'sequence'" in d["suggested_fix"], d      # and a file name that merely contains "yaml." does not make it a YAML syntax error
    assert "malformed" not in d["likely_cause"]
    assert "malformed" in diagnose_failure("yaml.scanner.ScannerError: mapping values are not allowed here")["likely_cause"]


def test_diagnose_failure():
    assert "memory" in diagnose_failure("torch.OutOfMemoryError: CUDA out of memory").get("likely_cause").lower()
    assert "SMILES" in diagnose_failure("ValueError: Could not parse SMILES")["likely_cause"]
    assert "ColabFold" in diagnose_failure("requests.exceptions.ConnectionError: api.colabfold.com")["likely_cause"]
    assert "Unrecognised" in diagnose_failure("something odd\nlast line")["likely_cause"]


def test_ligand_helpers():
    d = describe_smiles("CC(=O)Oc1ccccc1C(=O)O")
    if d["valid"] is None:
        return
    assert d["formula"] == "C9H8O4" and d["heavy_atoms"] == 13 and d["message"] == ""
    assert describe_smiles("C1CC")["valid"] is False
    assert "salt" in describe_smiles("CCN.Cl")["message"]
    svg = depict_svg("c1ccccc1")
    assert svg.startswith("<svg") and "<?xml" not in svg      # an XML declaration is not valid inside an HTML fragment


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
