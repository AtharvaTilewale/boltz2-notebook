"""Result card (in-notebook) and standalone HTML report, built from ``analysis.summary_dict``."""
from __future__ import annotations

import html
import json
import math
import uuid
from typing import Any

from .. import __version__
from .icons import brand_mark, icon, sprite
from .render import FONT_LINKS, read_asset
from .theme import theme_attr, theme_button, theme_script

PLDDT_BANDS = [(90, "#0053D6", "Very high (90-100)"), (70, "#65CBF3", "High (70-90)"), (50, "#FFDB13", "Low (50-70)"), (0, "#FF7D45", "Very low (<50)")]


def esc(x: Any) -> str:
    return html.escape(str(x))


def _f(x: Any, nd: int = 2, dash: str = "-") -> str:
    return dash if x is None else f"{float(x):.{nd}f}"


def tone_confidence(v: float | None) -> str | None:
    return None if v is None else "ok" if v >= 0.8 else "warn" if v >= 0.6 else "err"


def tone_plddt(v: float | None) -> str | None:
    return None if v is None else "ok" if v >= 90 else None if v >= 70 else "warn" if v >= 50 else "err"


def tone_pae(v: float | None) -> str | None:
    return None if v is None else "ok" if v <= 5 else "warn" if v <= 10 else "err"


def kpi(label: str, value: str, sub: str = "", tone: str | None = None, unit: str = "") -> str:
    t = f' data-tone="{tone}"' if tone else ""
    u = f"<small>{esc(unit)}</small>" if unit else ""
    s = f'<div class="bz-kpi-s">{esc(sub)}</div>' if sub else ""
    return f'<div class="bz-kpi"{t}><div class="bz-kpi-l">{esc(label)}</div><div class="bz-kpi-v">{esc(value)}{u}</div>{s}</div>'


def render_kpis(s: dict[str, Any]) -> str:
    best = next((m for m in s["models"] if m["model"] == s["best_model"]), s["models"][0])
    c = s["confidence"]
    tiles = [kpi("Confidence", _f(c.get("confidence_score")), "0.8 x pLDDT + 0.2 x ipTM", tone_confidence(c.get("confidence_score")))]
    if c.get("iptm") not in (None, 0):
        tiles.append(kpi("Interface ipTM", _f(c.get("iptm")), "chain-chain confidence", tone_confidence(c.get("iptm"))))
    mp = best.get("mean_plddt")
    if mp is not None:
        tiles.append(kpi("Mean pLDDT", _f(mp, 1), "per-token, 0-100", tone_plddt(mp)))
    ip = s.get("interface_pae") or {}
    if ip:
        low = min(ip.values())
        tiles.append(kpi("Interface PAE", _f(low, 1), "best chain pair, lower is better", tone_pae(low), "A"))
    a = s.get("affinity")
    if a:
        tiles.append(kpi("Binding probability", f"{a['binding_probability'] * 100:.0f}", a["probability_class"], "ok" if a["binding_probability"] >= 0.75 else "warn" if a["binding_probability"] >= 0.4 else "err", "%"))
    return f'<div class="bz-kpis">{"".join(tiles)}</div>'


def ring(prob: float, tone: str) -> str:
    r = 34
    c = 2 * math.pi * r
    return (f'<svg class="bz-ring" width="92" height="92" viewBox="0 0 80 80" role="img" aria-label="Binding probability {prob * 100:.0f} percent">'
            f'<circle cx="40" cy="40" r="{r}" fill="none" stroke="var(--bz-surface-3)" stroke-width="8"/>'
            f'<circle cx="40" cy="40" r="{r}" fill="none" stroke="var(--bz-{tone})" stroke-width="8" stroke-linecap="round" '
            f'stroke-dasharray="{c * prob:.1f} {c:.1f}" transform="rotate(-90 40 40)"/>'
            f'<text x="40" y="45" text-anchor="middle" font-size="17" font-weight="700" fill="var(--bz-text)" font-family="var(--bz-font)">{prob * 100:.0f}%</text></svg>')


