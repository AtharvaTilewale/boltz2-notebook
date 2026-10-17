"""Filesystem conventions shared by the notebooks, scripts and batch engine.

Every path is derived from ``BASE_DIR`` which defaults to the Colab location
``/content/boltz_data`` but can be redirected with the ``BOLTZ2NB_BASE_DIR``
environment variable so the same scripts run on a workstation or in CI.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_colab() -> bool:
    """True when running inside a Google Colab kernel."""
    return "google.colab" in sys.modules or "COLAB_RELEASE_TAG" in os.environ


def base_dir() -> Path:
    """Working directory for inputs and job outputs."""
    return Path(os.environ.get("BOLTZ2NB_BASE_DIR", "/content/boltz_data")).expanduser()


def upload_dir(kind: str | None = None) -> Path:
    d = base_dir() / "uploads"
    if kind:
        d = d / kind
    return d


def job_dir(job_name: str) -> Path:
    """Top-level output directory passed to ``boltz predict --out_dir``."""
    return base_dir() / job_name


def predictions_dir(job_name: str, out_dir: Path | None = None) -> Path:
    """Directory where Boltz writes models and JSON/NPZ confidence files.

    Boltz lays out ``<out_dir>/boltz_results_<yaml_stem>/predictions/<yaml_stem>/``.
    The notebooks name the YAML after the job, so stem == job_name.
    """
    out = out_dir or job_dir(job_name)
    return out / f"boltz_results_{job_name}" / "predictions" / job_name


def find_predictions_dir(out_dir: Path) -> Path | None:
    """Locate the predictions directory under an arbitrary ``--out_dir``."""
    out_dir = Path(out_dir)
    for cand in sorted(out_dir.glob("boltz_results_*/predictions/*")):
        if cand.is_dir():
            return cand
    return None


def ensure_dirs() -> None:
    for d in (base_dir(), upload_dir("templates"), upload_dir("msas")):
        d.mkdir(parents=True, exist_ok=True)
