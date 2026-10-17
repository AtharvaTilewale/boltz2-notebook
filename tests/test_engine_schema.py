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