def render_affinity(s: dict[str, Any]) -> str:
    a = s.get("affinity")
    if not a:
        return ""
    prob = a["binding_probability"]
    tone = "ok" if prob >= 0.75 else "warn" if prob >= 0.4 else "err"
    members = "".join(f'<span class="bz-prop">model {m["model"]}: {m["value"]:.2f}</span>' for m in a.get("ensemble_members", []))
    spread = ""
    if a.get("member_spread", 0) > 1.0:
        spread = (f'<div class="bz-alert bz-alert--warn" style="margin-top:12px">{icon("alert")}<div>The two affinity ensemble members differ by '
                  f'{a["member_spread"]:.2f} log units (at least 10x in IC50). Treat the value as uncertain.</div></div>')
    return (f'<div><div class="bz-sec-h"><h3>Binding affinity</h3><span>Boltz-2 affinity module</span></div>'
            f'<div class="bz-aff">{ring(prob, tone)}<div><h4>PREDICTED IC50</h4><div class="bz-aff-v">{esc(a["ic50"])}</div>'
            f'<div class="bz-muted" style="font-size:13px;margin-top:2px">{esc(a["potency_class"])} - {esc(a["probability_class"])}</div>'
            f'<dl><div><dt>log10 IC50 (uM)</dt><dd>{a["log10_ic50_um"]:.2f}</dd></div><div><dt>pIC50</dt><dd>{a["pic50"]:.2f}</dd></div>'
            f'<div><dt>approx. dG</dt><dd>{a["delta_g_kcal_mol_approx"]:.1f} kcal/mol</dd></div></dl>'
            f'<div class="bz-inline" style="margin-top:10px">{members}</div></div></div>{spread}'
            f'<p class="bz-hint" style="margin-top:10px">Use the binding probability to separate binders from decoys and the IC50 only to rank close analogues. '
            f'The affinity module is trained on small molecules and is not meaningful for peptides or protein binders.</p></div>')


def render_chain_table(s: dict[str, Any]) -> str:
    if not s["chains"]:
        return ""
    rows = ""
    for c in s["chains"]:
        v = c["mean_plddt"]
        t = tone_plddt(v)
        bar = f'<div class="bz-bar"{f" data-tone={chr(34)}{t}{chr(34)}" if t else ""}><i style="width:{max(2, min(100, v)):.0f}%"></i></div>'
        rows += (f'<tr><td><span class="bz-token">{esc(c["chain_id"])}</span> <span class="bz-muted">{esc(c["kind"])}</span></td><td>{c["n_tokens"]}</td>'
                 f'<td>{v:.1f}</td><td style="min-width:120px">{bar}</td><td>{c["pct_confident"]:.0f}%</td><td style="text-align:left">{esc(c["assessment"])}</td></tr>')
    return (f'<div><div class="bz-sec-h"><h3>Chains</h3><span>best sample</span></div><div class="bz-table-wrap"><table class="bz-table"><thead><tr>'
            f'<th>Chain</th><th>Tokens</th><th>Mean pLDDT</th><th></th><th>pLDDT &gt; 70</th><th style="text-align:left">Assessment</th></tr></thead><tbody>{rows}</tbody></table></div></div>')


