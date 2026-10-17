"""The Colab notebooks install ``boltz2nb`` as a regular (non-editable) package, so the UI assets must be inside the wheel."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    out = tmp_path_factory.mktemp("wheel")
    src = tmp_path_factory.mktemp("src")        # build from a copy so the working tree gets no build/ or egg-info side effects
    shutil.copytree(ROOT / "boltz2nb", src / "boltz2nb", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy(ROOT / f, src / f)
    proc = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", str(out), str(src)],
                          capture_output=True, text=True, timeout=300)
    wheels = list(out.glob("boltz2nb-*.whl"))
    if proc.returncode or not wheels:
        pytest.skip(f"could not build a wheel offline: {proc.stderr[-300:]}")
    return wheels[0]


def test_wheel_contains_every_ui_asset(wheel):
    names = set(zipfile.ZipFile(wheel).namelist())
    src = sorted(p.name for p in (ROOT / "boltz2nb" / "ui" / "assets").iterdir() if p.is_file())
    assert {"theme.css", "theme.js", "form.css", "form.html", "form.js", "results.css"} <= set(src)
    missing = [f for f in src if f"boltz2nb/ui/assets/{f}" not in names]
    assert not missing, f"assets missing from the wheel: {missing}"
    assert "boltz2nb/ui/__init__.py" in names and "boltz2nb/pdb_import.py" in names


def test_installed_copy_renders_the_form_without_the_source_tree(wheel, tmp_path):
    target = tmp_path / "site"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "-q", "--target", str(target), str(wheel)], check=True, capture_output=True, timeout=300)
    code = ("import boltz2nb, pathlib; from boltz2nb.ui.render import render_form; "
            "p = pathlib.Path(boltz2nb.__file__).resolve(); assert 'site' in p.parts, p; "
            "h = render_form(mode='advanced'); assert len(h) > 60000 and 'data-panel=\"3\"' in h and '<style>' in h and 'initChips' in h, len(h); print(len(h))")
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env={"PYTHONPATH": str(target), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-600:]
