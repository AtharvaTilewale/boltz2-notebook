# @title Generate Parameters (YAML file & Run Config)
# ruff: noqa: E402
"""Input builder for Boltz-2 (standard mode: proteins and ligands).

The interface lives in ``boltz2nb.ui`` (one design system for the form, the live run panel and the results);
every value is validated by ``boltz2nb.yaml_builder`` / ``boltz2nb.run_params`` on the Python side.
"""
import os


# --- refresh stale boltz2nb (the same block is in every notebook script; the check itself is boltz2nb/_build.py) ---
# Cell 1 can update the clone under a running kernel; modules imported from the older copy would then be mixed with this newer script.
def _refresh_stale_boltz2nb():
    import importlib.util
    import sys
    from pathlib import Path

    loaded = sys.modules.get("boltz2nb")
    if loaded is None or not getattr(loaded, "__file__", None):
        return
    build_file = Path(loaded.__file__).parent / "_build.py"
    if build_file.exists():
        spec = importlib.util.spec_from_file_location("_boltz2nb_build", build_file)
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        build.drop_stale_modules(loaded)


_refresh_stale_boltz2nb()
del _refresh_stale_boltz2nb
# --- end refresh ---

from boltz2nb.paths import base_dir, ensure_dirs
from boltz2nb.ui.callbacks import register_callbacks
from boltz2nb.ui.render import render_form

ensure_dirs()
os.chdir(base_dir())
_registered = register_callbacks()

try:
    from IPython.display import HTML, display
except ImportError:  # plain Python: nothing to draw
    HTML = display = None

if display is not None:
    if not _registered:
        print("Note: not running in Google Colab - the form renders, but Save needs the Colab kernel bridge.")
    display(HTML(render_form(mode="standard")))
else:
    print("The input builder needs IPython/Colab. Write params.yaml and run_params.txt by hand or use boltz2nb.yaml_builder.")
