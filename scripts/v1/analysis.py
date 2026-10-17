# @title Analyse Results
# Thin shim: v1 and v2 share one implementation in scripts/common/analysis.py
from pathlib import Path as _P

_here = _P(globals().get("__file__", "/content/boltz_data/scripts/v1/analysis.py")).resolve().parent
_impl = _here.parent / "common" / "analysis.py"
exec(compile(_impl.read_text(), str(_impl), "exec"))
