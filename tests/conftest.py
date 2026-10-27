import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


@pytest.fixture(scope="session")
def example_pred_dir(tmp_path_factory) -> Path:
    """Assemble a Boltz-style predictions directory from the shipped example data."""
    job = "prot_lig"
    d = tmp_path_factory.mktemp("pred") / job / f"boltz_results_{job}" / "predictions" / job
    d.mkdir(parents=True)
    shutil.copy(ASSETS / "pdb" / "prot_lig.pdb", d / f"{job}_model_0.pdb")
    shutil.copy(ASSETS / "pred_data" / "plddt.npz", d / f"plddt_{job}_model_0.npz")
    shutil.copy(ASSETS / "pred_data" / "pae.npz", d / f"pae_{job}_model_0.npz")
    shutil.copy(ASSETS / "pred_data" / "affinity.json", d / f"affinity_{job}.json")
    (d / f"confidence_{job}_model_0.json").write_text(
        '{"confidence_score": 0.91, "ptm": 0.93, "iptm": 0.88, "ligand_iptm": 0.86, "protein_iptm": 0.0,'
        ' "complex_plddt": 0.92, "complex_iplddt": 0.90, "complex_pde": 1.1, "complex_ipde": 1.5,'
        ' "chains_ptm": {"0": 0.93, "1": 0.8}, "pair_chains_iptm": {"0": {"0": 0.93, "1": 0.86}, "1": {"0": 0.86, "1": 0.8}}}')
    return d


def _ccd_record(name, formula, weight, smiles):
    return {"chem_comp": {"name": name, "formula": formula, "formula_weight": weight, "type": "non-polymer"},
            "rcsb_chem_comp_descriptor": {"SMILES_stereo": smiles}}


class CcdService:
    """Stands in for the RCSB chemical-component service: a few real components, 404 for anything else, and an offline switch."""

    records = {
        "SAH": _ccd_record("S-ADENOSYL-L-HOMOCYSTEINE", "C14 H20 N6 O5 S", 384.411,
                           "c1nc(c2c(n1)n(cn2)[C@H]3[C@@H]([C@@H]([C@H](O3)CSCC[C@@H](C(=O)O)N)O)O)N"),
        "ATP": _ccd_record("ADENOSINE-5'-TRIPHOSPHATE", "C10 H16 N5 O13 P3", 507.181,
                           "c1nc(c2c(n1)n(cn2)[C@H]3[C@@H]([C@@H]([C@H](O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O)N"),
        "ZN": _ccd_record("ZINC ION", "Zn", 65.409, "[Zn+2]"),
    }

    def __init__(self):
        self.offline = False
        self.calls: list[str] = []

    def fetch(self, code, timeout):
        self.calls.append(code)
        if self.offline:
            raise OSError("no connection")
        return self.records.get(code)


@pytest.fixture(autouse=True)
def ccd_service(monkeypatch):
    """No test reaches the real service; `ccd_service.offline = True` simulates a runtime without a connection."""
    from boltz2nb import ligand
    svc = CcdService()
    monkeypatch.setattr(ligand, "_fetch_ccd_json", svc.fetch)
    ligand.clear_ccd_cache()
    yield svc
    ligand.clear_ccd_cache()


@pytest.fixture(autouse=True)
def _forget_session_theme():
    """``set_theme`` keeps the last choice in a module global; no test may hand its choice on to the next."""
    from boltz2nb.ui import theme
    theme.reset_theme()
    yield
    theme.reset_theme()


@pytest.fixture(scope="session")
def three_sample_dir(tmp_path_factory, example_pred_dir) -> Path:
    """The example job with three diffusion samples (the two extra ones are noisy copies), as a typical run produces."""
    import json

    import numpy as np
    d = tmp_path_factory.mktemp("pred3") / "prot_lig" / "boltz_results_prot_lig" / "predictions" / "prot_lig"
    shutil.copytree(example_pred_dir, d)
    rng = np.random.default_rng(3)
    for i in (1, 2):
        shutil.copy(d / "prot_lig_model_0.pdb", d / f"prot_lig_model_{i}.pdb")
        p = np.load(d / "plddt_prot_lig_model_0.npz")["plddt"]
        np.savez(d / f"plddt_prot_lig_model_{i}.npz", plddt=np.clip(p + rng.normal(0, 0.03, p.shape), 0, 1))
        a = np.load(d / "pae_prot_lig_model_0.npz")["pae"]
        np.savez(d / f"pae_prot_lig_model_{i}.npz", pae=np.clip(a + rng.normal(0, 0.8, a.shape), 0, 32))
        c = json.loads((d / "confidence_prot_lig_model_0.json").read_text())
        c["confidence_score"] = 0.91 - 0.03 * i
        (d / f"confidence_prot_lig_model_{i}.json").write_text(json.dumps(c))
    return d


