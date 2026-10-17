"""Light is the default everywhere, every panel has a light / dark switch, and the choice is shared (no browser needed)."""
import json
import re
from pathlib import Path

import pytest

from boltz2nb.ui import callbacks as cb
from boltz2nb.ui.live import RunState, render_live, render_styles
from boltz2nb.ui.render import render_form
from boltz2nb.ui.results import render_report_document, render_report_fragment, render_result_card
from boltz2nb.ui.theme import DEFAULT_THEME, get_theme, reset_theme, resolve, set_theme, theme_attr, theme_button

ASSETS = Path(__file__).resolve().parents[2] / "boltz2nb" / "ui" / "assets"
CTX = {"engine": "boltz-community 2.10.12", "gpu_name": "Tesla T4", "timestamp_utc": "2026-10-17T10:00:00+00:00"}


@pytest.fixture(scope="module")
def summary(example_pred_dir):
    from boltz2nb.analysis import load_job, summary_dict
    return summary_dict(load_job(example_pred_dir))


def panels(summary, **kw):
    """Every panel the notebooks draw, rendered with the same arguments."""
    return {
        "form": render_form("advanced", uid="t", fonts=False, **kw),
        "live": render_live(RunState(job_name="j"), **kw),
        "card": render_result_card(summary, None, CTX, runtime=60, **kw),
        "report": render_report_fragment(summary, {"models": {}}, None, CTX, **kw),
    }


def test_default_is_light_and_there_is_no_os_following_mode(summary):
    assert DEFAULT_THEME == "light" == get_theme()
    for name, html in panels(summary).items():
        roots = re.findall(r'<div class="bz [^"]*"[^>]*data-theme="([a-z]+)"', html)
        assert roots == ["light"], (name, roots)
    # the stylesheet must not switch to dark just because the operating system prefers it
    assert "prefers-color-scheme" not in (ASSETS / "theme.css").read_text()


@pytest.mark.parametrize("which", ["form", "live", "card", "report"])
def test_every_panel_has_exactly_one_switch(summary, which):
    html = panels(summary)[which]
    buttons = re.findall(r'<button[^>]*data-act="theme"[^>]*>', html)
    assert len(buttons) == 1, buttons
    assert 'aria-label="Switch to dark theme"' in buttons[0] and 'title="Switch to dark theme"' in buttons[0]
    assert html.count('class="bz-ico bz-ico--moon"') == 1 and html.count('class="bz-ico bz-ico--sun"') == 1


def test_standalone_report_document_carries_the_switch_and_no_theme_hint(summary):
    doc = render_report_document(summary, {"models": {}}, None, {"engine": "e"}, None, 60)
    assert 'data-act="theme"' in doc and "__bzTheme" in doc                  # the switch and its script travel with the file
    assert re.search(r'<div class="bz bz-res bz-report">', doc), "the file must not pin a theme; the reader's choice is remembered"
    forced = render_report_document(summary, {"models": {}}, None, {"engine": "e"}, None, 60, theme="dark")
    assert 'bz-report" data-theme="dark"' in forced and "Switch to light theme" in forced


def test_run_panel_refreshes_leave_the_theme_to_the_page():
    state = RunState(job_name="j")
    first, refresh = render_live(state, standalone_css=False), render_live(state, standalone_css=False, hint=False)
    assert 'data-theme="light"' in first and "tellPython" in first                  # the first drawing carries the script
    assert "data-theme=" not in refresh and "tellPython" not in refresh             # a refresh must not undo a switch made mid-run
    assert "window.__bzTheme.apply()" in refresh and "tellPython" in render_styles() + first


def test_session_theme_flows_into_every_panel(summary):
    assert set_theme("dark") == "dark" == get_theme()
    for name, html in panels(summary).items():
        assert 'data-theme="dark"' in html and 'aria-label="Switch to light theme"' in html, name
    assert 'data-theme="light"' in panels(summary, theme="light")["card"]                  # an explicit argument wins
    reset_theme()
    assert get_theme() == "light"


def test_environment_variable_changes_the_default(monkeypatch):
    monkeypatch.setenv("BOLTZ2NB_THEME", "dark")
    assert get_theme() == "dark" and 'data-theme="dark"' in render_form(uid="t", fonts=False)
    set_theme("light")
    assert get_theme() == "light"                                                  # the user's switch beats the default
    monkeypatch.setenv("BOLTZ2NB_THEME", "neon")
    reset_theme()
    assert get_theme() == "light"                                                  # unknown values are ignored


@pytest.mark.parametrize("bad", ["auto", "", "Blue", None])
def test_invalid_themes_are_rejected(bad):
    with pytest.raises(ValueError):
        set_theme(bad)
    if bad is not None:
        with pytest.raises(ValueError):
            resolve(bad)


def test_theme_attr_and_button_helpers():
    assert theme_attr("dark") == ' data-theme="dark"' and theme_attr("dark", hint=False) == ""
    assert "Switch to light theme" in theme_button("dark") and "Switch to dark theme" in theme_button("light")


def test_set_theme_callback():
    assert cb.CALLBACKS["set_theme"]("dark") == {"status": "ok", "theme": "dark"} and get_theme() == "dark"
    res = cb.CALLBACKS["set_theme"]("neon")
    assert res["status"] == "error" and get_theme() == "dark"                      # a bad value changes nothing


def test_theme_script_is_valid_and_self_contained():
    esprima = pytest.importorskip("esprima")
    js = (ASSETS / "theme.js").read_text()
    esprima.parseScript(js)
    assert "@@" not in js and "http" not in js
    assert json.dumps(js)       # plain text
