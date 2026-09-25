# @title Analyse Results
# --- IMPORTS (MERGED FROM BOTH SCRIPTS) ---
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle, FancyBboxPatch
import io
import base64
from IPython.display import display, HTML
import os
import json
from Bio.PDB import PDBParser

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
os.chdir("/content/boltz_data/")
params_filepath = "/content/boltz_data/run_params.txt"
params = {}
with open(params_filepath, 'r') as f:
    for line in f:
        if '=' in line:
            key, value_str = line.split('=', 1)
            params[key.strip()] = parse_value(value_str)
job_name = params.get("job_name")
use_potentials = params.get("use_potentials", False)
override = params.get("override", False)
recycling_steps = params.get("recycling_steps", 3)
sampling_steps = params.get("sampling_steps", 50)
diffusion_samples = params.get("diffusion_samples", 1)
step_scale = params.get("step_scale", 10.0)
max_msa_seqs = params.get("max_msa_seqs", 254)
msa_pairing_strategy = params.get("msa_pairing_strategy", "unpaired_paired")

# ==============================================================================
# SECTION 1: AFFINITY PLOTTING CODE (from affinity.py)
# ==============================================================================

# --- Design Palette ---
FIG_BG_COLOR = "#ffffff"
CARD_BG_COLOR = "#ffffff"
SUBTLE_TEXT_COLOR = "#2f2f2f"
DIVIDER_COLOR = "#F3F3F3"
MIN_COLOR = "#79CBF8"
MAX_COLOR = "#0677DB"
TITLE_COLOR = "#0677DB"

# --- Helper Functions for Affinity Plotting ---
def get_color_shade(min_hex: str, max_hex: str, value: float) -> str:
    """Interpolates between two hex colors based on a value between 0 and 1."""
    min_rgb = mcolors.to_rgb(min_hex)
    max_rgb = mcolors.to_rgb(max_hex)
    new_rgb = [(1 - value) * min_rgb[i] + value * max_rgb[i] for i in range(3)]
    return mcolors.to_hex(new_rgb)

def get_prob_assessment(prob: float) -> str:
    """Return a qualitative confidence assessment based on probability."""
    if prob > 0.75: return "High Confidence Binder"
    if prob > 0.4: return "Moderate Confidence Binder"
    return "Low Confidence Binder"

def get_affinity_assessment(aff_val: float) -> str:
    """Return a qualitative binding strength based on the affinity value."""
    if aff_val < -2: return "Strong Binder"
    if aff_val < -1.5: return "Good Binder"
    if aff_val < 1: return "Moderate Binder"
    return "Weak Binder / Decoy"