def render_sample_table(s: dict[str, Any]) -> str:
    cols = [("model", "Sample"), ("confidence_score", "Confidence"), ("ptm", "pTM"), ("iptm", "ipTM"), ("ligand_iptm", "Ligand ipTM"),
            ("complex_plddt", "cpLDDT"), ("complex_pde", "cPDE"), ("mean_plddt", "Mean pLDDT")]
    cols = [(k, h) for k, h in cols if k == "model" or any(m.get(k) is not None for m in s["models"])]
    head = "".join(f"<th>{h}</th>" for _, h in cols)
    body = ""
    for m in s["models"]:
        cells = "".join(f'<td>{(("#" + str(m[k])) if k == "model" else _f(m.get(k), 1 if k == "mean_plddt" else 3))}</td>' for k, _ in cols)
        star = ' <span class="bz-chip bz-chip--primary" style="height:20px">best</span>' if m["model"] == s["best_model"] and len(s["models"]) > 1 else ""
        cells = cells.replace(f'<td>#{m["model"]}</td>', f'<td>#{m["model"]}{star}</td>', 1)
        body += f"<tr>{cells}</tr>"
    ens = s["ensemble"]
    extra = ""
    if ens["n_models"] > 1 and "confidence_score" in ens:
        e = ens["confidence_score"]
        extra = f'<p class="bz-hint" style="margin-top:8px">Across {ens["n_models"]} samples the confidence score is {e["mean"]:.3f} +/- {e["sd"]:.3f} (range {e["min"]:.3f} to {e["max"]:.3f}).</p>'
    elif ens["n_models"] == 1:
        extra = '<p class="bz-hint" style="margin-top:8px">One diffusion sample only. Use 3 or more to see how stable the prediction is.</p>'
    return f'<div><div class="bz-sec-h"><h3>Samples</h3><span>ranked by Boltz</span></div><div class="bz-table-wrap"><table class="bz-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{extra}</div>'


GUIDE = ('<details class="bz-guide"><summary>' + icon("info") + 'How to read these numbers<span class="bz-chev">' + icon("chevron-down") + '</span></summary><div class="bz-guide-b">'
         '<div><h5>pLDDT (per token, 0-100)</h5><ul><li><b>&gt;90</b>very high, side chains reliable</li><li><b>70-90</b>high, backbone reliable</li><li><b>50-70</b>low, treat with caution</li><li><b>&lt;50</b>very low, often disordered</li></ul></div>'
         '<div><h5>ipTM / confidence (0-1)</h5><ul><li><b>&gt;0.8</b>confident complex</li><li><b>0.6-0.8</b>grey zone</li><li><b>&lt;0.6</b>likely incorrect interface</li></ul></div>'
         '<div><h5>PAE (angstrom)</h5><ul><li><b>&lt;5</b>confident relative placement</li><li><b>5-10</b>uncertain</li><li><b>&gt;10</b>unreliable</li></ul>'
         '<p style="margin-top:6px">Rows are the aligned token, columns the scored token; the matrix is not symmetric.</p></div>'
         '<div><h5>Affinity</h5><ul><li><b>probability</b>binder vs decoy, for hit discovery</li><li><b>log10 IC50</b>in uM; -2 is 10 nM, 0 is 1 uM, 1 is 10 uM</li></ul></div></div></details>')


# The 3Dmol library is pinned (a moving "latest" build can change behaviour between two runs of the same notebook); a second host is
# tried by the viewer script when the first does not answer.
LIB_URL = "https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js"
LIB_FALLBACK_URL = "https://3Dmol.org/build/3Dmol-min.js"


