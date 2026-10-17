# @title Generate Parameters (YAML file & Run Config)
"""Input builder for Boltz-2 (standard mode: proteins and ligands).

The interface lives in ``boltz2nb.ui`` (one design system for the form, the live run panel and the results);
every value is validated by ``boltz2nb.yaml_builder`` / ``boltz2nb.run_params`` on the Python side.
"""
import os

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