# --- Core Function to Draw a Single Affinity Card (MODIFIED FOR BETTER SPACING) ---
# --- Core Function to Draw a Single Affinity Card (WITH IMPROVED FONT) ---
def create_analysis_card(ax: plt.Axes, title: str, prob: float, aff_val: float, color: str):
    font_family = 'sans-serif' 

    """Draws a single, self-contained analysis card with a top-down layout."""
    ax.axis("off")
    ax.set_aspect('equal', adjustable='box')
    ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96, facecolor=CARD_BG_COLOR,
                                 edgecolor=MAX_COLOR, boxstyle="round,pad=0,rounding_size=0.04",
                                 transform=ax.transAxes, linewidth=1))

    # Main Card Title
    ax.text(0.5, 0.93, title, ha="center", va="center", fontsize=15, fontweight="bold", transform=ax.transAxes, fontfamily=font_family)

    # --- CHANGE 1: UNCOMMENT AND ADD SECTION TITLE ---
    # Top Section: Hit Discovery
    ax.text(0.5, 0.86, "Hit Discovery", ha="center", va="center", fontsize=14, color=TITLE_COLOR, transform=ax.transAxes, fontfamily=font_family)
    
    donut_center, donut_radius, plot_linewidth = (0.5, 0.66), 0.14, 10
    theta_track = np.linspace(0, 2 * np.pi, 200)
    ax.plot(donut_center[0] + donut_radius * np.cos(theta_track), donut_center[1] + donut_radius * np.sin(theta_track),
            color=DIVIDER_COLOR, linewidth=plot_linewidth, transform=ax.transAxes)
    if prob > 0:
        start_angle, end_angle = 90, 90 - (prob * 360)
        theta_value = np.linspace(np.deg2rad(end_angle), np.deg2rad(start_angle), 200)
        ax.plot(donut_center[0] + donut_radius * np.cos(theta_value), donut_center[1] + donut_radius * np.sin(theta_value),
                color=color, linewidth=plot_linewidth, solid_capstyle='round', transform=ax.transAxes)
    ax.text(donut_center[0], donut_center[1], f"{prob:.1%}", ha="center", va="center", fontsize=20, fontweight="bold", transform=ax.transAxes, fontfamily=font_family)
    ax.text(
        0.5, 0.47, 
        f"({get_prob_assessment(prob)})",  # <-- add brackets here
        ha="center", va="center", fontsize=10, color=SUBTLE_TEXT_COLOR, style="italic", 
        transform=ax.transAxes, fontfamily=font_family
    )

    # --- CHANGE 2: UNCOMMENT AND ADD HORIZONTAL DIVIDER ---
    # ax.plot([0.05, 0.95], [0.44, 0.44], color=DIVIDER_COLOR, linestyle="--", linewidth=1.5, transform=ax.transAxes)

    # --- CHANGE 3: UNCOMMENT AND ADD SECTION TITLE ---
    # Bottom Section: Lead Optimization
    ax.text(0.5, 0.38, "Lead Optimization", ha="center", va="center", fontsize=14, color=TITLE_COLOR, transform=ax.transAxes, fontfamily=font_family)
    
    ic50 = 10 ** aff_val
    delta_g = (6 - aff_val) * 1.364
    ax.text(0.5, 0.28, f"Predicted IC₅₀: {ic50:.2f} µM", ha="center", va="center", fontsize=12, fontweight="bold", transform=ax.transAxes, fontfamily=font_family)
    ax.text(0.5, 0.21, f"ΔG ≈ -{delta_g:.2f} kcal/mol", ha="center", va="center", fontsize=12, transform=ax.transAxes, fontfamily=font_family)

    meter_y_pos, meter_range = 0.13, [-3, 2]
    norm_val = (meter_range[1] - aff_val) / (meter_range[1] - meter_range[0])
    bar_fill = max(0, min(1, norm_val))
    bar_width = 0.4
    bar_height = 0.005
    bar_x = 0.5 - bar_width / 2

    # Background bar (gray, rounded)
    ax.add_patch(FancyBboxPatch((bar_x, meter_y_pos), bar_width, bar_height,
                                 boxstyle="round,pad=0.01,rounding_size=0.015",
                                 linewidth=0, facecolor=DIVIDER_COLOR,
                                 transform=ax.transAxes))

    # Filled portion (colored, rounded)
    ax.add_patch(FancyBboxPatch((bar_x, meter_y_pos), bar_width * bar_fill, bar_height,
                                 boxstyle="round,pad=0.01,rounding_size=0.015",
                                 linewidth=0, facecolor=color,
                                 transform=ax.transAxes))

    ax.text(0.27, meter_y_pos + 0.0015, "Weak", ha="right", va="center", fontsize=11, color=SUBTLE_TEXT_COLOR, transform=ax.transAxes, fontfamily=font_family)
    ax.text(0.74, meter_y_pos + 0.0015, "Strong", ha="left", va="center", fontsize=11, color=SUBTLE_TEXT_COLOR, transform=ax.transAxes, fontfamily=font_family)
    ax.text(
      0.5, 0.08, 
      f"({get_affinity_assessment(aff_val)})",  # <-- add brackets here
      ha="center", va="center", fontsize=10, color=SUBTLE_TEXT_COLOR, style="italic", 
      transform=ax.transAxes, fontfamily=font_family
    )

