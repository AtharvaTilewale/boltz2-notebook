"""Usage reports: opt-in, sealed so only the maintainer can read them, limited to what docs/PRIVACY.md lists."""
from __future__ import annotations

import csv
import http.server
import json
import os
import re
import runpy
import shutil
import stat
import subprocess
import sys
import threading
import urllib.parse

import pytest

nacl_public = pytest.importorskip("nacl.public", reason="reports are sealed with libsodium (pynacl)")

from test_misc import (  # noqa: E402,F401  (tests/ is on sys.path; no package)
    REAL_TEMPLATE_PDB_WITHOUT_SEQRES,
    REAL_TEMPLATE_WITH_BOLTZ_LIGAND,
)
from test_notebooks_offline import Runner  # noqa: E402,F401
from test_run_scripts import ROOT, install_fake_boltz, workspace  # noqa: E402,F401

from boltz2nb import telemetry  # noqa: E402
from boltz2nb.yaml_builder import build_yaml, simple_spec  # noqa: E402

SEQ = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDG"
SMILES = "CC(=O)Oc1ccccc1C(=O)O"


# ----------------------------------------------------------------------------------------------------- fixtures
class Collector:
    """A local web server standing in for the collecting web app: it keeps every POST it receives."""

    def __init__(self):
        self.posts: list[dict] = []
        self.status = 200
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"])).decode()
                outer.posts.append({"form": dict(urllib.parse.parse_qsl(raw)), "raw": raw, "type": self.headers.get("Content-Type")})
                self.send_response(outer.status)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/collect"

    def reports(self, private_key: str) -> list[dict]:
        return [json.loads(telemetry.open_sealed(p["form"]["p"], private_key)) for p in self.posts]


@pytest.fixture()
def collector():
    c = Collector()
    yield c
    c.server.shutdown()


@pytest.fixture()
def keys():
    import base64
    private = nacl_public.PrivateKey.generate()
    return {"public": base64.b64encode(bytes(private.public_key)).decode(), "private": base64.b64encode(bytes(private)).decode()}


@pytest.fixture()
def opted_in(monkeypatch, collector, keys):
    monkeypatch.setenv("BOLTZ2NB_SEND_USAGE_STATS", "1")
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", collector.url)
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    return collector, keys


def _clean_env(monkeypatch):
    for var in ("BOLTZ2NB_SEND_USAGE_STATS", "BOLTZ2NB_TELEMETRY_URL", "BOLTZ2NB_TELEMETRY_KEY"):
        monkeypatch.delenv(var, raising=False)


# ----------------------------------------------------------------------------------------------------- opt-in, fail closed
@pytest.mark.parametrize("ticked,url,key,state", [
    (False, True, True, "off"),            # not ticked: nothing, even if the build is configured
    (True, False, False, "unconfigured"),  # ticked, but no endpoint and no key in this build (the shipped state)
    (True, True, False, "unconfigured"),   # an endpoint without the public key: never sent in the clear
    (True, False, True, "unconfigured"),
    (True, True, True, "on"),
])
def test_nothing_is_sent_unless_ticked_and_configured(monkeypatch, collector, keys, ticked, url, key, state):
    _clean_env(monkeypatch)
    if ticked:
        monkeypatch.setenv("BOLTZ2NB_SEND_USAGE_STATS", "1")
    if url:
        monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", collector.url)
    if key:
        monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    assert telemetry.state() == state
    sent = telemetry.send("boltz setup", engine="boltz 2.2.1")
    assert (sent is not None) == (state == "on") and len(collector.posts) == (1 if state == "on" else 0)


def test_the_shipped_config_is_well_formed():
    """The values committed in telemetry_config.py (read from the file: the tests blank the live module so none can reach the real endpoint)."""
    import base64
    import importlib.util
    spec = importlib.util.spec_from_file_location("shipped_telemetry_config", ROOT / "boltz2nb" / "telemetry_config.py")
    shipped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shipped)
    if shipped.ENDPOINT:
        assert re.fullmatch(r"https://script\.google\.com/macros/s/[\w-]+/exec", shipped.ENDPOINT), "reports must go to the deployed web app over https"
    if shipped.PUBLIC_KEY:                                    # catches a mistyped or truncated key before it silently makes every report unreadable
        assert len(base64.b64decode(shipped.PUBLIC_KEY, validate=True)) == 32


