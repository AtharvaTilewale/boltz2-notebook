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

**Usage statistics (opt-in).** If you tick `SEND_USAGE_STATS` in the first cell, one HTTP POST per
session is sent containing: event name (`setup`, `run_finished`, `run_failed`), the notebook version,
the engine version string, the Python version, the GPU model name, and a random UUID generated for the
session. It never contains your Google account, e-mail address, name, job names, sequences, ligands or
results. The endpoint is read from `BOLTZ2NB_TELEMETRY_URL`; when it is unset nothing is sent even if the
box is ticked. See `boltz2nb/telemetry.py` - the payload is restricted to an explicit allow-list of fields.

Versions before 2.1.0 authenticated the Colab user and transmitted the account e-mail address and name
to a usage log without asking. That code has been removed.
