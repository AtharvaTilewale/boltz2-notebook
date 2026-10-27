"""Cell 1 of the main notebooks must not keep running stale code from an earlier session's clone."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ["Boltz2.ipynb", "colab/v1/Boltz2_v1.0.0.ipynb", "colab/v2/Boltz2_V2.0.0.ipynb"]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def refresh_block(notebook):
    cell = "".join(json.loads((ROOT / notebook).read_text(encoding="utf-8"))["cells"][1]["source"])
    block = cell[cell.index("def _git"):].split("%run")[0]
    return block.replace("if FORCE_REINSTALL or not os.path.exists(REPO):", "if False:")   # only the 'already present' branch


@pytest.mark.parametrize("notebook", NOTEBOOKS)
def test_an_old_clone_is_fast_forwarded_and_no_restart_is_asked_for(tmp_path, notebook, capsys, monkeypatch):
    src = tmp_path / "src"
    sh("git", "init", "-q", "-b", "work", str(src))
    sh("git", "config", "user.name", "t", cwd=src)
    sh("git", "config", "user.email", "t@example.org", cwd=src)
    (src / "a.txt").write_text("1")
    sh("git", "add", ".", cwd=src)
    sh("git", "commit", "-qm", "one", cwd=src)
    remote = tmp_path / "remote.git"
    sh("git", "clone", "-q", "--bare", str(src), str(remote))
    clone = tmp_path / "clone"
    sh("git", "clone", "-q", "--depth", "1", "--branch", "work", f"file://{remote}", str(clone))   # left by an earlier session
    (src / "a.txt").write_text("2")
    sh("git", "commit", "-qam", "two", cwd=src)
    sh("git", "push", "-q", f"file://{remote}", "work", cwd=src)

    monkeypatch.setitem(sys.modules, "boltz2nb", sys.modules.get("boltz2nb") or type(sys)("boltz2nb"))   # an older copy is loaded
    ns = {"os": __import__("os"), "sys": sys, "subprocess": subprocess, "REPO": str(clone), "FORCE_REINSTALL": False,
          "NOTEBOOK_VERSION": "work"}
    exec("def _clone(ref):\n    return False\n" + refresh_block(notebook), ns)         # noqa: S102

    out = capsys.readouterr().out
    assert (clone / "a.txt").read_text() == "2"
    assert "already present" in out and "replaced when the next cells run" in out and "Restart" not in out


@pytest.mark.parametrize("notebook", NOTEBOOKS)
def test_an_unreachable_remote_keeps_the_existing_code(tmp_path, notebook, capsys):
    repo = tmp_path / "repo"
    sh("git", "init", "-q", "-b", "work", str(repo))
    sh("git", "config", "user.name", "t", cwd=repo)
    sh("git", "config", "user.email", "t@example.org", cwd=repo)
    (repo / "a.txt").write_text("1")
    sh("git", "add", ".", cwd=repo)
    sh("git", "commit", "-qm", "one", cwd=repo)
    sh("git", "remote", "add", "origin", "file:///nonexistent", cwd=repo)
    ns = {"os": __import__("os"), "sys": sys, "subprocess": subprocess, "REPO": str(repo), "FORCE_REINSTALL": False,
          "NOTEBOOK_VERSION": "work"}
    exec("def _clone(ref):\n    return False\n" + refresh_block(notebook), ns)         # noqa: S102
    assert "already present" in capsys.readouterr().out and (repo / "a.txt").read_text() == "1"
