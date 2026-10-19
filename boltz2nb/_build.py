"""Is the copy of ``boltz2nb`` loaded in this process the code that is on disk now?

A Colab runtime keeps its kernel (and every module it imported) while Cell 1 fast-forwards the clone underneath it, so a script from the new
code could call a function of the old code that is still loaded (``render_result_card() got an unexpected keyword argument``). Each notebook
script therefore loads *this file by path* (it imports nothing from the package, so an old loaded package cannot get in the way) and calls
``drop_stale_modules`` before its own imports.
"""
from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path

SUFFIXES = {".py", ".js", ".css", ".html"}


def fingerprint(package_dir: str | Path) -> str:
    """A short hash of the source and interface files of the package (names and contents; not timestamps, not ``__pycache__``)."""
    root = Path(package_dir)
    digest = hashlib.sha1()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in SUFFIXES and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def drop_stale_modules(package: object | None = None) -> int:
    """Forget the loaded ``boltz2nb`` modules when they are not the files on disk, so the next import reads the new code.

    Returns how many modules were dropped (0 when nothing is loaded or the loaded copy is current). A copy loaded before this mechanism
    existed has no ``BUILD_ID`` and counts as stale. The colour theme the user picked with the switch is kept.
    """
    pkg = package if package is not None else sys.modules.get("boltz2nb")
    if pkg is None or not getattr(pkg, "__file__", None):
        return 0
    try:
        current = fingerprint(Path(pkg.__file__).parent)
    except OSError:
        return 0
    if getattr(pkg, "BUILD_ID", None) == current:
        return 0
    theme = getattr(sys.modules.get("boltz2nb.ui.theme"), "_choice", None)
    names = [m for m in list(sys.modules) if m == "boltz2nb" or m.startswith("boltz2nb.")]
    for name in names:
        del sys.modules[name]
    importlib.invalidate_caches()
    if theme:
        try:
            importlib.import_module("boltz2nb.ui.theme").set_theme(theme)
        except Exception:  # noqa: BLE001  (a cosmetic preference must never stop a run)
            pass
    return len(names)
