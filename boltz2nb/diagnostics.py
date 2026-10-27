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
    (r"Template chain \S+ assigned for template.* is not one of the protein chains",
     "The template chain you named is not in the template file, as Boltz reads it.",
     "Leave the template chain empty to use every protein chain of the file. Boltz names the chains of a .pdb template A1, B1, ... while a .cif "
     "keeps A, B, ... so with a .pdb either use those names or upload the .cif."),
    # A template is read while the input is parsed; an unknown ligand inside it raises the CCD error below, so this rule must come first.
    (r"parsed_template = parse_(?:pdb|mmcif)\(|boltz[/\\]data[/\\]parse[/\\](?:pdb|mmcif)\.py",
     "A template file could not be read by Boltz.",
     "Boltz reads templates with its mmCIF reader. A .pdb template needs SEQRES records, which structures written by Boltz do not have: use the .cif "
     "instead (or the file from RCSB). A template that holds a ligand missing from the Chemical Component Dictionary (Boltz names its own ligands LIG1) "
     "fails as well: remove the ligand's HETATM records, or use a protein-only structure."),
    (r"CCD component .* not found|not in CCD",
     "A CCD code (ligand or modification) is unknown to Boltz.",
     "Use the 3-letter code exactly as in the PDB Chemical Component Dictionary, or provide a SMILES instead."),
    # not the bare word "msa": Boltz prints "Found explicit empty MSA ..." for every chain set to msa: empty, and that is no failure
    (r"requests\.exceptions|api\.colabfold\.com|MMseqs2 API|mmseqs|HTTPError|ConnectionError|Max retries|Read timed out",
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
    (r"matches none of the token layouts|LayoutMismatch",
     "The confidence arrays and the written structure use an unexpected token convention (engine version mismatch).",
     "Ranking metrics and affinity are still reported; send the run_context.json plus the model PDB so the layout can be supported."),
    (r"Killed|SIGKILL|MemoryError",
     "The process was killed - most likely host RAM exhaustion.",
     "Use a high-RAM runtime or reduce max_msa_seqs."),
    (r"ModuleNotFoundError|ImportError",
     "A Python dependency is missing or incompatible.",
     "Re-run the setup cell with FORCE_REINSTALL=True; on Python 3.13 the setup installs boltz-community."),
    (r"yaml\.(?:scanner|parser|constructor|reader)|YAMLError|ScannerError|ParserError|ValidationError",
     "The input YAML is malformed or violates the Boltz schema.",
     "Regenerate params.yaml with the parameter builder; quote SMILES containing ':' or '#'."),
]


# Boltz does not stop when it cannot process an input: it logs this line, skips the input and exits with code 0.
_SKIPPED = re.compile(r"Failed to process (\S+?)\. Skipping\. Error: (.+?)\.?\s*$", re.MULTILINE)


def diagnose_failure(log_text: str) -> dict[str, str]:
    text = log_text or ""
    for pattern, cause, fix in _RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {"likely_cause": cause, "suggested_fix": fix}
    skipped = _SKIPPED.search(text)
    if skipped:
        return {"likely_cause": "Boltz could not process the input and skipped it.",
                "suggested_fix": f"The engine reported: {skipped.group(2)}. Check the part of the input this points to (sequence, SMILES or CCD code, "
                                 "template, MSA file) and run again."}
    tail = "\n".join(text.strip().splitlines()[-5:])
    return {"likely_cause": "Unrecognised error.", "suggested_fix": f"Inspect the log tail:\n{tail}"}
