"""What the Python side must give Colab so the page can read the answer (no browser needed).

``google.colab.kernel.invokeFunction`` resolves with the notebook's *display* of the callback's return value. A plain ``dict``
is displayed as its ``repr`` (``text/plain``); only ``IPython.display.JSON`` arrives as parsed JSON (``application/json``), which is
what Colab's own callbacks return. Every callback is therefore registered through ``as_json_reply``.
"""
import json
import math

import pytest

pytest.importorskip("IPython", reason="the notebook display machinery is IPython")
from IPython.core.formatters import DisplayFormatter

from boltz2nb.ui import callbacks as cb

SEQ = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDG"


class Recorder:
    def __init__(self):
        self.registered = {}

    def register_callback(self, name, fn):
        self.registered[name] = fn


@pytest.fixture
def registered(tmp_path, monkeypatch):
    monkeypatch.setenv("BOLTZ2NB_BASE_DIR", str(tmp_path / "bd"))
    rec = Recorder()
    assert cb.register_callbacks(rec) is True
    return rec.registered


def shown(value):
    """What the page receives: the mime bundle the notebook builds from a callback's return value."""
    data, _ = DisplayFormatter().format(value)
    return data


PAYLOAD = {"sequences": [{"type": "protein", "data": {"id": ["A"], "sequence": SEQ, "msa": "server"}},
                         {"type": "ligand", "data": {"id": ["B"], "smiles": "CC(=O)Oc1ccccc1C(=O)O"}}],
           "templates": [], "constraints": {"bonds": [], "pockets": [], "contacts": []}, "properties": {"affinity_binder": "B"}}
CALLS = {
    "preview_params": [PAYLOAD],
    "save_params": [PAYLOAD],
    "describe_ligand": [{"kind": "smiles", "value": "CC(=O)Oc1ccccc1C(=O)O"}],
    "save_run_params": [{"filename": "run_params.txt", "content": 'job_name = "x"\nmsa_pairing_strategy = "greedy"'}],
    "save_uploaded_file": ["msa", "a.a3m", "Pm1zYQ=="],
    "process_pdb_upload": [{"pdb_content": "REMARK\n", "filename": "x.pdb"}],
    "set_theme": ["dark"],
}


def test_a_plain_dict_does_not_reach_the_page_as_json():
    """The reason for the wrapper: a dict is shown as text only, which the page cannot use."""
    data = shown(cb.CALLBACKS["describe_ligand"]({"kind": "smiles", "value": "CCO"}))
    assert "application/json" not in data and data["text/plain"].lstrip().startswith("{")


def test_every_callback_is_registered_and_covered_by_this_test(registered):
    assert set(registered) == set(cb.CALLBACKS) == set(CALLS), (set(registered) ^ set(CALLS))


@pytest.mark.parametrize("name", sorted(CALLS))
def test_every_registered_callback_answers_with_parsed_json(registered, name):
    data = shown(registered[name](*CALLS[name]))
    assert "application/json" in data, f"{name} would reach the page as {sorted(data)}"
    reply = data["application/json"]
    assert isinstance(reply, dict) and reply.get("status") in ("ok", "error"), reply
    json.dumps(reply, allow_nan=False)                      # the page parses it with JSON.parse, which rejects NaN / Infinity
    if reply["status"] == "error":
        assert reply.get("message"), f"{name}: an error without a message would be shown as 'undefined'"


def test_a_successful_preview_and_import_carry_the_fields_the_page_reads(registered, example_pred_dir):
    preview = shown(registered["preview_params"](PAYLOAD))["application/json"]
    assert preview["status"] == "ok" and preview["yaml"].startswith("version: 1")
    assert {"summary", "notes", "warnings"} <= set(preview)
    from tests.conftest import ASSETS
    imp = shown(registered["process_pdb_upload"]({"pdb_content": (ASSETS / "pdb" / "prot_lig_dna.pdb").read_text(), "filename": "x.pdb"}))["application/json"]
    assert imp["status"] == "ok" and isinstance(imp["entities"], list) and imp["entities"] and isinstance(imp["ligands"], list)
    assert {"kind", "sequence", "ids", "length"} <= set(imp["entities"][0])
    lig = shown(registered["describe_ligand"](*CALLS["describe_ligand"]))["application/json"]
    assert lig["valid"] is True and lig["svg"].startswith("<svg") and "<?xml" not in lig["svg"] and lig["formula"] == "C9H8O4"


def test_json_safe_makes_any_reply_parseable():
    import numpy as np
    out = cb.json_safe({"a": (1, 2), "b": float("nan"), "c": {3}, "d": 1.5, "e": float("inf"), "f": np.float32(2.5), "g": np.int64(7),
                        1: "int key", "h": [None, True, "x"], "i": object})
    assert out["a"] == [1, 2] and out["b"] is None and out["c"] == [3] and out["e"] is None
    assert out["f"] == 2.5 and out["g"] == 7 and out["1"] == "int key" and isinstance(out["i"], str)
    json.dumps(out, allow_nan=False)
    assert not any(isinstance(v, float) and not math.isfinite(v) for v in out.values() if isinstance(v, float))


def test_a_callback_that_raises_surfaces_as_an_exception_not_an_empty_reply(registered):
    """Colab reports the exception to the page ({ename, evalue}); the wrapper must not swallow it into a blank JSON object."""
    def boom():
        raise ValueError("boom")
    wrapped = cb.as_json_reply(boom)
    with pytest.raises(ValueError, match="boom"):
        wrapped()
