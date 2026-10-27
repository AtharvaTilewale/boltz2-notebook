"""The notebooks and the README cite the Boltz2-Notebook preprint on bioRxiv (DOI 10.64898/2026.09.18.752645), not a Zenodo record."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOI = "10.64898/2026.09.18.752645"
TITLE = ("Boltz2-Notebook: An Interactive Google Colab Platform for Diffusion-Based Biomolecular Structure and Binding Affinity Prediction "
         "using the Boltz2 model")                     # as registered with Crossref for the DOI
COLAB_NOTEBOOKS = ["Boltz2.ipynb", "colab/v2/Boltz2_V2.0.0.ipynb", "colab/v1/Boltz2_v1.0.0.ipynb", "batch/Boltz2_Batch_v1_beta.ipynb"]


def notebook_text(rel):
    return "\n".join("".join(c["source"]) for c in json.loads((ROOT / rel).read_text(encoding="utf-8"))["cells"])


@pytest.mark.parametrize("rel", COLAB_NOTEBOOKS + ["notebooks/Boltz2_paramgen.ipynb", "README.md", "CITATION.cff"])
def test_no_zenodo(rel):
    text = notebook_text(rel) if rel.endswith(".ipynb") else (ROOT / rel).read_text(encoding="utf-8")
    assert "zenodo" not in text.lower(), f"{rel} still cites Zenodo"


@pytest.mark.parametrize("rel", COLAB_NOTEBOOKS)
def test_each_notebook_ends_with_one_credits_cell_citing_the_preprint(rel):
    cells = json.loads((ROOT / rel).read_text(encoding="utf-8"))["cells"]
    credits = [c for c in cells if c["cell_type"] == "markdown" and "## How to cite" in "".join(c["source"])]
    assert len(credits) == 1 and credits[0] is cells[-1], f"{rel}: the credits / citation cell must be the last cell"
    text = "".join(credits[0]["source"])
    assert f"https://doi.org/{DOI}" in text and TITLE in text and "bioRxiv" in text
    assert "10.1101/2025.06.14.659707" in text                     # Boltz-2, the model


def test_the_readme_and_citation_file_agree_on_the_preprint():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bib = readme[readme.index("```bibtex"):]
    assert f"doi       = {{{DOI}}}" in bib and f"title     = {{{TITLE}}}" in re.sub(r"\n\s+", " ", bib)      # BibTeX may wrap the title
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f"doi: {DOI}" in cff and re.search(r"preferred-citation:\n  type: article", cff)
