"""Run parameters: defaults, profiles, and the ``run_params.txt`` format.

``run_params.txt`` is a flat ``key = value`` file written by the parameter GUI
and read by the runner.  Defaults here are the ones documented in the README;
previously the runner and the docs disagreed (step_scale 10.0 vs 1.638,
max_msa_seqs 254 vs 8192, sampling_steps 50 vs 200).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "job_name": "boltz2_job",
    "recycling_steps": 3,
    "sampling_steps": 200,
    "diffusion_samples": 1,
    "step_scale": 1.638,
    "max_msa_seqs": 8192,
    "subsample_msa": True,
    "num_subsampled_msa": 1024,
    "msa_pairing_strategy": "greedy",
    "use_potentials": False,
    "override": False,
    "output_format": "pdb",
    "seed": None,
    "write_full_pae": True,
    "max_parallel_samples": 5,
    "num_workers": None,
    "accelerator": None,  # None -> Boltz default (gpu); "cpu" forces CPU
}

PROFILES: dict[str, dict[str, Any]] = {
    "fast": {"recycling_steps": 2, "sampling_steps": 50, "diffusion_samples": 1, "max_msa_seqs": 256},
    "balanced": {},
    "scientific": {"recycling_steps": 5, "sampling_steps": 200, "diffusion_samples": 5,
                   "max_msa_seqs": 8192, "use_potentials": True},
}

RANGES = {
    "recycling_steps": (1, 20),
    "sampling_steps": (10, 1000),
    "diffusion_samples": (1, 25),
    "step_scale": (0.5, 5.0),
    "max_msa_seqs": (1, 16384),
    "num_subsampled_msa": (1, 16384),
    "max_parallel_samples": (1, 25),
    "num_workers": (0, 32),
}
PAIRING_STRATEGIES = ("greedy", "complete")
OUTPUT_FORMATS = ("pdb", "mmcif")
ACCELERATORS = (None, "", "gpu", "cpu", "tpu")


def parse_value(value_str: str) -> Any:
    """Convert a string from ``run_params.txt`` to bool/int/float/str."""
    v = value_str.strip()
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.lower() in ("none", "null", ""):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def parse_run_params_text(text: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        params[key.strip()] = parse_value(val)
    return params


def load_run_params(path: Path | str) -> dict[str, Any]:
    merged = dict(DEFAULTS)
    merged.update(parse_run_params_text(Path(path).read_text()))
    return merged


def serialize_run_params(params: dict[str, Any]) -> str:
    lines = []
    for k, v in params.items():
        if isinstance(v, bool):
            s = "true" if v else "false"
        elif v is None:
            s = "none"
        elif isinstance(v, str):
            s = f'"{v}"'
        else:
            s = str(v)
        lines.append(f"{k} = {s}")
    return "\n".join(lines) + "\n"


def apply_profile(profile: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """DEFAULTS <- profile preset <- explicit overrides (explicit values always win)."""
    key = (profile or "balanced").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown profile '{profile}'. Choose from {sorted(PROFILES)}.")
    p = dict(DEFAULTS)
    p.update(PROFILES[key])
    if overrides:
        p.update(overrides)
    return p


def validate_run_params(params: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems (empty list == valid)."""
    problems: list[str] = []
    name = str(params.get("job_name", "")).strip()
    if not name:
        problems.append("job_name is required.")
    elif any(c in name for c in "/\\ \t\n"):
        problems.append("job_name must not contain spaces or path separators.")
    for key, (lo, hi) in RANGES.items():
        if key not in params or params[key] is None:
            continue
        try:
            val = float(params[key])
        except (TypeError, ValueError):
            problems.append(f"{key} must be numeric (got {params[key]!r}).")
            continue
        if not (lo <= val <= hi):
            problems.append(f"{key}={params[key]} is outside the allowed range [{lo}, {hi}].")
    strat = params.get("msa_pairing_strategy")
    if strat not in PAIRING_STRATEGIES:
        problems.append(f"msa_pairing_strategy must be one of {PAIRING_STRATEGIES} (got {strat!r}).")
    if params.get("accelerator") not in ACCELERATORS:
        problems.append(f"accelerator must be one of gpu/cpu/tpu (got {params.get('accelerator')!r}).")
    fmt = params.get("output_format", "pdb")
    if fmt not in OUTPUT_FORMATS:
        problems.append(f"output_format must be one of {OUTPUT_FORMATS} (got {fmt!r}).")
    return problems