def test_tests_cannot_reach_the_real_endpoint(monkeypatch):
    from boltz2nb import telemetry_config
    _clean_env(monkeypatch)
    monkeypatch.setenv("BOLTZ2NB_SEND_USAGE_STATS", "1")
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", "AAAA")      # a key and nothing else: with the shipped endpoint this used to be enough to post for real
    assert telemetry_config.ENDPOINT == "" and telemetry.endpoint() == "" and telemetry.state() == "unconfigured"


# ----------------------------------------------------------------------------------------------------- sealing
def test_reports_are_sealed_and_only_the_private_key_opens_them(opted_in):
    collector, keys = opted_in
    sent = telemetry.send("job started", job_name="KRAS_G12C_screen", engine="boltz 2.2.1", n_chains=2, n_ligand_chains=1, polymer_residues=43,
                          params={"sampling_steps": 20})
    (post,) = collector.posts
    assert set(post["form"]) == {"v", "p"} and post["form"]["v"] == "1" and post["type"] == "application/x-www-form-urlencoded"
    for plain in ("KRAS_G12C_screen", "boltz 2.2.1", "sampling_steps", "job started"):
        assert plain not in post["raw"], f"{plain!r} travelled in the clear"
    assert collector.reports(keys["private"]) == [sent]
    other = nacl_public.PrivateKey.generate()
    import base64
    with pytest.raises(Exception):  # noqa: B017  (nacl.exceptions.CryptoError)
        telemetry.open_sealed(post["form"]["p"], base64.b64encode(bytes(other)).decode())


def test_a_failed_post_is_not_reported_as_sent(opted_in, tmp_path):
    collector, _ = opted_in
    collector.status = 500
    copy = tmp_path / "usage_reports.jsonl"
    assert telemetry.send("boltz setup", copy_to=copy) is None and not copy.exists()
    collector.status = 200
    assert telemetry.send("boltz setup", copy_to=copy) is not None and len(copy.read_text().splitlines()) == 1


def test_an_unreachable_endpoint_never_raises(monkeypatch, keys):
    monkeypatch.setenv("BOLTZ2NB_SEND_USAGE_STATS", "1")
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", "http://127.0.0.1:9/nothing")
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    assert telemetry.send("boltz setup", timeout=1) is None


# ----------------------------------------------------------------------------------------------------- what a report may hold
def test_setup_event_is_named_and_dated(opted_in):
    collector, keys = opted_in
    telemetry.send("boltz setup", engine="boltz 2.2.1", python="3.12.3", gpu="Tesla T4")
    (report,) = collector.reports(keys["private"])
    assert report["event"] == "boltz setup" and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", report["ts"])
    assert set(report) == {"v", "ts", "session_id", "event", "notebook_version", "engine", "python", "gpu"}
    assert report["session_id"] == telemetry.session_id() and report["engine"] == "boltz 2.2.1" and report["gpu"] == "Tesla T4"


def test_build_payload_rejects_anything_outside_the_allow_list():
    for event, extra in (("boltz setup", {"job_name": "x"}), ("job succeeded", {"log_tail": "x"}), ("job started", {"email": "a@b.c"}),
                         ("job failed", {"sequence": SEQ}), ("job started", {"smiles": SMILES})):
        with pytest.raises(ValueError):
            telemetry.build_payload(event, **extra)
    with pytest.raises(ValueError):
        telemetry.build_payload("anything else")
    assert telemetry.send("boltz setup", sequence=SEQ) is None            # an unexpected field loses the report, it is never sent


def test_job_started_has_counts_and_settings_but_never_sequences_ligands_or_modifications(opted_in):
    collector, keys = opted_in
    doc = build_yaml(simple_spec([SEQ, SEQ[:10]], ligand_smiles=SMILES, dna=["ACGTACGT"], affinity=True))
    doc["sequences"][0]["protein"]["modifications"] = [{"position": 4, "ccd": "SEP"}]
    doc["sequences"][0]["protein"]["id"] = ["A", "B"]                          # a homodimer: two chains share one entry
    from boltz2nb.run_params import DEFAULTS
    params = dict(DEFAULTS, job_name="demo job", sampling_steps=20, api_token="hunter2", note="x" * 500)
    sent = telemetry.job_started(doc, params, engine="boltz 2.2.1")
    (report,) = collector.reports(keys["private"])
    assert report == sent and report["event"] == "job started" and report["job_name"] == "demo job"
    assert (report["n_chains"], report["n_ligand_chains"], report["polymer_residues"]) == (5, 1, 2 * len(SEQ) + 10 + 8)
    assert report["params"]["sampling_steps"] == 20 and "job_name" not in report["params"] and set(report["params"]) <= telemetry.PARAM_KEYS
    text = json.dumps(report)
    for secret in (SEQ, SEQ[:10], SMILES, "SEP", "ACGTACGT", "hunter2", "xxxxx", "modifications"):
        assert secret not in text, secret