@pytest.fixture
def base_dir(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("BOLTZ2NB_BASE_DIR", str(tmp_path / "boltz_data"))
    return tmp_path / "boltz_data"


@pytest.fixture
def fake_boltz(tmp_path, monkeypatch) -> Path:
    """A stand-in `boltz` executable that writes plausible outputs for any YAML."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "boltz"
    script.write_text(f"""#!{os.environ.get('PYTHON_FOR_FAKE', 'python3')}
import sys, json, shutil, numpy as np, yaml
from pathlib import Path
args = sys.argv[1:]
assert args[0] == 'predict', args
yaml_path = Path(args[1]); out = Path(args[args.index('--out_dir') + 1])
n_samples = int(args[args.index('--diffusion_samples') + 1]) if '--diffusion_samples' in args else 1
doc = yaml.safe_load(yaml_path.read_text())
if any('FAILME' in (s.get('protein') or {{}}).get('sequence', '') for s in doc['sequences']):
    print('RuntimeError: CUDA out of memory. Tried to allocate 2 GiB', file=sys.stderr); sys.exit(1)
stem = yaml_path.stem
pred = out / f'boltz_results_{{stem}}' / 'predictions' / stem
pred.mkdir(parents=True, exist_ok=True)
assets = Path({str(ASSETS)!r})
for i in range(n_samples):
    shutil.copy(assets / 'pdb' / 'prot_lig.pdb', pred / f'{{stem}}_model_{{i}}.pdb')
    shutil.copy(assets / 'pred_data' / 'plddt.npz', pred / f'plddt_{{stem}}_model_{{i}}.npz')
    shutil.copy(assets / 'pred_data' / 'pae.npz', pred / f'pae_{{stem}}_model_{{i}}.npz')
    (pred / f'confidence_{{stem}}_model_{{i}}.json').write_text(json.dumps({{'confidence_score': 0.9 - 0.05*i, 'ptm': 0.9, 'iptm': 0.85, 'ligand_iptm': 0.8, 'protein_iptm': 0.0, 'complex_plddt': 0.9, 'complex_iplddt': 0.88, 'complex_pde': 1.0, 'complex_ipde': 1.4}}))
if doc.get('properties'):
    shutil.copy(assets / 'pred_data' / 'affinity.json', pred / f'affinity_{{stem}}.json')
if '--use_msa_server' in args:
    msa = out / f'boltz_results_{{stem}}' / 'msa'; msa.mkdir(parents=True, exist_ok=True)
    for k, s in enumerate(doc['sequences']):
        if 'protein' in s:
            (msa / f'{{stem}}_{{k}}.csv').write_text('key,sequence\\n-1,' + s['protein']['sequence'] + '\\n')
print('Boltz fake run complete'); sys.exit(0)
""")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return script


@pytest.fixture(autouse=True)
def _never_reach_the_real_usage_endpoint(monkeypatch):
    """boltz2nb/telemetry_config.py holds the maintainer's real endpoint. A test that ticks SEND_USAGE_STATS must only ever talk to the local collector it
    starts itself (via BOLTZ2NB_TELEMETRY_URL), so the shipped values are blanked for every test, whatever the environment variables say."""
    from boltz2nb import telemetry_config
    monkeypatch.setattr(telemetry_config, "ENDPOINT", "")
    monkeypatch.setattr(telemetry_config, "PUBLIC_KEY", "")
    # Subprocesses import a fresh copy of the package with the real values; an empty BOLTZ2NB_TELEMETRY_URL switches those off too.
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", "")
