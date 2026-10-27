"""boltz2nb - testable core for the Boltz2-Notebook Colab front-ends.

The Colab notebooks are thin shells; every piece of logic that can be
unit-tested without a browser lives here: YAML construction and validation,
run-parameter handling, command construction, structure/token mapping,
confidence and affinity analysis, report generation and batch orchestration.
"""

__version__ = "2.1.3"

# Fingerprint of the files this copy was imported from; notebook scripts compare it with the files on disk (see _build.py).
try:
    from pathlib import Path as _Path

    from ._build import fingerprint as _fingerprint
    BUILD_ID = _fingerprint(_Path(__file__).parent)
except Exception:  # noqa: BLE001  (read-only or zipped install: no check is possible, nothing is dropped)
    BUILD_ID = "unknown"

# Single source of truth for the Boltz engine version installed by the notebooks.
# Official `boltz` 2.2.1 declares `Requires-Python: <3.13,>=3.10`; the community
# fork supports 3.13+.  `install.pick_boltz_requirement()` chooses between them.
BOLTZ_OFFICIAL_PIN = "boltz[cuda]==2.2.1"
BOLTZ_COMMUNITY_PIN = "boltz-community[cuda]==2.10.12"
REPO_URL = "https://github.com/AtharvaTilewale/boltz2-notebook"
