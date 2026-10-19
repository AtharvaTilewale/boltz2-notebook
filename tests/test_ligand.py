"""SMILES and CCD-code checks: every message names the problem, the network is never needed to find a typing slip, and an unreachable
component service is never reported as 'invalid'."""
import pytest

from boltz2nb import ligand
from boltz2nb.ui import callbacks as cb
from boltz2nb.yaml_builder import SpecError, build_yaml

rdkit = pytest.importorskip("rdkit", reason="RDKit is needed for the chemistry checks")

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"


@pytest.mark.parametrize(("smiles", "words"), [
    ("", "Enter a SMILES"),
    ("CC(=O)O aspirin", "cannot contain spaces"),
    ("CC(=O)Oc1ccccc1C(=O", "'(' is never closed"),
    ("CC(=O)O)", "')' has no matching"),
    ("C[C@H](N)C(=O)O]", "']' has no matching"),
    ("[NH3+C", "'[' is never closed"),
    ("c1ccccc", "Ring label 1 is opened but never closed"),
    ("C%10CC", "Ring label %10"),
    ("C%1CC", "two digits"),
    ("CC=O;N", "not allowed"),
    ("CN(C)(C)(C)C", "chemically invalid"),
    ("xyz", "not a valid SMILES"),
    ("[]", "not a valid SMILES"),
])
def test_invalid_smiles_get_a_specific_message(smiles, words):
    d = ligand.describe_smiles(smiles)
    assert d["valid"] is False and words in d["message"], d


@pytest.mark.parametrize("smiles", [ASPIRIN, "C[N+](C)(C)C", "c1ccc2c(c1)cccc2", "C[C@H](N)C(=O)O", "[Fe]", "c1cc%10ccccc1%10", "[Na+].[Cl-]"])
def test_valid_smiles_are_accepted(smiles):
    d = ligand.describe_smiles(smiles)
    assert d["valid"] is True and d["formula"] and d["heavy_atoms"] > 0, d


def test_a_salt_is_valid_but_flagged():
    d = ligand.describe_smiles("CCN.Cl")
    assert d["valid"] is True and "several fragments" in d["message"]


def test_text_problems_are_found_without_rdkit(monkeypatch):
    monkeypatch.setattr(ligand, "_rdkit", lambda: None)
    assert ligand.describe_smiles("c1ccccc")["valid"] is False                    # a typing slip needs no chemistry
    d = ligand.describe_smiles(ASPIRIN)
    assert d["valid"] is None and "RDKit is not installed" in d["message"] and "setup cell" in d["message"]
    assert ligand.depict_svg(ASPIRIN) is None


def test_the_drawing_is_an_html_safe_svg():
    svg = ligand.depict_svg(ASPIRIN)
    assert svg.startswith("<svg") and "<?xml" not in svg


# ------------------------------------------------------------------------------------------------ CCD codes
def test_a_known_code_is_found_with_its_details_and_a_drawing(ccd_service):
    d = ligand.describe_ccd(" sah ")
    assert d["valid"] is True and d["code"] == "SAH"
    assert d["name"] == "S-ADENOSYL-L-HOMOCYSTEINE" and d["formula"] == "C14H20N6O5S" and d["mol_weight"] == 384.411
    assert d["svg"].startswith("<svg")


def test_a_code_that_is_not_in_the_dictionary_is_invalid(ccd_service):
    d = ligand.describe_ccd("ZZZQ")
    assert d["valid"] is False and "not in the PDB Chemical Component Dictionary" in d["message"] and "SMILES" in d["message"]


@pytest.mark.parametrize("code", ["", "TOOLONG", "A-B", "AB CD", "a.b"])
def test_text_that_cannot_be_a_code_never_reaches_the_service(ccd_service, code):
    d = ligand.describe_ccd(code)
    assert d["valid"] is False and "not a CCD code" in d["message"]
    assert ccd_service.calls == []


