"""Rewrite the first (markdown) cell of the main notebooks so they share one concise, accurate header, and keep the default
notebook (Boltz2.ipynb) identical to the Advanced V2.0.0 notebook.

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
    ("advanced", "Advanced (default)", "Proteins, DNA/RNA and ligands, binding affinity, templates, covalent bonds, pocket and contact constraints, custom MSA, cyclic peptides, 3-D viewer", DEFAULT),
    ("standard", "Standard", "A shorter form for proteins and small-molecule ligands, with binding affinity and a 3-D viewer", "colab/v1/Boltz2_v1.0.0.ipynb"),
    ("batch", "Batch (experimental)", "CSV / FASTA screens with automatic ranking", "batch/Boltz2_Batch_v1_beta.ipynb"),
]
BADGES = (
    "![Python](https://img.shields.io/badge/Python-3.10%20--%203.13-3B4FD6?logo=python&logoColor=white) "
    "![CUDA](https://img.shields.io/badge/CUDA-GPU-0B7F70?logo=nvidia&logoColor=white) "
    "![Boltz-2](https://img.shields.io/badge/Model-Boltz--2-7C8CFF) "
    "![Colab](https://img.shields.io/badge/Platform-Colab%20%7C%20Linux-F9AB00?logo=googlecolab&logoColor=white) "
    "![License](https://img.shields.io/badge/License-MIT-5A6985)"
)


def header(mode: str) -> str:
    here = {"standard": "Standard", "advanced": "Advanced"}[mode]
    table = ["| Notebook | Best for | |", "|:--|:--|:--|"]
    for key, name, text, path in ROWS:
        mark = " **← you are here**" if key == mode else ""
        table.append(f"| **{name}**{mark} | {text} | [![Open in Colab]({BADGE})]({COLAB}{path}) |")
    extra = ""
    if mode == "standard":
        extra = "\nNeed DNA/RNA, templates, covalent bonds or pocket and contact constraints? Use the **Advanced** notebook, which is the default.\n"
    if mode == "advanced":
        extra = (
            "\n**What the Advanced form adds:** DNA and RNA chains, structural templates, covalent bonds, pocket and contact conditioning, "
            "uploaded alignments (A3M), cyclic polymers and modified residues. You can also import chains and ligands straight from a PDB or mmCIF file.\n"
        )
    return f"""# Boltz2-Notebook · {here}

**Predict biomolecular structures and binding affinity with Boltz-2, from a guided form, on a free Colab GPU.**

{BADGES}

{chr(10).join(table)}
{extra}
## Run it in six steps

| Step | Cell | What happens |
|:--:|:--|:--|
| 1 | **Install dependencies** | Installs Boltz-2 and the notebook package, once per runtime. |
| 2 | **Download model weights** | About 6 GB of checkpoints and a 3-residue warm-up run, once per runtime. |
| 3 | **Generate parameters** | Fill in the form, check the live summary and YAML, press **Save configuration**. |
| 4 | **Run Boltz-2 engine** | Live progress with phases and a timer, then a result card with confidence scores, affinity and a 3-D viewer. |
| 5 | **Analyse results** | pLDDT and PAE plots, ensemble statistics and a downloadable HTML report. |
| 6 | **Export** | Copy the results to Google Drive or download them as a zip. |

Typical runtime: 2 to 10 minutes on a T4 GPU. Step-by-step examples are in the [Use Cases guide](https://atharvatilewale.github.io/boltz2-notebook/docs/use-cases.html).

## Before you start

- **GPU:** Runtime ▸ Change runtime type ▸ Hardware accelerator **GPU** (T4 or better).
- **Python:** 3.12 runtimes install the official `boltz` package; 3.13 runtimes automatically get the `boltz-community` fork.
- **Privacy:** nothing leaves your runtime except the ColabFold MSA request Boltz makes for your sequences. Usage reports are off unless you tick `SEND_USAGE_STATS` in the first cell: then your job names, chain and residue counts, run settings and outcomes (and the redacted end of the log of a failed job) are sent encrypted to the maintainer, never your sequences or ligands ([exactly what](https://github.com/AtharvaTilewale/boltz2-notebook/blob/main/docs/PRIVACY.md)).
- **Affinity values** are the predicted log10 IC50 in µM, reported together with a binding probability. Use the probability to separate binders from decoys, and the IC50 only to rank close analogues.

Questions or problems? Open an [issue](https://github.com/AtharvaTilewale/boltz2-notebook/issues). Credits and citation are at the end of this notebook.
"""


def lines(text: str) -> list[str]:
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def main(check: bool) -> int:
    stale = []
    for rel, mode in NOTEBOOKS.items():
        path = ROOT / rel
        nb = json.loads(path.read_text())
        cells = nb["cells"]
        want = lines(header(mode))
        # v1 has no closing credits cell: keep its existing credits and citation text verbatim and move it to the end
        if not any(c["cell_type"] == "markdown" and ("Citation" in "".join(c["source"]) or "Cite" in "".join(c["source"])) for c in cells[1:]):
            old = "".join(cells[0]["source"])
            start = old.find("##  Credits & Authorship")
            end = old.find("> **Before you start:**")
            if start >= 0 and end > start:
                tail = old[start:end].rstrip() + "\n"
                cells.append({"cell_type": "markdown", "metadata": {}, "source": lines(tail)})
        if cells[0]["source"] != want:
            stale.append(rel)
            cells[0]["source"] = want
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
