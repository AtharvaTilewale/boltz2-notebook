import base64
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from boltz2nb import run_params
from boltz2nb.ui import callbacks as cb
from boltz2nb.ui.icons import ICONS
from boltz2nb.ui.render import client_config, render_form

ASSETS = Path(__file__).resolve().parents[2] / "assets"
BUDGET_BYTES = 150_000  # the whole form is embedded in the notebook output


@pytest.fixture(scope="module", params=["standard", "advanced"])
def html(request):
    return render_form(mode=request.param, uid="t1"), request.param


def test_no_unresolved_placeholders(html):
    text, _ = html
    assert "@@" not in text
    assert "__ID__" in text  # only inside <template>, resolved per clone in the browser


def test_size_budget(html):
    assert len(html[0].encode()) < BUDGET_BYTES


def test_markup_is_balanced(html):
    VOID = {"input", "br", "hr", "img", "meta", "link", "use", "path", "circle", "rect", "stop", "lineargradient"}
    stack, errs = [], []

    class P(HTMLParser):
        def handle_starttag(self, t, a):
            if t not in VOID:
                stack.append(t)

        def handle_endtag(self, t):
            if t in VOID:
                return
            if not stack or stack[-1] != t:
                errs.append((t, self.getpos()))
            else:
                stack.pop()
    markup = re.sub(r"<script.*?</script>|<style.*?</style>", "", html[0], flags=re.S)
    P().feed(markup)
    assert not errs and not stack, (errs[:3], stack[:3])


def test_every_used_icon_is_defined(html):
    used = set(re.findall(r'href="#bz-i-([a-z-]+)"', html[0])) | set(re.findall(r"bz-i-([a-z-]+)", re.sub(r"<symbol.*?</symbol>", "", html[0], flags=re.S)))
    assert used <= set(ICONS), used - set(ICONS)


def test_only_font_hosts_are_external(html):
    hosts = set(re.findall(r'(?:src|href)="https?://([^/"]+)', html[0]))
    assert hosts <= {"fonts.googleapis.com", "fonts.gstatic.com"}, hosts
    assert "<script src" not in html[0]


def test_dom_ids_unique_outside_templates(html):
    body = re.sub(r"<template.*?</template>", "", html[0], flags=re.S)
    body = re.sub(r"<symbol.*?</symbol>", "", body, flags=re.S)
    ids = re.findall(r'\sid="([^"]+)"', body)
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]


def test_every_label_target_exists(html):
    body = html[0]
    for target in re.findall(r'<label[^>]*\sfor="([^"]+)"', body):
        assert f'id="{target}"' in body or "__ID__" in target, target


def test_js_parses(html):
    esprima = pytest.importorskip("esprima")
    js = re.search(r"<script>(.*)</script>", html[0], re.S).group(1)
    esprima.parseScript(js)


def test_form_is_one_self_contained_script(html):
    """Notebook front-ends re-insert <script> tags in different ways (often dropping ids), so the form must not depend on a
    second element: exactly one executable script, no JSON data element, and the Python config embedded inside it."""
    body = html[0]
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", body, re.S)
    assert len(scripts) == 1, [a for a, _ in scripts]
    attrs, js = scripts[0]
    assert "type=" not in attrs and "src=" not in attrs
    assert "bz-config-" not in body and "@@" not in js
    assert re.search(r"var CFG = \{\"", js), "config is not embedded in the script"


def test_embedded_config_is_exactly_the_python_config_and_script_safe():
    for mode in ("standard", "advanced"):
        js = re.search(r"<script>(.*)</script>", render_form(mode, uid="x"), re.S).group(1)
        literal = re.search(r"var CFG = (\{.*?\});\n", js, re.S).group(1)
        assert json.loads(literal) == json.loads(json.dumps(client_config(mode)))
        assert "<" not in literal and ">" not in literal
    # nothing in the script can end it early or open an HTML comment context
    assert "</script" not in js.lower() and "<!--" not in js


def test_script_json_escapes_everything_that_could_break_out():
    from boltz2nb.ui.render import script_json

    nasty = {"a": "</script><!-- \u2028 \u2029 >", "b": [1, 2.5, None, True]}
    out = script_json(nasty)
    assert "<" not in out and ">" not in out and "\u2028" not in out and "\u2029" not in out
    assert json.loads(out) == nasty


def test_client_config_matches_python_sources():
    cfg = client_config("advanced")
    assert cfg["profiles"] == run_params.PROFILES
    assert cfg["pairing"] == list(run_params.PAIRING_STRATEGIES)
    assert cfg["ranges"]["sampling_steps"] == list(run_params.RANGES["sampling_steps"])
    assert cfg["defaults"]["step_scale"] == run_params.DEFAULTS["step_scale"]
    assert cfg["defaults"]["use_potentials"] is False and cfg["defaults"]["override"] is False
    json.dumps(cfg)


def test_standard_mode_flag_and_unknown_mode():
    assert 'data-mode="standard"' in render_form("standard", uid="x")
    with pytest.raises(ValueError):
        render_form("fancy")


