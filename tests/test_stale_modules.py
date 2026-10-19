"""A Colab kernel outlives a `git pull` of the clone: the scripts of the new code must not run on modules of the old code that are still loaded.

The reported failure: ``render_result_card() got an unexpected keyword argument 'structure_format'``, from a new ``Boltz_Run.py`` calling the
old ``boltz2nb.ui.results`` that an earlier run had already imported in the same kernel.
"""
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import boltz2nb
from boltz2nb import _build

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "boltz2nb"
SCRIPTS = ["scripts/common/setup.py", "scripts/common/Boltz_Run.py", "scripts/common/analysis.py", "scripts/v1/param_gen.py",
           "scripts/v2/param_gen.py", "scripts/batch_utils.py"]
IGNORE = shutil.ignore_patterns("__pycache__")


def block_of(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    start, end = text.index("# --- refresh stale boltz2nb"), text.index("# --- end refresh ---")
    return text[start:end]


def test_every_notebook_script_carries_the_same_refresh_block():
    blocks = {s: block_of(s) for s in SCRIPTS}
    assert len(set(blocks.values())) == 1, "the refresh block differs between scripts"


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_block_comes_before_the_first_import_of_the_package(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    first = min(m.start() for m in re.finditer(r"^\s*(?:from boltz2nb\b|import boltz2nb\b)", text, re.M))
    assert text.index("# --- refresh stale boltz2nb") < first


def test_the_fingerprint_is_stable_and_follows_the_files(tmp_path):
    copy = tmp_path / "boltz2nb"
    shutil.copytree(PKG, copy, ignore=IGNORE)
    assert boltz2nb.BUILD_ID == _build.fingerprint(PKG) == _build.fingerprint(copy)      # same bytes anywhere, whatever the timestamps
    (copy / "ligand.py").write_text((copy / "ligand.py").read_text() + "\n# changed\n")
    assert _build.fingerprint(copy) != boltz2nb.BUILD_ID
    (copy / "__pycache__").mkdir(exist_ok=True)
    (copy / "__pycache__" / "x.py").write_text("ignored")
    shutil.copy(PKG / "ligand.py", copy / "ligand.py")
    assert _build.fingerprint(copy) == boltz2nb.BUILD_ID                                  # __pycache__ does not count


def test_a_current_copy_is_left_alone():
    import boltz2nb.ui.results as before
    assert _build.drop_stale_modules() == 0
    assert sys.modules["boltz2nb.ui.results"] is before


def run_python(code, tmp_path):
    env = {**os.environ, "PYTHONPATH": "", "BOLTZ2NB_BASE_DIR": str(tmp_path / "bd"), "MPLBACKEND": "Agg"}
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=120)


def old_copy(dst):
    """The package as an earlier session's clone had it: no fingerprint, and a result card that does not know `structure_format`."""
    shutil.copytree(PKG, dst / "boltz2nb", ignore=IGNORE)
    (dst / "boltz2nb" / "_build.py").unlink()
    init = dst / "boltz2nb" / "__init__.py"
    init.write_text(re.sub(r"\n# Fingerprint.*?BUILD_ID = \"unknown\"\n", "\n", init.read_text(), flags=re.S))
    results = dst / "boltz2nb" / "ui" / "results.py"
    text = results.read_text()
    text = text.replace(',\n                       structure_format: str = "pdb") -> str:', ") -> str:").replace("render_viewer(pdb_text, uid, structure_format)", "render_viewer(pdb_text, uid)")
    assert "structure_format: str" not in text.split("def render_result_card")[1].split(":\n", 1)[0]
    results.write_text(text)


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_reported_failure_is_gone_after_the_clone_is_updated_under_a_running_kernel(tmp_path, script):
    old_copy(tmp_path / "clone")
    block = block_of(script)
    code = f'''
        import inspect, shutil, sys
        sys.path.insert(0, {str(tmp_path / "clone")!r})
        import boltz2nb.ui.results as old
        assert not hasattr(sys.modules["boltz2nb"], "BUILD_ID")
        try:
            old.render_result_card({{}}, None, structure_format="pdb")
            raise SystemExit("the old copy should reject the new argument")
        except TypeError as exc:
            assert "structure_format" in str(exc), exc                       # the user's error, reproduced
        from boltz2nb.ui import theme
        theme.set_theme("dark")
        shutil.copytree({str(PKG)!r}, {str(tmp_path / "clone" / "boltz2nb")!r}, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))   # git pull
        {textwrap.indent(block, " " * 8).lstrip()}
        import boltz2nb
        import boltz2nb.ui.results as new
        assert new is not old and "structure_format" in inspect.signature(new.render_result_card).parameters
        from boltz2nb import _build
        assert boltz2nb.BUILD_ID == _build.fingerprint({str(tmp_path / "clone" / "boltz2nb")!r})
        from boltz2nb.ui import theme as t2
        assert t2.get_theme() == "dark", "the colour the user picked must survive the reload"
        print("OK")
    '''
    done = run_python(code, tmp_path)
    assert done.returncode == 0 and "OK" in done.stdout, done.stdout + done.stderr


def test_running_the_block_again_changes_nothing(tmp_path):
    code = f'''
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        import boltz2nb.ui.results as first
        {textwrap.indent(block_of("scripts/common/Boltz_Run.py"), " " * 8).lstrip()}
        {textwrap.indent(block_of("scripts/common/Boltz_Run.py"), " " * 8).lstrip()}
        import boltz2nb.ui.results as second
        assert first is second
        print("OK")
    '''
    done = run_python(code, tmp_path)
    assert done.returncode == 0 and "OK" in done.stdout, done.stdout + done.stderr


def test_a_directory_that_cannot_be_read_is_not_an_error(monkeypatch):
    monkeypatch.setattr(_build, "fingerprint", lambda p: (_ for _ in ()).throw(OSError("unreadable")))
    assert _build.drop_stale_modules() == 0
