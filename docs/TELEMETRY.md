# Collecting usage reports (maintainer guide)

What users are told is in [PRIVACY.md](PRIVACY.md); this page is how to receive the data. The design in one paragraph: `SEND_USAGE_STATS` is ticked by default (a user can untick it), and while it is ticked the user's
runtime seals each report with **your public key** and POSTs it to **a web app that only appends rows to a Google Sheet you own**.
The web app and the sheet only ever hold ciphertext; **the private key never leaves your machine**. Without both the endpoint and the public key in
`boltz2nb/telemetry_config.py` the notebooks send nothing, whatever the box says.

## One-time setup

1. **Make the key pair, on your own computer, outside the repository:**
   ```bash
   pip install pynacl
   python tools/telemetry_keygen.py          # writes ~/.boltz2nb/telemetry_private.key (mode 600) and prints the public key
   ```
   Back the private key up somewhere private. If you lose it every stored report is unreadable; if it leaks, anyone with the sheet can read the reports.
   The tool refuses to write a key inside a git working tree and never overwrites an existing one.
2. **Create the receiver:** make a new Google Sheet (it is the only place the data lives; keep it private), then *Extensions > Apps Script*, paste
   [`telemetry/receiver.gs`](../telemetry/receiver.gs) and *Deploy > New deployment > Web app* with **Execute as: Me** and **Who has access: Anyone**
   (the notebooks post without signing in). Copy the web app URL. The script appends `received_utc`, the format version and the sealed report to a `reports` sheet,
   rejects anything that is not a short base64 string, and cannot read what it stores. It does not see the sender's address.
3. **Put the two public values into [`boltz2nb/telemetry_config.py`](../boltz2nb/telemetry_config.py):** `ENDPOINT` (the web app URL) and `PUBLIC_KEY` (printed in step 1).
   Check with `python -c "from boltz2nb import telemetry; print(telemetry.configured())"`, run the tests, and release a new version: the notebooks fetch the
   code from the tag named in Cell 1, so collection starts for users of that tag.
4. **Try it:** run Cell 1 of a notebook with `SEND_USAGE_STATS` left ticked, and a row appears in the sheet (about a second later). The row is unreadable by design.

## Reading the data

Download the sheet as CSV (*File > Download > Comma-separated values*) and run
```bash
python tools/telemetry_read.py --key ~/.boltz2nb/telemetry_private.key reports.csv --jsonl reports.jsonl
```
It prints the number of reports and sessions, the events, the failed jobs by likely cause and the reports per day, and writes every opened report to
`reports.jsonl`. Rows that your key cannot open (anyone who knows the URL can post junk) are counted and skipped.

## Things to know

- **Who can read it:** the owner of the sheet sees ciphertext; only the private key opens it. Share the sheet freely without sharing the key, or the key without the sheet.
- **Public URL:** anyone who finds the web app URL (it is in the repository) can add junk rows. They cannot read or change anything. Delete junk rows by hand.
- **What a report contains:** see PRIVACY.md. `job_name` is whatever the user typed, `log_tail` is a masked best-effort excerpt: treat both as personal data.
- **Deleting a user's data:** a user can find their `session_id` in `usage_reports.jsonl`; open the CSV with the reader, find the rows with that id and delete
  them from the sheet (the reader prints reports in sheet order). Decide how long you keep reports and delete older rows on that schedule; PRIVACY.md promises
  deletion on request, so keep that promise or change the text.
- **Rotating the key:** run the keygen again with a new `--out`, put the new public key in `telemetry_config.py` and release. Keep the old private key for reports already stored.
- **Switching it off:** empty `ENDPOINT` or `PUBLIC_KEY` and release; or delete the web app deployment (users then send into the void, silently).
- **Forks and tests** can override both values with the environment variables `BOLTZ2NB_TELEMETRY_URL` and `BOLTZ2NB_TELEMETRY_KEY`.