def _js_string(value: str) -> str:
    """A JSON string that is also safe inside an inline <script> (no premature </script>, no line-separator characters)."""
    return json.dumps(value).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_viewer(structure_text: str | None, uid: str, structure_format: str = "pdb") -> str:
    """The 3-D viewer: colour (pLDDT or chain), style (cartoon, lines, spheres) and reset buttons above a WebGL canvas (3Dmol)."""
    if not structure_text:
        return ""
    fmt = "pdb" if str(structure_format).lower() == "pdb" else "cif"
    legend = "".join(f'<span><i style="background:{c}"></i>{esc(t)}</span>' for _, c, t in PLDDT_BANDS)
    script = (read_asset("viewer.js").replace("__UID__", _js_string(uid)).replace("__FORMAT__", _js_string(fmt))
              .replace("__STRUCTURE__", _js_string(structure_text)).replace("__FALLBACK__", "window.BZ_3DMOL_FALLBACK === undefined ? " + _js_string(LIB_FALLBACK_URL) + " : window.BZ_3DMOL_FALLBACK"))
    return (
        f'<div><div class="bz-sec-h"><h3>Structure</h3><span>best sample</span></div>'
        f'<div class="bz-viewer-bar"><div class="bz-seg" role="radiogroup" aria-label="Colour"><label><input type="radio" name="vc-{uid}" value="plddt" checked><span>pLDDT</span></label>'
        f'<label><input type="radio" name="vc-{uid}" value="chain"><span>Chain</span></label></div>'
        f'<div class="bz-seg" role="radiogroup" aria-label="Style"><label><input type="radio" name="vs-{uid}" value="cartoon" checked><span>Cartoon</span></label>'
        f'<label><input type="radio" name="vs-{uid}" value="line"><span>Lines</span></label><label><input type="radio" name="vs-{uid}" value="sphere"><span>Spheres</span></label></div>'
        f'<button type="button" class="bz-btn bz-btn--secondary bz-btn--sm" id="vr-{uid}">{icon("refresh")}<span>Reset view</span></button></div>'
        f'<div class="bz-viewer" id="v-{uid}"><div class="bz-viewer-msg">Loading 3-D viewer...</div></div>'
        f'<div class="bz-viewer-info" id="vi-{uid}" data-screen="1"></div>'
        f'<div class="bz-legend" data-screen="1">{legend}</div>'
        f'<script src="{LIB_URL}" onerror="window.BZ_3DMOL_CDN_FAILED=true"></script>'
        f'<script>{script}</script></div>')


def render_provenance(ctx: dict[str, Any] | None) -> str:
    if not ctx:
        return ""
    keys = [("engine", "Engine"), ("boltz2nb_version", "boltz2nb"), ("python", "Python"), ("torch", "PyTorch"), ("gpu_name", "GPU"), ("timestamp_utc", "Started (UTC)"), ("input_yaml_sha1", "Input SHA-1")]
    rows = "".join(f"<dt>{lbl}</dt><dd>{esc(ctx[k])}</dd>" for k, lbl in keys if ctx.get(k))
    cmd = f'<pre class="bz-pre" style="margin-top:12px;white-space:pre-wrap">{esc(" ".join(map(str, ctx["command"])))}</pre>' if ctx.get("command") else ""
    yml = (f'<details class="bz-acc" style="margin-top:12px"><summary style="padding:10px 14px"><span class="bz-acc-t" style="font-size:13px">Input YAML</span>'
           f'<span class="bz-chev">{icon("chevron-down")}</span></summary><pre class="bz-pre" style="border:0;border-top:1px solid var(--bz-border);border-radius:0 0 13px 13px">{esc(ctx["input_yaml"])}</pre></details>') if ctx.get("input_yaml") else ""
    return f'<div><div class="bz-sec-h"><h3>Provenance</h3><span>everything needed to reproduce this run</span></div><dl class="bz-prov">{rows}</dl>{cmd}{yml}</div>'


def _head(summary: dict[str, Any], ctx: dict[str, Any] | None, uid: str, runtime: float | None, theme: str | None = None) -> str:
    chips = []
    if ctx and ctx.get("engine"):
        chips.append(f'<span class="bz-chip bz-chip--glass">{esc(ctx["engine"])}</span>')
    if ctx and ctx.get("gpu_name"):
        chips.append(f'<span class="bz-chip bz-chip--glass">{esc(ctx["gpu_name"])}</span>')
    if runtime:
        chips.append(f'<span class="bz-chip bz-chip--glass">{int(runtime // 60)}:{int(runtime % 60):02d} min</span>')
    chips.append(f'<span class="bz-chip bz-chip--glass">{summary["n_models"]} sample{"s" if summary["n_models"] != 1 else ""}</span>')
    return (f'<div class="bz-res-h">{brand_mark("r" + uid)}<div style="min-width:0"><h2>Results</h2><p><code>{esc(summary["job_name"])}</code></p></div>'
            f'<div class="bz-inline" style="margin-left:auto;justify-content:flex-end">{"".join(chips)}{theme_button(theme)}</div></div>')


