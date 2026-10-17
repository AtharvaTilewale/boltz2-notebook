"""Structure import used by the input builder: chains are grouped into entities, ligands listed by CCD code."""
from pathlib import Path

import pytest

from boltz2nb.pdb_import import parse_structure_text

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "pdb"


@pytest.fixture(scope="module")
def parsed():
    return parse_structure_text((ASSETS / "prot_lig_dna.pdb").read_text(), "prot_lig_dna.pdb")


def test_identical_chains_share_one_entity(parsed):
    assert parsed["status"] == "ok" and parsed["filename"] == "prot_lig_dna.pdb"
    kinds = [(e["kind"], e["ids"]) for e in parsed["entities"]]
    assert kinds == [("protein", ["A", "B"]), ("dna", ["E"]), ("dna", ["F"])]
    prot = parsed["entities"][0]
    assert prot["length"] == 260 and set(prot["sequence"]) <= set("ACDEFGHIKLMNPQRSTVWY")


def test_ligand_components_are_reported_by_ccd_code(parsed):
    assert {x["ccd"] for x in parsed["ligands"]} == {"83Y", "BDP", "GCD"}
    assert all(not x["ion"] and x["atoms"] > 0 for x in parsed["ligands"])


def test_empty_or_garbage_files_give_a_readable_error():
    for text in ("", "REMARK nothing here\nEND\n", "not a structure"):
        r = parse_structure_text(text, "bad.pdb")
        assert r["status"] == "error" and r["message"] and r["hint"]


def test_mmcif_round_trip(tmp_path):
    pytest.importorskip("Bio")
    from Bio.PDB import MMCIFIO, PDBParser
    structure = PDBParser(QUIET=True).get_structure("x", str(ASSETS / "prot_lig.pdb"))
    io = MMCIFIO()
    io.set_structure(structure)
    out = tmp_path / "x.cif"
    io.save(str(out))
    r = parse_structure_text(out.read_text(), "x.cif")
    assert r["status"] == "ok" and r["entities"] and r["entities"][0]["kind"] == "protein"
