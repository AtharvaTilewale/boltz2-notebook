# Contributing

## Layout

```
boltz2nb/          importable package - all logic lives here and is unit-tested
scripts/common/    the three cells' implementations (setup / Boltz_Run / analysis), run via %run
scripts/v1, v2/    thin shims + launchers for the standard / advanced input builder
boltz2nb/ui/       the interface: design-system CSS, form HTML/JS (assets/), renderers, Python callbacks, live panel, result card, figures.py (the plots)
scripts/batch_utils.py   compatibility shim over boltz2nb.batch
Boltz2.ipynb      the default notebook: Advanced V2.0.0, a byte-for-byte copy of colab/v2/Boltz2_V2.0.0.ipynb (never edit it by hand)
colab/, batch/, notebooks/   the other notebooks (thin shells); colab/v2/Boltz2_V2.0.0_beta.ipynb is only a pointer to the renamed V2 notebook
tests/             pytest suite; engine tests skip unless a Boltz cache is present
tools/check_notebooks.py   compiles notebook cells and checks %run targets
tools/build_notebook_headers.py   regenerates the first cell of the main notebooks and copies the V2 notebook over Boltz2.ipynb (`--check` in CI)
tools/fetch_test_fonts.py  downloads Inter / JetBrains Mono for the browser tests
tools/telemetry_keygen.py, tools/telemetry_read.py, telemetry/receiver.gs   make the key pair for, receive and read the opt-in usage reports (docs/TELEMETRY.md)
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

### The default notebook

`Boltz2.ipynb` in the repository root is what the README, the website and the "Open in Colab" badge open. It is the Advanced V2.0.0 notebook and
must stay identical to `colab/v2/Boltz2_V2.0.0.ipynb`. Edit the versioned file, then run `python tools/build_notebook_headers.py`: it regenerates the
header cell of each main notebook and copies the V2 notebook over the root one. `--check` (CI) and `tests/test_default_notebook.py` fail when they differ.
The Standard notebook (`colab/v1/Boltz2_v1.0.0.ipynb`) and V2 are stable; only the Batch notebook is still labelled beta / experimental.
`tests/test_links.py` checks that every link into this repository or the site points at a file that exists; a renamed notebook keeps a pointer at its old path.

### Interface and browser tests

The interface lives in `boltz2nb/ui/assets/` (`theme.css`, `form.css`, `results.css`, `form.html`, `form.js`, `viewer.js`, `theme.js`) and is plain
ES2017 with no build step. All values the page needs (defaults, presets, ranges) come from `boltz2nb.run_params`; do not duplicate them in JS.
A new asset file needs no packaging change (`assets/*` is package data), but run `pytest tests/test_packaging.py`.

**Callbacks and the Colab reply.** The page calls Python through `google.colab.kernel.invokeFunction`, which resolves with the notebook's
*display* of the callback's return value: a plain `dict` arrives as its text `repr`, and only `IPython.display.JSON` arrives as parsed JSON.
Add a callback to `callbacks.CALLBACKS` and `register_callbacks` wraps it (`as_json_reply`); never register a bare function. The test
harness passes each return value through IPython's real `DisplayFormatter`, so a callback that returns something the page cannot read fails
`tests/test_colab_contract.py` instead of failing in Colab.

**Notebook scripts and a running kernel.** A Colab kernel keeps imported modules when Cell 1 updates the clone. Every script that is run by a notebook
(and imports `boltz2nb`) starts with the identical `# --- refresh stale boltz2nb ---` block; `tests/test_stale_modules.py` checks that all of them match and
that the block works. Copy it into any new notebook script, above its first `boltz2nb` import. The package's own `BUILD_ID` (see `boltz2nb/_build.py`) is a hash
of its source and interface files, so editing any of them is what marks a loaded copy as stale.

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
