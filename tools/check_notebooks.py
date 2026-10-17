"""Compile every code cell of every notebook (IPython magics commented out) and check %run targets exist."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []
for nb in sorted(ROOT.rglob("*.ipynb")):
    if ".ipynb_checkpoints" in nb.parts:
        continue
    cells = json.loads(nb.read_text())["cells"]
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"])
        py = "\n".join(("pass  # " + ln) if ln.lstrip().startswith(("%", "!")) else ln for ln in src.splitlines())
        try:
            ast.parse(py)
        except SyntaxError as e:
            errors.append(f"{nb.relative_to(ROOT)} cell {i}: {e}")
        for target in re.findall(r"%run\s+(\S+)", src):
            rel = re.sub(r"^/content/(boltz_data|boltz2-notebook)/", "", target)
            if not (ROOT / rel).exists():
                errors.append(f"{nb.relative_to(ROOT)} cell {i}: %run target missing in repo: {rel}")
for e in errors:
    print("ERROR", e)
print(f"checked notebooks: {'OK' if not errors else f'{len(errors)} problem(s)'}")
sys.exit(1 if errors else 0)
