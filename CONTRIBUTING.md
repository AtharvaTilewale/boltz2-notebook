# Contributing

## Layout

```
boltz2nb/          importable package - all logic lives here and is unit-tested
scripts/common/    the three cells' implementations (setup / Boltz_Run / analysis), run via %run
scripts/v1, v2/    thin shims + launchers for the standard / advanced input builder
boltz2nb/ui/       the interface: design-system CSS, form HTML/JS (assets/), renderers, Python callbacks, live panel, result card, figures.py (the plots)
scripts/batch_utils.py   compatibility shim over boltz2nb.batch
colab/, batch/, notebooks/, Boltz2.ipynb   the notebooks (thin shells)
tests/             pytest suite; engine tests skip unless a Boltz cache is present
tools/check_notebooks.py   compiles notebook cells and checks %run targets
tools/build_notebook_headers.py   regenerates the first cell of the three main notebooks (`--check` in CI)
tools/fetch_test_fonts.py  downloads Inter / JetBrains Mono for the browser tests
```

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,ligand,viewer]"
pytest                          # unit tests (no GPU, no Boltz needed)
ruff check boltz2nb tests scripts/common tools
python tools/check_notebooks.py
python tools/build_notebook_headers.py --check
```

### Interface and browser tests

The interface lives in `boltz2nb/ui/assets/` (`theme.css`, `form.css`, `results.css`, `form.html`, `form.js`, `viewer.js`, `theme.js`) and is plain
ES2017 with no build step. All values the page needs (defaults, presets, ranges) come from `boltz2nb.run_params`; do not duplicate them in JS.
A new asset file needs no packaging change (`assets/*` is package data), but run `pytest tests/test_packaging.py`.

**Callbacks and the Colab reply.** The page calls Python through `google.colab.kernel.invokeFunction`, which resolves with the notebook's
*display* of the callback's return value: a plain `dict` arrives as its text `repr`, and only `IPython.display.JSON` arrives as parsed JSON.
Add a callback to `callbacks.CALLBACKS` and `register_callbacks` wraps it (`as_json_reply`); never register a bare function. The test
harness passes each return value through IPython's real `DisplayFormatter`, so a callback that returns something the page cannot read fails
`tests/test_colab_contract.py` instead of failing in Colab.

**Ligand checks and the network.** `boltz2nb/ligand.py` checks SMILES with RDKit and looks CCD codes up on the RCSB data API. No test may reach the
network: `tests/conftest.py` replaces the lookup for every test with `ccd_service` (a few real components, 404 for the rest, `.offline = True` to
simulate no connection). The same goes for the 3-D viewer: headless browsers have no WebGL, so `tests/ui/test_results_browser.py` runs the viewer against a
stand-in that parses atoms and applies selections; change the viewer and the stand-in together.

**Figures.** Plots are drawn by `boltz2nb/ui/figures.py` on fixed-size canvases (no tight cropping), and `report.py` lays them out in rows
that rely on those sizes. A new figure needs an entry in `tests/test_figures.py` (inside its canvas, nothing overprinted, same size as its kind)
and, if it joins the report, a look at `tests/ui/test_report_layout_browser.py`.

Browser tests drive the real form against the real Python callbacks in headless Firefox:

```bash
pip install selenium                       # plus Firefox and geckodriver on PATH (or set BZ_FIREFOX / BZ_GECKODRIVER)
python tools/fetch_test_fonts.py fonts     # text metrics matter for the overflow checks
BZ_FONT_DIR=$PWD/fonts pytest tests/ui
```

They skip themselves when selenium or Firefox is missing. Headless Firefox cannot open a window narrower than about 500 px, so the
360 / 414 px checks load the page in an iframe of exactly that width. WebGL is not available in CI browsers, so the 3-D viewer is tested against a stub of 3Dmol.

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