# --- Main Function to Generate and Display Affinity Plot (MODIFIED FOR TALLER FIGURE) ---
def generate_affinity_plot_html(job_name: str, plots_dir: str) -> str:
    """
    Checks for 'affinity.json', generates the plot if it exists, saves it to a file,
    and returns it as an HTML <img> tag encoded in base64.
    """
    base_path = f"/content/boltz_data/{job_name}/boltz_results_{job_name}/predictions/{job_name}"
    affinity_json_path = f"{base_path}/affinity_{job_name}.json"
    if not os.path.exists(affinity_json_path):
        return ""

    try:
        with open(affinity_json_path, 'r') as f:
            json_data = json.load(f)

        # --- CHANGE HERE: Increased the figure height from 12 to 14 for a taller plot ---
        fig, ax = plt.subplots(1, 1, figsize=(6, 16), constrained_layout=True)
        fig.set_facecolor(FIG_BG_COLOR)

        card_data = [
            {"title": "Ensemble Model Analysis", "prob": json_data["affinity_probability_binary"], "aff_val": json_data["affinity_pred_value"]},
        ]

        for ax, data in zip([ax], card_data):
            dynamic_color = get_color_shade(MIN_COLOR, MAX_COLOR, data["prob"])
            create_analysis_card(ax, data["title"], data["prob"], data["aff_val"], dynamic_color)

        # Save plot to an in-memory buffer for HTML display
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, facecolor=FIG_BG_COLOR, bbox_inches="tight")
        buf.seek(0)
        affinity_b64 = base64.b64encode(buf.read()).decode('utf-8')

        # Save the same plot to a file
        affinity_filename = os.path.join(plots_dir, f"{job_name}_affinity.png")
        plt.savefig(affinity_filename, dpi=300, facecolor=FIG_BG_COLOR, bbox_inches="tight")
        plt.close(fig)

        # Return the plot with its own header and description as an HTML string
        return f"""
        <div class="dashboard-header">
            <h2>Affinity Result: {job_name}</h2>
            <p>
                Binding affinity predictions from the ensemble model and its individual components. The report includes Hit Discovery Potential (probability of binding) and Lead Optimization metrics (predicted IC₅₀ and ΔG). Lower IC₅₀ and more negative ΔG values suggest stronger binding.
            </p>
        </div>
        <div class="affinity-container" style="text-align: center; margin-bottom: 25px;">
             <img src="data:image/png;base64,{affinity_b64}" alt="Affinity Analysis Plot" style="max-width: 500px; width: 100%; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        </div>
        """
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not process '{affinity_json_path}'. Error: {e}. Skipping affinity plot.")
        return ""
# ==============================================================================
# SECTION 2: MODEL CONFIDENCE PLOTTING CODE (from MYCODE)
# ==============================================================================

