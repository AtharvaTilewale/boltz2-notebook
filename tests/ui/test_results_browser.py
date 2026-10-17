"""Layout and behaviour of the live run panel, the result card, the report and the 3-D viewer in a real browser.

3Dmol itself needs WebGL, which headless CI browsers do not have, so the viewer is exercised against a small stub that
records the calls the page makes to the library.
"""
import re
import time

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from boltz2nb.analysis import load_job, summary_dict
from boltz2nb.report import build_report
from boltz2nb.ui.live import RunState, render_live, render_styles
from boltz2nb.ui.results import render_result_card

from .test_form_browser import open_framed

CTX = {"engine": "boltz-community 2.10.12", "gpu_name": "Tesla T4", "python": "3.12.12", "timestamp_utc": "2026-10-17T10:00:00+00:00",
       "command": ["boltz", "predict", "x.yaml"], "input_yaml": "version: 1\n"}
STUB_3DMOL = """<script>
window.__calls = [];
window.$3Dmol = {createViewer: function (el, opts) {
  window.__calls.push(['createViewer', opts.backgroundColor]);
  var v = {addModel: function (t, f) { window.__calls.push(['addModel', t.slice(0, 4), f]); },
           setStyle: function (sel, spec) { window.__calls.push(['setStyle', JSON.stringify(sel), Object.keys(spec).join(','), spec.cartoon && spec.cartoon.colorfunc ? spec.cartoon.colorfunc({b: 95}) + '|' + spec.cartoon.colorfunc({b: 40}) : (spec.cartoon && spec.cartoon.colorscheme) || '']); },
           zoomTo: function () { window.__calls.push(['zoomTo']); }, render: function () { window.__calls.push(['render']); }};
  return v; }};
</script>"""
THROWING_3DMOL = '<script>window.$3Dmol = {createViewer: function () { throw new TypeError("this._gl is null"); }};</script>'
CDN = '<script src="https://3Dmol.org/build/3Dmol-min.js"></script>'


def _strip_links(html: str) -> str:
    return re.sub(r"<link[^>]*>", "", html)


def _page(body: str, theme: str = "light") -> str:
    body = body.replace('data-theme="light"', f'data-theme="{theme}"')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>html,body{{margin:0}}body{{padding:12px}}</style></head><body>{_strip_links(body)}</body></html>')


@pytest.fixture(scope="module")
def parts(tmp_path_factory, example_pred_dir):
    job = load_job(example_pred_dir)
    summary = summary_dict(job)
    pdb = job.best.structure_path.read_text()
    live = RunState(job_name="kinase_aspirin", has_affinity=True, gpu="Tesla T4", engine="boltz-community 2.10.12", samples=3, command="boltz predict x.yaml")
    for line in ("Checking input data.", "Calling MSA server for target 0 with 1 sequences", "Running structure prediction for 1 input."):
        live.feed(line)
    failed = RunState(job_name="kinase_aspirin", has_affinity=False, gpu="Tesla T4")
    failed.feed("torch.OutOfMemoryError: CUDA out of memory")
    failed.finish(False, "GPU ran out of memory.", "Use fewer samples or a smaller MSA.")
    return {
        "live": render_styles() + render_live(live, standalone_css=False) + render_live(failed, uid="f", standalone_css=False),
        "card": render_result_card(summary, pdb, CTX, runtime=118),
        "report": build_report(job, {"models": {}}, CTX, None, runtime=118, fragment=True),
        "pdb": pdb, "dir": tmp_path_factory.mktemp("pages"),
    }


def open_page(driver, parts, html, name, width=1100, theme="light"):
    f = parts["dir"] / f"{name}.html"
    f.write_text(_page(html, theme))
    outer = parts["dir"] / f"{name}.frame.html"
    outer.write_text(f'<!doctype html><body style="margin:0"><iframe id="f" src="file://{f}" style="width:{width}px;height:100vh;border:0"></iframe></body>')
    open_framed(driver, f"file://{f}", f"file://{outer}", width, 900)
    return driver


