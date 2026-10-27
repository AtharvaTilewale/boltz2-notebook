"""Rewrite the first (markdown) cell of the main notebooks and the closing credits / citation cell of every Colab notebook, and keep the
default notebook (Boltz2.ipynb) identical to the Advanced V2.0.0 notebook.

    python tools/build_notebook_headers.py          # rewrite in place (idempotent)
    python tools/build_notebook_headers.py --check  # exit 1 if a header is out of date (used by CI)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLAB = "https://colab.research.google.com/github/AtharvaTilewale/boltz2-notebook/blob/main/"
BADGE = "https://colab.research.google.com/assets/colab-badge.svg"
# The default notebook (Boltz2.ipynb) is the Advanced notebook; the versioned copy under colab/v2 is kept byte-identical to it.
DEFAULT = "Boltz2.ipynb"
VERSIONED = "colab/v2/Boltz2_V2.0.0.ipynb"
NOTEBOOKS = {
    VERSIONED: "advanced",
    "colab/v1/Boltz2_v1.0.0.ipynb": "standard",
}
ROWS = [
    ("advanced", "Advanced", "default", "Proteins, DNA/RNA and ligands, templates, constraints, covalent bonds, modified residues, custom MSA", DEFAULT),
    ("standard", "Standard", "", "Proteins and small-molecule ligands, with a shorter form", "colab/v1/Boltz2_v1.0.0.ipynb"),
    ("batch", "Batch", "experimental", "Screening many inputs from CSV or FASTA, with ranking", "batch/Boltz2_Batch_v1_beta.ipynb"),
]
REPO = "https://github.com/AtharvaTilewale/boltz2-notebook"
SITE = "https://atharvatilewale.github.io/boltz2-notebook"
BANNER = "https://raw.githubusercontent.com/AtharvaTilewale/boltz2-notebook/main/assets/boltz2-wordmark-horizontal-dark.svg"   # own dark card: reads on light and dark themes
PAPER_DOI = "https://doi.org/10.64898/2026.09.18.752645"
PAPER_TITLE = ("Boltz2-Notebook: An Interactive Google Colab Platform for Diffusion-Based Biomolecular Structure and Binding Affinity Prediction "
               "using the Boltz2 model")                         # as registered with Crossref for the DOI above
LINKS = (f"[Guide]({SITE}/docs/use-cases.html) · [FAQ]({SITE}/docs/faq.html) · [Report an issue]({REPO}/issues) · "
         f"[Privacy]({REPO}/blob/main/docs/PRIVACY.md) · [Cite]({PAPER_DOI})")
INTRO = {
    "advanced": "Predict the 3-D structure of proteins, DNA, RNA and small molecules, and how strongly a ligand binds, with **Boltz-2** on a free Colab GPU. "
                "No installation or coding needed.",
    "standard": "Predict the 3-D structure of proteins and protein-ligand complexes, and how strongly a ligand binds, with **Boltz-2** on a free Colab GPU. "
                "No installation or coding needed.",
}


def header(mode: str) -> str:
    here = {"standard": "Standard", "advanced": "Advanced"}[mode]
    table = ["| Notebook | Best for | |", "|:--|:--|:--|"]
    for key, name, tag, text, path in ROWS:
        label = f"**{name}**" + (f" · {tag}" if tag else "") + (" · *you are here*" if key == mode else "")
        table.append(f"| {label} | {text} | [![Open in Colab]({BADGE})]({COLAB}{path}) |")
    note = ""
    if mode == "standard":
        note = "\n> Need DNA/RNA, templates, covalent bonds or pocket and contact constraints? Use the **Advanced** notebook (the default).\n"
    return f"""<img src="{BANNER}" alt="Boltz2-Notebook" width="400">

# {here} notebook

{INTRO[mode]}

### Quick start

1. **Choose a GPU:** *Runtime ▸ Change runtime type ▸ T4 GPU* (or better).
2. **Install** and **Download model weights:** run the first two cells, once per session.
3. **Generate Parameters:** describe your molecules in the form, then press **Save configuration**.
4. **Run Boltz2 Engine**, then **Analyse Results:** the prediction takes 2 to 10 minutes on a T4; the analysis adds plots, a 3-D viewer and an HTML report.
5. *Optional:* save the results to Google Drive or download them as a zip with the last two cells.
{note}
> **Reading affinity:** use the binding *probability* to tell binders from non-binders, and the predicted IC50 only to rank close analogues.

### Notebooks

{chr(10).join(table)}

{LINKS}
"""


def closing() -> str:
    return f"""## Credits

Developed by **Atharva Tilewale** and **Dr. Dhaval Patel**, Gujarat Biotechnology University.

Code: [github.com/AtharvaTilewale/boltz2-notebook]({REPO}) · [MIT License]({REPO}/blob/main/LICENSE)

## How to cite

If this notebook helps your work, please cite:

**Boltz2-Notebook** [![bioRxiv](https://img.shields.io/badge/bioRxiv-10.64898%2F2026.09.18.752645-b31b1b)]({PAPER_DOI})

> Tilewale, A., Patel, D. (2026). {PAPER_TITLE}. bioRxiv. https://doi.org/10.64898/2026.09.18.752645

**Boltz-2**, the model

> Passaro, S., Corso, G., Wohlwend, J., et al. (2025). Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction. bioRxiv. https://doi.org/10.1101/2025.06.14.659707

**Boltz-1**

> Wohlwend, J., Corso, G., Passaro, S., et al. (2024). Boltz-1: Democratizing Biomolecular Interaction Modeling. bioRxiv. https://doi.org/10.1101/2024.11.19.624167

**ColabFold**, if you used the MSA server

> Mirdita, M., Schütze, K., Moriwaki, Y., Heo, L., Ovchinnikov, S., Steinegger, M. (2022). ColabFold: making protein folding accessible to all. Nature Methods 19, 679-682. https://doi.org/10.1038/s41592-022-01488-1
"""


CLOSING = list(NOTEBOOKS) + ["batch/Boltz2_Batch_v1_beta.ipynb"]      # the batch notebook keeps its own header; only the credits cell is shared


def is_credits(cell) -> bool:
    text = "".join(cell["source"])
    return cell["cell_type"] == "markdown" and any(h in text for h in ("## Citation", "## Cite", "## How to cite"))


def lines(text: str) -> list[str]:
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def main(check: bool) -> int:
    stale = []
    for rel in sorted(set(NOTEBOOKS) | set(CLOSING)):
        path = ROOT / rel
        nb = json.loads(path.read_text())
        cells = nb["cells"]
        changed = False
        if rel in NOTEBOOKS and cells[0]["source"] != lines(header(NOTEBOOKS[rel])):
            cells[0]["source"] = lines(header(NOTEBOOKS[rel]))
            changed = True
        if rel in CLOSING:
            want = lines(closing())
            at = [i for i, c in enumerate(cells) if i > 0 and is_credits(c)]
            if not at:
                cells.append({"cell_type": "markdown", "metadata": {}, "source": want})
                changed = True
            elif cells[at[-1]]["source"] != want:
                cells[at[-1]]["source"] = want
                changed = True
        if changed:
            stale.append(rel)
            if not check:
                path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    source, target = ROOT / VERSIONED, ROOT / DEFAULT
    if not target.exists() or target.read_bytes() != source.read_bytes():
        stale.append(DEFAULT)
        if not check:
            target.write_bytes(source.read_bytes())
    print(("out of date: " if check else "rewritten: ") + (", ".join(stale) or "none"))
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
