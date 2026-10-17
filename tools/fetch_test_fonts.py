"""Download the Inter and JetBrains Mono web fonts used by the interface into a folder (for the browser tests).

The interface loads these from Google Fonts at runtime; the browser tests run offline and serve local copies so that
text metrics - and therefore the no-overflow checks - match what users see.

    python tools/fetch_test_fonts.py fonts && BZ_FONT_DIR=$PWD/fonts pytest tests/ui
"""
import io
import sys
import tarfile
from pathlib import Path

import requests

PACKAGES = {
    "@fontsource/inter": [f"inter-latin-{w}-normal.woff2" for w in (400, 500, 600, 700)],
    "@fontsource/jetbrains-mono": [f"jetbrains-mono-latin-{w}-normal.woff2" for w in (400, 500, 600)],
}


def main(dest: str = "fonts") -> int:
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    for pkg, files in PACKAGES.items():
        meta = requests.get(f"https://registry.npmjs.org/{pkg.replace('/', '%2F')}/latest", timeout=60).json()
        tar = tarfile.open(fileobj=io.BytesIO(requests.get(meta["dist"]["tarball"], timeout=120).content))
        for name in files:
            member = tar.extractfile(f"package/files/{name}")
            (out / name).write_bytes(member.read())
        print(f"{pkg} {meta['version']}: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