def test_job_succeeded_has_the_name_and_the_time_only(opted_in):
    collector, keys = opted_in
    telemetry.job_ended(True, "demo", 123.456, engine="boltz 2.2.1")
    (report,) = collector.reports(keys["private"])
    assert report["event"] == "job succeeded" and report["job_name"] == "demo" and report["runtime_sec"] == 123.5
    assert "log_tail" not in report and "likely_cause" not in report


def test_job_failed_carries_the_cause_and_the_masked_end_of_the_log(opted_in):
    collector, keys = opted_in
    log = (f"Could not parse SMILES: {SMILES}\nsequence {SEQ} is odd\nwrote /content/drive/MyDrive/Lab/secret.yaml\nmail jane@example.org\n"
           "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.50 GiB\n")
    telemetry.job_ended(False, "demo", 12.0, engine="boltz 2.2.1", return_code=1, likely_cause="GPU ran out of memory.", log_text=log)
    (report,) = collector.reports(keys["private"])
    assert report["event"] == "job failed" and report["return_code"] == 1 and report["likely_cause"] == "GPU ran out of memory."
    assert "CUDA out of memory" in report["log_tail"]
    for secret in (SMILES, SEQ, "Lab/secret", "jane@example.org"):
        assert secret not in report["log_tail"], secret


# ----------------------------------------------------------------------------------------------------- masking
@pytest.mark.parametrize("raw,gone,kept", [
    (f"bad ligand {SMILES} here", SMILES, "bad ligand"),
    ("invalid SMILES C1CC( for B", "C1CC(", "invalid SMILES"),
    (f"chain A {SEQ}", SEQ, "chain A"),
    ("lowercase mkt" + "ayiakqrqisfvk" * 2, "ayiakqrqisfvkayiakqrqisfvk", "lowercase"),
    ("see /home/jane/projects/kras/run.yaml now", "/home/jane/projects", "run.yaml"),
    ("at /content/drive/MyDrive/My Lab/target one/x.pdb", "My Lab", "at"),
    ("contact jane.doe@example.org", "jane.doe@example.org", "contact"),
    ("GET https://api.colabfold.com/ticket/msa?token=abc&user=jane", "token=abc", "https://api.colabfold.com/ticket/msa"),
    ('File "/usr/lib/python3.12/site-packages/boltz/data/parse/yaml.py", line 68', "/usr/lib", "boltz/data/parse/yaml.py"),
])
def test_redact_log_masks_what_could_identify_an_input(raw, gone, kept):
    out = telemetry.redact_log(raw)
    assert gone not in out and kept in out, out


def test_redact_log_keeps_the_lines_a_maintainer_needs():
    for real in (REAL_TEMPLATE_PDB_WITHOUT_SEQRES, REAL_TEMPLATE_WITH_BOLTZ_LIGAND):
        out = telemetry.redact_log(real)
        assert "Failed to process t.yaml. Skipping. Error:" in out and "parsed_template = parse_" in out and "boltz/data/parse/mmcif.py" in out
        assert "<smiles>" not in out and "<seq" not in out                      # nothing was mistaken for an input
    assert "load_molecules(moldir, [ccd])[ccd]" in telemetry.redact_log("    mol = load_molecules(moldir, [ccd])[ccd]")


def test_redact_log_drops_progress_bars_and_keeps_the_tail():
    log = "\n".join(["Predicting DataLoader 0: 100%|██████████| 1/1 [00:02<00:00,  0.47it/s]"] + [f"line {i}" for i in range(200)])
    out = telemetry.redact_log(log, max_lines=60).splitlines()
    assert len(out) == 60 and out[-1] == "line 199" and not any("it/s" in ln for ln in out)
    assert len(telemetry.redact_log("x " * 10000, max_chars=6000)) <= 6000


