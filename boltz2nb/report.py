"""Report generation: plots, ``summary.json`` and a self-contained HTML report (see ``ui/results.py``)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .analysis import JobResult, generate_plots, summary_dict
from .ui.results import render_report_document, render_report_fragment


def _b64(path: str | None) -> str | None:
    return base64.b64encode(Path(path).read_bytes()).decode() if path and Path(path).exists() else None


def _figures(plots: dict[str, Any]) -> dict[str, Any]:
    return {
        "models": {mid: {k: _b64(v) for k, v in p.items()} for mid, p in plots.get("models", {}).items()},
        "ensemble": _b64(plots.get("ensemble")),
        "affinity": _b64(plots.get("affinity")),
    }


# The structure is embedded in the notebook output (saved with the .ipynb); past this size only the HTML report carries it.
INLINE_STRUCTURE_MAX_BYTES = 8_000_000


def structure_text(job: JobResult) -> tuple[str | None, str]:
    """The best sample's structure file as text and its viewer format (``pdb`` or ``cif``); (None, 'pdb') when it cannot be read."""
    p = job.best.structure_path
    try:
        return p.read_text(), ("pdb" if p.suffix.lower() == ".pdb" else "cif")
    except OSError:
        return None, "pdb"


def build_report(job: JobResult, plots: dict[str, Any], run_context: dict[str, Any] | None = None, ligand_svg: str | None = None,
                 embed_structure: bool = True, runtime: float | None = None, fragment: bool = False,
                 files: list[tuple[str, str]] | None = None) -> str:
    """HTML for the report; ``fragment=True`` returns an embeddable block instead of a full document."""
    summary = summary_dict(job)
    pdb, fmt = structure_text(job) if embed_structure else (None, "pdb")
    figures = _figures(plots)
    if fragment:
        return render_report_fragment(summary, figures, pdb, run_context, ligand_svg, runtime, files=files, structure_format=fmt)
    return render_report_document(summary, figures, pdb, run_context, ligand_svg, runtime, structure_format=fmt)


def write_report(job: JobResult, out_dir: Path | str, run_context: dict[str, Any] | None = None, ligand_svg: str | None = None,
                 runtime: float | None = None) -> dict[str, Any]:
    out_dir = Path(out_dir)
    plots = generate_plots(job, out_dir / "plots")
    summary = summary_dict(job)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    report_path = out_dir / f"{job.job_name}_report.html"
    report_path.write_text(build_report(job, plots, run_context, ligand_svg, runtime=runtime))
    files = [("report", str(report_path)), ("summary", str(out_dir / "summary.json")), ("plots", str(out_dir / "plots"))]
    # the notebook view shows the 3-D viewer as well; only a structure too big to keep in the .ipynb is left to the HTML report
    size = job.best.structure_path.stat().st_size if job.best.structure_path.exists() else 0
    fragment = build_report(job, plots, run_context, ligand_svg, embed_structure=size <= INLINE_STRUCTURE_MAX_BYTES, runtime=runtime,
                            fragment=True, files=files)
    if size > INLINE_STRUCTURE_MAX_BYTES:
        fragment += (f'<p class="bz-hint">The structure ({size / 1e6:.0f} MB) is too large to show inside the notebook; '
                     f'open {report_path.name} for the 3-D viewer.</p>')
    return {"report": str(report_path), "summary": str(out_dir / "summary.json"), "plots": plots, "fragment": fragment}
