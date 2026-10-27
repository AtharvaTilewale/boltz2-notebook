"""The default notebook is the Advanced (V2.0.0) notebook and it is stable: one file under two names, no beta tag, old links still land somewhere."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "Boltz2.ipynb"
VERSIONED = ROOT / "colab/v2/Boltz2_V2.0.0.ipynb"
OLD_BETA_PATH = ROOT / "colab/v2/Boltz2_V2.0.0_beta.ipynb"
STANDARD = ROOT / "colab/v1/Boltz2_v1.0.0.ipynb"
STABLE_NOTEBOOKS = [DEFAULT, VERSIONED, STANDARD]


def cells(path, kind=None):
    return [c for c in json.loads(path.read_text(encoding="utf-8"))["cells"] if kind is None or c["cell_type"] == kind]


def text(path):
    return "\n".join("".join(c["source"]) for c in cells(path))


def test_the_default_notebook_is_the_advanced_notebook_byte_for_byte():
    assert DEFAULT.read_bytes() == VERSIONED.read_bytes(), "run `python tools/build_notebook_headers.py` to sync them"


def test_the_default_notebook_runs_the_advanced_scripts():
    code = "\n".join("".join(c["source"]) for c in cells(DEFAULT, "code"))
    assert "scripts/v2/" in code and "scripts/v1/" not in code
    assert "scripts/v1/" in "\n".join("".join(c["source"]) for c in cells(STANDARD, "code"))


@pytest.mark.parametrize("path", STABLE_NOTEBOOKS, ids=lambda p: p.name)
def test_no_stable_notebook_calls_anything_beta(path):
    shown = text(path).replace("Boltz2_Batch_v1_beta.ipynb", "")             # the Batch notebook is still experimental; only its file name says beta
    assert not re.search(r"beta", shown, re.I), f"{path.name} still mentions beta"


def _row(head, name):
    return next(ln for ln in head.splitlines() if ln.startswith(f"| **{name}**"))


def test_the_header_names_the_default_and_where_you_are():
    head = "".join(cells(DEFAULT)[0]["source"])
    assert "\n# Advanced notebook\n" in head and "· default · *you are here*" in _row(head, "Advanced")
    assert "blob/main/Boltz2.ipynb" in _row(head, "Advanced")
    assert "experimental" in _row(head, "Batch")                           # the batch notebook really is still experimental
    std = "".join(cells(STANDARD)[0]["source"])
    assert "\n# Standard notebook\n" in std and "default" in _row(std, "Advanced") and "*you are here*" in _row(std, "Standard")
    assert "*you are here*" not in _row(std, "Advanced")


def test_the_header_is_short_and_links_privacy_instead_of_explaining_it():
    for nb in (DEFAULT, STANDARD):
        head = "".join(cells(nb)[0]["source"])
        assert "[Privacy](https://github.com/AtharvaTilewale/boltz2-notebook/blob/main/docs/PRIVACY.md)" in head
        assert "SEND_USAGE_STATS" not in head and "encrypted" not in head and "ColabFold MSA request" not in head
        assert len(head) < 2600, f"{nb.name} header grew to {len(head)} characters"
        assert "img.shields.io" not in head                                  # no badge wall in the notebook


def test_the_old_beta_link_still_opens_a_page_that_points_to_the_new_notebook():
    nb = json.loads(OLD_BETA_PATH.read_text(encoding="utf-8"))
    assert [c["cell_type"] for c in nb["cells"]] == ["markdown"], "the pointer must not carry runnable code"
    body = "".join(nb["cells"][0]["source"])
    assert "has moved" in body and "colab/v2/Boltz2_V2.0.0.ipynb" in body and "Boltz2_v1.0.0.ipynb" in body
    for rel in re.findall(r"blob/main/(\S+?\.ipynb)", body):
        assert (ROOT / rel).is_file(), rel


def test_the_public_text_calls_v2_stable_and_the_default():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    launch = readme[readme.index("## Choose a notebook"):].split("\n\n")[1].splitlines()
    assert launch[2].startswith("| **Advanced** (default)") and "Stable-Default" in launch[2] and "blob/main/Boltz2.ipynb" in launch[2]
    assert launch[3].startswith("| **Standard**") and "Stable" in launch[3] and "colab/v1/Boltz2_v1.0.0.ipynb" in launch[3]
    assert not [ln for ln in launch[2:4] if "Beta" in ln or "Experimental" in ln], "Advanced and Standard are not beta"
    assert "Beta-Latest" not in readme
    table = (ROOT / "releases/version_table.md").read_text(encoding="utf-8")
    assert "v2.0.0-beta" not in table and "| v2.0.0 | Stable |" in table and "Current, default" in table
    site = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "V2 beta" not in site and "Open V2 beta" not in site and "Main Notebook (V2.0.0)" in site
    faq = (ROOT / "assets/js/faq.js").read_text(encoding="utf-8") + (ROOT / "docs/faq.html").read_text(encoding="utf-8")
    assert "V2 beta" not in faq


def test_the_batch_notebook_is_still_labelled_experimental():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    batch = next(ln for ln in readme.splitlines() if ln.startswith("| **Batch**"))
    assert "Pre--release-Experimental" in batch and "batch/Boltz2_Batch_v1_beta.ipynb" in batch
    assert "Boltz2_Batch_v1_beta.ipynb" in (ROOT / "tools/build_notebook_headers.py").read_text(encoding="utf-8")