def render_result_card(summary: dict[str, Any], pdb_text: str | None = None, ctx: dict[str, Any] | None = None, runtime: float | None = None,
                       uid: str | None = None, standalone_css: bool = True, next_hint: bool = True, theme: str | None = None,
                       structure_format: str = "pdb") -> str:
    """Compact card shown right after a run: headline numbers, tables and the 3-D structure."""
    uid = uid or uuid.uuid4().hex[:8]
    notes = "".join(f'<div class="bz-alert bz-alert--warn">{icon("alert")}<div>{esc(n)}</div></div>' for n in summary.get("layout_notes", []))
    nxt = (f'<div class="bz-next">{icon("arrow-right")}<div>Run the <b>Analyse Results</b> cell for PAE and pLDDT plots, ensemble statistics and a downloadable HTML report.</div></div>'
           if next_hint else "")
    css = (FONT_LINKS + "<style>" + read_asset("theme.css") + "\n" + read_asset("results.css") + "</style>") if standalone_css else ""
    viewer = render_viewer(pdb_text, uid, structure_format)
    tables = render_chain_table(summary) + render_sample_table(summary)
    return (f'{css}<div class="bz bz-res"{theme_attr(theme)} id="bz-res-{uid}">{sprite()}{_head(summary, ctx, uid, runtime, theme)}'
            f'<div class="bz-res-b">{notes}{render_kpis(summary)}{render_affinity(summary)}{viewer}{tables}{GUIDE}{nxt}</div></div>{theme_script() if standalone_css else ""}')


def _figure(b64: str, alt: str, caption: str, kind: str) -> str:
    return (f'<figure class="bz-fig bz-fig--{kind}"><div class="bz-fig-img"><img alt="{esc(alt)}" src="data:image/png;base64,{b64}"></div>'
            f'<figcaption>{caption}</figcaption></figure>')


def render_figures(summary: dict[str, Any], figures: dict[str, Any]) -> str:
    """The plots, laid out so they line up: per sample one row with the PAE map and the pLDDT trace (drawn at the same height, in
    proportion to their widths), then one row with the per-sample confidence and the affinity figure (drawn at the same size)."""
    rows = {m["model"]: m for m in summary.get("models", [])}
    best, many = summary.get("best_model"), len(summary.get("models", [])) > 1
    blocks = []
    for mid, p in sorted(figures.get("models", {}).items()):
        cells = ""
        if p.get("pae"):
            cells += _figure(p["pae"], f"Predicted aligned error, sample {mid}",
                             "Rows: the token the structure is aligned on. Columns: the token being scored. Dark green means low expected error.",
                             "pae")
        if p.get("plddt"):
            cells += _figure(p["plddt"], f"Per-token pLDDT, sample {mid}",
                             "One value per token; for ligands and modified residues a token is a heavy atom.", "plddt")
        if not cells:
            continue
        m = rows.get(mid, {})
        bits = []
        if m.get("confidence_score") is not None:
            bits.append(f"confidence {m['confidence_score']:.3f}")
        if m.get("mean_plddt") is not None:
            bits.append(f"mean pLDDT {m['mean_plddt']:.1f}")
        chip = ' <span class="bz-chip bz-chip--primary" style="height:20px">best</span>' if mid == best and many else ""
        layout = "bz-figrow--pae" if p.get("pae") and p.get("plddt") else "bz-figrow--one"
        meta = " \u00b7 ".join(bits)
        blocks.append(f'<div class="bz-sample"><div class="bz-sample-h"><b>Sample {mid}</b>{chip}<span>{meta}</span></div>'
                      f'<div class="bz-figrow {layout}">{cells}</div></div>')
    extras = []
    if figures.get("ensemble"):
        extras.append(_figure(figures["ensemble"], "Confidence metrics per sample",
                              "Boltz ranks sample 0 first. The axis starts just below the lowest score, so small differences show.", "pair"))
    if figures.get("affinity"):
        extras.append(_figure(figures["affinity"], "Predicted binding affinity",
                              "Binding probability for hit discovery; IC50 only to rank close analogues.", "pair"))
    if extras:
        blocks.append(f'<div class="bz-figrow {"bz-figrow--even" if len(extras) == 2 else "bz-figrow--one"}">{"".join(extras)}</div>')
    if not blocks:
        return ""
    return (f'<div><div class="bz-sec-h"><h3>Figures</h3><span>PAE is asymmetric and drawn on a fixed 0-32 \u00c5 scale</span></div>'
            f'<div class="bz-figs">{"".join(blocks)}</div></div>')