# ----------------------------------------------------------------------------------------------------- through the notebook scripts
def _events(collector, keys):
    return [r["event"] for r in collector.reports(keys["private"])]


def test_run_script_reports_start_and_success(workspace, tmp_path, monkeypatch, opted_in, capsys):  # noqa: F811
    collector, keys = opted_in
    install_fake_boltz(tmp_path, monkeypatch)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    started, ended = collector.reports(keys["private"])
    assert (started["event"], ended["event"]) == ("job started", "job succeeded") and started["job_name"] == ended["job_name"] == "demo"
    assert started["n_chains"] == 2 and started["n_ligand_chains"] == 1 and started["polymer_residues"] == len(SEQ)
    assert started["params"]["diffusion_samples"] == 1
    copy = [json.loads(ln) for ln in (workspace / "demo" / "usage_reports.jsonl").read_text().splitlines()]
    assert copy == [started, ended]                                           # the user can read exactly what was sent
    out = capsys.readouterr().out
    assert "Usage statistics" not in out and "usage_reports.jsonl" not in out and "report sent" not in out   # reporting is silent
    assert SEQ not in json.dumps([started, ended]) and SMILES not in json.dumps([started, ended])


def test_run_script_reports_a_failed_job_with_its_log(workspace, tmp_path, monkeypatch, opted_in):  # noqa: F811
    collector, keys = opted_in
    install_fake_boltz(tmp_path, monkeypatch, fail=True)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    started, failed = collector.reports(keys["private"])
    assert failed["event"] == "job failed" and failed["return_code"] == 1 and failed["likely_cause"] == "GPU ran out of memory."
    assert "CUDA out of memory" in failed["log_tail"] and "demo" == failed["job_name"]


def test_run_script_reports_an_input_boltz_skipped_as_failed(workspace, tmp_path, monkeypatch, opted_in):  # noqa: F811
    collector, keys = opted_in
    install_fake_boltz(tmp_path, monkeypatch, skip=True)
    with pytest.raises(RuntimeError):
        runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    assert _events(collector, keys) == ["job started", "job failed"]
    assert "skipped" in collector.reports(keys["private"])[1]["likely_cause"]


def test_run_script_sends_nothing_when_not_ticked(workspace, tmp_path, monkeypatch, collector, keys, capsys):  # noqa: F811
    _clean_env(monkeypatch)
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", collector.url)
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    install_fake_boltz(tmp_path, monkeypatch)
    runpy.run_path(str(ROOT / "scripts" / "common" / "Boltz_Run.py"))
    assert collector.posts == [] and not (workspace / "demo" / "usage_reports.jsonl").exists()
    assert "Usage statistics" not in capsys.readouterr().out


@pytest.fixture()
def runner(tmp_path, monkeypatch):
    r = Runner(tmp_path, monkeypatch)
    yield r
    r.close()


def _says_anything_about_usage_reports(out):
    low = out.lower()
    return any(s in low for s in ("usage stat", "usage report", "report sent", "usage_reports.jsonl", "encryption library", "maintainer can read"))


@pytest.mark.parametrize("notebook", ["Boltz2.ipynb", "colab/v1/Boltz2_v1.0.0.ipynb"])
def test_setup_cell_reports_the_setup_silently(runner, monkeypatch, collector, keys, notebook):
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", collector.url)
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", keys["public"])
    off = runner.run(notebook, 1, {"SEND_USAGE_STATS": False})                       # unticked: nothing at all
    assert collector.posts == [] and not _says_anything_about_usage_reports(off)
    on = runner.run(notebook, 1)                                                     # the default: ticked, and the cell says nothing about it
    assert not _says_anything_about_usage_reports(on), on
    (report,) = collector.reports(keys["private"])
    assert report["event"] == "boltz setup" and set(report) >= {"ts", "session_id", "notebook_version"}      # engine is whatever the environment reports
    assert (runner.content / "boltz_data" / "usage_reports.jsonl").exists()


