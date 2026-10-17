"""Cache ColabFold-server MSAs by sequence hash so repeat runs skip the server.

After a ``--use_msa_server`` run Boltz leaves ``<out_dir>/boltz_results_<stem>/msa/<stem>_<i>.csv``
(one per protein entity, in YAML order).  We copy each into the cache keyed by the
SHA-1 of the chain sequence; on the next run of the same sequence the YAML gets
``msa: <cached file>`` and the server is not contacted.  Paired MSAs for complexes
are only reused when every protein chain is cached (otherwise Boltz would mix
server and file MSAs, which it does not allow).
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import yaml


def seq_key(sequence: str) -> str:
    return hashlib.sha1(sequence.strip().upper().encode()).hexdigest()


def _proteins(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [s["protein"] for s in doc.get("sequences", []) if "protein" in s]


def lookup(cache_dir: Path | str, sequence: str) -> Path | None:
    for ext in (".csv", ".a3m"):
        p = Path(cache_dir) / f"{seq_key(sequence)}{ext}"
        if p.exists():
            return p
    return None


def apply_cache(yaml_path: Path | str, cache_dir: Path | str) -> tuple[bool, list[str]]:
    """Rewrite the YAML to use cached MSAs if all protein chains are cached.

    Returns (applied, messages).
    """
    yaml_path, cache_dir = Path(yaml_path), Path(cache_dir)
    doc = yaml.safe_load(yaml_path.read_text())
    prots = _proteins(doc)
    if not prots:
        return False, ["No protein chains; nothing to cache."]
    if any(p.get("msa") for p in prots):
        return False, ["YAML already specifies MSAs; cache not applied."]
    hits = [lookup(cache_dir, p["sequence"]) for p in prots]
    if not all(hits):
        missing = sum(1 for h in hits if h is None)
        return False, [f"{missing}/{len(prots)} protein chains not in MSA cache; using the MSA server."]
    for p, h in zip(prots, hits):
        p["msa"] = str(h)
    yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return True, [f"Using cached MSAs for {len(prots)} protein chain(s)."]


def store(yaml_path: Path | str, out_dir: Path | str, cache_dir: Path | str) -> list[Path]:
    """Copy server-generated MSAs from a finished run into the cache."""
    yaml_path, out_dir, cache_dir = Path(yaml_path), Path(out_dir), Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    doc = yaml.safe_load(yaml_path.read_text())
    prots = _proteins(doc)
    stem = yaml_path.stem
    msa_dir = out_dir / f"boltz_results_{stem}" / "msa"
    stored: list[Path] = []
    if not msa_dir.exists():
        return stored
    # Boltz names server MSAs <stem>_<entity_index>.csv in order of protein entities.
    files = sorted(msa_dir.glob(f"{stem}_*.csv"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    for p, f in zip(prots, files):
        dest = cache_dir / f"{seq_key(p['sequence'])}.csv"
        if not dest.exists():
            shutil.copy2(f, dest)
            stored.append(dest)
    return stored
