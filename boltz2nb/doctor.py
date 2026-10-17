"""Inspect a Boltz output directory and report what the analysis can and cannot map.

    python -m boltz2nb.doctor /content/boltz_data/<job>

Prints the engine version, the files found, the confidence-array lengths and the token
count under every known convention, so a layout mismatch can be diagnosed without
sharing sequences or structures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from .install import engine_version
from .paths import find_predictions_dir
from .tokens import layout_counts


def report(target: Path | str) -> dict:
    target = Path(target)
    pred = target if list(target.glob("plddt_*_model_*.npz")) else find_predictions_dir(target)
    info: dict = {"engine": engine_version(), "target": str(target), "predictions_dir": str(pred) if pred else None,
                  "models": []}
    if pred is None:
        return info
    ctx = target / "run_context.json"
    if ctx.exists():
        try:
            c = json.loads(ctx.read_text())
            info["run_context"] = {k: c.get(k) for k in ("engine", "boltz2nb_version", "python", "gpu_name", "command")}
        except Exception:  # noqa: BLE001
            pass
    stem = pred.name
    for npz in sorted(pred.glob(f"plddt_{stem}_model_*.npz")):
        mid = npz.stem.rsplit("_", 1)[1]
        entry: dict = {"model": mid, "plddt_len": int(len(np.load(npz)["plddt"]))}
        pae = pred / f"pae_{stem}_model_{mid}.npz"
        if pae.exists():
            entry["pae_shape"] = list(np.load(pae)["pae"].shape)
        struct = next((p for ext in ("pdb", "cif", "mmcif") if (p := pred / f"{stem}_model_{mid}.{ext}").exists()), None)
        if struct is not None:
            entry["structure"] = struct.name
            entry["layout_counts"] = layout_counts(struct)
            entry["match"] = next((k for k, v in entry["layout_counts"].items() if v == entry["plddt_len"]), None)
        info["models"].append(entry)
    info["affinity_files"] = [p.name for p in sorted(pred.glob("affinity_*.json"))]
    info["confidence_files"] = [p.name for p in sorted(pred.glob("confidence_*.json"))]
    return info


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    target = Path(argv[0])
    if not target.exists():
        print(f"No such file or directory: {target}", file=sys.stderr)
        return 2
    info = report(target)
    print(json.dumps(info, indent=2))
    if info["predictions_dir"] is None:
        print(f"\nNo Boltz prediction files (plddt_*_model_*.npz) found under {target}.", file=sys.stderr)
        return 1
    unmatched = [m for m in info["models"] if m.get("match") is None and "layout_counts" in m]
    if unmatched:
        print("\nNo known token layout matches these models - please send this output to the maintainers:")
        for m in unmatched:
            print(f"  model {m['model']}: arrays {m['plddt_len']} vs layouts {m['layout_counts']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
