# @title Boltz2 Engine
# Thin shim: v1 and v2 share one implementation in scripts/common/Boltz_Run.py
from pathlib import Path as _P

_here = _P(globals().get("__file__", "/content/boltz_data/scripts/v2/Boltz_Run.py")).resolve().parent
_impl = _here.parent / "common" / "Boltz_Run.py"
exec(compile(_impl.read_text(), str(_impl), "exec"))
