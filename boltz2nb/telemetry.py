"""Usage reports, sealed so that only the maintainer can read them.

``SEND_USAGE_STATS`` in the setup cell is ticked by default; unticking it sends nothing. A report is sent only when it is ticked *and* this build
has both a collection endpoint and the maintainer's
public key (``telemetry_config.py``). Every report is encrypted with that public key before it leaves the runtime (libsodium sealed box): the
endpoint and anyone who can browse its storage hold only ciphertext, and only the holder of the private key - which is not in this repository -
can open it. If the key or the encryption library is missing nothing is sent: a report is never sent in the clear.

What a report may contain is the allow-list ``EVENT_FIELDS`` and nothing else (see docs/PRIVACY.md): the time, a random session id, the
versions, the GPU model; for a job its name, the number of chains and residues and the run settings; for its end the outcome and, for a failed
job, the last lines of the engine log with sequences, ligand strings, paths, e-mail addresses and URL queries masked. Sequences, ligands,
modifications, results and Google account details are never part of it. A plain copy of every report sent is kept next to the job's results
(``usage_reports.jsonl``) so the user can see exactly what left the runtime.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from . import __version__, telemetry_config
from .run_params import DEFAULTS

SCHEMA = 1
EVENTS = ("boltz setup", "job started", "job succeeded", "job failed")
_COMMON = {"v", "ts", "session_id", "event", "notebook_version", "engine", "python", "gpu"}
EVENT_FIELDS: dict[str, set[str]] = {
    "boltz setup": set(_COMMON),
    "job started": _COMMON | {"job_name", "n_chains", "n_ligand_chains", "polymer_residues", "params"},
    "job succeeded": _COMMON | {"job_name", "runtime_sec"},
    "job failed": _COMMON | {"job_name", "runtime_sec", "return_code", "likely_cause", "log_tail"},
}
ALLOWED_FIELDS: set[str] = set().union(*EVENT_FIELDS.values())
PARAM_KEYS = frozenset(DEFAULTS) - {"job_name"}               # the run settings of the parameter step; the name travels as its own field
_LIMITS = {"job_name": 80, "engine": 80, "python": 40, "gpu": 80, "likely_cause": 200, "log_tail": 6000}
_SESSION_ID = str(uuid.uuid4())


# --------------------------------------------------------------------------------------------- configuration
def enabled() -> bool:
    return os.environ.get("BOLTZ2NB_SEND_USAGE_STATS", "0") == "1"


def endpoint() -> str:
    """BOLTZ2NB_TELEMETRY_URL overrides the shipped endpoint; set to an empty string it switches reporting off."""
    url = os.environ.get("BOLTZ2NB_TELEMETRY_URL")
    return url if url is not None else telemetry_config.ENDPOINT


def public_key() -> str:
    key = os.environ.get("BOLTZ2NB_TELEMETRY_KEY")
    return key if key is not None else telemetry_config.PUBLIC_KEY


def configured() -> bool:
    return bool(endpoint() and public_key())


def state() -> str:
    """``off`` (not ticked), ``unconfigured`` (ticked, but this build cannot send) or ``on``."""
    return "off" if not enabled() else ("on" if configured() else "unconfigured")


def session_id() -> str:
    return _SESSION_ID


# --------------------------------------------------------------------------------------------- sealing
def seal(data: bytes, public_key_b64: str) -> str:
    from nacl.public import PublicKey, SealedBox
    return base64.b64encode(SealedBox(PublicKey(base64.b64decode(public_key_b64))).encrypt(data)).decode("ascii")


def open_sealed(token: str, private_key_b64: str) -> bytes:
    """What the maintainer does with a stored report (tools/telemetry_read.py)."""
    from nacl.public import PrivateKey, SealedBox
    return SealedBox(PrivateKey(base64.b64decode(private_key_b64))).decrypt(base64.b64decode(token))


# --------------------------------------------------------------------------------------------- payloads
def _clip(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def run_settings(params: dict[str, Any]) -> dict[str, Any]:
    """The run settings that may be reported: the parameter step's own keys with plain numbers, flags or short words as values."""
    out: dict[str, Any] = {}
    for key in sorted(PARAM_KEYS & set(params or {})):
        value = params[key]
        if value is None or isinstance(value, (bool, int, float)):
            out[key] = value
        elif isinstance(value, str) and len(value) <= 24:
            out[key] = value
    return out


def build_payload(event: str, **fields: Any) -> dict[str, Any]:
    if event not in EVENT_FIELDS:
        raise ValueError(f"unknown event {event!r}")
    extra = set(fields) - (EVENT_FIELDS[event] - {"v", "ts", "session_id", "event", "notebook_version"})
    if extra:
        raise ValueError(f"fields not allowed for {event!r}: {sorted(extra)}")
    payload: dict[str, Any] = {"v": SCHEMA, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "session_id": _SESSION_ID,
                               "event": event, "notebook_version": __version__}
    for key, value in fields.items():
        if key == "params":
            payload[key] = run_settings(value)
        elif key in _LIMITS:
            payload[key] = _clip(value, _LIMITS[key])
        elif key in ("n_chains", "n_ligand_chains", "polymer_residues", "return_code"):
            payload[key] = int(value)
        elif key == "runtime_sec":
            payload[key] = round(float(value), 1)
    assert set(payload) <= EVENT_FIELDS[event]
    return payload


