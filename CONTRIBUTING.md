# Contributing

## Layout

```
boltz2nb/          importable package - all logic lives here and is unit-tested
scripts/common/    the three cells' implementations (setup / Boltz_Run / analysis), run via %run
scripts/v1, v2/    thin shims + the two parameter-builder GUIs (HTML/JS with Python callbacks)
scripts/batch_utils.py   compatibility shim over boltz2nb.batch
colab/, batch/, notebooks/, Boltz2.ipynb   the notebooks (thin shells)
tests/             pytest suite; engine tests skip unless a Boltz cache is present
tools/check_notebooks.py   compiles notebook cells and checks %run targets
```

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,ligand,viewer]"
pytest                          # unit tests (no GPU, no Boltz needed)
ruff check boltz2nb tests scripts/common
python tools/check_notebooks.py
```

To run the engine-level tests and a real prediction locally:

```bash
pip install "boltz[cuda]==2.2.1"           # or boltz-community on Python 3.13
export BOLTZ_CACHE=/path/with/8GB/free     # weights + CCD are downloaded here
pytest tests/test_engine_schema.py
BOLTZ2NB_BASE_DIR=/tmp/boltz_data python scripts/common/Boltz_Run.py   # after writing params.yaml + run_params.txt
```

## Releasing

1. Bump `boltz2nb.__version__`, `pyproject.toml`, `CITATION.cff`, the `NOTEBOOK_VERSION` default in every
   notebook's first cell, and `releases/CHANGELOG.md`.
2. Wait for CI to pass on `main`.
3. Tag `vX.Y.Z` and push the tag. Notebooks clone that tag, so users are unaffected by later commits.
4. Create a GitHub release (Zenodo archives it if the integration is enabled).

Pull requests should add or update a test for behaviour they change; the notebooks must stay thin.
