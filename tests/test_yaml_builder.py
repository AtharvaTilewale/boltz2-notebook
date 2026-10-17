import pytest
import yaml

from boltz2nb.yaml_builder import (
    SpecError,
    build_yaml,
    dump_yaml,
    pop_warnings,
    simple_spec,
    spec_summary,
    yaml_has_explicit_msa,
)


def payload(**kw):
    p = {"sequences": [
        {"type": "protein", "data": {"id": ["A"], "sequence": "mkt ayi\nak"}},
        {"type": "ligand", "data": {"id": ["B"], "smiles": "CC(=O)Oc1ccccc1C(=O)O"}}],
        "constraints": {}, "templates": [], "properties": {"affinity_binder": "b"}}
    p.update(kw)
    return p


def test_basic_roundtrip():
    doc = build_yaml(payload())
    text = dump_yaml(doc)
    back = yaml.safe_load(text)
    assert back["version"] == 1
    assert back["sequences"][0]["protein"] == {"id": ["A"], "sequence": "MKTAYIAK"}
    assert back["sequences"][1]["ligand"]["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert back["properties"] == [{"affinity": {"binder": "B"}}]
    assert "id: [A]" in text and "smiles: 'CC(=O)Oc1ccccc1C(=O)O'" in text


def test_invalid_protein_characters():
    p = payload(); p["sequences"][0]["data"]["sequence"] = "MKTB1"
    with pytest.raises(SpecError, match="invalid characters"):
        build_yaml(p)


def test_dna_rna_alphabets():
    p = payload(); p["properties"] = {}
    p["sequences"] = [{"type": "dna", "data": {"id": "D", "sequence": "acgt"}},
                      {"type": "rna", "data": {"id": "R", "sequence": "ACGU"}}]
    doc = build_yaml(p)
    assert "dna" in doc["sequences"][0] and "rna" in doc["sequences"][1]
    p["sequences"][0]["data"]["sequence"] = "ACGU"
    with pytest.raises(SpecError):
        build_yaml(p)


def test_duplicate_chain_ids():
    p = payload(); p["sequences"][1]["data"]["id"] = ["A"]
    with pytest.raises(SpecError, match="more than once"):
        build_yaml(p)


def test_ligand_needs_exactly_one_of_ccd_smiles():
    p = payload(); p["sequences"][1]["data"]["ccd"] = "HEM"
    with pytest.raises(SpecError, match="exactly one"):
        build_yaml(p)


def test_bad_smiles_rejected():
    pytest.importorskip("rdkit")
    p = payload(); p["sequences"][1]["data"]["smiles"] = "C1CC"
    with pytest.raises(SpecError, match="SMILES"):
        build_yaml(p)


def test_affinity_binder_must_be_ligand():
    p = payload(); p["properties"] = {"affinity_binder": "A"}
    with pytest.raises(SpecError, match="only defined for small-molecule"):
        build_yaml(p)
    p["properties"] = {"affinity_binder": "Z"}
    with pytest.raises(SpecError, match="not a defined chain"):
        build_yaml(p)


def test_modifications_cyclic_msa():
    p = payload(); p["properties"] = {}
    p["sequences"][0]["data"].update({"msa": "/x/a.a3m", "cyclic": True,
                                       "modifications": [{"position": 2, "ccd": "ptr"}, {"position": "", "ccd": ""}]})
    doc = build_yaml(p)
    prot = doc["sequences"][0]["protein"]
    assert prot["msa"] == "/x/a.a3m" and prot["cyclic"] is True
    assert prot["modifications"] == [{"position": 2, "ccd": "PTR"}]
    p["sequences"][0]["data"]["modifications"] = [{"position": 99, "ccd": "PTR"}]
    with pytest.raises(SpecError, match="outside chain"):
        build_yaml(p)


def test_constraints_and_templates(tmp_path):
    p = payload()
    p["constraints"] = {
        "bonds": [{"chain1": "a", "res1": 3, "atom1": "SG", "chain2": "B", "res2": 1, "atom2": "C1"}],
        "pockets": [{"binder": "B", "contacts": [{"chain": "A", "ref": "2"}, {"chain": "A", "ref": "5"}], "max_distance": "6", "force": True}],
        "contacts": [{"chain1": "A", "ref1": "1", "chain2": "B", "ref2": "C1", "max_distance": "", "force": False}]}
    p["templates"] = [{"path": "/tmp/t.cif", "chain_id": ["a"], "template_id": ["x"], "force": True, "threshold": "0.5"}]
    doc = build_yaml(p)
    c = doc["constraints"]
    assert c[0] == {"bond": {"atom1": ["A", 3, "SG"], "atom2": ["B", 1, "C1"]}}
    assert c[1]["pocket"] == {"binder": "B", "contacts": [["A", 2], ["A", 5]], "max_distance": 6.0, "force": True}
    assert c[2]["contact"] == {"token1": ["A", 1], "token2": ["B", "C1"]}
    assert doc["templates"] == [{"cif": "/tmp/t.cif", "chain_id": "A", "template_id": "x", "force": True, "threshold": 0.5}]
    p["constraints"]["bonds"][0]["chain2"] = "Q"
    with pytest.raises(SpecError, match="unknown chain"):
        build_yaml(p)


def test_template_on_ligand_rejected():
    p = payload(); p["templates"] = [{"path": "t.pdb", "chain_id": ["B"]}]
    with pytest.raises(SpecError, match="protein chains"):
        build_yaml(p)


def test_multi_ligand_affinity_warning():
    p = payload(); p["sequences"].append({"type": "ligand", "data": {"id": ["C"], "ccd": "HEM"}})
    doc = build_yaml(p)
    assert pop_warnings(doc) and "_warnings" not in doc


def test_simple_spec_and_summary():
    doc = build_yaml(simple_spec(["MKTAYIAK", "MKTAYIAK"], ligand_smiles="c1ccccc1O", affinity=True, msa="empty", dna=["ACGT"]))
    ids = [list(s.values())[0]["id"][0] for s in doc["sequences"]]
    assert ids == ["A", "B", "C", "D"] and "dna" in doc["sequences"][2]
    s = spec_summary(doc)
    assert s["entities"] == {"protein": 2, "dna": 1, "ligand": 1} and s["has_affinity"] and s["single_sequence_chains"] == 2
    assert yaml_has_explicit_msa(dump_yaml(doc))


def test_v1_payload_dialect():
    v1 = {"sequences": [{"protein": {"id": ["A"], "sequence": "MKTAYIAK"}},
                        {"ligand": {"id": ["B"], "ccd": "HEM"}}],
          "properties": [{"affinity": {"binder": "B"}}]}
    doc = build_yaml(v1)
    assert doc["sequences"][1]["ligand"] == {"id": ["B"], "ccd": "HEM"}
    assert doc["properties"] == [{"affinity": {"binder": "B"}}]