OVERFLOW_JS = """
const root = document.querySelector('.bz'), rr = root.getBoundingClientRect(), bad = [];
root.querySelectorAll('*').forEach(function (el) {
  const up = el.parentElement;
  if (el.closest('svg') || el.closest('.bz-bar') || (up && (up.closest('.bz-table-wrap') || up.closest('pre')))) return;   // scroll containers may overflow internally; the bar animates in from outside
  const cs = getComputedStyle(el); if (cs.display === 'none' || cs.position === 'absolute') return;
  const r = el.getBoundingClientRect();
  if (r.width && (r.right > rr.right + 1 || r.left < rr.left - 1)) bad.push(el.tagName + '.' + String(el.className).slice(0, 36) + ' ' + Math.round(r.left - rr.left) + '..' + Math.round(r.right - rr.left) + ' of ' + Math.round(rr.width));
});
return {bad: bad.slice(0, 6), doc: document.documentElement.scrollWidth - window.innerWidth};
"""


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", [360, 414, 768, 1100])
@pytest.mark.parametrize("which", ["live", "card", "report"])
def test_no_overflow(driver, parts, which, width, theme):
    open_page(driver, parts, parts[which].replace(CDN, STUB_3DMOL), f"{which}-{width}-{theme}", width, theme)
    res = driver.execute_script(OVERFLOW_JS)
    assert res["doc"] <= 1, f"{which} scrolls sideways by {res['doc']}px at {width}px"
    assert not res["bad"], f"{which} @ {width}px {theme}: {res['bad']}"


def test_phase_tracker_stays_one_row_on_phones(driver, parts):
    open_page(driver, parts, parts["live"], "phases", 360)
    tops = driver.execute_script("return [...document.querySelectorAll('.bz-live:first-of-type .bz-phase')].map(e => Math.round(e.getBoundingClientRect().top))")
    assert len(tops) == 5 and len(set(tops)) == 1, tops


def test_tables_scroll_inside_their_wrapper_on_phones(driver, parts):
    open_page(driver, parts, parts["card"].replace(CDN, STUB_3DMOL), "scroll", 360)
    info = driver.execute_script("const w = document.querySelectorAll('.bz-table-wrap'); return [...w].map(e => [e.scrollWidth, e.clientWidth])")
    assert info and all(cw <= 360 for _, cw in info), info          # the wrapper never exceeds the 360 px viewport
    assert any(sw > cw for sw, cw in info), "expected at least one table to scroll inside its wrapper at 360px"


def test_viewer_drives_the_library(driver, parts):
    open_page(driver, parts, parts["card"].replace(CDN, STUB_3DMOL), "viewer", 1100)
    WebDriverWait(driver, 10).until(lambda d: d.execute_script("return window.__calls.some(c => c[0] === 'zoomTo')"))
    calls = driver.execute_script("return window.__calls")
    assert ["createViewer", "white"] in calls and ["addModel", "ATOM", "pdb"] in calls
    cartoon = [c for c in calls if c[0] == "setStyle" and "cartoon" in c[2]][-1]
    assert cartoon[1] == '{"hetflag":false}' and cartoon[3] == "#0053D6|#FF7D45"       # pLDDT 95 -> dark blue, 40 -> orange
    hets = [c for c in calls if c[0] == "setStyle" and c[1] == '{"hetflag":true}']
    assert hets and "stick" in hets[-1][2]
    n = len(calls)
    driver.find_element(By.CSS_SELECTOR, '.bz-viewer-bar input[value="chain"]').find_element(By.XPATH, "..").click()
    driver.find_element(By.CSS_SELECTOR, '.bz-viewer-bar input[value="line"]').find_element(By.XPATH, "..").click()
    time.sleep(0.2)
    later = driver.execute_script("return window.__calls")[n:]
    assert any(c[0] == "setStyle" and c[2] == "line" for c in later)
    assert any(c[0] == "setStyle" and c[2] == "cartoon" and c[3] == "chain" for c in later) or any(c[0] == "setStyle" and c[2] == "line" for c in later)
    m = len(driver.execute_script("return window.__calls"))
    driver.find_element(By.CSS_SELECTOR, 'button[id^="vr-"]').click()
    assert any(c[0] == "zoomTo" for c in driver.execute_script("return window.__calls")[m:])


def test_viewer_explains_missing_webgl(driver, parts):
    open_page(driver, parts, parts["card"].replace(CDN, THROWING_3DMOL), "nogl", 1100)
    WebDriverWait(driver, 10).until(lambda d: "no WebGL" in d.find_element(By.CSS_SELECTOR, ".bz-viewer").text)


def test_viewer_explains_offline(driver, parts):
    open_page(driver, parts, parts["card"].replace(CDN, ""), "offline", 1100)
    WebDriverWait(driver, 15).until(lambda d: "internet connection" in d.find_element(By.CSS_SELECTOR, ".bz-viewer").text)


def test_failed_run_shows_cause_and_fix(driver, parts):
    open_page(driver, parts, parts["live"], "failed", 1100)
    box = driver.find_elements(By.CSS_SELECTOR, ".bz-alert--err")
    assert box and "GPU ran out of memory." in box[0].text and "smaller MSA" in box[0].text
    assert any(c.text == "Failed" for c in driver.find_elements(By.CSS_SELECTOR, ".bz-chip--err"))
