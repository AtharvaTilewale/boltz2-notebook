import json
from pathlib import Path

import numpy as np
import pytest

from boltz2nb import analysis as an
from boltz2nb.report import write_report
from boltz2nb.tokens import chain_indices, chain_kinds, check_token_count, token_layout

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def test_token_layout_matches_shipped_npz():
    toks = token_layout(ASSETS / "pdb" / "prot_lig.pdb")
    n = len(np.load(ASSETS / "pred_data" / "plddt.npz")["plddt"])
    assert len(toks) == n == 608
    idx = chain_indices(toks)
    assert len(idx["A"]) == 585 and len(idx["B"]) == 23
    assert chain_kinds(toks) == {"A": "protein", "B": "ligand"}
    assert all(t.kind == "atom" for t in toks if t.chain_id == "B")
    with pytest.raises(ValueError):
        check_token_count(toks, 600)


def test_token_layout_dna_and_multi_ligand():
    toks = token_layout(ASSETS / "pdb" / "prot_lig_dna.pdb")
    kinds = chain_kinds(toks)
    assert kinds["A"] == "protein" and kinds["E"] == "dna" and kinds["C"] == "ligand"
    idx = chain_indices(toks)
    # chains C/D hold three ligands (83Y, BDP, GCD); hydrogens in the file must not become tokens
    assert len(idx["C"]) == 52 and len(idx["D"]) == 52
    assert all(t.kind == "atom" and t.atom_name is not None for t in toks if t.chain_id == "C")


def test_modified_residue_is_atomised(tmp_path):
    pdb = tmp_path / "m.pdb"
    lines = []
    atoms = [("N", "N"), ("CA", "C"), ("C", "C"), ("O", "O")]
    serial = 1
    for resi, resn in enumerate(["MET", "SEP", "LYS"], start=1):
        names = atoms + ([("CB", "C"), ("OG", "O"), ("P", "P")] if resn == "SEP" else [])
        for nm, el in names:
            lines.append(f"ATOM  {serial:5d}  {nm:<3s} {resn} A{resi:4d}    {0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 90.00           {el:>2s}")
            serial += 1
    pdb.write_text("\n".join(lines) + "\nEND\n")
    toks = token_layout(pdb)
    assert [t.kind for t in toks] == ["residue"] + ["atom"] * 7 + ["residue"]
    assert chain_kinds(toks) == {"A": "protein"}


def test_affinity_conversions():
    assert an.affinity_to_ic50_um(0.0) == 1.0
    assert an.affinity_to_pic50(-3.0) == 9.0
    assert an.format_ic50(-2.0) == "10.0 nM" and an.format_ic50(1.5).endswith("µM") and an.format_ic50(3.5).endswith("mM")
    assert an.affinity_to_kcal_per_mol(-3.0) == pytest.approx(-12.28, abs=0.05)
    assert an.affinity_assessment(-2.5).startswith("Very potent") and an.affinity_assessment(1.2).startswith("Very weak")
    assert an.probability_assessment(0.8).startswith("High") and an.probability_assessment(0.1).startswith("Low")


def test_load_job_and_summary(example_pred_dir):
    job = an.load_job(example_pred_dir)
    assert job.job_name == "prot_lig" and len(job.models) == 1
    m = job.best
    assert m.plddt.max() <= 100 and m.pae.shape == (608, 608)
    stats = {s["chain_id"]: s for s in (m.chain_stats(c) for c in m.chain_ids)}
    assert stats["A"]["mean_plddt"] == pytest.approx(93.8, abs=0.1)
    assert stats["B"]["mean_plddt"] == pytest.approx(59.5, abs=0.1) and stats["B"]["kind"] == "ligand"
    ipae = m.interface_pae()
    assert set(ipae) == {"A-B"} and 0 < ipae["A-B"] < 32
    # asymmetry must be preserved (no P + P.T)
    assert not np.allclose(m.pae, m.pae.T)
    aff = job.affinity_summary()
    assert aff["log10_ic50_um"] == pytest.approx(0.4428, abs=1e-3) and aff["ic50"] == "2.77 µM"
    assert aff["binding_probability"] == pytest.approx(0.379, abs=1e-3) and len(aff["ensemble_members"]) == 2
    assert aff["member_spread"] == pytest.approx(1.066, abs=1e-3)
    ens = job.ensemble_summary()
    assert ens["n_models"] == 1 and ens["confidence_score"]["sd"] == 0.0
    s = an.summary_dict(job)
    assert s["best_model"] == 0 and s["affinity"]["potency_class"].startswith("Weak")


