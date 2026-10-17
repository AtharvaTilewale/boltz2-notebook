"""Opt-in, anonymous usage counter.

Nothing is sent unless the user enables ``SEND_USAGE_STATS`` in the setup
cell.  Even then the payload is limited to an event name, the notebook and
engine versions, and a random per-session UUID - no Google account lookup,
no e-mail address, no user name, no job names or sequences.  The endpoint is
configurable so forks can point it elsewhere or leave it empty.
"""
from __future__ import annotations

import os
import uuid

from . import __version__

DEFAULT_ENDPOINT = os.environ.get("BOLTZ2NB_TELEMETRY_URL", "")
_SESSION_ID = str(uuid.uuid4())

ALLOWED_FIELDS = {"event", "notebook_version", "engine", "session_id", "python", "gpu"}


def enabled() -> bool:
    return os.environ.get("BOLTZ2NB_SEND_USAGE_STATS", "0") == "1"


def build_payload(event: str, engine: str | None = None, gpu: str | None = None,
                  python: str | None = None) -> dict[str, str]:
    payload = {"event": event, "notebook_version": __version__, "session_id": _SESSION_ID,
               "engine": engine or "", "gpu": gpu or "", "python": python or ""}
    assert set(payload) <= ALLOWED_FIELDS
    return payload


def send(event: str, endpoint: str | None = None, timeout: float = 3.0, **kw) -> bool:
    """Send a usage ping if (and only if) the user opted in. Never raises."""
    if not enabled():
        return False
    url = endpoint if endpoint is not None else DEFAULT_ENDPOINT
    if not url:
        return False
    try:
        import requests
        requests.post(url, data=build_payload(event, **kw), timeout=timeout)
        return True
    except Exception:
        return False
