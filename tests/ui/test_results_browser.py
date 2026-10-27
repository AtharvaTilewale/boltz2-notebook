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

from boltz2nb.analysis import generate_plots, load_job, summary_dict
from boltz2nb.report import build_report
from boltz2nb.ui.live import RunState, render_live, render_styles
from boltz2nb.ui.results import render_result_card

from .test_form_browser import open_framed

CTX = {"engine": "boltz-community 2.10.12", "gpu_name": "Tesla T4", "python": "3.12.12", "timestamp_utc": "2026-10-17T10:00:00+00:00",
       "command": ["boltz", "predict", "x.yaml"], "input_yaml": "version: 1\n"}
STUB_JS = """
window.__calls = []; window.__atoms = [];
function parsePdb(text) {
  var lines = text.split('\\n'), nb = {};
  lines.forEach(function (l) {                                       // bonded neighbours per atom serial, from the CONECT records
    if (l.slice(0, 6) !== 'CONECT') { return; }
    var ids = (l.slice(6).match(/\\d+/g) || []).map(Number);
    ids.slice(1).forEach(function (o) { (nb[ids[0]] = nb[ids[0]] || {})[o] = 1; (nb[o] = nb[o] || {})[ids[0]] = 1; });
  });
  return lines.filter(function (l) { return /^(ATOM|HETATM)/.test(l); }).map(function (l) {
    var serial = parseInt(l.slice(6, 11), 10);
    return {hetflag: l.charAt(0) === 'H', atom: l.slice(12, 16).trim(), resn: l.slice(17, 20).trim(), chain: l.charAt(21), resi: parseInt(l.slice(22, 26), 10),
            elem: (l.slice(76, 78).trim() || l.slice(12, 14).trim()), b: parseFloat(l.slice(60, 66)), serial: serial, bonds: Object.keys(nb[serial] || {}).length,
            style: {}};
  });
}
function matches(a, sel) {
  return Object.keys(sel).every(function (k) {
    if (k === 'chain') { return [].concat(sel.chain).indexOf(a.chain) >= 0; }
    if (k === 'hetflag') { return a.hetflag === sel.hetflag; }
    if (k === 'bonds') { return a.bonds === sel.bonds; }
    return a[k] === sel[k];
  });
}
// what each chain ended up drawn as, e.g. {"A:ATOM": "cartoon", "B:HETATM": "stick"}
window.__drawn = function () { var o = {}; window.__atoms.forEach(function (a) { var k = a.chain + ':' + (a.hetflag ? 'HETATM' : 'ATOM'), st = Object.keys(a.style).sort().join('+') || 'none'; o[k] = o[k] === undefined || o[k] === st ? st : o[k] + '|' + st; }); return o; };
window.$3Dmol = {createViewer: function (el, opts) {
  window.__calls.push(['createViewer', opts.backgroundColor]);
  var v = {addModel: function (t, f) { window.__calls.push(['addModel', t.slice(0, 4), f]); window.__atoms = parsePdb(t); },
           setStyle: function (sel, spec) {
             window.__calls.push(['setStyle', JSON.stringify(sel), Object.keys(spec).join(','), spec.cartoon && spec.cartoon.colorfunc ? spec.cartoon.colorfunc({b: 95}) + '|' + spec.cartoon.colorfunc({b: 40}) : (spec.cartoon && spec.cartoon.colorscheme) || '']);
             window.__atoms.forEach(function (a) { if (matches(a, sel)) { a.style = spec; } }); },
           addStyle: function (sel, spec) { window.__calls.push(['addStyle', JSON.stringify(sel), Object.keys(spec).join(',')]); window.__atoms.forEach(function (a) { if (matches(a, sel)) { a.style = Object.assign({}, a.style, spec); } }); },
           zoomTo: function () { window.__calls.push(['zoomTo']); }, render: function () { window.__calls.push(['render']); },
           resize: function () { window.__calls.push(['resize']); },
           setHoverable: function (sel, on, show, hide) { window.__calls.push(['setHoverable', JSON.stringify(sel), on]); window.__hover = [show, hide]; },
           addLabel: function (text) { window.__calls.push(['addLabel', text]); return {text: text}; }, removeLabel: function () { window.__calls.push(['removeLabel']); }};
  if (!window.__noAtomList) { v.selectedAtoms = function () { return window.__atoms; }; }
  return v; }};
"""
STUB_3DMOL = f"<script>{STUB_JS}</script>"
STUB_WITHOUT_ATOM_LIST = f"<script>window.__noAtomList = true;{STUB_JS}</script>"
THROWING_3DMOL = '<script>window.$3Dmol = {createViewer: function () { throw new TypeError("this._gl is null"); }};</script>'
CDN = '<script src="https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js" onerror="window.BZ_3DMOL_CDN_FAILED=true"></script>'
# what a page without internet sees: the library tag fails (here: a file that does not exist)
DEAD_CDN = '<script src="file:///nonexistent/3Dmol-min.js" onerror="window.BZ_3DMOL_CDN_FAILED=true"></script>'