# ---------------------------------------------------------------------------------------- callbacks
@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("BOLTZ2NB_BASE_DIR", str(tmp_path / "bd"))
    return tmp_path / "bd"


def payload(**kw):
    p = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": "MKTAYIAK", "msa": "empty"}},
                       {"type": "ligand", "data": {"id": ["B"], "smiles": "CC(=O)Oc1ccccc1C(=O)O"}}],
         "templates": [], "constraints": {"bonds": [], "pockets": [], "contacts": []}, "properties": {"affinity_binder": "B"}}
    p.update(kw)
    return p


def test_preview_does_not_write_and_returns_yaml(base):
    r = cb.preview_params(payload())
    assert r["status"] == "ok" and "affinity" in r["yaml"] and "sequence: MKTAYIAK" in r["yaml"]
    assert any("C9H8O4" in n for n in r["notes"]) and any("single-sequence" in n for n in r["notes"])
    assert not (base / "params.yaml").exists()


def test_save_params_writes_file(base):
    r = cb.save_params(payload())
    assert r["status"] == "ok" and (base / "params.yaml").read_text() == r["yaml"]


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p["properties"].update(affinity_binder="A"), "only defined for small-molecule"),
    (lambda p: p["sequences"][0]["data"].update(sequence="MKTB"), "invalid characters"),
    (lambda p: p["sequences"][1]["data"].update(smiles="C1CC"), "SMILES"),
    (lambda p: p["constraints"]["pockets"].append({"binder": "B", "contacts": [{"chain": "Z", "ref": "3"}]}), "unknown chain"),
])
def test_preview_errors_are_reported_not_raised(base, mutate, needle):
    p = payload(); mutate(p)
    r = cb.preview_params(p)
    assert r["status"] == "error" and needle in r["message"]


def test_large_complex_warning(base):
    p = payload(); p["sequences"][0]["data"]["sequence"] = "A" * 1600; p["properties"] = {}
    r = cb.preview_params(p)
    assert r["status"] == "ok" and any("T4" in w for w in r["warnings"])


def test_save_run_params_validates(base):
    good = 'job_name = "j"\nsampling_steps = 200\nmsa_pairing_strategy = "greedy"\nseed = 7'
    assert cb.save_run_params({"filename": "run_params.txt", "content": good})["status"] == "ok"
    assert run_params.load_run_params(base / "run_params.txt")["seed"] == 7
    bad = cb.save_run_params({"content": good.replace("200", "2")})
    assert bad["status"] == "error" and "sampling_steps" in bad["message"]
    assert cb.save_run_params({"filename": "../../etc/x", "content": good})["filename"] == "x"  # path stripped
    assert (base / "x").exists() and not (base.parent / "etc").exists()


def test_describe_ligand(base):
    ok = cb.describe_ligand({"kind": "smiles", "value": "CC(=O)Oc1ccccc1C(=O)O"})
    assert ok["valid"] is True and ok["formula"] == "C9H8O4" and ok["svg"].lstrip().startswith(("<?xml", "<svg"))
    assert cb.describe_ligand({"kind": "smiles", "value": "C1CC"})["valid"] is False
    assert cb.describe_ligand({"kind": "smiles", "value": ""})["valid"] is None
    assert cb.describe_ligand({"kind": "ccd", "value": "SAH"})["valid"] is True
    assert cb.describe_ligand({"kind": "ccd", "value": "TOOLONG1"})["valid"] is False


def test_uploads(base):
    r = cb.save_uploaded_file("msa", "../evil name.a3m", base64.b64encode(b">q\nMKT\n").decode())
    assert r["status"] == "ok" and Path(r["path"]).parent.name == "msas" and Path(r["path"]).name == "evil_name.a3m"
    assert cb.save_uploaded_file("template", "x.txt", "QQ==")["status"] == "error"
    assert cb.save_uploaded_file("mystery", "x.a3m", "QQ==")["status"] == "error"
    r = cb.save_uploaded_file("template", "t.pdb", "data:text/plain;base64," + base64.b64encode(b"ATOM").decode())
    assert r["status"] == "ok" and Path(r["path"]).read_bytes() == b"ATOM"


def test_process_pdb_upload_groups_identical_chains():
    r = cb.process_pdb_upload({"pdb_content": (ASSETS / "pdb" / "prot_lig_dna.pdb").read_text(), "filename": "x.pdb"})
    assert r["status"] == "ok"
    prot = [e for e in r["entities"] if e["kind"] == "protein"]
    assert len(prot) == 1 and prot[0]["ids"] == ["A", "B"] and prot[0]["length"] == 260
    assert {e["kind"] for e in r["entities"]} == {"protein", "dna"}
    assert {lig["ccd"] for lig in r["ligands"]} == {"83Y", "BDP", "GCD"}
    assert cb.process_pdb_upload({"pdb_content": "", "filename": "x.pdb"})["status"] == "error"


def test_register_callbacks():
    class Out:
        def __init__(self):
            self.reg = {}

        def register_callback(self, n, f):
            self.reg[n] = f
    o = Out()
    assert cb.register_callbacks(o) is True and set(o.reg) == set(cb.CALLBACKS)
    assert cb.register_callbacks() in (True, False)
