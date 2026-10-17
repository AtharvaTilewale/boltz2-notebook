"""The form must start and respond however a notebook front-end inserts it into its output frame.

Colab, JupyterLab, VS Code and classic Jupyter each put cell output into the page differently: some assign innerHTML and
re-create the <script> tags (usually without copying their ids), some use document.write, some insert the script before
the markup it needs, and Colab output frames run in a sandboxed iframe with no kernel bridge until the kernel answers.
A form that depends on any one of those behaviours renders fine and then does nothing, so each is exercised here.
"""
import json
import time

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By

from boltz2nb.ui.render import render_form

UID = "emb12345"
SAME_ORIGIN = "allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
OPAQUE = "allow-scripts allow-forms allow-popups allow-modals"          # no allow-same-origin: opaque origin, no storage

COLLECT = "window.__errs=[];window.addEventListener('error',function(e){window.__errs.push(String(e.message))});"
INSERT = {
    # innerHTML, then each executable script is re-created from its text
    "inner": """var h=document.getElementById('out'); h.innerHTML=HTML;
        h.querySelectorAll('script').forEach(function(o){ if(!o.type||/javascript/.test(o.type)){
          var s=document.createElement('script'); s.text=o.textContent; o.parentNode.replaceChild(s,o);} });""",
    # every <script> re-created from type + text only (ids and other attributes are lost), as notebook renderers often do
    "reinsert": """var h=document.getElementById('out'); h.innerHTML=HTML;
        h.querySelectorAll('script').forEach(function(o){ var s=document.createElement('script'); s.type=o.type;
          s.textContent=o.textContent; h.appendChild(s); o.remove(); });""",
    "write": "document.open(); document.write('<!doctype html><body><scr'+'ipt>'+COLLECT_JS+'</scr'+'ipt><div id=out>'+HTML+'</div>'); document.close();",
    # markup parsed in a <template>, then the scripts appended afterwards
    "template": """var h=document.getElementById('out'); var t=document.createElement('template'); t.innerHTML=HTML; var frag=t.content;
        var cl=[].slice.call(frag.querySelectorAll('script')).map(function(o){return {type:o.type,text:o.textContent};});
        h.appendChild(frag);
        cl.forEach(function(c){ if(!c.type||/javascript/.test(c.type)){ var s=document.createElement('script'); s.text=c.text; h.appendChild(s);} });""",
    # the script runs first; the markup it needs arrives 600 ms later
    "late-markup": """var s=document.createElement('script'); s.text=JS; document.body.appendChild(s);
        setTimeout(function(){ document.getElementById('out').innerHTML=MARKUP; }, 600);""",
}
CASES = [("inner", SAME_ORIGIN), ("inner", OPAQUE), ("reinsert", SAME_ORIGIN), ("write", SAME_ORIGIN),
         ("template", SAME_ORIGIN), ("late-markup", SAME_ORIGIN)]


def open_embedded(driver, tmp_path, html, how, sandbox, wait_ready=True):
    def js_string(text):
        return json.dumps(text).replace("</", "<\\/")         # a literal </script> in a JS string would end the wrapper script

    start = html.find("<script>")                            # the markup has no script; the form's one script comes last
    if start < 0:                                            # markup only (a script that was dropped)
        start = len(html)
    else:
        assert html.endswith("</script>")
    payload = js_string(html)
    parts = f"var MARKUP={js_string(html[:start])}; var JS={js_string(html[start + 8:-9])};"
    inner = tmp_path / f"frame_{how}.html"
    inner.write_text("<!doctype html><meta charset=utf-8><body style='margin:8px'><div id=out></div><script>" + COLLECT
                     + "window.addEventListener('load',function(){ var COLLECT_JS=" + json.dumps(COLLECT)
                     + "; var HTML=" + payload + ";" + parts + INSERT[how] + "});</script>")
    outer = tmp_path / f"outer_{how}.html"
    outer.write_text(f"<!doctype html><body style='margin:0'><iframe id=f sandbox='{sandbox}' src='file://{inner}' "
                     "style='width:900px;height:1000px;border:0'></iframe>")
    driver.set_window_size(1000, 1100)
    driver.get(f"file://{outer}")
    driver.switch_to.frame("f")
    root = f"document.getElementById('bz-root-{UID}')"
    deadline = time.time() + (10 if wait_ready else 0)
    while time.time() < deadline and not driver.execute_script(f"var r={root}; return !!(r && r._bz)"):
        time.sleep(0.2)


