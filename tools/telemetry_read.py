#!/usr/bin/env python3
"""Open the usage reports you collected (docs/TELEMETRY.md).

Export the Google Sheet that the receiver writes to as CSV (File > Download > CSV) and run

    python tools/telemetry_read.py --key ~/.boltz2nb/telemetry_private.key reports.csv [--jsonl reports.jsonl]

Rows that cannot be opened with your key (junk posted to the public URL) are counted and skipped.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

PREFIX = "sealed:"


def sealed_values(path: Path, column: str = "sealed_report") -> list[str]:
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    if not rows:
        return []
    header = rows[0]
    index = header.index(column) if column in header else len(header) - 1
    return [r[index] for r in rows[1:] if len(r) > index and r[index].strip()]


def open_sealed(token: str, private_key_b64: str) -> bytes:
    """Standalone on purpose: this script runs from a plain terminal, where only pynacl is needed (boltz2nb need not be installed)."""
    import base64

    from nacl.public import PrivateKey, SealedBox
    return SealedBox(PrivateKey(base64.b64decode(private_key_b64))).decrypt(base64.b64decode(token))


def open_reports(values: list[str], private_key_b64: str) -> tuple[list[dict], int]:
    reports, skipped = [], 0
    for value in values:
        try:
            token = value.strip()
            reports.append(json.loads(open_sealed(token[len(PREFIX):] if token.startswith(PREFIX) else token, private_key_b64)))
        except Exception:  # noqa: BLE001
            skipped += 1
    return reports, skipped


def summary(reports: list[dict]) -> str:
    lines = [f"{len(reports)} reports, {len({r.get('session_id') for r in reports})} sessions"]
    lines += [f"  {n:5d}  {event}" for event, n in collections.Counter(r.get("event") for r in reports).most_common()]
    failed = [r for r in reports if r.get("event") == "job failed"]
    if failed:
        lines.append("failed jobs by likely cause:")
        lines += [f"  {n:5d}  {cause}" for cause, n in collections.Counter(r.get("likely_cause") for r in failed).most_common()]
    days = collections.Counter(str(r.get("ts", ""))[:10] for r in reports)
    lines.append("reports per day: " + ", ".join(f"{d} {n}" for d, n in sorted(days.items())[-7:]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", type=Path, help="CSV export of the receiving sheet")
    ap.add_argument("--key", type=Path, required=True, help="private key file written by telemetry_keygen.py")
    ap.add_argument("--column", default="sealed_report")
    ap.add_argument("--jsonl", type=Path, help="also write the opened reports here, one JSON object per line")
    args = ap.parse_args(argv)
    try:
        import nacl  # noqa: F401
    except ImportError:
        print("pynacl is required: pip install pynacl", file=sys.stderr)
        return 2
    reports, skipped = open_reports(sealed_values(args.csv, args.column), args.key.read_text().strip())
    print(summary(reports))
    if skipped:
        print(f"{skipped} rows could not be opened with this key and were skipped")
    if args.jsonl:
        args.jsonl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reports), encoding="utf-8")
        print(f"written to {args.jsonl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
