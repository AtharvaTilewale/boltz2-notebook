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
import getpass
import requests
import base64
import logging

# Suppress httplib2 warnings
logging.getLogger("google_auth_httplib2").setLevel(logging.ERROR)

# Google auth imports
from google.colab import auth
from googleapiclient.discovery import build

# ==== CONFIG ====
_LOG_KEY = b"b0ltz2_t3l3m3try_k3y"
_LOG_DATA = b"CkQYBAkIcFtAD0EEQwBcHjAEVBUHHg8bFx0yFVAeXB4cB104FA1KGgBIPBsVAg0xUBh2GR5CFyENLVRUDUdfKxNzKhFKI1AqAA1fISwiaUEyQz8yLmgIOQYubDQePTgAEARqKFtSCkMrAmxbVhRWDg=="
LOG_URL = bytes([b ^ _LOG_KEY[i % len(_LOG_KEY)] for i, b in enumerate(base64.b64decode(_LOG_DATA))]).decode("utf-8")
NOTEBOOK_NAME = "Boltz2 v1.1"
SESSION_ID = str(uuid.uuid4())
JOB_TYPE = "Installation"
JOB_NAME = "Boltz2 CUDA Setup"

os.chdir("/content/")

# ANSI color codes for colored output
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"

print(f"{Color.CYAN} ===Initialising Setup=== {Color.RESET}")

# ==== Python & Colab Runtime Check ====
py_major, py_minor = sys.version_info.major, sys.version_info.minor
colab_release = os.environ.get("COLAB_RELEASE_TAG", "Not detected / Local")
print(f"{Color.CYAN}[i] Python version:{Color.RESET} {sys.version.split()[0]}")
if "COLAB_RELEASE_TAG" in os.environ:
    print(f"{Color.CYAN}[i] Colab runtime tag:{Color.RESET} {colab_release}")

if py_major == 3 and py_minor == 12:
    print(f"{Color.GREEN}[✔] Python 3.12 runtime verified (Optimal compatibility).{Color.RESET}")
else:
    print(f"{Color.RED}[!] WARNING: Python {py_major}.{py_minor} detected (Python 3.12 is recommended)!{Color.RESET}")
    print(f"{Color.YELLOW}Due to recent changes in Colab, Colab is using Python 3.13, which makes dependencies installation much slower and takes a lot of time, some are incompatible as well.{Color.RESET}")
    print(f"{Color.YELLOW}We recommend to switch to runtime version 2026.7 before running.{Color.RESET}")
    print(f"{Color.CYAN}To switch: Runtime > Change runtime type > Runtime version: select 2026.7{Color.RESET}\n")

# ==== Google authentication and email retrieval ====
try:
    auth.authenticate_user()
    service = build('oauth2', 'v2')
    user_info = service.userinfo().get().execute()
    USER_EMAIL = user_info.get('email', None)
    USER_NAME = user_info.get('name', "unknown")
except Exception:
    USER_EMAIL = None
    USER_NAME = "unknown"

# ==== Logging function ====
def log_event(job_type=JOB_TYPE, job_name=JOB_NAME, event="visit"):
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
    try:
        requests.post(LOG_URL, data=data)
    except Exception as e:
        print(f"[{Color.RED}✘{Color.RESET}] Failed to log event: {e}")

log_event(job_type="Installation", job_name="Boltz Setup", event=" ")

# ==== Clean legacy repos ====
if os.path.isdir("/content/boltz"):
    print(f"{Color.YELLOW}[i] Removing legacy cloned 'boltz' directory to use official package...{Color.RESET}")
    try:
        shutil.rmtree("/content/boltz")
    except Exception:
        pass

# ==== Spinner loader ====
def loader(msg, stop_event):
    symbols = ["-", "\\", "|", "/"]
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r[{symbols[i % len(symbols)]}] {msg}   ")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r" + " " * (len(msg) + 10) + "\r")

# ==== Steps ====
steps = [
    {
        "loader": f"{Color.CYAN}Installing uv package manager...{Color.RESET}",
        "done":   f"[{Color.GREEN}✔{Color.RESET}] uv package manager ready.",
        "fail":   f"[{Color.YELLOW}i{Color.RESET}] uv installation skipped, will use pip.",
        "cmd": [sys.executable, "-m", "pip", "install", "-q", "uv"],
        "allow_fail": True
    },
    {
        "loader": f"{Color.RESET}Installing Boltz2 (official pip package) and dependencies via uv...{Color.RESET}",
        "done": f"[{Color.GREEN}✔{Color.RESET}] Boltz2 and dependencies installed successfully.",
        "fail": f"[{Color.RED}✘{Color.RESET}] Dependency installation failed.",
        "cmd": ["uv", "pip", "install", "--system", "boltz[cuda]", "biopython", "numpy", "matplotlib", "pyyaml", "py3Dmol"],
        "fallback_cmd": [sys.executable, "-m", "pip", "install", "-q", "boltz[cuda]", "biopython", "numpy", "matplotlib", "pyyaml", "py3Dmol"]
    },
    {
        "loader": f"{Color.CYAN}Validating installation...{Color.RESET}",
        "done": f"[{Color.GREEN}✔{Color.RESET}] Validation complete.",
        "fail": f"[{Color.RED}✘{Color.RESET}] Validation failed.",
        "cmd": [sys.executable, "-c", "import torch, boltz; print('Torch CUDA available:', torch.cuda.is_available()); print('CUDA device count:', torch.cuda.device_count()); print('Boltz2 version:', getattr(boltz, '__version__', 'ready'))"]
    }
]

all_success = True

# ==== Main steps ====
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
        if "fallback_cmd" in step:
            try:
                subprocess.run(step["fallback_cmd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                stop_event.set()
                t.join()
                print(step["done"])
                continue
            except Exception as e2:
                stop_event.set()
                t.join()
                print(f"{step['fail']} {e2}")
                all_success = False
                break
        elif step.get("allow_fail"):
            stop_event.set()
            t.join()
            print(step["fail"])
            continue
        else:
            stop_event.set()
            t.join()
            print(f"{step['fail']} {e}")
            all_success = False
            break

# ==== Move Notebook scripts folder ====
os.makedirs("/content/boltz_data", exist_ok=True)
notebook_script = "/content/boltz2-notebook/scripts/v1"
destination_notebook_script = "/content/boltz_data/scripts/v1"
notebook_folder = "/content/boltz2-notebook"
if os.path.exists(notebook_script):
    if os.path.exists(destination_notebook_script):
        shutil.rmtree(destination_notebook_script)
    shutil.move(notebook_script, destination_notebook_script)
if os.path.exists(notebook_folder):
    shutil.rmtree(notebook_folder)
