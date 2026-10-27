"""Validate builder output with Boltz's own parser. Skipped unless the Boltz CCD cache exists."""
import os
from pathlib import Path

import pytest
import yaml

try:  # boltz's CLI imports this before the parser (featurizerv2); AllChem.Descriptors relies on that order
    import rdkit.Chem.Descriptors  # noqa: F401
except Exception:  # pragma: no cover
    pass

from boltz2nb.yaml_builder import build_yaml, dump_yaml, simple_spec

MOLS = Path(os.environ.get("BOLTZ_CACHE", Path.home() / ".boltz")) / "mols"
pytestmark = pytest.mark.skipif(not MOLS.exists(), reason="Boltz CCD cache not available")


def _parse(doc):
    from boltz.data.parse.schema import parse_boltz_schema
    text = dump_yaml(doc)
    return parse_boltz_schema("t", yaml.safe_load(text), ccd={}, mol_dir=MOLS, boltz_2=True)


def test_protein_ligand_affinity():
    t = _parse(build_yaml(simple_spec("MKTAYIAKQRQISFVKSHFSRQ", ligand_smiles="CC(=O)Oc1ccccc1C(=O)O", affinity=True, msa="empty")))
    assert len(t.structure.chains) == 2 and t.record.affinity is not None


def test_dna_rna_multichain():
    t = _parse(build_yaml(simple_spec(["MKTAYIAK", "MKTAYIAK"], dna=["ACGTACGT"], rna=["ACGU"], msa="empty")))
    assert len(t.structure.chains) == 4


def test_ptm_cyclic_ccd_ligand_constraints():
    payload = {"sequences": [
        {"type": "protein", "data": {"id": ["A"], "sequence": "MKTSYIAKCRQISFVKSHFSRQ", "msa": "empty",
                                     "modifications": [{"position": 4, "ccd": "SEP"}], "cyclic": False}},
        {"type": "ligand", "data": {"id": ["B"], "ccd": "ATP"}}],
        "constraints": {"bonds": [], "pockets": [{"binder": "B", "contacts": [{"chain": "A", "ref": "5"}, {"chain": "A", "ref": "9"}],
                                                   "max_distance": 7, "force": False}],
                        "contacts": [{"chain1": "A", "ref1": "3", "chain2": "B", "ref2": "PG", "max_distance": 6, "force": False}]},
        "templates": [], "properties": {"affinity_binder": "B"}}
    t = _parse(build_yaml(payload))
    assert t.structure is not None and t.record.affinity is not None


def test_cyclic_peptide():
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "CYKLPGSC", "msa": "empty", "cyclic": True}}],
               "constraints": {}, "templates": [], "properties": {}}
    t = _parse(build_yaml(payload))
    assert t.structure.chains[0]["cyclic_period"] == 8


def _template_pdb(path, sequence="MKTAYI", chain="A"):
    """A minimal PDB that Boltz accepts as a template: SEQRES (Boltz reads the sequence from it) and backbone atoms on a straight chain."""
    three = {"M": "MET", "K": "LYS", "T": "THR", "A": "ALA", "Y": "TYR", "I": "ILE"}
    lines = [f"SEQRES {1:>3} {chain} {len(sequence):>4}  " + " ".join(three[c] for c in sequence)]       # fixed columns: residue names start at 20
    n = 0
    for i, c in enumerate(sequence, 1):
        for name, el, dx in (("N", "N", 0.0), ("CA", "C", 1.4), ("C", "C", 2.5), ("O", "O", 3.2)):
            n += 1
            lines.append(f"ATOM  {n:>5}  {name:<3} {three[c]} {chain}{i:>4}    {i * 3.8 + dx:>8.3f}{0.0:>8.3f}{0.0:>8.3f}  1.00 50.00           {el}")
    lines.append("END")
    Path(path).write_text("\n".join(lines) + "\n")


def test_covalent_bond_custom_msa_and_template(tmp_path):
    a3m = tmp_path / "msa.a3m"
    a3m.write_text(">query\nMKTCYIAKQRQISFVKSHFSRQ\n>hit\nMKTCYIAKQRQISFVKSHFSRQ\n")
    template = tmp_path / "template.pdb"
    _template_pdb(template)
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTCYIAKQRQISFVKSHFSRQ", "msa": str(a3m)}},
                             {"type": "ligand", "data": {"id": ["B"], "ccd": "SAH"}}],
               "constraints": {"bonds": [{"chain1": "A", "res1": 4, "atom1": "SG", "chain2": "B", "res2": 1, "atom2": "SD"}], "pockets": [], "contacts": []},
               "templates": [{"path": str(template), "chain_id": ["A"], "template_id": ["A1"], "force": True, "threshold": "0.5"}], "properties": {}}      # A1: how Boltz names a .pdb chain
    with_bond = _parse(build_yaml(payload))
    payload["constraints"]["bonds"] = []
    without_bond = _parse(build_yaml(payload))
    assert len(with_bond.structure.bonds) == len(without_bond.structure.bonds) + 1      # the covalent link is one more bond in the parsed structure
    assert len(with_bond.structure.chains) == 2 and with_bond.templates, "the template was not read"


def test_pdb_template_chains_are_named_a1_by_the_engine(tmp_path):
    """The reason for the builder's template warning: boltz 2.2.1 calls the chains of a .pdb template A1, B1, ... and those of a .cif A, B, ...
    If this test starts failing the engine changed and ``template_file_warnings`` should be revisited."""
    template = tmp_path / "template.pdb"
    _template_pdb(template)
    base = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTAYI", "msa": "empty"}}], "constraints": {}, "properties": {},
            "templates": [{"path": str(template), "chain_id": ["A"], "template_id": ["A1"]}]}
    assert _parse(build_yaml(base)).templates
    base["templates"][0]["template_id"] = ["A"]
    with pytest.raises(ValueError, match="not one of the protein chains"):
        _parse(build_yaml(base))
    base["templates"][0].pop("template_id")                                                  # no chain named: every protein chain is used
    assert _parse(build_yaml(base)).templates


def test_pdb_template_without_seqres_stops_the_engine(tmp_path):
    """The other reason: without SEQRES the engine fails with an IndexError, which is what the builder warns about."""
    template = tmp_path / "template.pdb"
    _template_pdb(template)
    template.write_text("\n".join(line for line in template.read_text().splitlines() if not line.startswith("SEQRES")) + "\n")
    payload = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTAYI", "msa": "empty"}}], "constraints": {}, "properties": {},
               "templates": [{"path": str(template), "chain_id": ["A"]}]}
    with pytest.raises(IndexError):
        _parse(build_yaml(payload))
