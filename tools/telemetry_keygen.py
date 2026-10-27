#!/usr/bin/env python3
"""Make the key pair for usage reports (docs/TELEMETRY.md).

The PRIVATE key is written to a file outside this repository (mode 600) and must never be committed or shared: whoever holds it can read every
report. The PUBLIC key is printed; it is the only part that goes into ``boltz2nb/telemetry_config.py``.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

DEFAULT_OUT = Path.home() / ".boltz2nb" / "telemetry_private.key"


def inside_a_git_worktree(path: Path) -> bool:
    return any((p / ".git").exists() for p in [path.resolve().parent, *path.resolve().parent.parents])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"where to write the private key (default {DEFAULT_OUT})")
    ap.add_argument("--allow-inside-repo", action="store_true", help="write the private key even inside a git working tree (not recommended)")
    args = ap.parse_args(argv)
    out = args.out.expanduser()
    if out.exists():
        print(f"refusing to overwrite {out}: reports sealed with the old public key could no longer be read", file=sys.stderr)
        return 2
    if inside_a_git_worktree(out) and not args.allow_inside_repo:
        print(f"{out} is inside a git working tree; a private key there can end up in a commit. Choose a path outside it.", file=sys.stderr)
        return 2
    try:
        from nacl.public import PrivateKey
    except ImportError:
        print("pynacl is required: pip install pynacl", file=sys.stderr)
        return 2
    key = PrivateKey.generate()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(base64.b64encode(bytes(key)).decode("ascii") + "\n")
    print(f"private key written to {out} (mode 600). Back it up somewhere safe and private; there is no other copy.")
    print("public key (put this in boltz2nb/telemetry_config.py as PUBLIC_KEY):")
    print(base64.b64encode(bytes(key.public_key)).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
