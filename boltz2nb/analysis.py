"""Load Boltz outputs and compute confidence / affinity summaries.

Units and conventions (Boltz-2 ``docs/prediction.md``):

* ``plddt_*.npz['plddt']`` is per token in [0, 1]; we report it on 0-100.
* ``pae_*.npz['pae']`` is a token x token matrix in Å, **asymmetric** (row =
  aligned token, column = scored token).  It must not be symmetrised by
  addition; the previous implementation plotted ``P + P.T``.
* ``affinity_pred_value`` is log10(IC50) with IC50 in µM (lower = tighter);
  ``affinity_probability_binary`` is the probability that the ligand is a
  binder.  Neither is a kcal/mol free energy.
"""
from __future__ import annotations

import glob
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .tokens import LayoutMismatch, Token, chain_indices, chain_kinds, resolve_layout

PAE_MAX = 32.0  # Boltz PAE bins end at ~32 Å; fixed scale keeps plots comparable


# ------------------------------------------------------------------ affinity
def affinity_to_ic50_um(value: float) -> float:
    return float(10.0 ** value)


def affinity_to_pic50(value: float) -> float:
    return 6.0 - float(value)  # µM -> M: pIC50 = -log10(IC50 [M]) = 6 - log10(IC50 [µM])


def affinity_to_kcal_per_mol(value: float, temperature_k: float = 298.15) -> float:
    """Approximate ΔG = RT ln(IC50 [M]); treats IC50 as a dissociation constant."""
    rt = 1.987204e-3 * temperature_k
    return rt * math.log(10.0) * (float(value) - 6.0)


def format_ic50(value: float) -> str:
    ic50_um = affinity_to_ic50_um(value)
    if ic50_um < 1e-3:
        return f"{ic50_um * 1e6:.1f} pM"
    if ic50_um < 1:
        return f"{ic50_um * 1e3:.1f} nM"
    if ic50_um < 1e3:
        return f"{ic50_um:.2f} µM"
    return f"{ic50_um / 1e3:.2f} mM"


def affinity_assessment(value: float) -> str:
    """Qualitative potency class on the log10(µM) scale."""
    if value < -2:
        return "Very potent (IC50 < 10 nM)"
    if value < -1:
        return "Potent (10-100 nM)"
    if value < 0:
        return "Moderate (0.1-1 µM)"
    if value < 1:
        return "Weak (1-10 µM)"
    return "Very weak / likely inactive (> 10 µM)"


def probability_assessment(prob: float) -> str:
    if prob >= 0.75:
        return "High confidence binder"
    if prob >= 0.4:
        return "Moderate confidence binder"
    return "Low confidence binder / likely decoy"


def plddt_assessment(mean_plddt: float) -> str:
    if mean_plddt >= 90:
        return "Very high confidence"
    if mean_plddt >= 70:
        return "High confidence"
    if mean_plddt >= 50:
        return "Low confidence"
    return "Very low confidence"


# ------------------------------------------------------------------ loading
@dataclass
class ModelResult:
    model_id: int
    structure_path: Path
    plddt: np.ndarray | None           # 0-100 per token (None when the layout is unknown)
    pae: np.ndarray | None             # token x token, Å
    confidence: dict[str, Any]
    tokens: list[Token]
    layout: str = "atomised"           # which token convention matched the arrays
    layout_note: str = ""              # set when per-token analysis had to be skipped
    chain_index: dict[str, list[int]] = field(default_factory=dict)
    chain_kind: dict[str, str] = field(default_factory=dict)

    @property
    def chain_ids(self) -> list[str]:
        return list(self.chain_index)

    @property
    def per_token(self) -> bool:
        """False when the confidence arrays could not be mapped onto the structure."""
        return self.plddt is not None and bool(self.chain_index)

    def chain_plddt(self, chain_id: str) -> np.ndarray:
        return self.plddt[self.chain_index[chain_id]]

    def chain_stats(self, chain_id: str) -> dict[str, Any]:
        p = self.chain_plddt(chain_id)
        return {
            "chain_id": chain_id,
            "kind": self.chain_kind.get(chain_id, "?"),
            "n_tokens": int(len(p)),
            "mean_plddt": float(p.mean()),
            "min_plddt": float(p.min()),
            "pct_confident": float((p > 70).mean() * 100),
            "pct_very_high": float((p > 90).mean() * 100),
            "assessment": plddt_assessment(float(p.mean())),
        }

    def pae_block(self, chain_a: str, chain_b: str) -> np.ndarray | None:
        if self.pae is None:
            return None
        return self.pae[np.ix_(self.chain_index[chain_a], self.chain_index[chain_b])]

    def interface_pae(self) -> dict[str, float]:
        """Mean PAE of each off-diagonal chain pair, averaged over both directions."""
        out: dict[str, float] = {}
        if self.pae is None or not self.per_token:
            return out
        ids = self.chain_ids
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                ab, ba = self.pae_block(a, b), self.pae_block(b, a)
                out[f"{a}-{b}"] = float((ab.mean() + ba.mean()) / 2)
        return out

    def chain_boundaries(self) -> list[tuple[str, int, int]]:
        return [(cid, idx[0], idx[-1]) for cid, idx in self.chain_index.items()]