def test_plots_and_report(example_pred_dir, tmp_path):
    job = an.load_job(example_pred_dir)
    out = write_report(job, tmp_path, run_context={"engine": "boltz 2.2.1", "command": ["boltz", "predict"],
                                                  "input_yaml": "version: 1", "input_yaml_sha1": "abc"})
    html = Path(out["report"]).read_text()
    assert "Boltz-2 report" in html and 'class="bz-aff-v">2.77 µM<' in html and "data:image/png;base64" in html
    assert "fixed 0-32 Å scale" in html and "$3Dmol.createViewer" in html and "boltz 2.2.1" in html
    assert 'id="bz-' in html and 'lang="en"' in html and "<script src=\"https://cdn.jsdelivr.net/npm/3dmol@2.5.5/" in html
    assert 'name="viewport"' in html            # responsive on phones
    assert Path(out["plots"]["models"][0]["pae"]).exists() and Path(out["plots"]["affinity"]).exists()
    summary = json.loads(Path(out["summary"]).read_text())
    assert summary["chains"][1]["kind"] == "ligand"


def test_ensemble_with_multiple_models(example_pred_dir, tmp_path):
    import shutil
    d = tmp_path / "prot_lig" / "boltz_results_prot_lig" / "predictions" / "prot_lig"
    shutil.copytree(example_pred_dir, d)
    for i in (1, 2):
        for prefix, ext in (("", "pdb"), ("plddt_", "npz"), ("pae_", "npz")):
            shutil.copy(d / f"{prefix}prot_lig_model_0.{ext}", d / f"{prefix}prot_lig_model_{i}.{ext}")
        (d / f"confidence_prot_lig_model_{i}.json").write_text(json.dumps({"confidence_score": 0.91 - 0.1 * i, "ptm": 0.9, "iptm": 0.8}))
    job = an.load_job(d)
    ens = job.ensemble_summary()
    assert ens["n_models"] == 3
    assert ens["confidence_score"]["mean"] == pytest.approx(0.81, abs=1e-6) and ens["confidence_score"]["sd"] == pytest.approx(0.1, abs=1e-6)
    assert an.plot_ensemble(job, tmp_path / "ens.png") is not None
    assert len(job.metrics_table()) == 3


def test_layout_resolution_and_graceful_mismatch(example_pred_dir, tmp_path):
    import shutil

    import numpy as np

    from boltz2nb.tokens import LayoutMismatch, layout_counts, resolve_layout
    counts = layout_counts(ASSETS / "pdb" / "prot_lig.pdb")
    assert counts == {"atomised": 608, "atomised_std": 608, "atomised_all": 608, "residue": 586}
    # the DNA/ligand example file carries hydrogens, so the layouts differ there
    assert layout_counts(ASSETS / "pdb" / "prot_lig_dna.pdb") == {"atomised": 678, "atomised_std": 678,
                                                                 "atomised_all": 740, "residue": 582}
    toks, mode = resolve_layout(ASSETS / "pdb" / "prot_lig.pdb", 586)
    assert mode == "residue" and len(toks) == 586
    with pytest.raises(LayoutMismatch, match="matches none of the token layouts"):
        resolve_layout(ASSETS / "pdb" / "prot_lig.pdb", 20)

    # A model whose arrays do not match any layout must not break the analysis:
    d = tmp_path / "prot_lig" / "boltz_results_prot_lig" / "predictions" / "prot_lig"
    shutil.copytree(example_pred_dir, d)
    np.savez_compressed(d / "plddt_prot_lig_model_0.npz", plddt=np.full(20, 0.8))
    job = an.load_job(d)
    m = job.best
    assert m.per_token is False and m.layout == "unknown" and "20 entries" in m.layout_note
    assert job.layout_notes and m.interface_pae() == {}
    s = an.summary_dict(job)
    assert s["chains"] == [] and s["confidence"]["confidence_score"] == 0.91
    assert s["affinity"]["ic50"] == "2.77 µM"          # affinity is unaffected
    out = write_report(job, tmp_path / "rep")
    html = Path(out["report"]).read_text()
    assert "Per-token analysis unavailable" in html and "2.77 µM" in html
    assert out["plots"]["models"][0]["plddt"] is None and out["plots"]["models"][0]["pae"] is None
    assert an.summary_dict(job)["models"][0]["mean_plddt"] is None


def test_affinity_per_binder_files(example_pred_dir, tmp_path):
    import json as _json
    import shutil
    d = tmp_path / "prot_lig" / "boltz_results_prot_lig" / "predictions" / "prot_lig"
    shutil.copytree(example_pred_dir, d)
    (d / "affinity_prot_lig_C.json").write_text(_json.dumps({"affinity_pred_value": -1.0, "affinity_probability_binary": 0.9}))
    job = an.load_job(d)
    assert job.affinity["_additional_binders"]["C"]["affinity_probability_binary"] == 0.9