def render_report_fragment(summary: dict[str, Any], figures: dict[str, Any], pdb_text: str | None = None, ctx: dict[str, Any] | None = None,
                           ligand_svg: str | None = None, runtime: float | None = None, standalone_css: bool = True, uid: str | None = None,
                           files: list[tuple[str, str]] | None = None, theme: str | None = None, hint: bool = True, structure_format: str = "pdb") -> str:
    """The full report as an embeddable block (used inline in the notebook and inside the HTML document)."""
    uid = uid or uuid.uuid4().hex[:8]
    fig_sec = render_figures(summary, figures)
    lig = (f'<div><div class="bz-sec-h"><h3>Ligand</h3></div><div class="bz-plate" style="max-width:340px;padding:8px">{ligand_svg}</div></div>') if ligand_svg else ""
    notes = "".join(f'<div class="bz-alert bz-alert--warn">{icon("alert")}<div><strong>Per-token analysis unavailable.</strong> {esc(n)}</div></div>' for n in summary.get("layout_notes", []))
    files_sec = ""
    if files:
        rows = "\n".join(f"{label:<10}{path}" for label, path in files)
        files_sec = f'<div><div class="bz-sec-h"><h3>Saved files</h3><span>download from the Colab file browser or the Drive cell</span></div><pre class="bz-pre">{esc(rows)}</pre></div>'
    css = (FONT_LINKS + "<style>" + read_asset("theme.css") + "\n" + read_asset("results.css") + "</style>") if standalone_css else ""
    return (f'{css}<div class="bz bz-res bz-report"{theme_attr(theme, hint)}>{sprite()}{_head(summary, ctx, uid, runtime, theme)}<div class="bz-res-b">{notes}{render_kpis(summary)}{render_affinity(summary)}{lig}'
            f'{render_chain_table(summary)}{render_sample_table(summary)}{fig_sec}{render_viewer(pdb_text, uid, structure_format)}{GUIDE}{render_provenance(ctx)}{files_sec}'
            f'<p class="bz-hint" style="text-align:center">Generated by boltz2nb {__version__}</p></div></div>{theme_script() if standalone_css else ""}')


def render_report_document(summary: dict[str, Any], figures: dict[str, Any], pdb_text: str | None = None, ctx: dict[str, Any] | None = None,
                           ligand_svg: str | None = None, runtime: float | None = None, theme: str | None = None, structure_format: str = "pdb") -> str:
    """Self-contained HTML report (figures embedded as base64). Light unless ``theme`` is given or the reader switched it
    (the switch is remembered by the browser, so no theme is written into the file)."""
    body = render_report_fragment(summary, figures, pdb_text, ctx, ligand_svg, runtime, standalone_css=False,
                                  theme=theme, hint=theme is not None, structure_format=structure_format)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Boltz-2 report - {esc(summary["job_name"])}</title>{FONT_LINKS}<style>{read_asset("theme.css")}\n{read_asset("results.css")}</style></head>'
            f'<body class="bz-page">{body}{theme_script()}</body></html>')
