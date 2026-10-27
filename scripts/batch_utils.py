"""Backward-compatible shim: the batch engine now lives in ``boltz2nb.batch``.

Older copies of the batch notebook download this single file and ``import Batch_Utils``.
If the package is not installed yet, install it from GitHub, then re-export everything.
"""
import os
import subprocess
import sys


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

try:
    from boltz2nb.batch import *  # noqa: F401,F403
    from boltz2nb.batch import (  # noqa: F401
        apply_run_profile,
        build_manifest_from_csv,
        build_manifest_from_fasta,
        build_manifest_from_yaml_dir,
        create_export_zip,
        default_run_params,
        discover_uploads,
        extract_yaml_zip,
        failure_diagnostics_table,
        manifest_overview,
        preflight_manifest,
        progress_table,
        rank_results,
        run_manifest,
        save_uploaded_file,
        set_work_root,
        summarize_manifest,
        validate_manifest,
    )
    from boltz2nb.batch import capture_batch_context as capture_run_context
except ImportError:  # pragma: no cover
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "git+https://github.com/AtharvaTilewale/boltz2-notebook.git@v2.1.3"], check=True)
    from boltz2nb.batch import *  # noqa: F401,F403
    from boltz2nb.batch import capture_batch_context as capture_run_context  # noqa: F401
    from boltz2nb.batch import set_work_root

# The notebook sets BOLTZ2NB_BATCH_ROOT in Step 1 and re-imports this shim in later steps; follow the variable even when
# boltz2nb.batch was first imported earlier in the same kernel (its work root is fixed at import time otherwise).
if os.environ.get("BOLTZ2NB_BATCH_ROOT"):
    set_work_root(os.environ["BOLTZ2NB_BATCH_ROOT"])
