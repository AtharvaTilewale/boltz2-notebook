
# @title Generate Parameters (YAML file & Run Config)
from IPython.display import HTML, display
from google.colab import output
import yaml
import os
import re
import base64
import uuid
from pathlib import Path

BASE_DIR = Path("/content/boltz_data")
UPLOAD_DIR = BASE_DIR / "uploads"
TEMPLATE_DIR = UPLOAD_DIR / "templates"
MSA_DIR = UPLOAD_DIR / "msas"

BASE_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
MSA_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(BASE_DIR)

class IdList(list):
    pass

class QuotedString(str):
    pass

class MyDumper(yaml.SafeDumper):
    pass

def represent_id_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def quoted_str_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")

def str_presenter(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

MyDumper.add_representer(IdList, represent_id_list)
MyDumper.add_representer(QuotedString, quoted_str_presenter)
MyDumper.add_representer(str, str_presenter)

def _clean_ids(values):
    if isinstance(values, str):
        values = values.split(',')
    cleaned = [str(v).strip().upper().replace(' ', '') for v in values if str(v).strip()]
    return IdList(cleaned)

def _clean_token_list(values):
    if isinstance(values, str):
        values = values.split(',')
    return [str(v).strip() for v in values if str(v).strip()]

def _clean_sequence(seq):
    return re.sub(r'\s+', '', str(seq or '')).upper()

def _save_uploaded_file(file_kind, filename, content_b64):
    try:
        filename = os.path.basename(filename)
        ext = Path(filename).suffix.lower()
        allowed = {
            "template": {".cif", ".pdb"},
            "msa": {".a3m", ".csv"},
        }
        if file_kind not in allowed:
            return {"status": "error", "message": f"Unsupported file kind: {file_kind}"}
        if ext not in allowed[file_kind]:
            return {"status": "error", "message": f"Invalid extension {ext} for {file_kind} upload."}

        dest_dir = TEMPLATE_DIR if file_kind == "template" else MSA_DIR
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        dest_path = dest_dir / safe_name
        with open(dest_path, "wb") as fh:
            fh.write(base64.b64decode(content_b64))
        return {"status": "ok", "path": str(dest_path)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _build_sequences(raw_sequences):
    sequences_fixed = []
    for entry in raw_sequences:
        entity_type = entry.get("type")
        item = entry.get("data", {})
        ids = _clean_ids(item.get("id", []))
        if not ids:
            raise ValueError(f"{entity_type} entry is missing IDs.")

        if entity_type in {"protein", "dna", "rna"}:
            sequence = _clean_sequence(item.get("sequence", ""))
            if not sequence:
                raise ValueError(f"{entity_type} entry {ids} is missing sequence.")
            polymer = {"id": ids, "sequence": sequence}
            msa = item.get("msa")
            if entity_type == "protein" and msa not in (None, ""):
                polymer["msa"] = msa
            modifications = []
            for mod in item.get("modifications", []):
                position = mod.get("position")
                ccd = str(mod.get("ccd", "")).strip().upper()
                if position and ccd:
                    modifications.append({"position": int(position), "ccd": ccd})
            if modifications:
                polymer["modifications"] = modifications
            if item.get("cyclic"):
                polymer["cyclic"] = True
            sequences_fixed.append({entity_type: polymer})

        elif entity_type == "ligand":
            ligand = {"id": ids}
            ccd = str(item.get("ccd", "")).strip().upper()
            smiles = str(item.get("smiles", "")).strip()
            if bool(ccd) == bool(smiles):
                raise ValueError(f"Ligand entry {ids} must have exactly one of CCD or SMILES.")
            if ccd:
                ligand["ccd"] = ccd
            if smiles:
                ligand["smiles"] = QuotedString(smiles)
            sequences_fixed.append({"ligand": ligand})
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")
    return sequences_fixed

def _save_params(data):
    try:
        if not isinstance(data, dict) or "sequences" not in data:
            return {"status": "error", "message": 'Invalid data structure: "sequences" key missing.'}

        final_yaml_data = {"version": 1}
        final_yaml_data["sequences"] = _build_sequences(data.get("sequences", []))

        constraints = []
        for bond in data.get("constraints", {}).get("bonds", []):
            atom1 = [str(bond.get("chain1", "")).strip().upper(), int(bond.get("res1", 1)), str(bond.get("atom1", "")).strip()]
            atom2 = [str(bond.get("chain2", "")).strip().upper(), int(bond.get("res2", 1)), str(bond.get("atom2", "")).strip()]
            if atom1[0] and atom1[2] and atom2[0] and atom2[2]:
                constraints.append({"bond": {"atom1": atom1, "atom2": atom2}})

        for pocket in data.get("constraints", {}).get("pockets", []):
            binder = str(pocket.get("binder", "")).strip().upper()
            max_distance = pocket.get("max_distance")
            raw_contacts = pocket.get("contacts", [])
            contacts = []
            for token in raw_contacts:
                chain = str(token.get("chain", "")).strip().upper()
                ref = str(token.get("ref", "")).strip()
                if chain and ref:
                    try:
                        ref_val = int(ref)
                    except ValueError:
                        ref_val = ref
                    contacts.append([chain, ref_val])
            if binder and contacts:
                pocket_dict = {"binder": binder, "contacts": contacts}
                if max_distance not in (None, "", 0):
                    pocket_dict["max_distance"] = float(max_distance)
                if pocket.get("force"):
                    pocket_dict["force"] = True
                constraints.append({"pocket": pocket_dict})

        for contact in data.get("constraints", {}).get("contacts", []):
            ch1 = str(contact.get("chain1", "")).strip().upper()
            ref1 = str(contact.get("ref1", "")).strip()
            ch2 = str(contact.get("chain2", "")).strip().upper()
            ref2 = str(contact.get("ref2", "")).strip()
            if ch1 and ref1 and ch2 and ref2:
                try:
                    ref1_val = int(ref1)
                except ValueError:
                    ref1_val = ref1
                try:
                    ref2_val = int(ref2)
                except ValueError:
                    ref2_val = ref2
                contact_dict = {
                    "token1": [ch1, ref1_val],
                    "token2": [ch2, ref2_val],
                }
                if contact.get("max_distance") not in (None, "", 0):
                    contact_dict["max_distance"] = float(contact["max_distance"])
                if contact.get("force"):
                    contact_dict["force"] = True
                constraints.append({"contact": contact_dict})

        if constraints:
            final_yaml_data["constraints"] = constraints

        templates = []
        for template in data.get("templates", []):
            path = template.get("path", "").strip()
            if not path:
                continue
            tmpl = {}
            ext = Path(path).suffix.lower()
            if ext == ".cif":
                tmpl["cif"] = path
            elif ext == ".pdb":
                tmpl["pdb"] = path
            else:
                continue
            chain_ids = _clean_token_list(template.get("chain_id", []))
            template_ids = _clean_token_list(template.get("template_id", []))
            if chain_ids:
                tmpl["chain_id"] = chain_ids if len(chain_ids) > 1 else chain_ids[0]
            if template_ids:
                tmpl["template_id"] = template_ids if len(template_ids) > 1 else template_ids[0]
            if template.get("force"):
                tmpl["force"] = True
                if template.get("threshold") not in (None, ""):
                    tmpl["threshold"] = float(template["threshold"])
            templates.append(tmpl)
        if templates:
            final_yaml_data["templates"] = templates

        props = []
        affinity = data.get("properties", {}).get("affinity_binder")
        if affinity:
            props.append({"affinity": {"binder": str(affinity).strip().upper()}})
        if props:
            final_yaml_data["properties"] = props

        filename = "params.yaml"
        with open(filename, "w") as f:
            yaml.dump(final_yaml_data, f, Dumper=MyDumper, sort_keys=False, default_flow_style=False, indent=2)
        return {"status": "ok", "filename": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _save_run_params(data):
    try:
        filename = data.get("filename", "run_params.txt")
        content = data.get("content", "")
        with open(filename, "w") as f:
            f.write(content)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

output.register_callback("save_params", _save_params)
output.register_callback("save_run_params", _save_run_params)
output.register_callback("save_uploaded_file", _save_uploaded_file)

html = r"""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
:root {
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --primary-color: #3b82f6; --primary-hover: #2563eb;
  --danger-color: #ef4444; --danger-hover: #dc2626;
  --secondary-color: #6b7280; --secondary-hover: #4b5563;
  --success-color: #22c55e; --success-hover: #16a34a;
  --accent-color: #a855f7; --info-color: #0ea5e9;
  --bg-light: #f9fafb; --bg-soft: #f3f4f6;
  --border-color: #d1d5db; --text-dark: #1f2937; --text-light: #4b5563;
  --radius: 8px; --shadow: 0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -2px rgba(0,0,0,0.10);
}
@keyframes fadeIn { from { opacity:0; transform: translateY(-8px);} to { opacity:1; transform: translateY(0);} }
.container { font-family: var(--font-family); color: var(--text-dark); background:#fff; padding:24px; }
.block {
  border:1px solid var(--border-color); padding:20px; margin:16px 0; border-radius:var(--radius);
  background:#fff; box-shadow:var(--shadow); animation:fadeIn .3s ease-out; border-top:4px solid var(--primary-color);
}
.block[data-type="ligand"] { border-top-color: var(--accent-color); }
.block[data-type="dna"], .block[data-type="rna"] { border-top-color: #10b981; }
.block-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; gap:10px; }
.title { font-weight:600; font-size:1.05em; color:var(--text-dark); display:flex; align-items:center; gap:8px; }
.subtitle { font-size:.88em; color:var(--text-light); margin-top:4px; }
.row { display:flex; gap:25px; align-items:center; margin-bottom:16px; }
.row label { width:170px; color:var(--text-light); font-size:.92em; flex-shrink:0; display:flex; align-items:center; justify-content:space-between; gap:8px; }
input[type="text"], input[type="number"], textarea, select {
  flex:1; padding:10px; border:1px solid var(--border-color); border-radius:6px;
  font-size:14px; color:var(--text-dark); background:var(--bg-light);
}
textarea { min-height: 88px; resize: vertical; }
input[type="text"]:focus, input[type="number"]:focus, textarea:focus, select:focus {
  outline:none; border-color:var(--primary-color); box-shadow: 0 0 0 2px rgba(59,130,246,.25);
}
input[type="checkbox"] { width:16px; height:16px; cursor:pointer; }
.btn {
  display:inline-flex; align-items:center; gap:6px; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;
  font-size:14px; font-weight:500; transition: background-color .2s, transform .1s;
}
.btn:active { transform: scale(.98); }
.btn.primary { background: var(--primary-color); color:#fff; }
.btn.primary:hover { background: var(--primary-hover); }
.btn.secondary { background: var(--secondary-color); color:#fff; }
.btn.secondary:hover { background: var(--secondary-hover); }
.btn.success { background: var(--success-color); color:#fff; }
.btn.success:hover { background: var(--success-hover); }
.btn.accent { background: var(--accent-color); color:#fff; }
.btn.accent:hover { filter: brightness(.95); }
.btn.small { padding: 6px 10px; font-size: 13px; }
.remove-btn {
  background:transparent; color:var(--secondary-color); border:none; width:32px; height:32px; border-radius:50%;
  cursor:pointer; display:inline-flex; align-items:center; justify-content:center; font-size:1em;
}
.remove-btn:hover { background:#fee2e2; color:var(--danger-color); }
.controls { margin-top:24px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.status-message { display:flex; align-items:center; gap:8px; padding:8px 12px; border-radius:6px; font-size:.9em; animation:fadeIn .2s; }
.status-message.success { background:#dcfce7; color:#166534; }
.status-message.error { background:#fee2e2; color:#991b1b; }
.status-message.warning { background:#fef3c7; color:#92400e; }
.status-message.info { background:#e0f2fe; color:#075985; }
.info-box, .warning-box {
  border-radius: 8px; padding: 12px 14px; margin: 10px 0 18px 0; font-size: .92em;
  border:1px solid var(--border-color); background: var(--bg-light);
}
.warning-box { background:#fff7ed; border-color:#fdba74; color:#9a3412; }
.info-box { background:#eff6ff; border-color:#93c5fd; color:#1d4ed8; }
.grid-2 { display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin-top:8px; }
.section-header {
  display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px;
}
.mini-card {
  border:1px dashed var(--border-color); border-radius:8px; background:var(--bg-light); padding:12px; margin-top:10px;
}
.file-chip {
  display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px;
  background:#eef2ff; color:#3730a3; font-size:.88em; margin-top:8px; word-break:break-all;
}
.template-section summary, details summary { font-weight:600; cursor:pointer; }
.helper { color: var(--text-light); font-size: .84em; margin-top: 6px; }
.badge {
  display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:4px 10px; font-size:12px;
  background:#eff6ff; color:#1d4ed8; font-weight:600;
}
.inline-toggle { display:flex; align-items:center; gap:10px; }
</style>

<div class="container">
  <div id="main_params_container">
    <div class="info-box">
      <div class="title"><i class="fa-solid fa-wand-magic-sparkles"></i>Boltz2 V2 Advanced Input Builder</div>
      <div class="subtitle">This builder now supports proteins, DNA, RNA, custom MSAs, modified residues, cyclic polymers, templates, covalent constraints, and pocket/contact conditioning.</div>
    </div>

    <div class="block" style="border-top-color:#0ea5e9;">
      <div class="section-header">
        <div>
          <div class="title"><i class="fa-solid fa-layer-group"></i>Chain Builder</div>
          <div class="subtitle">Add protein, DNA, RNA, and ligand entities that will be written into the Boltz YAML.</div>
        </div>
        <span class="badge"><i class="fa-solid fa-file-code"></i>YAML-first workflow</span>
      </div>
      <div id="sequences_container"></div>
      <div id="affinity_prediction_container"></div>
      <div class="controls">
        <button class="btn primary" onclick="addPolymer('protein', true)"><i class="fa-solid fa-dna"></i> Add Primary Protein</button>
        <button class="btn primary" onclick="addPolymer('protein', false)"><i class="fa-solid fa-plus"></i> Add Protein</button>
        <button class="btn primary" style="background:#10b981;" onclick="addPolymer('dna', false)"><i class="fa-solid fa-dna"></i> Add DNA</button>
        <button class="btn primary" style="background:#059669;" onclick="addPolymer('rna', false)"><i class="fa-solid fa-wave-square"></i> Add RNA</button>
        <button class="btn accent" onclick="addLigand()"><i class="fa-solid fa-puzzle-piece"></i> Add Ligand</button>
      </div>
    </div>

    <div class="block" style="border-top-color:#8b5cf6;">
      <div class="section-header">
        <div>
          <div class="title"><i class="fa-solid fa-sliders"></i>Advanced Modeling</div>
          <div class="subtitle">Guided builders for templates, covalent bonds, pocket/contact constraints, MSA-aware warnings, and modified residues.</div>
        </div>
        <span class="badge"><i class="fa-solid fa-screwdriver-wrench"></i>New in V2</span>
      </div>

      <details class="template-section" open>
        <summary><i class="fa-solid fa-file-arrow-up"></i> Structural Templates</summary>
        <div class="helper">Upload one or more template files (.cif or .pdb), then optionally define explicit chain mapping and force/threshold settings.</div>
        <div id="templates_container"></div>
        <div class="controls">
          <button class="btn secondary small" onclick="addTemplateRow()"><i class="fa-solid fa-plus"></i> Add Template</button>
        </div>
      </details>

      <details style="margin-top:14px;" open>
        <summary><i class="fa-solid fa-link"></i> Covalent Ligand Bond Builder</summary>
        <div class="helper">Define covalent bonds between canonical residues and CCD ligands using chain ID, residue index, and atom name.</div>
        <div id="bonds_container"></div>
        <div class="controls">
          <button class="btn secondary small" onclick="addBondRow()"><i class="fa-solid fa-plus"></i> Add Bond</button>
        </div>
      </details>

      <details style="margin-top:14px;" open>
        <summary><i class="fa-solid fa-bullseye"></i> Pocket / Contact Conditioning</summary>
        <div class="helper">Bias the model toward a binding site or residue/atom contact using optional distance-based constraints.</div>
        <div id="pockets_container"></div>
        <div class="controls">
          <button class="btn secondary small" onclick="addPocketRow()"><i class="fa-solid fa-plus"></i> Add Pocket Constraint</button>
        </div>
        <div id="contacts_container" style="margin-top:16px;"></div>
        <div class="controls">
          <button class="btn secondary small" onclick="addContactRow()"><i class="fa-solid fa-plus"></i> Add Contact Constraint</button>
        </div>
      </details>
    </div>

    <div class="controls">
      <button class="btn secondary" onclick="clearAll()"><i class="fa-solid fa-broom"></i> Clear Added</button>
      <button class="btn secondary" id="saveBtn" onclick="saveYaml()"><i id="saveIcon" class="fa-solid fa-save"></i> <span id="saveBtnText">Save YAML</span></button>
      <button class="btn success" id="nextBtn" onclick="showRunParams()" style="display:none;"><span id="nextBtnText">Next</span> <i class="fa-solid fa-arrow-right"></i></button>
      <div id="status"></div>
    </div>
  </div>

  <div id="run_params_container" style="display:none;">
    <div class="block">
      <div class="title" style="margin-bottom:20px;"><i class="fa-solid fa-gears"></i>Run Parameters</div>
      <div class="row">
        <label for="rp_job_name">Job Name</label>
        <input type="text" id="rp_job_name" value="" placeholder="Insulin_Peptide" required>
      </div>
      <div class="row">
        <label for="rp_use_potentials">Use Potentials</label>
        <input type="checkbox" id="rp_use_potentials" checked>
      </div>
      <div class="row">
        <label for="rp_override">Override</label>
        <input type="checkbox" id="rp_override" checked>
      </div>

      <details>
        <summary>Advanced Options</summary>
        <div style="padding-top:20px;">
          <div class="row">
            <label for="rp_recycling_steps">Recycling Steps</label>
            <input type="number" id="rp_recycling_steps" value="3" step="1" min="1">
          </div>
          <div class="row">
            <label for="rp_sampling_steps">Sampling Steps</label>
            <input type="range" id="rp_sampling_steps" min="50" max="400" step="50" value="200" oninput="this.nextElementSibling.value = this.value">
            <output>200</output>
          </div>
          <div class="row">
            <label for="rp_diffusion_samples">Diffusion Samples</label>
            <input type="number" id="rp_diffusion_samples" value="1" step="1" min="1">
          </div>
          <div class="row">
            <label for="rp_step_scale">Step Scale</label>
            <input type="number" id="rp_step_scale" value="1.638" step="0.1" min="0.1">
          </div>
          <div class="row">
            <label for="rp_max_msa_seqs">Max MSA Sequences</label>
            <select id="rp_max_msa_seqs">
              <option>32</option><option>64</option><option>128</option><option>256</option><option>512</option>
              <option>1024</option><option>2048</option><option>4096</option><option selected>8192</option>
            </select>
          </div>
          <div class="row">
            <label for="rp_subsample_msa">Subsample MSA</label>
            <input type="checkbox" id="rp_subsample_msa" onchange="toggleNumSubsampled(this)">
          </div>
          <div class="row" id="num_subsampled_msa_row" style="display:none;">
            <label for="rp_num_subsampled_msa">Number of Subsampled MSA</label>
            <select id="rp_num_subsampled_msa">
              <option>4</option><option>8</option><option>16</option><option>32</option><option>64</option>
              <option>128</option><option>256</option><option>512</option><option selected>1024</option>
            </select>
          </div>
          <div class="row">
            <label for="rp_msa_pairing_strategy">MSA Pairing Strategy</label>
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

  <template id="polymer_template">
    <div class="block seq-block" data-type="protein">
      <div class="block-header">
        <div>
          <div class="title"><i class="fa-solid fa-dna"></i><span class="entity-title">Protein</span></div>
          <div class="subtitle entity-subtitle">Primary macromolecular chain.</div>
        </div>
        <button class="remove-btn" onclick="removeBlock(this)" title="Remove block"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="row"><label>Type</label>
        <select class="entity-type" onchange="onEntityTypeChange(this)">
          <option value="protein">Protein</option>
          <option value="dna">DNA</option>
          <option value="rna">RNA</option>
        </select>
      </div>
      <div class="row"><label>IDs (comma)</label><input class="entity-ids" type="text" placeholder="A,B" oninput="formatIDs(this); refreshChainAwareUI();"></div>
      <div class="row"><label>Sequence</label><textarea class="entity-seq" rows="5"></textarea></div>
      <div class="row protein-only"><label>MSA Mode</label>
        <select class="msa-mode" onchange="onMsaModeChange(this)">
          <option value="server" selected>Auto-generate with MSA server</option>
          <option value="custom">Upload custom/precomputed MSA</option>
          <option value="empty">Single-sequence mode (msa: empty)</option>
        </select>
      </div>
      <div class="row protein-only msa-upload-row" style="display:none;">
        <label>MSA Upload</label>
        <div style="flex:1;">
          <input class="msa-upload-input" type="file" accept=".a3m,.csv" onchange="handleMsaUpload(this)">
          <div class="helper">Use .a3m for a single protein chain, or CSV with columns <code>sequence</code> and <code>key</code> for paired multi-chain workflows.</div>
          <div class="msa-upload-status"></div>
        </div>
      </div>
      <div class="warning-box msa-empty-warning" style="display:none;">
        <i class="fa-solid fa-triangle-exclamation"></i> Single-sequence mode reduces prediction accuracy and disables evolutionary context. Use only when no meaningful MSA is available.
      </div>
      <div class="row"><label>Cyclic Polymer</label><input class="entity-cyclic" type="checkbox"></div>

      <details style="margin-top:8px;">
        <summary>Modified Residues</summary>
        <div class="helper">Supported for protein, DNA, and RNA polymers. Positions are 1-based and CCD codes should match the modified residue component.</div>
        <div class="mods-container"></div>
        <div class="controls">
          <button class="btn secondary small" type="button" onclick="addModificationRow(this.closest('.seq-block'))"><i class="fa-solid fa-plus"></i> Add Modification</button>
        </div>
      </details>
    </div>
  </template>

  <template id="ligand_template">
    <div class="block seq-block" data-type="ligand">
      <div class="block-header">
        <div>
          <div class="title"><i class="fa-solid fa-puzzle-piece"></i>Ligand</div>
          <div class="subtitle">Define ligand using CCD code or SMILES.</div>
        </div>
        <button class="remove-btn" onclick="removeBlock(this)" title="Remove block"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="row"><label>IDs (comma)</label><input class="l-ids" type="text" placeholder="L" oninput="formatIDs(this); refreshChainAwareUI();"></div>
      <div class="row"><label>Type</label>
        <select class="l-type" onchange="onLigandTypeChange(this)">
          <option value="ccd">CCD</option>
          <option value="smiles">SMILES</option>
        </select>
      </div>
      <div class="row lig-value-row"><label>Value</label><input class="l-value" type="text" placeholder="e.g., SAH"></div>
    </div>
  </template>

  <template id="template_row_template">
    <div class="mini-card template-row">
      <div class="section-header">
        <div class="title"><i class="fa-solid fa-file-code"></i>Template</div>
        <button class="remove-btn" onclick="this.closest('.template-row').remove()"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="row">
        <label>Template File</label>
        <div style="flex:1;">
          <input type="file" class="template-file" accept=".cif,.pdb" onchange="handleTemplateUpload(this)">
          <div class="template-upload-status"></div>
        </div>
      </div>
      <div class="grid-2">
        <div>
          <div class="helper">Explicit YAML chain IDs</div>
          <input type="text" class="template-chain-id" placeholder="A,B">
        </div>
        <div>
          <div class="helper">Template chain IDs</div>
          <input type="text" class="template-template-id" placeholder="A1,B1">
        </div>
      </div>
      <div class="grid-2">
        <div class="inline-toggle">
          <input type="checkbox" class="template-force" onchange="this.closest('.template-row').querySelector('.template-threshold').disabled = !this.checked;">
          <span>Force template</span>
        </div>
        <div>
          <div class="helper">Threshold (Å)</div>
          <input type="number" class="template-threshold" value="2.0" step="0.5" min="0.1" disabled>
        </div>
      </div>
    </div>
  </template>

  <template id="bond_row_template">
    <div class="mini-card bond-row">
      <div class="section-header">
        <div class="title"><i class="fa-solid fa-link"></i>Bond Constraint</div>
        <button class="remove-btn" onclick="this.closest('.bond-row').remove()"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="grid-2">
        <div>
          <div class="helper">Atom 1: chain, residue, atom</div>
          <div class="grid-2">
            <input type="text" class="bond-chain1" placeholder="A">
            <input type="number" class="bond-res1" placeholder="145" value="1" min="1">
          </div>
          <input type="text" class="bond-atom1" placeholder="SG" style="margin-top:8px;">
        </div>
        <div>
          <div class="helper">Atom 2: chain, residue, atom</div>
          <div class="grid-2">
            <input type="text" class="bond-chain2" placeholder="L">
            <input type="number" class="bond-res2" placeholder="1" value="1" min="1">
          </div>
          <input type="text" class="bond-atom2" placeholder="C1" style="margin-top:8px;">
        </div>
      </div>
    </div>
  </template>

  <template id="pocket_row_template">
    <div class="mini-card pocket-row">
      <div class="section-header">
        <div class="title"><i class="fa-solid fa-bullseye"></i>Pocket Constraint</div>
        <button class="remove-btn" onclick="this.closest('.pocket-row').remove()"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="row"><label>Binder Chain</label><input type="text" class="pocket-binder" placeholder="L"></div>
      <div class="row"><label>Contacts</label>
        <textarea class="pocket-contacts" rows="3" placeholder="A:145, A:147, B:TYR"></textarea>
      </div>
      <div class="grid-2">
        <div><div class="helper">Max distance (Å)</div><input type="number" class="pocket-max-distance" value="6" min="4" max="20" step="0.5"></div>
        <div class="inline-toggle" style="padding-top:24px;"><input type="checkbox" class="pocket-force"><span>Force pocket</span></div>
      </div>
    </div>
  </template>

  <template id="contact_row_template">
    <div class="mini-card contact-row">
      <div class="section-header">
        <div class="title"><i class="fa-solid fa-arrows-left-right-to-line"></i>Contact Constraint</div>
        <button class="remove-btn" onclick="this.closest('.contact-row').remove()"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="grid-2">
        <div>
          <div class="helper">Token 1</div>
          <div class="grid-2">
            <input type="text" class="contact-chain1" placeholder="A">
            <input type="text" class="contact-ref1" placeholder="145 or NZ">
          </div>
        </div>
        <div>
          <div class="helper">Token 2</div>
          <div class="grid-2">
            <input type="text" class="contact-chain2" placeholder="L">
            <input type="text" class="contact-ref2" placeholder="1 or C1">
          </div>
        </div>
      </div>
      <div class="grid-2">
        <div><div class="helper">Max distance (Å)</div><input type="number" class="contact-max-distance" value="6" min="4" max="20" step="0.5"></div>
        <div class="inline-toggle" style="padding-top:24px;"><input type="checkbox" class="contact-force"><span>Force contact</span></div>
      </div>
    </div>
  </template>

  <template id="mod_row_template">
    <div class="mini-card mod-row">
      <div class="section-header">
        <div class="title"><i class="fa-solid fa-pen-to-square"></i>Modified Residue</div>
        <button class="remove-btn" onclick="this.closest('.mod-row').remove()"><i class="fa-solid fa-trash-can"></i></button>
      </div>
      <div class="grid-2">
        <div><div class="helper">Position (1-based)</div><input type="number" class="mod-position" placeholder="15" min="1"></div>
        <div><div class="helper">CCD code</div><input type="text" class="mod-ccd" placeholder="SEP"></div>
      </div>
    </div>
  </template>
</div>

<script>
const seqContainer = document.getElementById('sequences_container');
const templatesContainer = document.getElementById('templates_container');
const bondsContainer = document.getElementById('bonds_container');
const pocketsContainer = document.getElementById('pockets_container');
const contactsContainer = document.getElementById('contacts_container');

const validAminoAcids = new Set(['A','C','D','E','F','G','H','I','K','L','M','N','P','Q','R','S','T','V','W','Y']);
const validDna = new Set(['A','C','G','T','N']);
const validRna = new Set(['A','C','G','U','N']);

function formatIDs(inputElement) {
  const formattedValue = (inputElement.value || '').replace(/[\s,]+/g, '').split('').join(',');
  inputElement.value = formattedValue.toUpperCase();
}
function restrictPolymerSequence(inputElement, type) {
  const map = { protein: validAminoAcids, dna: validDna, rna: validRna };
  const allowed = map[type];
  if (!allowed) return;
  const val = inputElement.value.toUpperCase().replace(/\s+/g,'');
  const filtered = val.split('').filter(c => allowed.has(c)).join('');
  if (val !== filtered) inputElement.value = filtered;
}
function setStatus(message, type) {
  const statusEl = document.getElementById('status');
  const icon = { success: 'fa-check-circle', error: 'fa-circle-xmark', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' }[type] || 'fa-circle-info';
  statusEl.innerHTML = `<div class="status-message ${type}"><i class="fa-solid ${icon}"></i> ${message}</div>`;
  document.getElementById('nextBtn').style.display = (type === 'success') ? 'inline-flex' : 'none';
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
  document.getElementById('num_subsampled_msa_row').style.display = checkbox.checked ? 'flex' : 'none';
}
async function saveRunParams() {
  const getVal = id => document.getElementById(id).value;
  const getChecked = id => document.getElementById(id).checked;
  const jobName = getVal('rp_job_name').trim();
  const runStatusEl = document.getElementById('run_status');
  if (!jobName) {
    runStatusEl.innerHTML = `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> <strong>Error:</strong> Job Name is required.</div>`;
    return;
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
  try {
    const result = await google.colab.kernel.invokeFunction('save_run_params', [{ filename: 'run_params.txt', content: content.trim() }], {});
    if (result && result.status === 'ok') {
      runStatusEl.innerHTML = `<div class="status-message success"><i class="fa-solid fa-check-circle"></i> Parameters saved successfully. You can run BoltzEngine now.</div>`;
    } else {
      runStatusEl.innerHTML = `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> <strong>Error:</strong> ${result?.message || 'Unknown error.'}</div>`;
    }
  } catch (err) {
    runStatusEl.innerHTML = `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> <strong>Save failed:</strong> ${err.toString()}</div>`;
  }
}
function addPolymer(entityType='protein', first=false) {
  const node = document.getElementById('polymer_template').content.cloneNode(true);
  const block = node.querySelector('.seq-block');
  if (first) {
    block.classList.add('first-polymer');
  }
  seqContainer.appendChild(node);
  const created = seqContainer.lastElementChild;
  created.dataset.type = entityType;
  const typeSelect = created.querySelector('.entity-type');
  typeSelect.value = entityType;
  onEntityTypeChange(typeSelect);
  const seqArea = created.querySelector('.entity-seq');
  seqArea.addEventListener('input', () => restrictPolymerSequence(seqArea, created.dataset.type));
  refreshChainAwareUI();
}
function addLigand() {
  const node = document.getElementById('ligand_template').content.cloneNode(true);
  seqContainer.appendChild(node);
  ensureAffinityPanel();
  refreshChainAwareUI();
}
function removeBlock(btn) {
  btn.closest('.seq-block')?.remove();
  refreshChainAwareUI();
  if (document.querySelectorAll('.seq-block[data-type="ligand"]').length === 0) {
    document.getElementById('affinity_prediction_container').innerHTML = '';
  }
}
function onEntityTypeChange(selectEl) {
  const block = selectEl.closest('.seq-block');
  const type = selectEl.value;
  block.dataset.type = type;
  const titleMap = {
    protein: ['Protein', 'Primary macromolecular chain.'],
    dna: ['DNA', 'Single-stranded DNA input.'],
    rna: ['RNA', 'Single-stranded RNA input.']
  };
  block.querySelector('.entity-title').textContent = titleMap[type][0];
  block.querySelector('.entity-subtitle').textContent = titleMap[type][1];
  const icons = { protein: 'fa-dna', dna: 'fa-dna', rna: 'fa-wave-square' };
  block.querySelector('.title i').className = `fa-solid ${icons[type]}`;
  block.querySelectorAll('.protein-only').forEach(el => el.style.display = type === 'protein' ? 'flex' : 'none');
  block.querySelector('.entity-seq').placeholder = type === 'protein' ? 'Amino acid sequence' : (type === 'dna' ? 'DNA sequence (ACGTN)' : 'RNA sequence (ACGUN)');
  restrictPolymerSequence(block.querySelector('.entity-seq'), type);
}
function onLigandTypeChange(select) {
  const valueInput = select.closest('.seq-block').querySelector('.l-value');
  valueInput.placeholder = select.value === 'ccd' ? 'e.g., SAH' : 'e.g., CCO... (SMILES)';
  if (select.value === 'ccd') valueInput.style.textTransform = 'uppercase';
  else valueInput.style.textTransform = 'none';
}
function onMsaModeChange(selectEl) {
  const block = selectEl.closest('.seq-block');
  const mode = selectEl.value;
  block.querySelector('.msa-upload-row').style.display = mode === 'custom' ? 'flex' : 'none';
  block.querySelector('.msa-empty-warning').style.display = mode === 'empty' ? 'block' : 'none';
}
function ensureAffinityPanel() {
  if (document.getElementById('affinity-prediction-section')) return;
  document.getElementById('affinity_prediction_container').innerHTML = `
    <div id="affinity-prediction-section" class="block" style="border-top-color: var(--secondary-color); margin-bottom: 0;">
      <div class="row" style="align-items: center; margin-bottom: 12px;">
        <input type="checkbox" id="predict_affinity_toggle" onchange="toggleAffinityOptions(this)" style="width:16px;height:16px;">
        <label for="predict_affinity_toggle" style="width:auto; cursor:pointer; color:var(--text-dark); font-weight:500;">Predict Ligand Affinity</label>
      </div>
      <div id="ligand_chain_selector_container" style="display:none; margin-top:10px;" class="row">
        <label for="ligand_chain_id_select">Ligand Chain</label>
        <select id="ligand_chain_id_select"></select>
      </div>
    </div>`;
}
function toggleAffinityOptions(checkbox) {
  const selectorContainer = document.getElementById('ligand_chain_selector_container');
  if (!selectorContainer) return;
  selectorContainer.style.display = checkbox.checked ? 'flex' : 'none';
  updateLigandChainSelector();
}
function updateLigandChainSelector() {
  const selector = document.getElementById('ligand_chain_id_select');
  if (!selector) return;
  const currentVal = selector.value;
  selector.innerHTML = '';
  const ligandIDs = new Set();
  document.querySelectorAll('.seq-block[data-type="ligand"] .l-ids').forEach(input => {
    (input.value || '').split(',').map(s => s.trim()).filter(Boolean).forEach(id => ligandIDs.add(id.toUpperCase()));
  });
  if (ligandIDs.size === 0) {
    selector.innerHTML = `<option value="">No ligand IDs defined</option>`;
  } else {
    [...ligandIDs].forEach(id => {
      const option = document.createElement('option');
      option.value = id;
      option.textContent = id;
      selector.appendChild(option);
    });
    if (ligandIDs.has(currentVal)) selector.value = currentVal;
  }
}
function refreshChainAwareUI() {
  updateLigandChainSelector();
}
function clearAll() {
  seqContainer.innerHTML = '';
  templatesContainer.innerHTML = '';
  bondsContainer.innerHTML = '';
  pocketsContainer.innerHTML = '';
  contactsContainer.innerHTML = '';
  document.getElementById('affinity_prediction_container').innerHTML = '';
  document.getElementById('status').innerHTML = '';
  document.getElementById('nextBtn').style.display = 'none';
  addPolymer('protein', true);
}
function addTemplateRow() {
  templatesContainer.appendChild(document.getElementById('template_row_template').content.cloneNode(true));
}
function addBondRow() {
  bondsContainer.appendChild(document.getElementById('bond_row_template').content.cloneNode(true));
}
function addPocketRow() {
  pocketsContainer.appendChild(document.getElementById('pocket_row_template').content.cloneNode(true));
}
function addContactRow() {
  contactsContainer.appendChild(document.getElementById('contact_row_template').content.cloneNode(true));
}
function addModificationRow(block) {
  block.querySelector('.mods-container').appendChild(document.getElementById('mod_row_template').content.cloneNode(true));
}
function splitCSVLike(text) {
  return (text || '').split(',').map(x => x.trim()).filter(Boolean);
}
function parseContactTokens(text) {
  const items = splitCSVLike(text);
  const parsed = [];
  for (const item of items) {
    const [chain, ref] = item.split(':').map(x => (x || '').trim());
    if (chain && ref) parsed.push({ chain: chain.toUpperCase(), ref });
  }
  return parsed;
}
async function uploadFile(inputEl, fileKind, statusContainer) {
  const file = inputEl.files && inputEl.files[0];
  if (!file) return null;
  statusContainer.innerHTML = `<div class="status-message warning"><i class="fa-solid fa-spinner fa-spin"></i> Uploading ${file.name}...</div>`;
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => resolve(e.target.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  const contentB64 = String(dataUrl).split(',')[1];
  const result = await google.colab.kernel.invokeFunction('save_uploaded_file', [fileKind, file.name, contentB64], {});
  if (result && result.status === 'ok') {
    statusContainer.innerHTML = `<div class="file-chip"><i class="fa-solid fa-paperclip"></i>${file.name}</div>`;
    return result.path;
  }
  statusContainer.innerHTML = `<div class="status-message error"><i class="fa-solid fa-circle-xmark"></i> ${result?.message || 'Upload failed.'}</div>`;
  return null;
}
async function handleTemplateUpload(inputEl) {
  const row = inputEl.closest('.template-row');
  const statusContainer = row.querySelector('.template-upload-status');
  const path = await uploadFile(inputEl, 'template', statusContainer);
  if (path) row.dataset.path = path;
}
async function handleMsaUpload(inputEl) {
  const block = inputEl.closest('.seq-block');
  const statusContainer = block.querySelector('.msa-upload-status');
  const path = await uploadFile(inputEl, 'msa', statusContainer);
  if (path) block.dataset.msaPath = path;
}

async function saveYaml() {
  const saveBtn = document.getElementById('saveBtn');
  const saveIcon = document.getElementById('saveIcon');
  const saveBtnText = document.getElementById('saveBtnText');
  setStatus('Validating...', 'warning');

  const blocks = document.querySelectorAll('.seq-block');
  const sequences = [];
  const allIDs = new Set();

  for (const [idx, block] of Array.from(blocks).entries()) {
    const type = block.dataset.type;
    if (type === 'ligand') {
      const ids = splitCSVLike(block.querySelector('.l-ids').value.toUpperCase());
      const ltype = block.querySelector('.l-type').value;
      const value = block.querySelector('.l-value').value.trim();
      if (!ids.length || !value) {
        setStatus(`<strong>Error:</strong> Ligand block ${idx + 1} requires both IDs and a value.`, 'error');
        return;
      }
      for (const id of ids) {
        if (allIDs.has(id)) {
          setStatus(`<strong>Error:</strong> Duplicate ID <strong>${id}</strong> found.`, 'error');
          return;
        }
        allIDs.add(id);
      }
      const ligand = { id: ids };
      if (ltype === 'ccd') ligand.ccd = value.toUpperCase();
      else ligand.smiles = value;
      sequences.push({ type: 'ligand', data: ligand });
    } else {
      const ids = splitCSVLike(block.querySelector('.entity-ids').value.toUpperCase());
      const seq = block.querySelector('.entity-seq').value.trim().toUpperCase().replace(/\s+/g, '');
      if (!ids.length || !seq) {
        setStatus(`<strong>Error:</strong> ${type.toUpperCase()} block ${idx + 1} requires both IDs and a sequence.`, 'error');
        return;
      }
      for (const id of ids) {
        if (allIDs.has(id)) {
          setStatus(`<strong>Error:</strong> Duplicate ID <strong>${id}</strong> found.`, 'error');
          return;
        }
        allIDs.add(id);
      }
      const entity = { id: ids, sequence: seq, cyclic: block.querySelector('.entity-cyclic').checked };
      if (type === 'protein') {
        const msaMode = block.querySelector('.msa-mode').value;
        if (msaMode === 'custom') {
          const msaPath = block.dataset.msaPath;
          if (!msaPath) {
            setStatus(`<strong>Error:</strong> Protein block ${idx + 1} is set to custom MSA but no file was uploaded.`, 'error');
            return;
          }
          entity.msa = msaPath;
        } else if (msaMode === 'empty') {
          entity.msa = 'empty';
        }
      }
      const modifications = [];
      block.querySelectorAll('.mod-row').forEach(row => {
        const pos = row.querySelector('.mod-position').value;
        const ccd = row.querySelector('.mod-ccd').value.trim().toUpperCase();
        if (pos && ccd) modifications.push({ position: Number(pos), ccd });
      });
      if (modifications.length) entity.modifications = modifications;
      sequences.push({ type, data: entity });
    }
  }

  const templateRows = document.querySelectorAll('.template-row');
  const templates = [];
  for (const row of templateRows) {
    const path = row.dataset.path || '';
    const chain_id = splitCSVLike(row.querySelector('.template-chain-id').value.toUpperCase());
    const template_id = splitCSVLike(row.querySelector('.template-template-id').value);
    const force = row.querySelector('.template-force').checked;
    const threshold = row.querySelector('.template-threshold').value;
    if (path) {
      templates.push({
        path,
        chain_id,
        template_id,
        force,
        threshold: force ? threshold : ''
      });
    }
  }

  const bonds = [];
  document.querySelectorAll('.bond-row').forEach(row => {
    const item = {
      chain1: row.querySelector('.bond-chain1').value.trim().toUpperCase(),
      res1: row.querySelector('.bond-res1').value,
      atom1: row.querySelector('.bond-atom1').value.trim(),
      chain2: row.querySelector('.bond-chain2').value.trim().toUpperCase(),
      res2: row.querySelector('.bond-res2').value,
      atom2: row.querySelector('.bond-atom2').value.trim(),
    };
    if (item.chain1 && item.atom1 && item.chain2 && item.atom2) bonds.push(item);
  });

  const pockets = [];
  document.querySelectorAll('.pocket-row').forEach(row => {
    const binder = row.querySelector('.pocket-binder').value.trim().toUpperCase();
    const contacts = parseContactTokens(row.querySelector('.pocket-contacts').value);
    if (binder && contacts.length) {
      pockets.push({
        binder,
        contacts,
        max_distance: row.querySelector('.pocket-max-distance').value,
        force: row.querySelector('.pocket-force').checked
      });
    }
  });

  const contacts = [];
  document.querySelectorAll('.contact-row').forEach(row => {
    const item = {
      chain1: row.querySelector('.contact-chain1').value.trim().toUpperCase(),
      ref1: row.querySelector('.contact-ref1').value.trim(),
      chain2: row.querySelector('.contact-chain2').value.trim().toUpperCase(),
      ref2: row.querySelector('.contact-ref2').value.trim(),
      max_distance: row.querySelector('.contact-max-distance').value,
      force: row.querySelector('.contact-force').checked
    };
    if (item.chain1 && item.ref1 && item.chain2 && item.ref2) contacts.push(item);
  });

  const payload = {
    sequences,
    templates,
    constraints: { bonds, pockets, contacts },
    properties: {}
  };

  const predictAffinityCheckbox = document.getElementById('predict_affinity_toggle');
  if (predictAffinityCheckbox && predictAffinityCheckbox.checked) {
    const selectedLigandId = document.getElementById('ligand_chain_id_select').value;
    if (!selectedLigandId) {
      setStatus('<strong>Error:</strong> Affinity prediction is enabled, but no ligand chain is selected.', 'error');
      return;
    }
    payload.properties.affinity_binder = selectedLigandId;
  }

  saveBtn.disabled = true;
  saveBtnText.innerText = 'Saving...';
  saveIcon.className = 'fa-solid fa-spinner fa-spin';
  try {
    const result = await google.colab.kernel.invokeFunction('save_params', [payload], {});
    if (result && result.status === 'ok') {
      let msg = `Parameter file saved successfully.`;
      const emptyMsaCount = sequences.filter(x => x.type === 'protein' && x.data.msa === 'empty').length;
      if (emptyMsaCount > 0) msg += ` ${emptyMsaCount} protein chain(s) are using single-sequence mode.`;
      setStatus(msg, emptyMsaCount > 0 ? 'warning' : 'success');
      document.getElementById('nextBtn').style.display = 'inline-flex';
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

document.getElementById("rp_job_name").addEventListener("input", function() {
  this.value = this.value.replace(/\s+/g, "_");
});
addPolymer('protein', true);
addTemplateRow();
</script>
"""
display(HTML(html))