def test_setup_cell_stays_quiet_when_reporting_cannot_send(runner, monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", "")                               # switched off: nothing to send, nothing to say
    assert not _says_anything_about_usage_reports(runner.run("Boltz2.ipynb", 1))
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_URL", "http://127.0.0.1:9/unreachable")  # configured but the post fails: still silent, setup goes on
    monkeypatch.setenv("BOLTZ2NB_TELEMETRY_KEY", "/oYKKLFUqgUAV5pBhKM8+Vte+fudNBqh+pNh+H3QBWo=")
    out = runner.run("Boltz2.ipynb", 1)
    assert not _says_anything_about_usage_reports(out) and "Traceback" not in out


# ----------------------------------------------------------------------------------------------------- maintainer tools
def _tool(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_keygen_keeps_the_private_key_private_and_outside_the_repository(tmp_path, capsys):
    keygen = _tool("telemetry_keygen")
    out = tmp_path / "keys" / "private.key"
    assert keygen.inside_a_git_worktree(ROOT / "x.key") and not keygen.inside_a_git_worktree(out) or not (tmp_path / ".git").exists()
    assert keygen.main(["--out", str(out)]) == 0
    public = capsys.readouterr().out.strip().splitlines()[-1]
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    sealed = telemetry.seal(b"hello", public)
    assert telemetry.open_sealed(sealed, out.read_text().strip()) == b"hello"            # the printed public key matches the stored private one
    assert keygen.main(["--out", str(out)]) == 2                                          # never overwrites a key that reports were sealed for
    assert keygen.main(["--out", str(ROOT / "private.key")]) == 2 and not (ROOT / "private.key").exists()   # refuses a path inside this repository


def test_reader_opens_the_exported_sheet_and_skips_junk(opted_in, tmp_path, capsys):
    collector, keys = opted_in
    telemetry.send("boltz setup", engine="boltz 2.2.1")
    telemetry.job_ended(False, "j1", 3.0, engine="e", return_code=1, likely_cause="GPU ran out of memory.", log_text="boom")
    telemetry.job_ended(True, "j2", 4.0, engine="e")
    export = tmp_path / "reports.csv"
    with export.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["received_utc", "schema", "sealed_report"])
        for post in collector.posts:
            w.writerow(["2026-10-27T10:00:00Z", "1", "sealed:" + post["form"]["p"]])
        w.writerow(["2026-10-27T10:00:01Z", "1", "sealed:QUJDREVGRw=="])              # junk posted to the public URL
    key_file = tmp_path / "k"
    key_file.write_text(keys["private"])
    reader = _tool("telemetry_read")
    assert reader.main(["--key", str(key_file), str(export), "--jsonl", str(tmp_path / "out.jsonl")]) == 0
    out = capsys.readouterr().out
    assert "3 reports" in out and "boltz setup" in out and "GPU ran out of memory." in out and "1 rows could not be opened" in out
    assert [json.loads(ln)["event"] for ln in (tmp_path / "out.jsonl").read_text().splitlines()] == ["boltz setup", "job failed", "job succeeded"]


def _plain_env(tmp_path):
    """The environment of a maintainer's terminal: the package is not importable. The interpreter running the tests may have it installed
    (CI installs it in editable mode), so a stub package that refuses to import is put first on the path instead of relying on its absence."""
    stub = tmp_path / "no_boltz2nb" / "boltz2nb"
    stub.mkdir(parents=True, exist_ok=True)
    (stub / "__init__.py").write_text('raise ImportError("boltz2nb is not installed in a plain terminal")\n')
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONPATH"] = str(stub.parent)
    return env


def test_the_maintainer_tools_run_from_a_plain_terminal(opted_in, tmp_path):
    """Run as `python tools/<tool>.py` from any directory with only pynacl installed, where the package cannot be imported.
    (The tools were first tested in-process with the repository on the path, which hid an import of boltz2nb that fails in a real terminal.)"""
    collector, keys = opted_in
    probe = subprocess.run([sys.executable, "-c", "import boltz2nb"], capture_output=True, cwd=tmp_path, env=_plain_env(tmp_path))
    assert probe.returncode != 0, "boltz2nb is importable here, so this test would not catch a hidden dependency on it"
    telemetry.job_ended(False, "j1", 3.0, engine="e", return_code=1, likely_cause="GPU ran out of memory.", log_text="boom")
    export = tmp_path / "reports.csv"
    with export.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["received_utc", "schema", "sealed_report"])
        w.writerow(["2026-10-27T10:00:00Z", "1", "sealed:" + collector.posts[0]["form"]["p"]])
    key_file = tmp_path / "private.key"
    key_file.write_text(keys["private"])
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "telemetry_read.py"), "--key", str(key_file), str(export), "--jsonl", "out.jsonl"],
                          capture_output=True, text=True, cwd=tmp_path, env=_plain_env(tmp_path))
    assert done.returncode == 0, done.stderr
    assert "1 reports" in done.stdout and "GPU ran out of memory." in done.stdout and json.loads((tmp_path / "out.jsonl").read_text())["event"] == "job failed"
    made = subprocess.run([sys.executable, str(ROOT / "tools" / "telemetry_keygen.py"), "--out", str(tmp_path / "keys" / "k.key")],
                          capture_output=True, text=True, cwd=tmp_path, env=_plain_env(tmp_path))
    assert made.returncode == 0, made.stderr
    assert len(made.stdout.strip().splitlines()[-1]) == 44                       # a base64 32-byte public key


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_receiver_script_stores_sealed_reports_and_rejects_everything_else():
    script = json.dumps((ROOT / "telemetry" / "receiver.gs").read_text(encoding="utf-8"))
    js = f"""
const vm = require('vm');
const rows = []; let sheets = {{}};
const sheet = {{ getLastRow: () => rows.length, appendRow: r => rows.push(r) }};
const book = {{ getSheetByName: n => sheets[n] || null, insertSheet: n => (sheets[n] = sheet) }};
const ctx = {{ SpreadsheetApp: {{ getActiveSpreadsheet: () => book }}, ContentService: {{ createTextOutput: t => t }}, Date, RegExp }};
vm.createContext(ctx); vm.runInContext({script}, ctx);
const post = (p, v) => ctx.doPost({{ parameter: {{ p, v }} }});
const out = [post('QUJD+/=', '1'), post('=SUM(A1)', '1'), post('QUJD', '2'), post('', '1'), post('A'.repeat(40001), '1'), ctx.doPost({{}}), ctx.doGet()];
console.log(JSON.stringify({{ out, rows }}));
"""
    result = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert result["out"][:6] == ["ok", "rejected", "rejected", "rejected", "rejected", "rejected"] and "write-only" in result["out"][6]
    assert result["rows"][0] == ["received_utc", "schema", "sealed_report"] and len(result["rows"]) == 2
    assert result["rows"][1][1:] == ["1", "sealed:QUJD+/="]            # a stored value never starts with = or +, so Sheets can not read it as a formula


