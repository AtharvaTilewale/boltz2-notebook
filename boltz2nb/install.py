"""Choose and verify the Boltz engine distribution for the running interpreter."""
from __future__ import annotations

import importlib
import subprocess
import sys
from collections.abc import Sequence

from . import BOLTZ_COMMUNITY_PIN, BOLTZ_OFFICIAL_PIN

NOTEBOOK_EXTRAS: Sequence[str] = ("biopython", "numpy", "matplotlib", "pyyaml", "py3Dmol", "rdkit")


def pick_boltz_requirement(version_info=None) -> str:
    """Official ``boltz`` on Python <3.13, the community fork on 3.13+.

    Official boltz 2.2.1 publishes ``Requires-Python: <3.13,>=3.10``; on a
    Python 3.13 Colab runtime a plain ``pip install boltz`` fails to resolve.
    """
    vi = version_info or sys.version_info
    if (vi.major, vi.minor) >= (3, 13):
        return BOLTZ_COMMUNITY_PIN
    return BOLTZ_OFFICIAL_PIN


def install_commands(python: str = sys.executable, requirement: str | None = None) -> list[list[str]]:
    """Return the ordered install commands (uv first, pip fallback is the caller's job)."""
    req = requirement or pick_boltz_requirement()
    pkgs = [req, *NOTEBOOK_EXTRAS]
    return [
        [python, "-m", "pip", "install", "-q", "uv"],
        ["uv", "pip", "install", "--system", "--python", python, *pkgs],
    ]


def pip_fallback_command(python: str = sys.executable, requirement: str | None = None) -> list[str]:
    req = requirement or pick_boltz_requirement()
    return [python, "-m", "pip", "install", "-q", req, *NOTEBOOK_EXTRAS]


def engine_version() -> str | None:
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover
        return None
    for dist in ("boltz", "boltz-community"):
        try:
            return f"{dist} {metadata.version(dist)}"
        except metadata.PackageNotFoundError:
            continue
    return None


def verify_installation(python: str = sys.executable) -> tuple[bool, str]:
    """Import boltz and torch in a fresh interpreter; return (ok, message)."""
    code = (
        "import torch, boltz, importlib.metadata as m;"
        "v=next((f'{d} {m.version(d)}' for d in ('boltz','boltz-community') "
        "if any(x.metadata['Name']==d for x in m.distributions())), 'unknown');"
        "print('engine', v, '| torch', torch.__version__, '| cuda', torch.cuda.is_available())"
    )
    res = subprocess.run([python, "-c", code], capture_output=True, text=True)
    ok = res.returncode == 0
    return ok, (res.stdout or res.stderr).strip()


def module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False
