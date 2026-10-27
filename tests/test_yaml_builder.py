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


# -- template files that Boltz is known to stop on (boltz 2.2.1): a warning before the run, not a rejection --------------------

PDB_WITH_SEQRES = "SEQRES   1 A    3  MET LYS THR\nATOM      1  N   MET A   1       0.000   0.000   0.000  1.00 50.00           N\nEND\n"
PDB_BOLTZ_STYLE = ("ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00 50.00           N\n"
                   "HETATM  346  C21 LIG B   1       8.105   0.765  13.684  1.00 50.00           C\nEND\n")
CIF_BOLTZ_STYLE = "data_x\nloop_\n_atom_site.group_PDB\n_atom_site.label_comp_id\nATOM MET\nHETATM LIG1\n"


def _template_payload(path, template_id=None):
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTAYIAKQ"}}], "constraints": {}, "properties": {},
               "templates": [{"path": str(path), "chain_id": ["A"]}]}
    if template_id:
        payload["templates"][0]["template_id"] = template_id
    return payload


def test_template_warnings_for_the_inputs_the_engine_rejects(tmp_path):
    from boltz2nb.yaml_builder import pop_warnings
    boltz_pdb = tmp_path / "pred.pdb"; boltz_pdb.write_text(PDB_BOLTZ_STYLE)
    warnings = pop_warnings(build_yaml(_template_payload(boltz_pdb)))
    assert len(warnings) == 2 and "no SEQRES" in warnings[0] and ".cif" in warnings[0] and "LIG" in warnings[1]
    boltz_cif = tmp_path / "pred.cif"; boltz_cif.write_text(CIF_BOLTZ_STYLE)
    warnings = pop_warnings(build_yaml(_template_payload(boltz_cif)))
    assert len(warnings) == 1 and "LIG1" in warnings[0] and "protein-only" in warnings[0]
    good = tmp_path / "rcsb.pdb"; good.write_text(PDB_WITH_SEQRES)
    warnings = pop_warnings(build_yaml(_template_payload(good, ["A"])))                    # Boltz calls this chain A1
    assert len(warnings) == 1 and "A1" in warnings[0] and "Leave the template chain empty" in warnings[0]


def test_no_template_warning_when_the_engine_accepts_the_file(tmp_path):
    good = tmp_path / "rcsb.pdb"; good.write_text(PDB_WITH_SEQRES)
    for doc in (build_yaml(_template_payload(good)), build_yaml(_template_payload(good, ["A1"])), build_yaml(_template_payload(tmp_path / "missing.pdb", ["A"]))):
        assert "_warnings" not in doc                                                       # the key is not even created
    cif = tmp_path / "ok.cif"; cif.write_text("data_x\nloop_\n_atom_site.label_comp_id\nMET\nLYS\n")
    assert "_warnings" not in build_yaml(_template_payload(cif, ["A"]))                    # a .cif keeps its chain names
