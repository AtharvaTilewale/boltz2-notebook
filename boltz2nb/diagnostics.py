"""Turn a Boltz log into a likely cause and a concrete fix."""
from __future__ import annotations

import re

_RULES: list[tuple[str, str, str]] = [
    (r"CUDA out of memory|OutOfMemoryError|CUBLAS_STATUS_ALLOC_FAILED",
     "GPU ran out of memory.",
     "Reduce max_msa_seqs (e.g. 256), diffusion_samples (1) and max_parallel_samples (1); split very large complexes; use an A100/L4 runtime."),
    (r"Could not parse SMILES|Invalid SMILES|rdkit.*None|Explicit valence",
     "The ligand SMILES could not be parsed by RDKit.",
     "Check the SMILES string (aromaticity, ring closures, charges). PubChem's 'Isomeric SMILES' field is a safe source."),
    (r"CCD component .* not found|not in CCD",
     "A CCD code (ligand or modification) is unknown to Boltz.",
     "Use the 3-letter code exactly as in the PDB Chemical Component Dictionary, or provide a SMILES instead."),
    (r"msa|mmseqs|colabfold|api\.colabfold\.com|HTTPError|ConnectionError|Max retries|Read timed out",
     "MSA generation via the ColabFold server failed or timed out.",
     "Retry later, upload a precomputed .a3m MSA, or set the chain to single-sequence mode (msa: empty)."),
    (r"Chain ID .* used more than once|Duplicate",
     "Duplicate chain IDs in the input.",
     "Give every chain a unique single-letter ID."),
    (r"No such file or directory.*(templates?|\.cif|\.pdb)",
     "A template or MSA file path does not exist in the runtime.",
     "Re-upload the file in the parameter step; Colab files are lost when the runtime restarts."),
    (r"affinity.*(ligand|binder)|binder .* not found",
     "Affinity was requested for a chain that is not a small-molecule ligand.",
     "Affinity is only supported for ligand chains; disable it for protein-protein jobs."),
    (r"Killed|SIGKILL|MemoryError",
     "The process was killed - most likely host RAM exhaustion.",
     "Use a high-RAM runtime or reduce max_msa_seqs."),
    (r"ModuleNotFoundError|ImportError",
     "A Python dependency is missing or incompatible.",
     "Re-run the setup cell with FORCE_REINSTALL=True; on Python 3.13 the setup installs boltz-community."),
    (r"yaml\.|YAMLError|ScannerError|ParserError|ValidationError",
     "The input YAML is malformed or violates the Boltz schema.",
     "Regenerate params.yaml with the parameter builder; quote SMILES containing ':' or '#'."),
]


def diagnose_failure(log_text: str) -> dict[str, str]:
    text = log_text or ""
    for pattern, cause, fix in _RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {"likely_cause": cause, "suggested_fix": fix}
    tail = "\n".join(text.strip().splitlines()[-5:])
    return {"likely_cause": "Unrecognised error.", "suggested_fix": f"Inspect the log tail:\n{tail}"}
