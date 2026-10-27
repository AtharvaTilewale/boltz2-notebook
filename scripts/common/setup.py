# @title Install Dependencies and Boltz2 with CUDA support
# ruff: noqa: E402
"""Environment setup shared by every notebook (executed via %run from Cell 1).

Reads these environment variables (set by the notebook cell):
  BOLTZ2NB_REPO_DIR          clone of this repository (default /content/boltz2-notebook)
  FORCE_REINSTALL            "1" to reinstall even if boltz imports
  BOLTZ2NB_SEND_USAGE_STATS  "1" while SEND_USAGE_STATS is ticked, the default (encrypted usage reports, see boltz2nb/telemetry.py and docs/PRIVACY.md)
No Google account information is read or transmitted.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


class Color:
    CYAN = "\033[96m"; GREEN = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"; RESET = "\033[0m"


REPO_DIR = Path(os.environ.get("BOLTZ2NB_REPO_DIR", "/content/boltz2-notebook"))
BASE_DIR = Path(os.environ.get("BOLTZ2NB_BASE_DIR", "/content/boltz_data"))
FORCE_REINSTALL = os.environ.get("FORCE_REINSTALL", "0") == "1"
all_success = True


def _spin(msg, stop):
    syms = "-\\|/"
    i = 0
    while not stop.is_set():
        sys.stdout.write(f"\r[{syms[i % 4]}] {msg}   "); sys.stdout.flush(); time.sleep(0.1); i += 1
    sys.stdout.write("\r" + " " * (len(msg) + 12) + "\r"); sys.stdout.flush()


def step(msg, fn, allow_fail=False):
    global all_success
    stop = threading.Event()
    t = threading.Thread(target=_spin, args=(msg, stop)); t.start()
    try:
        out = fn()
        stop.set(); t.join()
        print(f"[{Color.GREEN}✔{Color.RESET}] {msg}" + (f" {out}" if isinstance(out, str) and out else ""))
        return True
    except Exception as e:  # noqa: BLE001
        stop.set(); t.join()
        tag = Color.YELLOW + "i" if allow_fail else Color.RED + "✘"
        print(f"[{tag}{Color.RESET}] {msg} failed: {str(e)[:400]}")
        if not allow_fail:
            all_success = False
        return False


def run(cmd, **kw):
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip()[-1500:])
    return res.stdout


print(f"{Color.CYAN}=== Boltz2-Notebook setup ==={Color.RESET}")
print(f"[i] Python {sys.version.split()[0]}  |  Colab runtime: {os.environ.get('COLAB_RELEASE_TAG', 'not Colab')}")

# --- 1. make the package importable (installs boltz2nb from the clone) ---------------
sys.path.insert(0, str(REPO_DIR))
# --- refresh stale boltz2nb (the same block is in every notebook script; the check itself is boltz2nb/_build.py) ---
# Cell 1 can update the clone under a running kernel; modules imported from the older copy would then be mixed with this newer script.
def _refresh_stale_boltz2nb():
    import importlib.util
    import sys
    from pathlib import Path

    loaded = sys.modules.get("boltz2nb")
    if loaded is None or not getattr(loaded, "__file__", None):
        return
    build_file = Path(loaded.__file__).parent / "_build.py"
    if build_file.exists():
        spec = importlib.util.spec_from_file_location("_boltz2nb_build", build_file)
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        build.drop_stale_modules(loaded)


_refresh_stale_boltz2nb()
del _refresh_stale_boltz2nb
# --- end refresh ---
try:
    from boltz2nb import __version__ as NB_VERSION
    from boltz2nb.install import engine_version, module_available, pick_boltz_requirement, verify_installation
except Exception as e:  # noqa: BLE001
    raise SystemExit(f"Cannot import boltz2nb from {REPO_DIR}: {e}. Re-run the cell with FORCE_REINSTALL=True.") from e

engine_req = pick_boltz_requirement()
print(f"[i] boltz2nb {NB_VERSION}  |  engine to install: {engine_req}")
if sys.version_info >= (3, 13):
    print(f"{Color.YELLOW}[i] Python 3.13 runtime: the official 'boltz' wheel does not support 3.13 yet, "
          f"installing the community fork ({engine_req}). To use the official package pick runtime version 2026.7 "
          f"(Python 3.12) under Runtime > Change runtime type.{Color.RESET}")

already = (not FORCE_REINSTALL) and module_available("boltz") and module_available("torch") and shutil.which("boltz")
if already:
    print(f"[{Color.GREEN}✔{Color.RESET}] Boltz engine already installed ({engine_version()}); skipping (FORCE_REINSTALL=True to redo).")
else:
    step("Installing uv package manager", lambda: run([sys.executable, "-m", "pip", "install", "-q", "uv"]), allow_fail=True)
    pkgs = [f"{REPO_DIR}[ligand,viewer]", engine_req]

    def install():
        try:
            return run(["uv", "pip", "install", "--system", "--python", sys.executable, "-q", *pkgs])
        except Exception:  # noqa: BLE001  (uv missing or failed -> pip)
            return run([sys.executable, "-m", "pip", "install", "-q", *pkgs])
    step(f"Installing Boltz engine + boltz2nb ({engine_req})", install)

ok, msg = verify_installation()
if ok:
    print(f"[{Color.GREEN}✔{Color.RESET}] Validation: {msg}")
    if "cuda False" in msg:
        print(f"{Color.YELLOW}[!] No GPU visible to torch. Runtime > Change runtime type > GPU (T4 or better).{Color.RESET}")
else:
    all_success = False
    print(f"[{Color.RED}✘{Color.RESET}] Validation failed: {msg[-800:]}")

# --- 2. stage scripts into the work dir and keep a copy of the package ------------------
BASE_DIR.mkdir(parents=True, exist_ok=True)
dst_scripts = BASE_DIR / "scripts"
if dst_scripts.exists():
    shutil.rmtree(dst_scripts)
shutil.copytree(REPO_DIR / "scripts", dst_scripts)
(BASE_DIR / "VERSION").write_text(NB_VERSION + "\n")
print(f"[{Color.GREEN}✔{Color.RESET}] Notebook scripts staged in {dst_scripts}")

# --- 3. usage reports (SEND_USAGE_STATS; docs/PRIVACY.md lists exactly what is sent) -------------
# Silent by design: the form's description line and docs/PRIVACY.md disclose it, and a copy of every
# report sent is kept in usage_reports.jsonl. Nothing here may print, slow down or fail the setup.
try:
    from boltz2nb import telemetry
    if telemetry.state() == "on":
        if not module_available("nacl"):
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pynacl"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False)
        telemetry.setup_done(engine_version(), sys.version.split()[0], copy_to=BASE_DIR / "usage_reports.jsonl")
except Exception:  # noqa: BLE001
    pass

if all_success:
    print(f"{Color.GREEN}All setup steps completed.{Color.RESET}")
else:
    print(f"{Color.RED}Setup finished with errors - see messages above.{Color.RESET}")
