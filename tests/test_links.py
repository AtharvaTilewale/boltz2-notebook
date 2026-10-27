"""Every link that points into this repository must resolve to a file that exists (a renamed notebook must not leave a 404 behind)."""
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
SKIP_SUFFIX = ".egg-info"
OWN = r"AtharvaTilewale/boltz2-notebook"
ABSOLUTE = [
    re.compile(rf"colab\.research\.google\.com/github/{OWN}/blob/[^/\s\"')]+/([^\s\"')#?]+)"),
    re.compile(rf"github\.com/{OWN}/(?:blob|tree)/[^/\s\"')]+/([^\s\"')#?]+)"),
    re.compile(rf"raw\.githubusercontent\.com/{OWN}/[^/\s\"')]+/([^\s\"')#?]+)"),
]
SITE = re.compile(r"atharvatilewale\.github\.io/boltz2-notebook/([^\s\"')#?]*)")
RELATIVE = [re.compile(r"\]\(([^)\s]+)\)"), re.compile(r'(?:href|src)="([^"]+)"')]
SUFFIXES = {".md", ".html", ".js", ".ipynb", ".py", ".yml", ".toml"}


def files():
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and p.suffix in SUFFIXES and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and SKIP_SUFFIX not in str(p):
            yield p


def body(p):
    s = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix == ".ipynb":
        s = "\n".join("".join(c["source"]) for c in json.loads(s)["cells"])
    return s


def own_targets():
    for p in files():
        s = body(p)
        for rx in ABSOLUTE:
            for m in rx.finditer(s):
                yield p, unquote(m.group(1))
        for m in SITE.finditer(s):
            yield p, unquote(m.group(1)) or "index.html"


def relative_targets():
    for p in files():
        if p.suffix not in {".md", ".html"}:
            continue
        for rx in RELATIVE:
            for m in rx.finditer(body(p)):
                link = m.group(1)
                if re.match(r"(https?:|mailto:|#|data:|//|javascript:|\{)", link) or "@@" in link:
                    continue
                yield p, unquote(link.split("#")[0].split("?")[0])


@pytest.mark.parametrize("source,target", sorted({(str(p.relative_to(ROOT)), t) for p, t in own_targets()}))
def test_links_into_this_repository_resolve(source, target):
    path = ROOT / target.rstrip("/")
    assert path.exists(), f"{source} links to {target}, which does not exist"


@pytest.mark.parametrize("source,target", sorted({(str(p.relative_to(ROOT)), t) for p, t in relative_targets() if t}))
def test_relative_links_resolve(source, target):
    base = (ROOT / source).parent
    assert (base / target).exists() or (ROOT / target.lstrip("/")).exists(), f"{source} links to {target}, which does not exist"
