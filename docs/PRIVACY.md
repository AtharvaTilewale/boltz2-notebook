# Privacy

Boltz2-Notebook runs entirely inside your Google Colab runtime (or your own machine).

**What leaves the runtime**

| Data | Destination | When |
|---|---|---|
| Your protein sequences | ColabFold MSA server (`api.colabfold.com`) | Only when a chain has no `msa:` entry (Boltz's `--use_msa_server`). Upload an `.a3m`/`.csv` MSA or use single-sequence mode to avoid this. |
| The CCD code of a ligand you enter (for example `SAH`) | RCSB PDB data API (`data.rcsb.org`) | Only while a ligand is described by a CCD code: the form looks the code up to confirm it exists and to draw it. Nothing else about your system is sent. Set `BOLTZ2NB_OFFLINE=1` to turn the lookup off (codes are then only format-checked). |
| Nothing else | - | - |

Your *browser* also fetches page resources when the interface or a report is shown: fonts from Google Fonts and the 3-D viewer library
(3Dmol, pinned to one version) from jsDelivr, with 3Dmol.org as a second host. These are plain file downloads; they carry no input of yours.
The viewer and the form still work without them (system fonts, no 3-D view).

**Usage reports (opt-in).** They exist to find out what breaks and how the tool is used, so it can be improved. They are off unless you tick
`SEND_USAGE_STATS` in the first cell of the Standard or Advanced notebook (the batch and parameter notebooks send nothing). Cell 1 prints a summary of this
when you do, and a plain copy of every report is written to `usage_reports.jsonl` (next to your job's results, and in the work folder for the setup report),
so you can read exactly what left the runtime.

| Event | When | Fields |
|---|---|---|
| `boltz setup` | the first cell finishes | `ts` (date and time, UTC), `session_id` (a random id made when the notebook starts; no account), `notebook_version`, `engine` (the Boltz version), `python`, `gpu` (model name) |
| `job started` | a job is launched | the fields above, plus `job_name` (as you typed it), `n_chains`, `n_ligand_chains`, `polymer_residues` (the total length of the protein, DNA and RNA chains) and `params` (the run settings: recycling and sampling steps, number of samples, MSA options, output format, seed, accelerator and similar numbers or flags) |
| `job succeeded` | the job finished | the common fields, `job_name`, `runtime_sec` |
| `job failed` | the job failed, or the engine skipped the input | the common fields, `job_name`, `runtime_sec`, `return_code`, `likely_cause` (the tool's diagnosis) and `log_tail` (the last lines of the engine log) |

The common fields are `v` (the format version), `ts`, `session_id`, `event`, `notebook_version`, `engine`, `python` and `gpu`.

**Never sent:** protein, DNA or RNA sequences, ligand SMILES or codes, residue modifications, constraints, templates, MSAs, structures, results, file contents,
your Google account, e-mail address or name. **Job names are sent as typed**, so do not put anything confidential in one while the box is ticked.
`log_tail` has sequences, ligand strings, file paths, e-mail addresses and URL queries masked before it is sent; the masking is best effort, which is why
the log is only ever sent for a failed job and only with your opt-in.

**Who can read it.** Every report is encrypted inside your runtime with the maintainer's *public key* (a libsodium sealed box) before it is sent, so the web
app that collects it and anyone who could browse its storage see only ciphertext. Only the holder of the private key, the maintainer, can open it. The
key pair and the collecting endpoint are configured in `boltz2nb/telemetry_config.py`; while either is missing, nothing is sent even if you tick the box, and a
report is never sent unencrypted. The collecting web app does not record your IP address. To have your reports deleted, send the `session_id` from your
`usage_reports.jsonl` to the maintainer.

Versions before 2.1.0 authenticated the Colab user and transmitted the account e-mail address and name
to a usage log without asking. That code has been removed.