@dataclass
class JobResult:
    job_name: str
    predictions_dir: Path
    models: list[ModelResult]
    affinity: dict[str, Any] | None

    @property
    def best(self) -> ModelResult:
        # Boltz writes models sorted by confidence_score; model_0 is the best.
        return self.models[0]

    @property
    def per_token(self) -> bool:
        return all(m.per_token for m in self.models)

    @property
    def layout_notes(self) -> list[str]:
        return [m.layout_note for m in self.models if m.layout_note]

    def ensemble_summary(self) -> dict[str, Any]:
        """Mean ± SD of headline metrics across diffusion samples."""
        keys = ["confidence_score", "ptm", "iptm", "ligand_iptm", "protein_iptm",
                "complex_plddt", "complex_iplddt", "complex_pde", "complex_ipde"]
        summary: dict[str, Any] = {"n_models": len(self.models)}
        for k in keys:
            vals = [m.confidence.get(k) for m in self.models if isinstance(m.confidence.get(k), (int, float))]
            if vals:
                arr = np.asarray(vals, dtype=float)
                summary[k] = {"mean": float(arr.mean()), "sd": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
                              "min": float(arr.min()), "max": float(arr.max()), "values": [float(v) for v in arr]}
        if self.per_token:
            mean_plddts = np.asarray([m.plddt.mean() for m in self.models])
            summary["mean_plddt"] = {"mean": float(mean_plddts.mean()),
                                     "sd": float(mean_plddts.std(ddof=1)) if len(mean_plddts) > 1 else 0.0}
        ipae = [m.interface_pae() for m in self.models]
        if ipae and ipae[0]:
            summary["interface_pae"] = {pair: {"mean": float(np.mean([d[pair] for d in ipae])),
                                               "sd": float(np.std([d[pair] for d in ipae], ddof=1)) if len(ipae) > 1 else 0.0}
                                        for pair in ipae[0]}
        return summary

    def affinity_summary(self) -> dict[str, Any] | None:
        if not self.affinity:
            return None
        a = self.affinity
        value, prob = float(a["affinity_pred_value"]), float(a["affinity_probability_binary"])
        members = []
        for i in (1, 2):
            if f"affinity_pred_value{i}" in a:
                members.append({"model": i, "value": float(a[f"affinity_pred_value{i}"]),
                                "probability": float(a.get(f"affinity_probability_binary{i}", float("nan")))})
        return {
            "log10_ic50_um": value,
            "ic50": format_ic50(value),
            "ic50_um": affinity_to_ic50_um(value),
            "pic50": affinity_to_pic50(value),
            "delta_g_kcal_mol_approx": affinity_to_kcal_per_mol(value),
            "binding_probability": prob,
            "potency_class": affinity_assessment(value),
            "probability_class": probability_assessment(prob),
            "ensemble_members": members,
            "member_spread": (max(m["value"] for m in members) - min(m["value"] for m in members)) if len(members) > 1 else 0.0,
        }

    def metrics_table(self) -> list[dict[str, Any]]:
        rows = []
        for m in self.models:
            c = m.confidence
            rows.append({"model": m.model_id,
                         "confidence_score": c.get("confidence_score"), "ptm": c.get("ptm"), "iptm": c.get("iptm"),
                         "ligand_iptm": c.get("ligand_iptm"), "protein_iptm": c.get("protein_iptm"),
                         "complex_plddt": c.get("complex_plddt"), "complex_iplddt": c.get("complex_iplddt"),
                         "complex_pde": c.get("complex_pde"),
                         "mean_plddt": float(m.plddt.mean()) if m.per_token else None,
                         **{f"pae_{k}": v for k, v in m.interface_pae().items()}})
        return rows


def _model_ids(pred_dir: Path, stem: str) -> list[int]:
    ids = set()
    for f in pred_dir.glob(f"plddt_{stem}_model_*.npz"):
        m = re.search(r"_model_(\d+)\.npz$", f.name)
        if m:
            ids.add(int(m.group(1)))
    return sorted(ids)


def _structure_for(pred_dir: Path, stem: str, model_id: int) -> Path:
    for ext in ("pdb", "cif", "mmcif"):
        p = pred_dir / f"{stem}_model_{model_id}.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"No structure file for model {model_id} in {pred_dir}")