# ----------------------------------------------------------------------------------------------------- the disclosure matches the code
def test_privacy_doc_names_every_event_and_field_the_code_can_send():
    text = (ROOT / "docs" / "PRIVACY.md").read_text(encoding="utf-8")
    for event in telemetry.EVENTS:
        assert f"`{event}`" in text, f"docs/PRIVACY.md does not mention the event {event!r}"
    for field in sorted(telemetry.ALLOWED_FIELDS - {"v"}):
        assert f"`{field}`" in text, f"docs/PRIVACY.md does not mention the field {field!r}"
    assert "usage_reports.jsonl" in text and "public key" in text
    assert "on by default" in text and "untick it before running the cell and nothing is sent" in text    # the default and the way out
    leaves = text[text.index("**What leaves the runtime**"):text.index("| Nothing else |")]
    assert "Usage reports" in leaves and "SEND_USAGE_STATS" in leaves, "the summary table must list the usage reports"


@pytest.mark.parametrize("notebook", ["Boltz2.ipynb", "colab/v1/Boltz2_v1.0.0.ipynb", "colab/v2/Boltz2_V2.0.0.ipynb"])
def test_notebooks_turn_usage_reports_on_by_default_and_link_the_details(notebook):
    cell = "".join(json.loads((ROOT / notebook).read_text(encoding="utf-8"))["cells"][1]["source"])
    line = next(ln for ln in cell.splitlines() if "SEND_USAGE_STATS**" in ln)
    assert line == ("# @markdown - **SEND_USAGE_STATS**: help improve the tool by sending usage reports, no personal data is shared. "
                    "See [PRIVACY.md](https://github.com/AtharvaTilewale/boltz2-notebook/blob/main/docs/PRIVACY.md) for more info."), line
    assert 'SEND_USAGE_STATS = True  # @param {type:"boolean"}' in cell
    assert '"BOLTZ2NB_SEND_USAGE_STATS": "1" if SEND_USAGE_STATS else "0"' in cell                 # unticking it really switches reports off