def job_summary(doc: dict[str, Any] | None) -> dict[str, int]:
    """Counts only, read from the input document: chains, ligand chains and polymer residues. No sequence or ligand string leaves this function."""
    chains = ligands = residues = 0
    for item in (doc or {}).get("sequences", []) or []:
        for kind, data in item.items():
            ids = (data or {}).get("id")
            n = len(ids) if isinstance(ids, (list, tuple)) else (1 if ids else 0)
            n = n or 1
            chains += n
            if kind == "ligand":
                ligands += n
            else:
                residues += n * len(str((data or {}).get("sequence", "")))
    return {"n_chains": chains, "n_ligand_chains": ligands, "polymer_residues": residues}


def gpu_name() -> str:
    try:
        import torch
        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------------------------- log masking
_PROGRESS = re.compile(r"\d+%\||it/s\]|s/it\]|[━╸╺]|\x1b\[")
_URL_QUERY = re.compile(r"(https?://[^\s?#'\"]+)[?#][^\s'\"]*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DRIVE = re.compile(r"/content/drive/[^\n'\"]*")
_SITE = re.compile(r"(?<![\w.])/(?:[\w.+@-]+/)*site-packages/")
_PATH = re.compile(r"(?<![\w.:/])/(?:[\w.+@-]+/)+([\w.+@-]+)")
_SEQ_UPPER = re.compile(r"\b[A-Z]{8,}\b")
_SEQ_ANY = re.compile(r"\b[ACDEFGHIKLMNPQRSTVWYacdefghiklmnpqrstvwy]{12,}\b")
_BRACKET_ATOM = r"\[\d{0,3}(?:[A-Z][a-z]?|[bcnops]|se|as)(?:@{1,2})?(?:H\d?)?(?:[+-]{1,2}\d?)?(?::\d+)?\]"      # [C@H] [nH] [O-] [13C]: not [ccd]
_SMILES_TOKEN = re.compile(r"(?:" + _BRACKET_ATOM + r"|Cl|Br|[BCNOPSFIbcnops]|[0-9%]|[=#$:/\\()+\-.@*])+")


def _mask_smiles(token: str) -> str:
    core = token.rstrip(",;:'\")")
    if len(core) >= 5 and _SMILES_TOKEN.fullmatch(core) and re.search(r"[()=#\[\]@]|[A-Za-z][0-9]", core):
        return "<smiles>" + token[len(core):]
    return token


def redact_log(text: str, max_lines: int = 60, max_chars: int = 6000) -> str:
    """The end of an engine log with what could identify an input masked. Best effort: it removes sequences, ligand strings, file paths, e-mail
    addresses and URL queries, but a log can always contain something unexpected, which is why this is only sent when the user opts in."""
    lines = [ln for ln in str(text or "").replace("\r", "\n").splitlines() if ln.strip() and not _PROGRESS.search(ln)]
    out = []
    for line in lines[-max_lines:]:
        line = _EMAIL.sub("<email>", line)
        line = _URL_QUERY.sub(r"\1?<query>", line)
        line = _DRIVE.sub("<drive path>", line)
        line = _SITE.sub("\x01", line)                                   # keep the package-relative part of a traceback path (boltz/data/parse/yaml.py)
        line = _PATH.sub(lambda m: "<path>/" + m.group(1), line)
        line = _SEQ_UPPER.sub(lambda m: f"<seq {len(m.group(0))}>", line)
        line = _SEQ_ANY.sub(lambda m: f"<seq {len(m.group(0))}>", line)
        out.append(" ".join(_mask_smiles(tok) for tok in line.split(" ")).replace("\x01", "<site-packages>/"))
    return "\n".join(out)[-max_chars:]


# --------------------------------------------------------------------------------------------- sending
def send(event: str, *, copy_to: str | Path | None = None, timeout: float = 3.0, **fields: Any) -> dict[str, Any] | None:
    """Send one report if (and only if) the user opted in and the build is configured. Never raises; returns what was sent, else None."""
    if not enabled():
        return None
    try:
        url, key = endpoint(), public_key()
        if not (url and key):
            return None
        payload = build_payload(event, **fields)
        body = seal(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), key)
        import requests
        if not requests.post(url, data={"v": str(SCHEMA), "p": body}, timeout=timeout).ok:
            return None
        if copy_to:
            with open(copy_to, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return payload
    except Exception:  # noqa: BLE001
        return None


def setup_done(engine: str, python: str, copy_to: str | Path | None = None) -> dict[str, Any] | None:
    return send("boltz setup", copy_to=copy_to, engine=engine, python=python, gpu=gpu_name())


def job_started(doc: dict[str, Any] | str | None, params: dict[str, Any], engine: str, copy_to: str | Path | None = None) -> dict[str, Any] | None:
    """``doc`` is the input document or its YAML text; it is only read, for counts, when the user opted in and the build can send."""
    if state() != "on":
        return None
    try:
        if isinstance(doc, str):
            import yaml
            doc = yaml.safe_load(doc)
        return send("job started", copy_to=copy_to, job_name=params.get("job_name", ""), engine=engine, gpu=gpu_name(), params=params, **job_summary(doc))
    except Exception:  # noqa: BLE001
        return None


def job_ended(ok: bool, job_name: str, runtime_sec: float, engine: str, copy_to: str | Path | None = None, return_code: int = 0,
              likely_cause: str = "", log_text: str = "") -> dict[str, Any] | None:
    try:
        if ok:
            return send("job succeeded", copy_to=copy_to, job_name=job_name, runtime_sec=runtime_sec, engine=engine, gpu=gpu_name())
        return send("job failed", copy_to=copy_to, job_name=job_name, runtime_sec=runtime_sec, return_code=return_code, likely_cause=likely_cause,
                    log_tail=redact_log(log_text), engine=engine, gpu=gpu_name())
    except Exception:  # noqa: BLE001
        return None