def create_dashboard_data(job_name, model_id=0, plots_dir=''):
    """Generates pLDDT/PAE plots, saves them, and provides summary statistics."""
    base_path = f"/content/boltz_data/{job_name}/boltz_results_{job_name}/predictions/{job_name}"
    plddt_file = f"{base_path}/plddt_{job_name}_model_{model_id}.npz"
    pae_file = f"{base_path}/pae_{job_name}_model_{model_id}.npz"
    pdb_file = f"{base_path}/{job_name}_model_{model_id}.pdb"

    for f in [plddt_file, pae_file, pdb_file]:
        if not os.path.exists(f):
            raise FileNotFoundError(f"File not found: {f}")

    plddt_data = np.load(plddt_file)["plddt"] * 100
    pae_data = np.load(pae_file)["pae"]
    structure = PDBParser(QUIET=True).get_structure("protein", pdb_file)

    chain_info = {}
    residue_index = 0
    for chain in structure[0]:
        chain_id = chain.id
        chain_info[chain_id] = {'indices': []}
        for residue in chain:
            if residue.id[0] == ' ':
                chain_info[chain_id]['indices'].append(residue_index)
                residue_index += 1

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    color_to_cmap_map = {'#1f77b4': 'Blues_r', '#ff7f0e': 'Oranges_r', '#2ca02c': 'Greens_r', '#d62728': 'Reds_r',
                         '#9467bd': 'Purples_r', '#8c564b': 'YlOrBr_r', '#e377c2': 'RdPu_r', '#7f7f7f': 'Greys_r',
                         '#bcbd22': 'summer_r', '#17becf': 'GnBu_r'}

    all_chain_data = []
    for i, (chain_id, info) in enumerate(chain_info.items()):
        indices = info['indices']
        if not indices: continue

        chain_color, pae_cmap = colors[i % len(colors)], color_to_cmap_map.get(colors[i % len(colors)], 'Blues_r')
        chain_plddt = plddt_data[indices]

        axis_color = '#777'

        # --- Generate pLDDT plot ---
        fig, ax = plt.subplots(figsize=(10, 4))
        for spine in ['top', 'bottom', 'left', 'right']:
            ax.spines[spine].set_color(axis_color)
        ax.plot(chain_plddt, color=chain_color, linewidth=1)
        ax.fill_between(np.arange(len(chain_plddt)), chain_plddt, color=chain_color, alpha=0.2)
        ax.set_title(f"pLDDT for Chain {chain_id}", fontsize=14, fontweight='bold')
        ax.set_xlabel(f"Residue Index (Chain {chain_id})", fontsize=12)
        ax.set_ylabel("pLDDT Score", fontsize=12)
        ax.set_xlim(0, len(chain_plddt) - 1)
        ax.set_ylim(0, 100)
        ax.grid(False)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plddt_filename = os.path.join(plots_dir, f"{job_name}_model_{model_id}_chain_{chain_id}_plddt.png")
        plt.savefig(plddt_filename, bbox_inches='tight', dpi=150)
        buf.seek(0)
        plddt_b64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        # --- Generate PAE heatmap ---
        fig, ax = plt.subplots(figsize=(6, 6))
        chain_pae = pae_data[np.ix_(indices, indices)]
        im = ax.imshow(chain_pae + chain_pae.T - np.diag(np.diag(chain_pae)), cmap=pae_cmap, origin='lower', interpolation='none')
        ax.set_title(f"PAE for Chain {chain_id}", fontsize=14, fontweight='bold')
        ax.set_xlabel(f"Residue (Chain {chain_id})", fontsize=12)
        ax.set_ylabel(f"Residue (Chain {chain_id})", fontsize=12)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label("Expected Position Error (Å)", fontsize=12)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        pae_filename = os.path.join(plots_dir, f"{job_name}_model_{model_id}_chain_{chain_id}_pae.png")
        plt.savefig(pae_filename, bbox_inches='tight', dpi=150)
        buf.seek(0)
        pae_b64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        all_chain_data.append({
            "chain_id": chain_id, "plddt_plot": plddt_b64, "pae_plot": pae_b64,
            "mean_plddt": np.mean(chain_plddt),
            "pct_confident": np.mean(np.array(chain_plddt) > 70) * 100,
            "pct_very_high": np.mean(np.array(chain_plddt) > 90) * 100
        })
    return all_chain_data

# ==============================================================================
# SECTION 3: HTML TEMPLATES & MAIN EXECUTION
# ==============================================================================

