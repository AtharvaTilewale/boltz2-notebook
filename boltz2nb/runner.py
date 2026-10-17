"""Construct and execute ``boltz predict`` with live log streaming and provenance."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .install import engine_version
from .run_params import DEFAULTS
from .yaml_builder import yaml_has_explicit_msa

MSA_SERVER_URL = "https://api.colabfold.com"


def build_boltz_cmd(yaml_path: Path | str, out_dir: Path | str, params: dict[str, Any],
                    use_msa_server: bool | None = None, executable: str = "boltz") -> list[str]:
    """Single source of truth for the command line (used by single-job and batch)."""
    p = dict(DEFAULTS)
    p.update(params)
    yaml_path, out_dir = Path(yaml_path), Path(out_dir)
    if use_msa_server is None:
        use_msa_server = not yaml_has_explicit_msa(yaml_path.read_text())
    cmd = [executable, "predict", str(yaml_path), "--out_dir", str(out_dir),
           "--recycling_steps", str(int(p["recycling_steps"])),
           "--sampling_steps", str(int(p["sampling_steps"])),
           "--diffusion_samples", str(int(p["diffusion_samples"])),
           "--step_scale", str(float(p["step_scale"])),
           "--max_msa_seqs", str(int(p["max_msa_seqs"])),
           "--output_format", str(p.get("output_format", "pdb"))]
    if use_msa_server:
        cmd += ["--use_msa_server", "--msa_pairing_strategy", str(p["msa_pairing_strategy"])]
    if p.get("subsample_msa", True):
        cmd += ["--subsample_msa", "--num_subsampled_msa", str(int(p["num_subsampled_msa"]))]
    if p.get("max_parallel_samples"):
        cmd += ["--max_parallel_samples", str(int(p["max_parallel_samples"]))]
    if p.get("seed") not in (None, ""):
        cmd += ["--seed", str(int(p["seed"]))]
    if p.get("accelerator") not in (None, ""):
        cmd += ["--accelerator", str(p["accelerator"])]
    if p.get("num_workers") not in (None, ""):
        cmd += ["--num_workers", str(int(p["num_workers"]))]
    if p.get("write_full_pae", True):
        cmd += ["--write_full_pae"]
    if p.get("use_potentials"):
        cmd += ["--use_potentials"]
    if p.get("override"):
        cmd += ["--override"]
    return cmd


def gpu_info() -> dict[str, Any]:
    info: dict[str, Any] = {"cuda_available": False}
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
    except Exception:
        pass
    return info


def capture_run_context(params: dict[str, Any], cmd: list[str], yaml_path: Path | str) -> dict[str, Any]:
    import hashlib
    yaml_text = Path(yaml_path).read_text()
    return {
        "boltz2nb_version": __version__,
        "engine": engine_version(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": cmd,
        "run_params": params,
        "input_yaml_sha1": hashlib.sha1(yaml_text.encode()).hexdigest(),
        "input_yaml": yaml_text,
        **gpu_info(),
    }


def unique_output_dir(path: Path | str) -> Path:
    """Never clobber an existing job: suffix with a timestamp instead."""
    path = Path(path)
    if not path.exists():
        return path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cand = path.with_name(f"{path.name}_{stamp}")
    i = 1
    while cand.exists():
        cand = path.with_name(f"{path.name}_{stamp}_{i}")
        i += 1
    return cand


def run_boltz(cmd: list[str], log_path: Path | str, on_line: Callable[[str], None] | None = None,
              env: dict[str, str] | None = None) -> dict[str, Any]:
    """Run the command, stream merged stdout/stderr to ``log_path`` and ``on_line``."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    merged_env = dict(os.environ)
    merged_env.setdefault("PYTHONUNBUFFERED", "1")
    if env:
        merged_env.update(env)
    lines: list[str] = []
    with open(log_path, "w") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                bufsize=1, env=merged_env)
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            lines.append(line)
            if on_line:
                on_line(line.rstrip("\n"))
        proc.wait()
    return {"return_code": proc.returncode, "runtime_sec": round(time.time() - t0, 1),
            "log_path": str(log_path), "tail": "".join(lines[-60:])}


def write_json(path: Path | str, obj: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, default=str))


def boltz_available() -> bool:
    return shutil.which("boltz") is not None