def count(driver, sel):
    return len(driver.find_elements(By.CSS_SELECTOR, sel))


def theme(driver):
    return driver.execute_script("return document.querySelector('.bz').getAttribute('data-theme')")


@pytest.mark.parametrize("mode", ["standard", "advanced"])
@pytest.mark.parametrize("how,sandbox", CASES, ids=[f"{h}-{'opaque' if s == OPAQUE else 'same-origin'}" for h, s in CASES])
def test_form_responds_however_it_is_inserted(driver, tmp_path, mode, how, sandbox):
    open_embedded(driver, tmp_path, render_form(mode=mode, uid=UID, fonts=False), how, sandbox)
    try:
        assert driver.execute_script(f"var r=document.getElementById('bz-root-{UID}'); return !!(r && r._bz)"), \
            f"form did not start; errors: {driver.execute_script('return window.__errs')}"
        assert not count(driver, '[data-f="ui-problem"]'), driver.find_element(By.CSS_SELECTOR, '[data-f="ui-problem"]').text
        assert not count(driver, '[data-f="boot-note"]')

        before = count(driver, ".bz-entity")
        driver.find_element(By.CSS_SELECTOR, "[data-act=add-ligand]").click()
        assert count(driver, ".bz-entity") == before + 1

        t0 = theme(driver)
        driver.find_element(By.CSS_SELECTOR, "[data-act=theme]").click()
        assert theme(driver) != t0

        step = "var s=document.querySelector('.bz-step[aria-current=step]'); return s && s.dataset.go"
        s0 = driver.execute_script(step)
        driver.find_element(By.CSS_SELECTOR, "[data-act=next]").click()
        assert driver.execute_script(step) != s0
        assert not driver.execute_script("return window.__errs")
    finally:
        driver.switch_to.default_content()


def test_a_broken_part_is_reported_on_screen_and_the_rest_still_works(driver, tmp_path):
    """If one start-up step fails, the form says so (instead of looking fine and being dead) and keeps working."""
    html = render_form(mode="advanced", uid=UID, fonts=False).replace('data-r="max_msa_seqs"', 'data-r="renamed_by_test"')
    open_embedded(driver, tmp_path, html, "inner", SAME_ORIGIN)
    try:
        banner = driver.find_element(By.CSS_SELECTOR, '[data-f="ui-problem"]')
        assert banner.is_displayed()
        assert "did not start" in banner.text and "run settings" in banner.text
        before = count(driver, ".bz-entity")                      # the molecule list and the theme switch were not affected
        driver.find_element(By.CSS_SELECTOR, "[data-act=add-ligand]").click()
        assert count(driver, ".bz-entity") == before + 1
        t0 = theme(driver)
        driver.find_element(By.CSS_SELECTOR, "[data-act=theme]").click()
        assert theme(driver) != t0
    finally:
        driver.switch_to.default_content()


def test_a_failure_while_starting_is_reported_on_screen(driver, tmp_path):
    """A failure that stops the whole start-up (here: the root element has no step tracker) still produces a visible message."""
    html = render_form(mode="standard", uid=UID, fonts=False)
    # make the very first statement of start() throw by making its config unusable
    html = html.replace('var CFG = {', 'var CFG = null && {', 1) if 'var CFG = {' in html else html
    open_embedded(driver, tmp_path, html, "inner", SAME_ORIGIN)
    try:
        banner = driver.find_element(By.CSS_SELECTOR, '[data-f="ui-problem"]')
        assert banner.is_displayed() and "could not start" in banner.text
    finally:
        driver.switch_to.default_content()


def test_a_script_that_never_runs_explains_itself(driver, tmp_path):
    """If the output frame blocks or drops the script, no JavaScript can report it; the markup carries its own fallback text."""
    html = render_form(mode="standard", uid=UID, fonts=False)
    markup_only = html[:html.index("<script>")]
    open_embedded(driver, tmp_path, markup_only, "inner", SAME_ORIGIN, wait_ready=False)
    try:
        note = driver.find_element(By.CSS_SELECTOR, '[data-f="boot-note"]')
        assert not note.is_displayed() or note.size["height"] < 5       # quiet at first ...
        time.sleep(5)
        assert note.is_displayed() and note.size["height"] > 20          # ... then visible
        assert "has not started" in note.text
    finally:
        driver.switch_to.default_content()
