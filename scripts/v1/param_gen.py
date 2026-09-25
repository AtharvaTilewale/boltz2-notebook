# @title Generate Parameters (YAML file & Run Config)
# Colab HTML UI -> Python File Savers
from IPython.display import HTML, display
import yaml
from google.colab import output
import os
import re
import json
import base64
import subprocess
import sys
from io import StringIO

# Install required libraries
print("🔧 Installing required dependencies...")
try:
    import Bio
    print("✓ BioPython already installed")
except ImportError:
    print("📦 Installing BioPython...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "biopython"])
    print("✓ BioPython installed successfully")

from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import is_aa

# Ensure the directory exists before changing into it
if not os.path.exists("/content/boltz_data/"):
    os.makedirs("/content/boltz_data/")
os.chdir("/content/boltz_data/")

# --- START: Custom YAML Formatting (No changes needed here) ---
class IdList(list): pass

def represent_id_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def str_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

class MyDumper(yaml.SafeDumper):
    pass

class QuotedString(str): pass

def quoted_str_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")

MyDumper.add_representer(QuotedString, quoted_str_presenter)
MyDumper.add_representer(IdList, represent_id_list)
MyDumper.add_representer(str, str_presenter)
# --- END: Custom YAML Formatting ---

def _save_params(data):
    if not isinstance(data, dict) or 'sequences' not in data:
        return {'status': 'error', 'message': 'Invalid data structure: "sequences" key missing.'}

    sequences_fixed = []
    for entry in data['sequences']:
        if 'protein' in entry:
            ids = IdList([i.upper().replace(' ', '') for i in entry['protein'].get('id', [])])
            seq = re.sub(r'\s+', '', entry['protein'].get('sequence', '').upper())
            protein_dict = {'id': ids, 'sequence': seq}
            sequences_fixed.append({'protein': protein_dict})
        elif 'ligand' in entry:
            ids = IdList([i.upper().replace(' ', '') for i in entry['ligand'].get('id', [])])
            ligand_dict = {'id': ids}
            if 'ccd' in entry['ligand']:
                ligand_dict['ccd'] = entry['ligand']['ccd'].upper().replace(' ', '')
            if 'smiles' in entry['ligand']:
                smiles_val = entry['ligand']['smiles'].replace(' ', '')
                ligand_dict['smiles'] = QuotedString(smiles_val)
            sequences_fixed.append({'ligand': ligand_dict})

    # Reconstruct the final dictionary to be dumped in the desired order
    final_yaml_data = {'version': 1}
    final_yaml_data['sequences'] = sequences_fixed # Add sequences first
    if 'properties' in data:
        final_yaml_data['properties'] = data['properties'] # Add properties last

    filename = "params.yaml"
    try:
        with open(filename, 'w') as f:
            yaml.dump(
                final_yaml_data,
                f, Dumper=MyDumper, sort_keys=False, default_flow_style=False, indent=2
            )
        return {'status': 'ok', 'filename': filename}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def _save_run_params(data):
    try:
        filename = data.get('filename', 'run_params.txt')
        content = data.get('content', '')
        with open(filename, 'w') as f:
            f.write(content)
        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

output.register_callback('save_params', _save_params)
output.register_callback('save_run_params', _save_run_params)

# --- PDB PARSING FUNCTIONS ---
def parse_pdb_file_biopython(pdb_content):
    """
    Parse PDB using BioPython (primary method)
    Returns: dict with chain_id as key and sequence as value
    """
    try:
        from io import StringIO
        from Bio.PDB import PDBIO, Select
        
        # Create a temporary PDB file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False) as tmp:
            tmp.write(pdb_content)
            tmp_path = tmp.name
        
        try:
            # Debug: Check if file was written correctly
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise ValueError("Temporary PDB file creation failed")
            
            # Parse PDB file
            parser = PDBParser(QUIET=True)
            structure = parser.get_structure('protein', tmp_path)
            
            chains = {}
            for model in structure:
                for chain in model:
                    chain_id = chain.id.strip() if chain.id else 'A'
                    sequence = []
                    
                    for residue in chain:
                        if is_aa(residue):
                            # Get 3-letter code and convert to 1-letter
                            res_name = residue.resname.strip()
                            seq_code = residue.get_id()[1]  # Residue number
                            
                            # 3-letter to 1-letter conversion
                            atom_3to1 = {
                                'ALA':'A', 'CYS':'C', 'ASP':'D', 'GLU':'E', 'PHE':'F', 'GLY':'G',
                                'HIS':'H', 'ILE':'I', 'LYS':'K', 'LEU':'L', 'MET':'M', 'ASN':'N',
                                'PRO':'P', 'GLN':'Q', 'ARG':'R', 'SER':'S', 'THR':'T', 'VAL':'V',
                                'TRP':'W', 'TYR':'Y'
                            }
                            
                            if res_name in atom_3to1:
                                sequence.append(atom_3to1[res_name])
                    
                    if sequence:
                        chains[chain_id] = ''.join(sequence)
            
            os.unlink(tmp_path)
            return chains if chains else {'error': 'No valid protein chains found in structure'}
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise e
    except Exception as e:
        # Fall back to manual parsing if BioPython fails
        print(f"[DEBUG] BioPython parsing failed: {str(e)}")
        return parse_pdb_file_manual(pdb_content)

def parse_pdb_file_manual(pdb_content):
    """
    Fallback manual PDB parser (when BioPython is unavailable)
    Returns: dict with chain_id as key and sequence as value
    """
    atom_3to1 = {
        'ALA':'A', 'CYS':'C', 'ASP':'D', 'GLU':'E', 'PHE':'F', 'GLY':'G',
        'HIS':'H', 'ILE':'I', 'LYS':'K', 'LEU':'L', 'MET':'M', 'ASN':'N',
        'PRO':'P', 'GLN':'Q', 'ARG':'R', 'SER':'S', 'THR':'T', 'VAL':'V',
        'TRP':'W', 'TYR':'Y'
    }
    
    try:
        lines = pdb_content.strip().split('\n')
        chain_residues = {}  # {chain_id: {res_num: aa}}
        processed_atoms = 0
        skipped_atoms = 0
        
        for line_num, line in enumerate(lines):
            # Look for ATOM and HETATM records
            if not (line.startswith('ATOM') or line.startswith('HETATM')):
                continue
            
            # Ensure line is long enough (PDB format requirement)
            if len(line) < 27:
                skipped_atoms += 1
                continue
            
            try:
                # Parse PDB line format (columns are 0-indexed, standard PDB format)
                # Standard PDB format:
                # Columns 1-6: Record name (ATOM/HETATM)
                # Columns 13-16: Atom name
                # Columns 18-20: Residue name
                # Columns 22-26: Residue number
                # Column 27: Insertion code
                # Column 22: Chain identifier (in standard this is after residue #)
                
                atom_name = line[12:16].strip()
                res_name = line[17:20].strip()
                chain_id = line[21].strip() if len(line) > 21 else 'A'
                res_num_str = line[22:26].strip()
                
                # Validate data
                if not chain_id:
                    chain_id = 'A'
                    
                if not res_name or res_name not in atom_3to1:
                    skipped_atoms += 1
                    continue
                    
                if atom_name != 'CA':  # Only use CA atoms (C-alpha)
                    skipped_atoms += 1
                    continue
                    
                if not res_num_str:
                    skipped_atoms += 1
                    continue
                
                # Initialize chain dict if needed
                if chain_id not in chain_residues:
                    chain_residues[chain_id] = {}
                
                # Store residue (use res_num as key to avoid duplicates)
                if res_num_str not in chain_residues[chain_id]:
                    chain_residues[chain_id][res_num_str] = atom_3to1[res_name]
                    processed_atoms += 1
                    
            except (IndexError, ValueError, KeyError) as e:
                skipped_atoms += 1
                continue
        
        print(f"[DEBUG] Manual parser stats: {processed_atoms} atoms processed, {skipped_atoms} skipped")
        
        # Convert to sequences (sorted by residue number)
        chains = {}
        for chain_id, residues in chain_residues.items():
            if residues:
                # Sort by residue number
                try:
                    sorted_res_nums = sorted(residues.keys(), key=lambda x: int(x.strip().split()[0] if x.strip() else 0))
                except:
                    sorted_res_nums = sorted(residues.keys())
                
                sequence = ''.join(residues[res_num] for res_num in sorted_res_nums)
                if sequence:
                    chains[chain_id] = sequence
                    print(f"[DEBUG] Manual parser: Chain {chain_id} -> {len(sequence)} aa")
        
        return chains if chains else {'error': 'Manual parser: No valid chains found'}
    except Exception as e:
        print(f"[DEBUG] Manual parser exception: {str(e)}")
        return {'error': f'Manual parsing failed: {str(e)}'}

def parse_pdb_file(pdb_content):
    """
    Main PDB parser that tries BioPython first, then falls back to manual parsing
    Returns: dict with chain_id as key and sequence as value
    """
    try:
        # Try BioPython first
        result = parse_pdb_file_biopython(pdb_content)
        if result and not ('error' in result):
            return result
        
        # Fall back to manual if BioPython fails
        return parse_pdb_file_manual(pdb_content)
    except Exception as e:
        return {'error': f'PDB parsing error: {str(e)}'}

def _process_pdb_upload(data):
    """Backend callback to process uploaded PDB file"""
    try:
        pdb_content = data.get('pdb_content', '').strip()
        
        # Validate input
        if not pdb_content:
            result = {'status': 'error', 'message': 'No PDB content provided. Please upload a valid PDB file.'}
            print(f"[DEBUG] Returning error (no content): {result}")
            return result
        
        # Count ATOM and HETATM records
        atom_count = pdb_content.count('ATOM')
        hetatm_count = pdb_content.count('HETATM')
        
        print(f"[DEBUG] PDB file analysis:")
        print(f"  - Total lines: {len(pdb_content.split(chr(10)))}")
        print(f"  - ATOM records: {atom_count}")
        print(f"  - HETATM records: {hetatm_count}")
        
        # Check if content looks like PDB
        if atom_count == 0 and hetatm_count == 0:
            result = {
                'status': 'error', 
                'message': 'Invalid PDB file: No ATOM or HETATM records found.\n\nThe file does not appear to be a valid PDB format.',
                'hint': 'PDB files should start with ATOM or HETATM records. Please ensure you uploaded a valid PDB structure file (usually downloaded from PDB database).'
            }
            print(f"[DEBUG] Returning error (no records): {result}")
            return result
        
        # Parse PDB
        print("[DEBUG] Starting PDB parsing...")
        chains = parse_pdb_file(pdb_content)
        print(f"[DEBUG] Parsing result: {chains}")
        
        # Check for errors from parser
        if isinstance(chains, dict) and 'error' in chains:
            parse_error = chains.get('error', 'Unknown parser error')
            print(f"[DEBUG] Parser error: {parse_error}")
            result = {'status': 'error', 'message': f'Parsing Error: {parse_error}'}
            print(f"[DEBUG] Returning parser error: {result}")
            return result
        
        if not chains or (isinstance(chains, dict) and len(chains) == 0):
            print("[DEBUG] No chains found after parsing")
            result = {
                'status': 'error', 
                'message': 'No valid protein chains found in the PDB file.\n\nThe file may contain:\n- Non-standard residues\n- Only ligands/ions (no protein chains)\n- Corrupted structure data',
                'hint': 'Try uploading a PDB file with standard protein chains. Example: 1MBN, 1HHB, or 2GHQ from RCSB PDB.'
            }
            print(f"[DEBUG] Returning no chains error: {result}")
            return result
        
        # Build chain info
        print(f"[DEBUG] Found {len(chains)} chain(s): {list(chains.keys())}")
        chain_info = {}
        for chain_id, sequence in chains.items():
            chain_info[chain_id] = {
                'sequence': sequence,
                'length': len(sequence)
            }
            print(f"[DEBUG] Chain {chain_id}: {len(sequence)} amino acids")
        
        # Build and return success response
        result = {'status': 'ok', 'chains': chain_info}
        print(f"[DEBUG] ✓ SUCCESS! Returning result with {len(chain_info)} chains")
        print(f"[DEBUG] Chain info: {result}")
        return result
        
    except Exception as e:
        print(f"[DEBUG] Exception in _process_pdb_upload: {str(e)}")
        import traceback
        traceback.print_exc()
        result = {
            'status': 'error', 
            'message': f'Unexpected error while processing PDB file:\n{str(e)}',
            'hint': 'Please try with a different PDB file or check the file format. Make sure the file is in valid PDB/PDBx format.'
        }
        print(f"[DEBUG] Returning exception error: {result}")
        return result

output.register_callback('process_pdb_upload', _process_pdb_upload)

# HTML + JS with a Revamped UI and a second page
html = r"""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
    /* --- 1. THEME & GLOBAL STYLES --- */
    :root {
        --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        --primary-color: #3b82f6; --primary-hover: #2563eb;
        --danger-color: #ef4444; --danger-hover: #dc2626;
        --secondary-color: #6b7280; --secondary-hover: #4b5563;
        --success-color: #22c55e; --success-hover: #16a34a;
        --bg-light: #f9fafb; --border-color: #d1d5db;
        --text-dark: #1f2937; --text-light: #4b5563;
        --radius: 8px; --shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }

    /* --- 2. LAYOUT & TYPOGRAPHY --- */
    .container { font-family: var(--font-family); color: var(--text-dark); background: #fff; padding: 24px; }
    .block {
        border: 1px solid var(--border-color); padding: 20px; margin: 16px 0; border-radius: var(--radius);
        background: #fff; box-shadow: var(--shadow); animation: fadeIn 0.4s ease-out; border-top: 4px solid var(--primary-color);
    }
    .block[data-type="ligand"] { border-top-color: #a855f7; }
    .block-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
    .title { font-weight: 600; font-size: 1.1em; color: var(--text-dark); display:flex; align-items:center; gap: 8px; }
    .row { display:flex; gap:25px; align-items:center; margin-bottom:20px; }
    .row label { width: 150px; color: var(--text-light); font-size: 0.9em; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; }
    input[type="checkbox"] { width: auto; flex: 0; height: 16px; width: 16px; cursor: pointer; }
    details { border: 1px solid var(--border-color); border-radius: var(--radius); padding: 12px; margin-top: 20px; }
    summary { font-weight: 500; cursor: pointer; }

    /* --- 3. FORMS & BUTTONS --- */
    input[type="text"], input[type="number"], textarea, select {
        flex: 1; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px;
        font-size: 14px; color: var(--text-dark); background: var(--bg-light); transition: border-color 0.2s, box-shadow 0.2s;
    }
    input[type="text"]:focus, input[type="number"]:focus, textarea:focus, select:focus {
        outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.4);
    }
    .btn {
        display: inline-flex; align-items: center; gap: 6px; border: none; padding: 8px 16px;
        border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500;
        transition: background-color 0.2s, transform 0.1s;
    }
    .btn:active { transform: scale(0.98); }
    .btn.primary { background: var(--primary-color); color: #fff; }
    .btn.primary:hover { background: var(--primary-hover); }
    .btn.secondary { background: var(--secondary-color); color: #fff; }
    .btn.secondary:hover { background: var(--secondary-hover); }
    .btn.success { background: var(--success-color); color: #fff; }
    .btn.success:hover { background: var(--success-hover); }
    .remove-btn {background: transparent; color: var(--secondary-color); border: none; width: 32px; height: 32px; border-radius: 50%; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; font-size: 1em; transition: background-color 0.2s, color 0.2s;}
    .remove-btn:hover {background-color: #fee2e2; color: var(--danger-color);}

    /* --- 4. TOOLTIPS --- */
    .tooltip-icon {
        position: relative;
        display: inline-block;
        cursor: help;
        color: #ccc;
        border: 1px solid #ccc;
        border-radius: 50%;
        width: 16px;
        height: 16px;
        font-size: 12px;
        line-height: 14px;
        text-align: center;
        font-style: normal;
    }
    .tooltip-icon .tooltip-text {
        visibility: hidden;
        width: 220px;
        background-color: #333;
        color: #fff;
        text-align: left;
        font-size: 0.8em;
        font-weight: 400;
        border-radius: 6px;
        padding: 8px;
        position: absolute;
        z-index: 10;
        bottom: 50%;
        left: 120%;
        transform: translateY(50%);
        opacity: 0;
        transition: opacity 0.3s;
        box-shadow: var(--shadow);
    }
    .tooltip-icon:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
    }


    /* --- 5. CONTROLS & STATUS --- */
    .controls { margin-top: 24px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    .status-message {
        display: flex; align-items: center; gap: 8px; padding: 8px 12px;
        border-radius: 6px; font-size: 0.9em; animation: fadeIn 0.3s;
    }
    .status-message.success { background-color: #dcfce7; color: #166534; }
    .status-message.error { background-color: #fee2e2; color: #991b1b; }
    .status-message.warning { background-color: #fef3c7; color: #92400e; }

    /* --- 6. PDB UPLOAD SECTION --- */
    .pdb-upload-section {
        border: 2px dashed var(--primary-color);
        padding: 20px;
        border-radius: var(--radius);
        background: linear-gradient(135deg, rgba(59,130,246,0.05) 0%, rgba(59,130,246,0.02) 100%);
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .pdb-upload-section:hover {
        border-color: var(--primary-hover);
        background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(59,130,246,0.05) 100%);
    }
    .pdb-upload-section.dragover {
        border-color: var(--success-color);
        background: linear-gradient(135deg, rgba(34,197,94,0.1) 0%, rgba(34,197,94,0.05) 100%);
    }
    #pdbFileInput { display: none; }
    .pdb-chain-selector {
        display: none;
        margin-top: 20px;
        padding: 16px;
        background: var(--bg-light);
        border-radius: var(--radius);
        border: 1px solid var(--border-color);
    }
    .pdb-chain-selector.show { display: block; animation: fadeIn 0.3s; }
    .chain-option {
        display: flex;
        align-items: center;
        padding: 12px;
        margin: 8px 0;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        background: #fff;
        cursor: pointer;
        transition: all 0.2s;
    }
    .chain-option:hover {
        background: var(--bg-light);
        border-color: var(--primary-color);
    }
    .chain-option input[type="radio"] {
        margin-right: 12px;
        cursor: pointer;
        width: 16px;
        height: 16px;
    }
    .chain-info {
        display: flex;
        gap: 20px;
        flex-grow: 1;
    }
    .chain-info-item {
        display: flex;
        flex-direction: column;
    }
    .chain-info-label {
        font-size: 0.8em;
        color: var(--text-light);
        font-weight: 500;
        text-transform: uppercase;
    }
    .chain-info-value {
        font-size: 1.1em;
        font-weight: 600;
        color: var(--text-dark);
    }
    .pdb-sequence-preview {
        margin-top: 12px;
        padding: 10px;
        background: #fff;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85em;
        color: var(--text-light);
        word-break: break-all;
        max-height: 80px;
        overflow-y: auto;
    }
</style>

<div class="container">
    <div id="main_params_container">
        <!-- PDB Upload Section -->
        <div class="pdb-upload-section" id="pdbUploadSection">
            <div style="margin-bottom: 12px;">
                <div class="title" style="margin-bottom: 8px;"><i class="fa-solid fa-file"></i> Upload or Paste PDB File</div>
                <p style="font-size: 0.9em; color: var(--text-light); margin: 0;">Extract protein sequence from a PDB structure file</p>
            </div>
            <div style="display: flex; gap: 10px; margin: 12px 0;">
                <button class="btn primary" onclick="document.getElementById('pdbFileInput').click()" style="flex:1;"><i class="fa-solid fa-upload"></i> Upload PDB File</button>
            </div>
            <input type="file" id="pdbFileInput" accept=".pdb,.txt" onchange="handlePdbFileUpload(event)">
            
            <!-- Chain Selector -->
            <div class="pdb-chain-selector" id="pdbChainSelector">
                <div style="margin-bottom: 12px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid fa-list"></i> Select Chain
                </div>
                <div id="chainOptionsContainer"></div>
                <div style="display: flex; gap: 10px; margin-top: 12px;">
                    <button class="btn success" onclick="confirmChainSelection()" style="flex:1;"><i class="fa-solid fa-check"></i> Use This Chain</button>
                    <button class="btn secondary" onclick="resetPdbUpload()" style="flex:1;"><i class="fa-solid fa-refresh"></i> Reset</button>
                </div>
            </div>
        </div>

        <div id="sequences_container"></div>
        <div id="affinity_prediction_container"></div>
        <div class="controls">
            <button class="btn primary" onclick="addProtein()"><i class="fa-solid fa-dna"></i> Add Protein</button>
            <button class="btn primary" style="background-color:#a855f7;" onclick="addLigand()"><i class="fa-solid fa-puzzle-piece"></i> Add Ligand</button>
            <button class="btn secondary" onclick="clearAll()"><i class="fa-solid fa-broom"></i> Clear Added</button>
            <button class="btn secondary" id="saveBtn" onclick="saveYaml()"><i id="saveIcon" class="fa-solid fa-save"></i> <span id="saveBtnText">Save YAML</span></button>
            <button class="btn success" id="nextBtn" onclick="showRunParams()" style="display:none;"><span id="nextBtnText">Next</span> <i class="fa-solid fa-arrow-right"></i></button>
            <div id="status"></div>
        </div>
    </div>

    <div id="run_params_container" style="display:none;">
      <div class="block">
          <div class="title" style="margin-bottom: 20px;"><i class="fa-solid fa-gears"></i> Run Parameters</div>
          <div class="row">
            <label for="rp_job_name">Job Name</label>
            <input type="text" id="rp_job_name" value="" placeholder="Insulin_Peptide" required>
          </div>
          <div class="row">
            <label for="rp_use_potentials">Use Potentials <i class="tooltip-icon">?<span class="tooltip-text">Enable the use of pre-computed potentials to guide the generation process.</span></i></label>
            <input type="checkbox" id="rp_use_potentials" checked>
          </div>
          <div class="row">
            <label for="rp_override">Override <i class="tooltip-icon">?<span class="tooltip-text">If a file with the same job name already exists, this option will overwrite it.</span></i></label>
            <input type="checkbox" id="rp_override" checked>
          </div>

          <details>
              <summary>Advanced Options</summary>
              <div style="padding-top: 20px;">
                  <div class="row">
                    <label for="rp_recycling_steps">Recycling Steps <i class="tooltip-icon">?<span class="tooltip-text">Number of times to recycle the output structure back into the model for refinement.</span></i></label>
                    <input type="number" id="rp_recycling_steps" value="3" step="1" min="1">
                  </div>
                  <div class="row">
                      <label for="rp_sampling_steps">Sampling Steps <i class="tooltip-icon">?<span class="tooltip-text">Number of steps in the diffusion process. More steps can lead to higher quality but take longer.</span></i></label>
                      <input type="range" id="rp_sampling_steps" min="50" max="400" step="50" value="200" oninput="this.nextElementSibling.value = this.value">
                      <output>200</output>
                  </div>
                  <div class="row">
                    <label for="rp_diffusion_samples">Diffusion Samples <i class="tooltip-icon">?<span class="tooltip-text">Number of independent structures to generate.</span></i></label>
                    <input type="number" id="rp_diffusion_samples" value="1" step="1" min="1">
                  </div>
                  <div class="row">
                    <label for="rp_step_scale">Step Scale <i class="tooltip-icon">?<span class="tooltip-text">Controls the noise schedule during diffusion. Higher values can sometimes improve structure quality.</span></i></label>
                    <input type="number" id="rp_step_scale" value="1.638" step="0.1" min="0.1">
                  </div>
                  <div class="row">
                      <label for="rp_max_msa_seqs">Max MSA Sequences<i class="tooltip-icon">?<span class="tooltip-text">The maximum number of sequences to use from the Multiple Sequence Alignment (MSA).</span></i></label>
                      <select id="rp_max_msa_seqs">
                          <option>32</option><option>64</option><option>128</option><option>256</option><option>512</option>
                          <option>1024</option><option>2048</option><option>4096</option><option selected>8192</option>
                      </select>
                  </div>
                  <div class="row">
                    <label for="rp_subsample_msa">Subsample MSA <i class="tooltip-icon">?<span class="tooltip-text">If enabled, a smaller, random subset of the MSA will be used.</span></i></label>
                    <input type="checkbox" id="rp_subsample_msa" onchange="toggleNumSubsampled(this)">
                  </div>
                   <div class="row" id="num_subsampled_msa_row" style="display:none;">
                      <label for="rp_num_subsampled_msa">Number of Subsampled MSA <i class="tooltip-icon">?<span class="tooltip-text">The number of sequences to use when subsampling the MSA.</span></i></label>
                      <select id="rp_num_subsampled_msa">
                          <option>4</option><option>8</option><option>16</option><option>32</option><option>64</option>
                          <option>128</option><option>256</option><option>512</option><option selected>1024</option>
                      </select>
                  </div>
                  <div class="row">
                      <label for="rp_msa_pairing_strategy">MSA Pairing Strategy <i class="tooltip-icon">?<span class="tooltip-text">Strategy for pairing sequences in the MSA. 'greedy' is faster, 'complete' can be more thorough.</span></i></label>
                      <select id="rp_msa_pairing_strategy">
                          <option>greedy</option><option>complete</option>
                      </select>
                  </div>
              </div>
          </details>
      </div>
      <div class="controls">
          <button class="btn secondary" onclick="showMainParams()"><i class="fa-solid fa-arrow-left"></i> Back</button>
          <button class="btn success" onclick="saveRunParams()"><i class="fa-solid fa-check"></i> OK</button>
          <div id="run_status"></div>
      </div>
    </div>

    <template id="first_protein_template">
        <div class="block seq-block first-protein" data-type="protein">
          <div class="block-header"><div class="title"><i class="fa-solid fa-dna"></i>Protein (Primary)</div></div>
          <div class="row"><label>IDs (comma):</label><input class="p-ids" type="text" placeholder="A,B" oninput="formatIDs(this)"/></div>
          <div class="row"><label>Sequence:</label><textarea class="p-seq" rows="5" style="text-transform: uppercase;"></textarea></div>
        </div>
    </template>

    <template id="protein_template">
        <div class="block seq-block" data-type="protein">
          <div class="block-header">
            <div class="title"><i class="fa-solid fa-dna"></i>Protein</div>
            <button class="remove-btn" onclick="removeBlock(this)" title="Remove block"><i class="fa-solid fa-trash-can"></i></button>
          </div>
          <div class="row"><label>IDs (comma):</label><input class="p-ids" type="text" placeholder="C,D" oninput="formatIDs(this)"/></div>
          <div class="row"><label>Sequence:</label><textarea class="p-seq" rows="5" style="text-transform: uppercase;"></textarea></div>
        </div>
    </template>

    <template id="ligand_template">
        <div class="block seq-block" data-type="ligand">
          <div class="block-header">
            <div class="title"><i class="fa-solid fa-puzzle-piece"></i>Ligand</div>
            <button class="remove-btn" onclick="removeBlock(this)" title="Remove block"><i class="fa-solid fa-trash-can"></i></button>
          </div>
          <div class="row"><label>IDs (comma):</label><input class="l-ids" type="text" placeholder="E,F" oninput="formatIDs(this); updateLigandChainSelector();"/></div>
          <div class="row"><label>Type:</label>
            <select class="l-type" onchange="onLigandTypeChange(this)">
              <option value="ccd">CCD</option><option value="smiles">SMILES</option>
            </select>
          </div>
          <div class="row lig-value-row"><label>Value:</label><input class="l-value" style="text-transform: uppercase;" type="text" placeholder="e.g., SAH" /></div>
        </div>
    </template>
</div>

<script>
const container = document.getElementById('sequences_container');

// Allowed amino acids (canonical 20 only)
// Allowed amino acids (canonical 20 only)
const validAminoAcids = new Set(['A','C','D','E','F','G','H','I','K','L','M','N','P','Q','R','S','T','V','W','Y']);

// Restrict protein sequence input to valid amino acids only
function restrictProteinSequence(inputElement) {
  const val = inputElement.value.toUpperCase();
  const filtered = val.split('').filter(c => validAminoAcids.has(c)).join('');
  if (val !== filtered) {
    inputElement.value = filtered;
  }
}


// Format IDs input (removes spaces, converts to uppercase, adds commas)
function formatIDs(inputElement) {
  const originalValue = inputElement.value;
  const formattedValue = originalValue.replace(/[\s,]+/g, '').split('').join(',');
  inputElement.value = formattedValue.toUpperCase();
}

function showRunParams() {
    document.getElementById('main_params_container').style.display = 'none';
    document.getElementById('run_params_container').style.display = 'block';
}
function showMainParams() {
    document.getElementById('run_params_container').style.display = 'none';
    document.getElementById('main_params_container').style.display = 'block';
    document.getElementById('run_status').innerHTML = '';
}
function toggleNumSubsampled(checkbox) {
    const row = document.getElementById('num_subsampled_msa_row');
    row.style.display = checkbox.checked ? 'flex' : 'none';
}

async function saveRunParams() {
      const getVal = id => document.getElementById(id).value;
      const getChecked = id => document.getElementById(id).checked;
      const jobName = getVal('rp_job_name').trim();
      if (!jobName) {
          document.getElementById('run_status').innerHTML = 
              `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> <strong>Error:</strong> Job Name is required. Cannot save.</div>`;
          return;  // Stop execution if job name is empty
      }

      const content = `job_name = "${jobName}"
      use_potentials = ${getChecked('rp_use_potentials')}
      override = ${getChecked('rp_override')}
      recycling_steps = ${getVal('rp_recycling_steps')}
      sampling_steps = ${getVal('rp_sampling_steps')}
      diffusion_samples = ${getVal('rp_diffusion_samples')}
      step_scale = ${getVal('rp_step_scale')}
      max_msa_seqs = ${getVal('rp_max_msa_seqs')}
      subsample_msa = ${getChecked('rp_subsample_msa')}
      num_subsampled_msa = ${getVal('rp_num_subsampled_msa')}
      msa_pairing_strategy = "${getVal('rp_msa_pairing_strategy')}"`;

    const payload = { filename: 'run_params.txt', content: content.trim() };
    const runStatusEl = document.getElementById('run_status');

    try {
        const result = await google.colab.kernel.invokeFunction('save_run_params', [payload], {});
        if (result && result.status === 'ok') {
            runStatusEl.innerHTML = `<div class="status-message success"><i class="fa-solid fa-check-circle"></i> Parameters saved successfully, you can run BoltzEngine now.</div>`;
        } else {
            runStatusEl.innerHTML = `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> <strong>Error:</strong> ${result?.message || 'Unknown error.'}</div>`;
        }
    } catch (err) {
        runStatusEl.innerHTML = `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> <strong>Save failed:</strong> ${err.toString()}</div>`;
    }
}

function addBlock(templateId) {
    const tpl = document.getElementById(templateId);
    const node = tpl.content.cloneNode(true);
    container.appendChild(node);

    // Attach sequence restriction to protein sequence textareas
    node.querySelectorAll('.p-seq').forEach(el => {
        el.addEventListener('input', () => restrictProteinSequence(el));
    });
}

function addProtein(first=false) { addBlock(first ? 'first_protein_template' : 'protein_template'); 
// Attach restriction for already existing protein sequence inputs
document.querySelectorAll('.p-seq').forEach(el => {
  el.addEventListener('input', () => restrictProteinSequence(el));
});
}

function addLigand() {
    addBlock('ligand_template');
    if (!document.getElementById('affinity-prediction-section')) {
        const affinityContainer = document.getElementById('affinity_prediction_container');
        affinityContainer.innerHTML = `
          <div id="affinity-prediction-section" class="block" style="border-top-color: var(--secondary-color); margin-bottom: 0;">
              <div class="row" style="align-items: center; margin-bottom: 12px;">
                  <input type="checkbox" id="predict_affinity_toggle" onchange="toggleAffinityOptions(this)" style="width: auto; flex: 0; height: 16px; width: 16px; cursor: pointer;">
                  <label for="predict_affinity_toggle" style="width: auto; cursor: pointer; color: var(--text-dark); font-weight: 500;">Predict Ligand Affinity</label>
              </div>
              <div id="ligand_chain_selector_container" style="display:none; margin-top: 10px;" class="row">
                  <label for="ligand_chain_id_select">Ligand Chain:</label>
                  <select id="ligand_chain_id_select"></select>
              </div>
          </div>`;
    }
}

function toggleAffinityOptions(checkbox) {
    const selectorContainer = document.getElementById('ligand_chain_selector_container');
    if (checkbox.checked) {
        selectorContainer.style.display = 'flex';
        updateLigandChainSelector();
    } else {
        selectorContainer.style.display = 'none';
    }
}

function updateLigandChainSelector() {
    const selector = document.getElementById('ligand_chain_id_select');
    if (!selector) return;
    const currentVal = selector.value;
    selector.innerHTML = '';
    const allLigandIDs = new Set();
    document.querySelectorAll('.seq-block[data-type="ligand"] .l-ids').forEach(input => {
        (input.value || '').split(',').map(s => s.trim()).filter(Boolean).forEach(id => allLigandIDs.add(id));
    });

    if (allLigandIDs.size === 0) {
        const option = document.createElement('option');
        option.textContent = 'No ligand IDs defined';
        option.value = '';
        selector.appendChild(option);
    } else {
        allLigandIDs.forEach(id => {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = id;
            selector.appendChild(option);
        });
    }
    if (allLigandIDs.has(currentVal)) { selector.value = currentVal; }
}

function removeBlock(btn) {
    btn.closest('.seq-block')?.remove();
    if (document.querySelectorAll('.seq-block[data-type="ligand"]').length === 0) {
        document.getElementById('affinity_prediction_container').innerHTML = '';
    } else {
        updateLigandChainSelector();
    }
}

function clearAll() {
    container.querySelectorAll('.seq-block:not(.first-protein)').forEach(el => el.remove());
    const first = container.querySelector('.first-protein');
    if (first) {
        first.querySelectorAll('input, textarea').forEach(el => el.value = '');
    }
    document.getElementById('affinity_prediction_container').innerHTML = '';
    document.getElementById('status').innerHTML = '';
    document.getElementById('nextBtn').style.display = 'none';
}

function onLigandTypeChange(select) {
    const valueInput = select.closest('.seq-block').querySelector('.l-value');
    valueInput.placeholder = select.value === 'ccd' ? 'e.g., SAH' : 'e.g., CCO... (SMILES)';
}

function setStatus(message, type) {
    const statusEl = document.getElementById('status');
    const icon = { success: 'fa-check-circle', error: 'fa-circle-xmark', warning: 'fa-triangle-exclamation'}[type] || 'fa-circle-info';
    statusEl.innerHTML = `<div class="status-message ${type}"><i class="fa-solid ${icon}"></i> ${message}</div>`;
    document.getElementById('nextBtn').style.display = (type === 'success') ? 'inline-flex' : 'none';
}

async function saveYaml() {
    const saveBtn = document.getElementById('saveBtn');
    const saveIcon = document.getElementById('saveIcon');
    const saveBtnText = document.getElementById('saveBtnText');
    setStatus('Validating...', 'warning');
    const sequences = [];
    const blocks = document.querySelectorAll('.seq-block');
    const allIDs = new Set();
    let valid = true;

    for (const [idx, b] of Array.from(blocks).entries()) {
        const type = b.dataset.type;
        let currentIds = [];

        if (type === 'protein') {
            currentIds = (b.querySelector('.p-ids').value || '').split(',').map(s => s.trim()).filter(Boolean);
            const seq = b.querySelector('.p-seq').value.trim();
            if (currentIds.length === 0 || !seq) {
                valid = false; setStatus(`<strong>Error:</strong> Protein block ${idx + 1} requires both IDs and a Sequence.`, 'error'); break;
            } else {
                sequences.push({ protein: { id: currentIds, sequence: seq } });
            }
        } else if (type === 'ligand') {
            currentIds = (b.querySelector('.l-ids').value || '').split(',').map(s => s.trim()).filter(Boolean);
            const ltype = b.querySelector('.l-type').value;
            const lvalue = b.querySelector('.l-value').value.trim();
            if (currentIds.length === 0 || !lvalue) {
                valid = false; setStatus(`<strong>Error:</strong> Ligand block ${idx + 1} requires both IDs and a Value.`, 'error'); break;
            } else {
                const entry = { id: currentIds };
                if (ltype === 'ccd') entry.ccd = lvalue; else entry.smiles = lvalue;
                sequences.push({ ligand: entry });
            }
        }
        for (const id of currentIds) {
            if (allIDs.has(id)) {
                valid = false; setStatus(`<strong>Error:</strong> Duplicate ID '<strong>${id}</strong>' found in block ${idx + 1}. IDs must be unique.`, 'error'); break;
            }
            allIDs.add(id);
        }
        if (!valid) break;
    }
    if (!valid) return;

    const payload = { sequences: sequences };
    const predictAffinityCheckbox = document.getElementById('predict_affinity_toggle');
    if (predictAffinityCheckbox && predictAffinityCheckbox.checked) {
        const selectedLigandId = document.getElementById('ligand_chain_id_select').value;
        if (selectedLigandId) {
            payload.properties = [{ affinity: { binder: selectedLigandId } }];
        } else {
            setStatus('<strong>Error:</strong> "Predict Ligand Affinity" is checked, but no ligand chain is selected or defined.', 'error'); return;
        }
    }

    saveBtn.disabled = true;
    saveBtnText.innerText = 'Saving...';
    saveIcon.className = 'fa-solid fa-spinner fa-spin';
    try {
        const result = await google.colab.kernel.invokeFunction('save_params', [payload], {});
        if (result && result.status === 'ok') {
            setStatus(`Parameter File Saved Successfully`, 'success');
        } else {
            setStatus(`<strong>Error:</strong> ${result?.message || 'Unknown error occurred.'}`, 'error');
        }
    } catch (err) {
        setStatus(`<strong>Save failed:</strong> ${err.toString()}`, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtnText.innerText = 'Save YAML';
        saveIcon.className = 'fa-solid fa-save';
    }
}

// Replace spaces in job name with underscores
document.getElementById("rp_job_name").addEventListener("input", function() {
  this.value = this.value.replace(/\s+/g, "_");
});

// Initialize UI
addProtein(true);

// --- PDB UPLOAD HANDLING ---
let pdbData = {
    content: '',
    chains: {},
    selectedChain: null
};

async function handlePdbFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = async (e) => {
        const content = e.target.result;
        pdbData.content = content;
        // Auto-parse after loading
        await parsePdbContentDirect();
    };
    reader.readAsText(file);
}

async function parsePdbContentDirect() {
    const content = pdbData.content.trim();
    
    if (!content) {
        showErrorMessage('❌ Upload Failed', 'Please upload a valid PDB file first.');
        return;
    }
    
    try {
        console.log('[DEBUG] Calling process_pdb_upload with', content.length, 'bytes of PDB content');
        const result = await google.colab.kernel.invokeFunction('process_pdb_upload', [{pdb_content: content}], {});
        
        console.log('[DEBUG] Raw callback result:', result);
        console.log('[DEBUG] Result type:', typeof result);
        console.log('[DEBUG] Result keys:', Object.keys(result || {}));
        
        // Handle Google Colab callback response - may be wrapped
        let response = result;
        if (result && result.data) {
            response = result.data;
            console.log('[DEBUG] Unwrapped from result.data:', response);
        }
        
        console.log('[DEBUG] Processing response:', response);
        
        // Check for success
        if (response && response.status === 'ok' && response.chains) {
            console.log('[DEBUG] ✓ Success! Found chains:', Object.keys(response.chains));
            pdbData.chains = response.chains || {};
            const chainCount = Object.keys(pdbData.chains).length;
            
            if (chainCount === 0) {
                console.log('[DEBUG] No chains in response');
                showErrorMessage(
                    '❌ No Chains Found',
                    'No valid protein chains were found in the PDB file.\n\n💡 Hint: The file may not contain ATOM records with standard protein residues.\nPlease ensure you uploaded a valid protein structure PDB file.'
                );
                pdbData.chains = {};
            } else {
                console.log('[DEBUG] Displaying chain selector with', chainCount, 'chains');
                displayChainSelector();
            }
            return;  // Exit after success
        }
        
        // If we got here, it's an error
        console.log('[DEBUG] Error response detected');
        const errorMsg = response?.message || 'Unknown error. The file may not be a valid PDB format.';
        const hint = response?.hint || 'Make sure the file is in PDB format and contains protein structure data.';
        console.log('[DEBUG] Error message:', errorMsg);
        showErrorMessage('❌ Parsing Error', errorMsg + '\n\n💡 ' + hint);
        pdbData.chains = {};
        
    } catch (err) {
        console.log('[DEBUG] Exception caught:', err);
        const errorDetail = err?.message || err?.toString?.() || 'Unknown error occurred';
        showErrorMessage(
            '❌ Processing Error', 
            'Failed to process the PDB file: ' + errorDetail + '\n\n💡 Please try uploading a different file or check the file format.'
        );
        pdbData.chains = {};
    }
}

function showErrorMessage(title, message) {
    // Create a styled error popup instead of basic alert
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #fff;
        border: 3px solid #ef4444;
        border-radius: 12px;
        padding: 20px;
        max-width: 600px;
        z-index: 1000;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        font-family: system-ui, -apple-system, sans-serif;
        max-height: 80vh;
        overflow-y: auto;
    `;
    
    errorDiv.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 1.2em; font-weight: 600; color: #991b1b;">${title}</div>
        <div style="color: #4b5563; white-space: pre-wrap; font-size: 0.95em; line-height: 1.6; margin-bottom: 15px;">${message}</div>
        <div style="font-size: 0.85em; color: #6b7280; background: #f9fafb; padding: 10px; border-radius: 6px; margin-bottom: 15px; border-left: 3px solid #3b82f6;">
            <strong>💡 Troubleshooting Tips:</strong><br/>
            • Check browser console (F12 → Console) for detailed debug logs<br/>
            • Ensure the PDB file is from RCSB PDB or similar database<br/>
            • Try a different, known-good PDB file (e.g., 1MBN, 1HHB)
        </div>
        <button onclick="this.parentElement.remove()" style="
            padding: 8px 16px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            width: 100%;
        ">OK</button>
    `;
    
    document.body.appendChild(errorDiv);
}

function displayChainSelector() {
    const chains = pdbData.chains;
    const chainIds = Object.keys(chains);
    
    if (chainIds.length === 0) {
        alert('No valid protein chains found');
        return;
    }
    
    const container = document.getElementById('chainOptionsContainer');
    container.innerHTML = '';
    
    chainIds.forEach((chainId, idx) => {
        const chain = chains[chainId];
        const isFirst = idx === 0;
        const optionDiv = document.createElement('div');
        optionDiv.className = 'chain-option';
        optionDiv.innerHTML = `
            <input type="radio" name="pdb_chain" value="${chainId}" ${isFirst ? 'checked' : ''} onchange="updateChainPreview('${chainId}')">
            <div class="chain-info">
                <div class="chain-info-item">
                    <span class="chain-info-label">Chain ID</span>
                    <span class="chain-info-value">${chainId}</span>
                </div>
                <div class="chain-info-item">
                    <span class="chain-info-label">Length</span>
                    <span class="chain-info-value">${chain.length} aa</span>
                </div>
            </div>
        `;
        container.appendChild(optionDiv);
    });
    
    // Show selector and update preview
    document.getElementById('pdbChainSelector').classList.add('show');
    pdbData.selectedChain = chainIds[0];
    updateChainPreview(chainIds[0]);
}

function updateChainPreview(chainId) {
    pdbData.selectedChain = chainId;
    const chain = pdbData.chains[chainId];
    
    // Remove existing preview
    const oldPreview = document.querySelector('.pdb-sequence-preview');
    if (oldPreview) oldPreview.remove();
    
    // Add new preview
    const container = document.getElementById('chainOptionsContainer');
    const preview = document.createElement('div');
    preview.className = 'pdb-sequence-preview';
    preview.innerHTML = `<strong>Sequence:</strong> ${chain.sequence}`;
    container.appendChild(preview);
}

function confirmChainSelection() {
    const selectedChain = pdbData.selectedChain;
    if (!selectedChain) {
        alert('Please select a chain');
        return;
    }
    
    const chainData = pdbData.chains[selectedChain];
    if (!chainData) {
        alert('Invalid chain selection');
        return;
    }
    
    // Check if monomer or polymer
    if (Object.keys(pdbData.chains).length === 1) {
        // Monomer: auto-populate
        populateProteinFromPdb(selectedChain, chainData.sequence);
    } else {
        // Polymer: populate with selected chain
        populateProteinFromPdb(selectedChain, chainData.sequence);
    }
    
    // Reset PDB upload
    resetPdbUpload();
}

function populateProteinFromPdb(chainId, sequence) {
    const firstProteinBlock = document.querySelector('.first-protein');
    if (firstProteinBlock) {
        const idsInput = firstProteinBlock.querySelector('.p-ids');
        const seqInput = firstProteinBlock.querySelector('.p-seq');
        
        idsInput.value = chainId;
        seqInput.value = sequence;
        
        // Trigger input events to apply validation
        idsInput.dispatchEvent(new Event('input', { bubbles: true }));
        seqInput.dispatchEvent(new Event('input', { bubbles: true }));
        
        // Scroll to protein block
        setTimeout(() => {
            firstProteinBlock.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }
}

function resetPdbUpload() {
    pdbData = {
        content: '',
        chains: {},
        selectedChain: null
    };
    
    document.getElementById('pdbChainSelector').classList.remove('show');
    document.getElementById('chainOptionsContainer').innerHTML = '';
    document.getElementById('pdbFileInput').value = '';
}

// Add drag-and-drop support
const uploadSection = document.getElementById('pdbUploadSection');
uploadSection.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadSection.classList.add('dragover');
});
uploadSection.addEventListener('dragleave', () => {
    uploadSection.classList.remove('dragover');
});
uploadSection.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadSection.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        document.getElementById('pdbFileInput').files = files;
        handlePdbFileUpload({target: {files: files}});
    }
});
</script>


"""

display(HTML(html))