# @title Install Dependencies and Boltz2 with CUDA support
# Thin shim: v1 and v2 share one implementation in scripts/common/setup.py
from pathlib import Path as _P

_here = _P(globals().get("__file__", "/content/boltz_data/scripts/v2/setup.py")).resolve().parent
_impl = _here.parent / "common" / "setup.py"
exec(compile(_impl.read_text(), str(_impl), "exec"))