# --- HTML Templates ---
main_html_template = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
    .dashboard-container {{ font-family: 'Roboto', sans-serif; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 12px; padding: 25px; margin: 10px; }}
    .dashboard-header h2 {{ color: #145ABE; border-bottom: 2px solid #185FE2; padding-bottom: 10px; font-size: 1.8em; margin-top: 0; }}
    .dashboard-header p {{ margin-bottom: 25px; color: #6c757d; line-height: 1.6; }}
    .chain-card {{ background-color: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); overflow: hidden; }}
    .card-header {{ padding: 15px 20px; background-color: #f8f9fa; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e9ecef; }}
    .card-header h3 {{ margin: 0; color: #343a40; font-size: 1.4em; }}
    .stats-container {{ display: flex; gap: 20px; }}
    .stat-item {{ color: #495057; font-size: 0.95em; }}
    .stat-item strong {{ font-weight: 500; }}
    .stat-item span {{ font-weight: 700; padding: 4px 8px; border-radius: 5px; color: #fff; }}
    .plddt-high {{ background-color: #28a745; }}
    .plddt-medium {{ background-color: #fd7e14; }}
    .plddt-low {{ background-color: #dc3545; }}
    .plot-grid {{ display: grid; grid-template-columns: 65% 35%; gap: 0; padding: 20px; }}
    .plot-item {{ text-align: center; }}
    .plot-item img {{ max-width: 100%; height: auto; border-radius: 5px; }}
</style>
<div class="dashboard-container">
    <div class="dashboard-header">
        <h2>Model Confidence: {job_name}</h2>
        <p>
            Summary statistics and confidence plots for each predicted protein chain.
            Higher pLDDT scores and lower PAE values indicate a more reliable prediction.
        </p>
    </div>
    {all_chain_html}
    {affinity_section_html}
</div>
"""

chain_card_template = """
<div class="chain-card">
    <div class="card-header">
        <h3>Chain {chain_id}</h3>
        <div class="stats-container">
            <div class="stat-item"><strong>Mean pLDDT:</strong> <span class="{plddt_color_class}">{mean_plddt:.2f}</span></div>
            <div class="stat-item"><strong>Confident (&gt;70):</strong> {pct_confident:.1f}%</div>
            <div class="stat-item"><strong>Very High (&gt;90):</strong> {pct_very_high:.1f}%</div>
        </div>
    </div>
    <div class="plot-grid">
        <div class="plot-item"><img src="data:image/png;base64,{plddt_plot}" alt="pLDDT Plot"></div>
        <div class="plot-item"><img src="data:image/png;base64,{pae_plot}" alt="PAE Plot"></div>
    </div>
</div>
"""

# --- Main Execution Block ---
try:
    # 0. Define and create the output directory for plots
    plots_dir = f"/content/boltz_data/{job_name}/boltz_results_{job_name}/plots"
    os.makedirs(plots_dir, exist_ok=True)

    # 1. Generate the per-chain confidence plots and save them
    chain_data_list = create_dashboard_data(job_name=job_name, model_id=0, plots_dir=plots_dir)

    # 2. Generate the affinity plot HTML and save it
    affinity_html = generate_affinity_plot_html(job_name=job_name, plots_dir=plots_dir)

    if not chain_data_list and not affinity_html:
        print("No data found to generate a report.")
    else:
        all_cards_html = ""
        for chain_data in chain_data_list:
            mean_plddt = chain_data['mean_plddt']
            plddt_class = 'plddt-high' if mean_plddt >= 90 else ('plddt-medium' if mean_plddt >= 70 else 'plddt-low')
            all_cards_html += chain_card_template.format(
                chain_id=chain_data['chain_id'],
                plddt_plot=chain_data['plddt_plot'],
                pae_plot=chain_data['pae_plot'],
                mean_plddt=mean_plddt,
                pct_confident=chain_data['pct_confident'],
                pct_very_high=chain_data['pct_very_high'],
                plddt_color_class=plddt_class
            )

        # 3. Assemble and display the final HTML report
        final_html = main_html_template.format(
            job_name=job_name,
            all_chain_html=all_cards_html,
            affinity_section_html=affinity_html
        )
        display(HTML(final_html))

except FileNotFoundError as e:
    print(f"Error: A required file was not found. {e}")
except NameError:
    print("Error: The 'job_name' variable is not defined. Please define it before running this cell.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")