def _strip_links(html: str) -> str:
    return re.sub(r"<link[^>]*>", "", html)


def _page(body: str, theme: str = "light") -> str:
    body = body.replace('data-theme="light"', f'data-theme="{theme}"')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>html,body{{margin:0}}body{{padding:12px}}</style></head><body>{_strip_links(body)}</body></html>')


@pytest.fixture(scope="module")
def parts(tmp_path_factory, example_pred_dir, three_sample_dir):
    job = load_job(example_pred_dir)
    job3 = load_job(three_sample_dir)
    plots = generate_plots(job3, tmp_path_factory.mktemp("plots"))        # the report is checked with its real figures
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
        "report": build_report(job3, plots, CTX, None, runtime=118, fragment=True),
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
  if (el.closest('svg') || el.closest('.bz-bar') || (up && (up.closest('.bz-table-wrap') || up.closest('.bz-fig-img') || up.closest('pre')))) return;   // scroll containers (tables, figures on phones) may overflow internally; the bar animates in from outside
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
    assert cartoon[1] == '{"chain":["A"]}' and cartoon[3] == "#0053D6|#FF7D45"        # pLDDT 95 -> dark blue, 40 -> orange; the protein chain only
    hets = [c for c in calls if c[0] == "setStyle" and c[1] == '{"chain":["B"]}']
    assert hets and "stick" in hets[-1][2]
    assert driver.execute_script("return window.__drawn()") == {"A:ATOM": "cartoon", "B:HETATM": "stick"}
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
    """Both hosts fail: the viewer says so at once instead of waiting out the slow-connection allowance."""
    dead_fallback = "<script>window.BZ_3DMOL_FALLBACK = 'file:///nonexistent/fallback.js';</script>"
    t0 = time.time()
    open_page(driver, parts, parts["card"].replace(CDN, dead_fallback + DEAD_CDN), "offline", 1100)
    WebDriverWait(driver, 15).until(lambda d: "internet connection" in d.find_element(By.CSS_SELECTOR, ".bz-viewer").text)
    assert time.time() - t0 < 12


def _stub_file(parts, delay_ms=0):
    f = parts["dir"] / f"stub3dmol_{delay_ms}.js"
    f.write_text(STUB_JS if not delay_ms else "setTimeout(function () {" + STUB_JS + f"}}, {delay_ms});")
    return f"file://{f}"


def test_a_failing_cdn_switches_to_the_second_host_straight_away(driver, parts):
    fallback = f"<script>window.BZ_3DMOL_FALLBACK = '{_stub_file(parts)}';</script>"
    t0 = time.time()
    open_page(driver, parts, parts["card"].replace(CDN, fallback + DEAD_CDN), "fallback", 1100)
    WebDriverWait(driver, 10).until(lambda d: d.execute_script("return !!window.__calls && window.__calls.some(c => c[0] === 'zoomTo')"))
    assert time.time() - t0 < 4                                              # not after the 4 s wait meant for a slow first host
    assert driver.execute_script("return window.__drawn()") == {"A:ATOM": "cartoon", "B:HETATM": "stick"}


def test_a_slow_library_download_is_waited_for_with_a_note(driver, parts):
    """The library arrives after 6 s (the old viewer gave up after about 10 s; a slow Colab link can take longer)."""
    slow = f"<script src=\"{_stub_file(parts, 6000)}\"></script><script>window.BZ_3DMOL_FALLBACK = '';</script>"
    open_page(driver, parts, parts["card"].replace(CDN, slow), "slow", 1100)
    WebDriverWait(driver, 6).until(lambda d: "slow connection" in d.find_element(By.CSS_SELECTOR, ".bz-viewer").text)
    WebDriverWait(driver, 15).until(lambda d: d.execute_script("return !!window.__calls && window.__calls.some(c => c[0] === 'zoomTo')"))
    assert "internet connection" not in driver.find_element(By.CSS_SELECTOR, ".bz-viewer").text


def test_the_viewer_waits_until_its_box_is_laid_out(driver, parts):
    """An output frame can be sized after the script runs; a viewer created in a 0 x 0 box would draw nothing."""
    late = ('<div id="wrap" style="display:none">' + parts["card"].replace(CDN, STUB_3DMOL) + '</div>'
            '<script>setTimeout(function () { window.__shownAt = Date.now(); document.getElementById("wrap").style.display = ""; }, 1200);</script>')
    late = late.replace("window.__calls.push(['createViewer', opts.backgroundColor]);",
                        "window.__calls.push(['createViewer', opts.backgroundColor]); window.__createdAt = Date.now(); window.__boxAtCreate = [el.clientWidth, el.clientHeight];")
    open_page(driver, parts, late, "late", 1100)
    WebDriverWait(driver, 15).until(lambda d: d.execute_script("return window.__calls.some(c => c[0] === 'zoomTo')"))
    created, shown, box = driver.execute_script("return [window.__createdAt, window.__shownAt, window.__boxAtCreate]")
    assert created >= shown and box[0] > 0 and box[1] > 0, (created, shown, box)