def test_an_unreachable_service_is_unknown_not_invalid(ccd_service):
    ccd_service.offline = True
    d = ligand.describe_ccd("ATP")
    assert d["valid"] is None and "could not be reached" in d["message"]
    ccd_service.offline = False
    assert ligand.describe_ccd("ATP")["valid"] is True, "an unknown answer must not be remembered"


def test_offline_mode_sends_nothing(ccd_service, monkeypatch):
    monkeypatch.setenv("BOLTZ2NB_OFFLINE", "1")
    d = ligand.describe_ccd("ATP")
    assert d["valid"] is None and ccd_service.calls == []
    assert ligand.describe_ccd("not a code")["valid"] is False               # format checks still work


def test_answers_are_remembered_so_each_code_is_asked_once(ccd_service):
    for _ in range(3):
        ligand.describe_ccd("ATP"); ligand.describe_ccd("NOPE")
    assert ccd_service.calls == ["ATP", "NOPE"]


def test_a_component_whose_smiles_rdkit_rejects_still_validates(ccd_service, monkeypatch):
    ccd_service.records["ODD"] = {"chem_comp": {"name": "ODD", "formula": "X", "formula_weight": 1.0, "type": "non-polymer"},
                                  "rcsb_chem_comp_descriptor": {"SMILES": "not a smiles"}}
    d = ligand.describe_ccd("ODD")
    assert d["valid"] is True and d.get("svg") in (None, "")


# ------------------------------------------------------------------------------------------------ builder and callbacks
def payload(**ligand_fields):
    return {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTAYIAKQRQISFVKSHFSRQ", "msa": "server"}},
                          {"type": "ligand", "data": {"id": ["B"], **ligand_fields}}]}


def test_the_builder_refuses_text_that_is_not_a_ccd_code():
    with pytest.raises(SpecError, match="not a CCD code"):
        build_yaml(payload(ccd="TOOLONGCODE"))
    assert build_yaml(payload(ccd="sah"))["sequences"][1]["ligand"]["ccd"] == "SAH"


def test_the_builder_gives_the_specific_smiles_message():
    with pytest.raises(SpecError, match="never closed"):
        build_yaml(payload(smiles="CC(=O)Oc1ccccc1C(=O"))


def test_saving_a_missing_ccd_code_is_refused_with_the_reason(base_dir, ccd_service):
    r = cb.save_params(payload(ccd="ZZZQ"))
    assert r["status"] == "error" and "not in the PDB Chemical Component Dictionary" in r["message"]
    assert not (base_dir / "params.yaml").exists()


def test_saving_a_known_ccd_code_works_and_names_the_component(base_dir, ccd_service):
    r = cb.save_params(payload(ccd="SAH"))
    assert r["status"] == "ok" and any("S-ADENOSYL-L-HOMOCYSTEINE" in n for n in r["notes"])
    assert (base_dir / "params.yaml").exists()


def test_saving_is_never_blocked_by_an_unreachable_service(base_dir, ccd_service):
    ccd_service.offline = True
    r = cb.save_params(payload(ccd="ATP"))
    assert r["status"] == "ok" and any("could not confirm" in w and "ATP" in w for w in r["warnings"])


def test_describe_ligand_reply_for_each_kind(ccd_service):
    smiles = cb.describe_ligand({"kind": "smiles", "value": ASPIRIN})
    assert smiles["status"] == "ok" and smiles["valid"] is True and smiles["svg"].startswith("<svg") and smiles["formula"] == "C9H8O4"
    ccd = cb.describe_ligand({"kind": "ccd", "value": "ATP"})
    assert ccd["valid"] is True and ccd["name"].startswith("ADENOSINE") and ccd["svg"]
    assert cb.describe_ligand({"kind": "smiles", "value": "  "}) == {"status": "ok", "valid": None, "kind": "smiles", "empty": True}
    assert cb.describe_ligand({"kind": "ccd", "value": "QQQQQ"})["valid"] is False