def load_model(pred_dir: Path | str, stem: str, model_id: int) -> ModelResult:
    pred_dir = Path(pred_dir)
    plddt = np.load(pred_dir / f"plddt_{stem}_model_{model_id}.npz")["plddt"].astype(float) * 100.0
    pae_path = pred_dir / f"pae_{stem}_model_{model_id}.npz"
    pae = np.load(pae_path)["pae"].astype(float) if pae_path.exists() else None
    conf_path = pred_dir / f"confidence_{stem}_model_{model_id}.json"
    confidence = json.loads(conf_path.read_text()) if conf_path.exists() else {}
    structure_path = _structure_for(pred_dir, stem, model_id)
    try:
        tokens, layout = resolve_layout(structure_path, len(plddt))
    except LayoutMismatch as exc:
        # Keep the ranking metrics and affinity usable rather than failing the whole analysis.
        return ModelResult(model_id, structure_path, None, None, confidence, [], "unknown", str(exc))
    if pae is not None and pae.shape[0] != len(tokens):
        return ModelResult(model_id, structure_path, None, None, confidence, tokens,
                           layout, f"PAE matrix is {pae.shape[0]}x{pae.shape[1]} but the model has "
                                   f"{len(tokens)} tokens; per-token analysis skipped.")
    return ModelResult(model_id, structure_path, plddt, pae, confidence, tokens, layout, "",
                       chain_indices(tokens), chain_kinds(tokens))


def load_job(pred_dir: Path | str, job_name: str | None = None) -> JobResult:
    pred_dir = Path(pred_dir)
    stem = job_name or pred_dir.name
    ids = _model_ids(pred_dir, stem)
    if not ids:
        raise FileNotFoundError(f"No plddt_{stem}_model_*.npz files in {pred_dir}")
    models = [load_model(pred_dir, stem, i) for i in ids]
    # Boltz 2.2.x writes affinity_<stem>.json; the community fork writes one file per
    # binder copy as affinity_<stem>_<chain>.json.
    aff_files = sorted(pred_dir.glob(f"affinity_{stem}*.json"))
    affinity = json.loads(aff_files[0].read_text()) if aff_files else None
    if affinity is not None and len(aff_files) > 1:
        affinity["_additional_binders"] = {f.stem.replace(f"affinity_{stem}_", ""): json.loads(f.read_text())
                                           for f in aff_files[1:]}
    return JobResult(stem, pred_dir, models, affinity)


# ------------------------------------------------------------------ plotting
def plot_plddt(model: ModelResult, out_path: Path | str) -> Path | None:
    if not model.per_token:
        return None
    from .ui.figures import draw_plddt
    return draw_plddt(model.plddt, model.chain_boundaries(), model.model_id, out_path)


def plot_pae(model: ModelResult, out_path: Path | str) -> Path | None:
    if model.pae is None or not model.per_token:
        return None
    from .ui.figures import draw_pae
    return draw_pae(model.pae, model.chain_boundaries(), model.model_id, out_path, vmax=PAE_MAX)


def plot_affinity_card(job: JobResult, out_path: Path | str) -> Path | None:
    summ = job.affinity_summary()
    if not summ:
        return None
    from .ui.figures import draw_affinity
    members = [(f"member {m['model']}", m["value"]) for m in summ["ensemble_members"]]
    return draw_affinity(summ["binding_probability"], str(summ["ic50"]), summ["log10_ic50_um"], members, out_path)


def plot_ensemble(job: JobResult, out_path: Path | str) -> Path | None:
    if len(job.models) < 2 or not any(r.get("confidence_score") is not None for r in job.metrics_table()):
        return None
    from .ui.figures import draw_ensemble
    return draw_ensemble(job.metrics_table(), out_path)


def generate_plots(job: JobResult, plots_dir: Path | str, model_ids: Sequence[int] | None = None) -> dict[str, Any]:
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Any] = {"models": {}}
    for m in job.models:
        if model_ids is not None and m.model_id not in model_ids:
            continue
        plddt_path = plot_plddt(m, plots_dir / f"{job.job_name}_model_{m.model_id}_plddt.png")
        out["models"][m.model_id] = {
            "plddt": str(plddt_path) if plddt_path else None,
            "pae": (lambda p: str(p) if p else None)(plot_pae(m, plots_dir / f"{job.job_name}_model_{m.model_id}_pae.png")),
        }
    aff = plot_affinity_card(job, plots_dir / f"{job.job_name}_affinity.png")
    out["affinity"] = str(aff) if aff else None
    ens = plot_ensemble(job, plots_dir / f"{job.job_name}_ensemble.png")
    out["ensemble"] = str(ens) if ens else None
    return out


def summary_dict(job: JobResult) -> dict[str, Any]:
    best = job.best
    return {
        "job_name": job.job_name,
        "n_models": len(job.models),
        "best_model": best.model_id,
        "token_layout": best.layout,
        "layout_notes": job.layout_notes,
        "chains": [best.chain_stats(c) for c in best.chain_ids] if best.per_token else [],
        "interface_pae": best.interface_pae(),
        "confidence": best.confidence,
        "ensemble": job.ensemble_summary(),
        "affinity": job.affinity_summary(),
        "models": job.metrics_table(),
    }


def find_prediction_dirs(root: Path | str) -> list[Path]:
    return sorted(Path(p).parent for p in glob.glob(str(Path(root) / "**" / "plddt_*_model_0.npz"), recursive=True))