def test_failed_run_shows_cause_and_fix(driver, parts):
    open_page(driver, parts, parts["live"], "failed", 1100)
    box = driver.find_elements(By.CSS_SELECTOR, ".bz-alert--err")
    assert box and "GPU ran out of memory." in box[0].text and "smaller MSA" in box[0].text
    assert any(c.text == "Failed" for c in driver.find_elements(By.CSS_SELECTOR, ".bz-chip--err"))


# ------------------------------------------------------------------------------------------------ what the viewer draws
def viewer_page(driver, parts, pdb_text, name, stub=STUB_3DMOL, fmt="pdb"):
    from boltz2nb.ui.results import render_viewer
    html = render_viewer(pdb_text, "u" + name, fmt)
    open_page(driver, parts, html.replace(CDN, stub), name, 1100)
    WebDriverWait(driver, 10).until(lambda d: d.execute_script("return window.__calls.some(c => c[0] === 'zoomTo')"))


def variant(pdb, how):
    lines = pdb.splitlines()
    if how == "all-hetatm":                                    # every record flagged as hetero
        return "\n".join("HETATM" + ln[6:] if ln.startswith("ATOM  ") else ln for ln in lines)
    if how == "ligand-as-atom":                                # the ligand flagged as a polymer atom
        return "\n".join("ATOM  " + ln[6:] if ln.startswith("HETATM") else ln for ln in lines)
    if how == "same-chain":                                    # the ligand written into the protein's chain
        return "\n".join(ln[:21] + "A" + ln[22:] if ln.startswith("HETATM") else ln for ln in lines)
    return pdb


@pytest.mark.parametrize(("how", "expected"), [
    ("as-written", {"A:ATOM": "cartoon", "B:HETATM": "stick"}),
    ("all-hetatm", {"A:HETATM": "cartoon", "B:HETATM": "stick"}),          # a file that flags every record as hetero is still a cartoon
    ("ligand-as-atom", {"A:ATOM": "cartoon", "B:ATOM": "stick"}),           # and a ligand flagged as polymer is still sticks
])
def test_cartoon_and_sticks_follow_the_atoms_not_the_record_type(driver, parts, how, expected):
    pdb = parts["pdb"]
    viewer_page(driver, parts, variant(pdb, how), "rec-" + how)
    assert driver.execute_script("return window.__drawn()") == expected


def test_a_ligand_written_into_the_protein_chain_does_not_break_the_protein_cartoon(driver, parts):
    viewer_page(driver, parts, variant(parts["pdb"], "same-chain"), "samechain")
    drawn = driver.execute_script("return window.__drawn()")
    assert set(drawn.values()) == {"cartoon"}, drawn                      # one chain, one polymer: all of it is a cartoon


def test_the_viewer_says_what_it_loaded(driver, parts):
    viewer_page(driver, parts, parts["pdb"], "info")
    text = driver.find_element(By.CSS_SELECTOR, ".bz-viewer-info").text
    assert "A protein, 585 residues" in text and "B ligand, 23 atoms" in text and "hover" in text


def test_the_pdb_file_name_extension_decides_the_format_passed_to_the_library(driver, parts):
    viewer_page(driver, parts, parts["pdb"], "fmt", fmt="cif")
    assert ["addModel", "ATOM", "cif"] in driver.execute_script("return window.__calls")


def test_hovering_reports_the_plddt_of_the_atom(driver, parts):
    viewer_page(driver, parts, parts["pdb"], "hover")
    label = driver.execute_script("""
      const show = window.__hover[0], atom = window.__atoms[10]; show(atom, window.__viewerStub || {addLabel: function (t) { window.__calls.push(['addLabel', t]); return {}; }});
      return window.__calls.filter(c => c[0] === 'addLabel').pop()[1];""")
    assert "pLDDT" in label and "(A)" in label


def test_the_viewer_refits_when_its_panel_changes_size(driver, parts):
    viewer_page(driver, parts, parts["pdb"], "resize")
    driver.execute_script("document.querySelector('.bz-viewer').style.height = '300px'")
    WebDriverWait(driver, 5).until(lambda d: d.execute_script("return window.__calls.some(c => c[0] === 'resize')"))


def test_a_viewer_library_that_cannot_list_atoms_still_gets_a_cartoon(driver, parts):
    viewer_page(driver, parts, parts["pdb"], "noatoms", stub=STUB_WITHOUT_ATOM_LIST)
    calls = driver.execute_script("return window.__calls")
    assert any(c[0] == "setStyle" and c[1] == '{"hetflag":false}' and "cartoon" in c[2] for c in calls)
    assert any(c[0] == "setStyle" and c[1] == '{"hetflag":true}' and "stick" in c[2] for c in calls)
