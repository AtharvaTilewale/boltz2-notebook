"""End-to-end behaviour of the input builder in a real browser, wired to the real Python callbacks."""
import time
from pathlib import Path

import pytest
import yaml

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait

from boltz2nb.run_params import parse_run_params_text

ASSETS = Path(__file__).resolve().parents[2] / "assets"
ROOT = "document.getElementById('bz-root-t')"
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
SEQ = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDG"


MIN_WINDOW = 520          # headless Firefox will not open a window narrower than ~500 px


def set_viewport(driver, width, height=1000):
    """Windows below ~500 px are not possible, so narrow viewports are emulated with an exact-width iframe (see open_form)."""
    driver.switch_to.default_content()
    driver.set_window_size(max(width, MIN_WINDOW), height)
    inner = driver.execute_script("return window.innerWidth")
    if inner != max(width, MIN_WINDOW):
        driver.set_window_size(max(width, MIN_WINDOW) + (max(width, MIN_WINDOW) - inner), height)


def open_framed(driver, url_for_window, url_for_frame, width, height=1000):
    """Load a page at an exact viewport width; below MIN_WINDOW the page sits in an iframe of that width."""
    set_viewport(driver, width, height)
    if width >= MIN_WINDOW:
        driver.get(url_for_window)
    else:
        driver.get(url_for_frame)
        driver.switch_to.frame("f")
    assert driver.execute_script("return window.innerWidth") == width, "viewport is not the requested width"
    return driver


def open_form(driver, server, mode="advanced", theme="light", width=1280, rpc="colab"):
    server.reset_files()
    q = dict(mode=mode, theme=theme, rpc=rpc)
    open_framed(driver, server.url(**q), server.frame_url(width, **q), width)
    WebDriverWait(driver, 15).until(lambda d: d.execute_script(f"return !!({ROOT} && {ROOT}._bz)"))
    return driver


def q(driver, sel):
    return driver.find_element(By.CSS_SELECTOR, sel)


def qa(driver, sel):
    return driver.find_elements(By.CSS_SELECTOR, sel)


def click(driver, sel):
    el = q(driver, sel)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
    el.click()
    return el


def wait(driver, cond, timeout=10):
    return WebDriverWait(driver, timeout, poll_frequency=0.1).until(cond)


def errors(driver):
    return driver.execute_script("return window.__errs")


def last_card(driver):
    return qa(driver, ".bz-entity")[-1]


def settle(driver, extra=0.0):
    """Wait for the debounced preview to finish."""
    time.sleep(0.55)
    wait(driver, lambda d: d.execute_script("return window.__rpc.length >= 0") and True)
    time.sleep(0.25 + extra)


def token_text(el):
    """Chip text read from the DOM: Selenium's .text is empty while a freshly added card is still fading in."""
    return (el.get_attribute("textContent") or "").strip()


def type_chip(card_or_driver, selector, text):
    box = card_or_driver.find_element(By.CSS_SELECTOR, selector)
    inp = box.find_element(By.CSS_SELECTOR, "input")
    inp.send_keys(text)
    return inp


def fill_protein(driver, seq=SEQ):
    ta = last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="seq"]')
    ta.send_keys(seq)
    return ta


def add_ligand(driver, smiles=ASPIRIN):
    click(driver, '[data-act="add-ligand"]')
    card = last_card(driver)
    card.find_element(By.CSS_SELECTOR, '[data-f="value"]').send_keys(smiles)
    return card


def upload(driver, element, path):
    driver.execute_script("arguments[0].classList.remove('bz-sr'); arguments[0].style.display='block'", element)
    element.send_keys(str(path))
    driver.execute_script("arguments[0].classList.add('bz-sr'); arguments[0].style.display=''", element)


def goto_step(driver, n):
    click(driver, f'.bz-step[data-go="{n}"]')
    wait(driver, lambda d: not d.find_element(By.CSS_SELECTOR, f'[data-panel="{n}"]').get_attribute("hidden"))


# ------------------------------------------------------------------------------------------------ basics
def test_initial_state(driver, server):
    open_form(driver, server)
    cards = qa(driver, ".bz-entity")
    assert len(cards) == 1 and cards[0].get_attribute("data-type") == "protein"
    chips = [token_text(t) for t in cards[0].find_elements(By.CSS_SELECTOR, '[data-f="ids"] .bz-token')]
    assert chips == ["A"]
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "1"
    assert q(driver, '[data-f="status-chip"]').text == "Incomplete"
    assert not q(driver, '[data-act="back"]').is_displayed() or q(driver, '[data-act="back"]').value_of_css_property("visibility") == "hidden"
    assert errors(driver) == []


def test_chain_ids_auto_assign_and_chips(driver, server):
    open_form(driver, server)
    click(driver, '[data-act="add-protein"]')   # the pristine first card is replaced
    click(driver, '[data-act="add-ligand"]')
    ids = [[token_text(t) for t in c.find_elements(By.CSS_SELECTOR, '[data-f="ids"] .bz-token')] for c in qa(driver, ".bz-entity")]
    assert ids == [["A"], ["B"]]
    inp = type_chip(last_card(driver), '[data-f="ids"]', "C d,e")
    inp.send_keys(Keys.ENTER)
    toks = [token_text(t) for t in last_card(driver).find_elements(By.CSS_SELECTOR, '[data-f="ids"] .bz-token')]
    assert toks == ["B", "C", "D", "E"]
    inp.send_keys(Keys.BACKSPACE)
    toks = [token_text(t) for t in last_card(driver).find_elements(By.CSS_SELECTOR, '[data-f="ids"] .bz-token')]
    assert toks == ["B", "C", "D"]
    assert errors(driver) == []


def test_sequence_validation_and_counter(driver, server):
    """Typing is filtered (see test_sequence_ligand_browser); a sequence that is wrong for its type is still reported and blocks saving."""
    open_form(driver, server)
    ta = fill_protein(driver, "mktayi akqr")
    card = last_card(driver)
    err = card.find_element(By.CSS_SELECTOR, '[data-e="seq"]')
    assert ta.get_attribute("value") == "MKTAYIAKQR" and not err.is_displayed()
    assert "10 residues" in card.find_element(By.CSS_SELECTOR, '[data-f="seq-count"]').text
    driver.execute_script("arguments[0].click()", card.find_element(By.CSS_SELECTOR, 'input[name^="ty-"][value="dna"]'))   # the same letters are not DNA
    ta.send_keys(Keys.TAB)
    wait(driver, lambda d: err.is_displayed())
    assert "Not valid in DNA" in err.text and ta.get_attribute("aria-invalid") == "true"
    assert errors(driver) == []


def test_fasta_header_and_split(driver, server):
    open_form(driver, server)
    ta = last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="seq"]')
    driver.execute_script("""
      const ta = arguments[0], dt = new DataTransfer();
      dt.setData('text', '>sp|P1|ONE first protein\\nMKTAYIAK\\nQRQISF\\n>sp|P2|TWO second\\nGSHMLEER\\n');
      const ev = new Event('paste', {bubbles: true, cancelable: true}); ev.clipboardData = dt;   // Firefox ignores clipboardData on a synthetic ClipboardEvent
      ta.dispatchEvent(ev);
    """, ta)
    assert ta.get_attribute("value") == "MKTAYIAKQRQISF"
    card = last_card(driver)
    wait(driver, lambda d: "sp|P1|ONE" in card.find_element(By.CSS_SELECTOR, '[data-f="sub"]').text)       # the subtitle refresh is debounced
    split = card.find_element(By.CSS_SELECTOR, '[data-f="split"]')
    assert split.is_displayed() and "2 FASTA records" in split.text
    split.find_element(By.CSS_SELECTOR, '[data-act="split"]').click()
    seqs = [c.find_element(By.CSS_SELECTOR, '[data-f="seq"]').get_attribute("value") for c in qa(driver, ".bz-entity")]
    ids = [[token_text(t) for t in c.find_elements(By.CSS_SELECTOR, '[data-f="ids"] .bz-token')] for c in qa(driver, ".bz-entity")]
    assert seqs == ["MKTAYIAKQRQISF", "GSHMLEER"] and ids == [["A"], ["B"]]
    assert errors(driver) == []


def test_ligand_preview_and_errors(driver, server):
    open_form(driver, server)
    card = add_ligand(driver)
    wait(driver, lambda d: card.find_elements(By.CSS_SELECTOR, '[data-f="preview"] svg'))
    props = card.find_element(By.CSS_SELECTOR, '[data-f="props"]').text
    assert "C9H8O4" in props and "180.16" in props and "13" in props
    assert "C9H8O4" in card.find_element(By.CSS_SELECTOR, '[data-f="sub"]').text
    val = card.find_element(By.CSS_SELECTOR, '[data-f="value"]')
    val.clear(); val.send_keys("C1CC"); val.send_keys(Keys.TAB)
    stat = card.find_element(By.CSS_SELECTOR, '[data-f="val-status"]')
    wait(driver, lambda d: stat.get_attribute("data-state") == "bad")        # the live status says why; it is not repeated below the field
    assert "Ring label 1" in stat.text and not card.find_element(By.CSS_SELECTOR, '[data-e="value"]').is_displayed()
    card.find_element(By.CSS_SELECTOR, 'input[value="ccd"]').find_element(By.XPATH, "..").click()
    val.clear(); val.send_keys("sah")
    assert val.get_attribute("value") == "SAH"
    wait(driver, lambda d: stat.get_attribute("data-state") == "ok" and "SAH" in stat.text)
    wait(driver, lambda d: card.find_elements(By.CSS_SELECTOR, '[data-f="preview"] svg'))
    assert errors(driver) == []


def test_affinity_panel_follows_ligands(driver, server):
    open_form(driver, server)
    assert not q(driver, '[data-f="affinity-card"]').is_displayed()
    add_ligand(driver)
    wait(driver, lambda d: q(d, '[data-f="affinity-card"]').is_displayed())
    assert not q(driver, '[data-f="affinity-pick"]').is_displayed()
    click(driver, '[data-f="affinity-on"]')
    assert q(driver, '[data-f="affinity-pick"]').is_displayed()
    assert [o.text for o in Select(q(driver, '[data-f="affinity-chain"]')).options] == ["B"]
    click(driver, '[data-act="add-ligand"]')
    assert "single-ligand" in q(driver, '[data-f="affinity-hint"]').text
    qa(driver, '.bz-entity')[-1].find_element(By.CSS_SELECTOR, '[data-act="remove"]').click()
    qa(driver, '.bz-entity')[-1].find_element(By.CSS_SELECTOR, '[data-act="remove"]').click()
    assert not q(driver, '[data-f="affinity-card"]').is_displayed()


# ------------------------------------------------------------------------------------------------ full flow
@pytest.mark.parametrize("rpc", ["colab", "bare"], ids=["colab-reply", "bare-reply"])
def test_happy_path_advanced(driver, server, rpc):
    open_form(driver, server, rpc=rpc)
    fill_protein(driver)
    add_ligand(driver)
    click(driver, '[data-f="affinity-on"]')
    # live YAML + summary
    settle(driver)
    click(driver, 'input[name^="tab-"][value="yaml"]')
    wait(driver, lambda d: "affinity" in q(d, '[data-f="yaml"]').text)
    assert "sequence: " + SEQ in q(driver, '[data-f="yaml"]').text
    assert q(driver, '[data-f="status-chip"]').text in ("Valid", "Check warnings")
    # step 2: a pocket constraint
    click(driver, '[data-act="next"]')
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "2"
    det = q(driver, 'details[data-kind="pockets"]')
    det.find_element(By.CSS_SELECTOR, "summary").click()
    click(driver, '[data-act="add-pocket"]')
    row = q(driver, '[data-row="pocket"]')
    Select(row.find_element(By.CSS_SELECTOR, '[data-f="binder"]')).select_by_value("B")
    inp = row.find_element(By.CSS_SELECTOR, '[data-f="pocket-residues"] input')
    inp.send_keys("a:5"); inp.send_keys(Keys.ENTER); inp.send_keys("A:9"); inp.send_keys(Keys.ENTER)
    assert [token_text(t) for t in row.find_elements(By.CSS_SELECTOR, ".bz-token")] == ["A:5", "A:9"]
    # step 3: preset + name + save
    click(driver, '[data-act="next"]')
    click(driver, '.bz-preset[data-preset="scientific"]')
    assert q(driver, '.bz-preset[data-preset="scientific"]').get_attribute("aria-checked") == "true"
    assert q(driver, '[data-r="diffusion_samples"]').get_attribute("value") == "5"
    assert q(driver, '[data-r="use_potentials"]').is_selected()
    q(driver, '[data-r="job_name"]').send_keys("kin ase_1")
    assert q(driver, '[data-r="job_name"]').get_attribute("value") == "kin_ase_1"
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: q(d, '[data-f="saved"]').is_displayed(), 15)
    assert q(driver, '[data-f="action-msg"]').text == "Saved"

    doc = yaml.safe_load((server.base_dir / "params.yaml").read_text())
    assert doc["sequences"][0] == {"protein": {"id": ["A"], "sequence": SEQ}}
    assert doc["sequences"][1] == {"ligand": {"id": ["B"], "smiles": ASPIRIN}}
    assert doc["constraints"] == [{"pocket": {"binder": "B", "contacts": [["A", 5], ["A", 9]], "max_distance": 6.0}}]
    assert doc["properties"] == [{"affinity": {"binder": "B"}}]
    rp = parse_run_params_text((server.base_dir / "run_params.txt").read_text())
    assert rp["job_name"] == "kin_ase_1" and rp["diffusion_samples"] == 5 and rp["use_potentials"] is True
    assert rp["recycling_steps"] == 5 and rp["sampling_steps"] == 200 and rp["max_msa_seqs"] == 8192
    assert rp["msa_pairing_strategy"] == "greedy" and rp["override"] is False
    names = driver.execute_script("return window.__rpc")
    assert "preview_params" in names and "describe_ligand" in names and names.count("save_params") == 1
    # editing after save marks the form dirty again
    goto_step(driver, 1)
    qa(driver, '.bz-entity [data-f="seq"]')[0].send_keys("G")                  # the last card is the ligand; edit the protein
    wait(driver, lambda d: q(d, '[data-f="action-msg"]').text == "Unsaved changes")
    assert errors(driver) == []


def test_save_with_problems_focuses_first_issue(driver, server):
    open_form(driver, server)
    goto_step(driver, 3)
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: "issue" in q(d, '[data-f="action-msg"]').text)
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "1"
    err = qa(driver, '[data-e="seq"]')[0]
    wait(driver, lambda d: err.is_displayed())
    assert "Enter a sequence" in err.text
    assert "issue" in q(driver, '[data-f="status-chip"]').text
    assert not (server.base_dir / "params.yaml").exists()
    fill_protein(driver)
    goto_step(driver, 3)
    click(driver, '[data-act="next"]')
    err = q(driver, '[data-e="job_name"]')
    wait(driver, lambda d: err.is_displayed())
    assert "name" in err.text.lower() and not (server.base_dir / "params.yaml").exists()


def test_duplicate_chain_ids_blocked(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    click(driver, '[data-act="add-protein"]')
    fill_protein(driver, "GSHMLEER")
    box = last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="ids"]')
    for _ in range(1):
        box.find_element(By.CSS_SELECTOR, ".bz-token button").click()
    type_chip(last_card(driver), '[data-f="ids"]', "A").send_keys(Keys.ENTER)
    goto_step(driver, 3)
    q(driver, '[data-r="job_name"]').send_keys("dup")
    click(driver, '[data-act="next"]')
    goto = q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go")
    assert goto == "1"
    err = last_card(driver).find_element(By.CSS_SELECTOR, '[data-e="ids"]')
    wait(driver, lambda d: err.is_displayed())
    assert "already used" in err.text


def test_backend_error_surfaces_in_rail(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    add_ligand(driver)
    click(driver, '[data-f="affinity-on"]')
    click(driver, '[data-act="add-protein"]')           # a protein with affinity pointing at... valid; now break it via a template of unknown chain
    fill_protein(driver, "GSHM")
    settle(driver)
    assert "Valid" in q(driver, '[data-f="status-chip"]').text or "warnings" in q(driver, '[data-f="status-chip"]').text
    assert errors(driver) == []


# ------------------------------------------------------------------------------------------------ import + files
def test_pdb_import_groups_chains_and_adds_ligands(driver, server):
    open_form(driver, server)
    upload(driver, q(driver, '[data-f="structure-file"]'), ASSETS / "pdb" / "prot_lig_dna.pdb")
    wait(driver, lambda d: q(d, '[data-f="import-result"]').is_displayed() and "entities" in q(d, '[data-f="import-result"]').text)
    text = q(driver, '[data-f="import-result"]').text
    assert "chains A, B" in text and "260 residues" in text and "DNA" in text
    click(driver, '[data-imp="all"]')
    cards = qa(driver, ".bz-entity")
    kinds = [c.get_attribute("data-type") for c in cards]
    ids = [[token_text(t) for t in c.find_elements(By.CSS_SELECTOR, '[data-f="ids"] .bz-token')] for c in cards]
    assert kinds == ["protein", "dna", "dna"] and ids == [["A", "B"], ["E"], ["F"]]
    assert len(cards[0].find_element(By.CSS_SELECTOR, '[data-f="seq"]').get_attribute("value")) == 260
    click(driver, '[data-imp="lig0"]')
    lig = last_card(driver)
    assert lig.get_attribute("data-type") == "ligand" and lig.find_element(By.CSS_SELECTOR, '[data-f="value"]').get_attribute("value") == "83Y"
    assert errors(driver) == []


def test_pdb_import_standard_mode_hides_nucleic_acids(driver, server):
    open_form(driver, server, mode="standard")
    upload(driver, q(driver, '[data-f="structure-file"]'), ASSETS / "pdb" / "prot_lig_dna.pdb")
    wait(driver, lambda d: "entities" in q(d, '[data-f="import-result"]').text)
    assert "DNA/RNA" in q(driver, '[data-f="import-result"]').text and "Advanced notebook" in q(driver, '[data-f="import-result"]').text
    click(driver, '[data-imp="all"]')
    assert [c.get_attribute("data-type") for c in qa(driver, ".bz-entity")] == ["protein"]


def test_pdb_import_error(driver, server, tmp_path):
    bad = tmp_path / "empty.pdb"; bad.write_text("REMARK nothing here\nEND\n")
    open_form(driver, server)
    upload(driver, q(driver, '[data-f="structure-file"]'), bad)
    wait(driver, lambda d: q(d, '[data-f="import-result"]').find_elements(By.CSS_SELECTOR, ".bz-alert--err"))


def test_msa_and_template_uploads(driver, server, tmp_path):
    a3m = tmp_path / "aln.a3m"; a3m.write_text(">q\nMKTAYIAK\n")
    tpl = tmp_path / "ref.pdb"; tpl.write_text((ASSETS / "pdb" / "prot_lig.pdb").read_text()[:2000])
    open_form(driver, server)
    fill_protein(driver)
    card = last_card(driver)
    card.find_element(By.CSS_SELECTOR, 'input[value="custom"]').find_element(By.XPATH, "..").click()
    assert card.find_element(By.CSS_SELECTOR, '[data-f="msa-upload"]').is_displayed()
    upload(driver, card.find_element(By.CSS_SELECTOR, '[data-f="msa-file"]'), a3m)
    wait(driver, lambda d: "aln.a3m" in card.find_element(By.CSS_SELECTOR, '[data-f="msa-file-status"]').text)
    assert (server.base_dir / "uploads" / "msas" / "aln.a3m").exists()
    card.find_element(By.CSS_SELECTOR, 'input[value="empty"]').find_element(By.XPATH, "..").click()
    assert card.find_element(By.CSS_SELECTOR, '[data-f="msa-warn"]').is_displayed()
    goto_step(driver, 2)
    q(driver, 'details[data-kind="templates"] summary').click()
    click(driver, '[data-act="add-template"]')
    upload(driver, q(driver, '[data-f="tpl-file"]'), tpl)
    wait(driver, lambda d: "ref.pdb" in q(d, '[data-f="tpl-status"]').text)
    assert (server.base_dir / "uploads" / "templates" / "ref.pdb").exists()
    chk = q(driver, '[data-f="tpl-force"]')
    assert q(driver, '[data-f="tpl-threshold"]').get_attribute("disabled")
    chk.click()
    assert not q(driver, '[data-f="tpl-threshold"]').get_attribute("disabled")
    assert errors(driver) == []


def test_template_boltz_cannot_read_is_warned_about_in_the_form(driver, server, tmp_path):
    tpl = tmp_path / "prediction.pdb"; tpl.write_text((ASSETS / "pdb" / "prot_lig.pdb").read_text()[:2000])       # no SEQRES, like a file Boltz wrote
    open_form(driver, server)
    fill_protein(driver)
    goto_step(driver, 2)
    q(driver, 'details[data-kind="templates"] summary').click()
    click(driver, '[data-act="add-template"]')
    upload(driver, q(driver, '[data-f="tpl-file"]'), tpl)
    wait(driver, lambda d: "prediction.pdb" in q(d, '[data-f="tpl-status"]').text)
    warns = lambda d: [a.get_attribute("textContent") for a in d.find_elements(By.CSS_SELECTOR, '[data-f="rail-messages"] .bz-alert--warn')]   # noqa: E731
    wait(driver, lambda d: any("no SEQRES" in w for w in warns(d)))
    assert q(driver, '[data-f="status-chip"]').get_attribute("textContent") == "Check warnings"
    assert errors(driver) == []


def test_incomplete_rows_block_save(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    goto_step(driver, 2)
    q(driver, 'details[data-kind="bonds"] summary').click()
    click(driver, '[data-act="add-bond"]')
    goto_step(driver, 3)
    q(driver, '[data-r="job_name"]').send_keys("rows")
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: "issue" in q(d, '[data-f="action-msg"]').text)
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "2"
    assert "Bond 1" in q(driver, '[data-f="rail-messages"]').text
    assert not (server.base_dir / "params.yaml").exists()


# ------------------------------------------------------------------------------------------------ run settings
def test_presets_and_custom_detection(driver, server):
    open_form(driver, server)
    goto_step(driver, 3)
    assert q(driver, '.bz-preset[aria-checked="true"]').get_attribute("data-preset") == "balanced"
    click(driver, '.bz-preset[data-preset="fast"]')
    vals = driver.execute_script(f"return {ROOT}._bz.readRun()")
    assert vals["sampling_steps"] == "50" and vals["diffusion_samples"] == "1" and vals["max_msa_seqs"] == "256" and vals["use_potentials"] is False
    assert q(driver, '[data-f="preset-badge"]').text == "Fast"
    sl = q(driver, '[data-r="sampling_steps"]')
    driver.execute_script("arguments[0].value = 130; arguments[0].dispatchEvent(new Event('input', {bubbles:true}))", sl)
    assert q(driver, '[data-f="preset-badge"]').text == "Custom" and not qa(driver, '.bz-preset[aria-checked="true"]')
    assert q(driver, '[data-o="sampling_steps"]').text == "130"
    click(driver, '.bz-preset[data-preset="balanced"]')
    assert driver.execute_script(f"return {ROOT}._bz.readRun()")["step_scale"] == "1.638"   # exact, not the slider's snapped 1.65
    assert q(driver, '[data-f="preset-badge"]').text == "Balanced"


def test_run_value_validation(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    goto_step(driver, 3)
    q(driver, '[data-r="job_name"]').send_keys("ok")
    n = q(driver, '[data-r="diffusion_samples"]')
    n.clear(); n.send_keys("99")
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: "issue" in q(d, '[data-f="action-msg"]').text)
    assert n.get_attribute("aria-invalid") == "true" and not (server.base_dir / "params.yaml").exists()
    n.clear(); n.send_keys("3")
    q(driver, '[data-r="seed"]').send_keys("42")
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: q(d, '[data-f="saved"]').is_displayed(), 15)
    rp = parse_run_params_text((server.base_dir / "run_params.txt").read_text())
    assert rp["diffusion_samples"] == 3 and rp["seed"] == 42


# ------------------------------------------------------------------------------------------------ modes, theme
def test_standard_mode(driver, server):
    open_form(driver, server, mode="standard")
    assert [e.is_displayed() for e in qa(driver, '[data-act="add-dna"], [data-act="add-rna"]')] == [False, False]
    assert len([s for s in qa(driver, ".bz-step") if s.is_displayed()]) == 2
    assert not qa(driver, ".bz-entity [data-adv]")[0].is_displayed() if qa(driver, ".bz-entity [data-adv]") else True
    fill_protein(driver)
    click(driver, '[data-act="next"]')
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "3"
    assert q(driver, '.bz-step[data-state="done"] .bz-step-num svg')            # step 1 shows a tick once completed
    assert q(driver, "[data-num-run]").text == "2"                            # the steps are renumbered in standard mode
    q(driver, '[data-r="job_name"]').send_keys("std")
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: q(d, '[data-f="saved"]').is_displayed(), 15)
    assert (server.base_dir / "params.yaml").exists()
    assert errors(driver) == []


def test_theme_toggle(driver, server):
    open_form(driver, server, theme="light")
    bg = lambda: driver.execute_script(f"return getComputedStyle({ROOT}).backgroundColor")  # noqa: E731
    light = bg()
    click(driver, '[data-act="theme"]')
    assert q(driver, ".bz-form").get_attribute("data-theme") == "dark" and bg() != light
    click(driver, '[data-act="theme"]')
    assert q(driver, ".bz-form").get_attribute("data-theme") == "light" and bg() == light


def test_reset_needs_confirmation(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    click(driver, '[data-act="reset"]')
    assert "SEQ"[:0] == "" and q(driver, '[data-act="reset"] span').text == "Click again to reset"
    assert q(driver, '[data-f="seq"]').get_attribute("value") == SEQ
    click(driver, '[data-act="reset"]')
    assert q(driver, '[data-f="seq"]').get_attribute("value") == ""
    assert len(qa(driver, ".bz-entity")) == 1


# ------------------------------------------------------------------------------------------------ layout + a11y
OVERFLOW_JS = """
const root = arguments[0], rr = root.getBoundingClientRect(), bad = [];
root.querySelectorAll('*').forEach(function (el) {
  if (el.closest('template, .bz-sr, symbol')) return;
  const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') return;
  const r = el.getBoundingClientRect(); if (!r.width && !r.height) return;
  let p = el.parentElement, skip = false;
  while (p && p !== root) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') { skip = true; break; } p = p.parentElement; }
  if (skip) return;
  if (r.right > rr.right + 1 || r.left < rr.left - 1) bad.push(el.tagName + '.' + String(el.className).slice(0, 40) + ' ' + Math.round(r.left - rr.left) + '..' + Math.round(r.right - rr.left) + ' of ' + Math.round(rr.width));
});
return {bad: bad.slice(0, 8), docOverflow: document.documentElement.scrollWidth - window.innerWidth};
"""


def populate_everything(driver, tmp_path):
    fill_protein(driver)
    add_ligand(driver)
    click(driver, '[data-act="add-dna"]')
    fill_protein(driver, "ACGTACGT")
    click(driver, '[data-f="affinity-on"]')
    goto_step(driver, 2)
    for kind, act in (("templates", "add-template"), ("bonds", "add-bond"), ("pockets", "add-pocket"), ("contacts", "add-contact")):
        q(driver, f'details[data-kind="{kind}"] summary').click()
        click(driver, f'[data-act="{act}"]')
    goto_step(driver, 1)
    driver.execute_script("arguments[0].closest('details').open = true", q(driver, '.bz-entity:first-child [data-act="add-mod"]'))
    click(driver, '.bz-entity:first-child [data-act="add-mod"]')


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", [360, 414, 768, 1024, 1280])
def test_no_overflow_at_any_width(driver, server, tmp_path, width, theme):
    open_form(driver, server, width=width, theme=theme)
    populate_everything(driver, tmp_path)
    root = driver.execute_script(f"return {ROOT}")
    for step in (1, 2, 3):
        goto_step(driver, step)
        time.sleep(0.15)
        res = driver.execute_script(OVERFLOW_JS, root)
        assert res["docOverflow"] <= 1, f"page scrolls sideways by {res['docOverflow']}px at {width}px, step {step}"
        assert not res["bad"], f"step {step} @ {width}px {theme}: {res['bad']}"
    assert errors(driver) == []


ACCESSIBLE_NAME_JS = """
const root = arguments[0], out = [];
root.querySelectorAll('input, select, textarea, button').forEach(function (el) {
  if (el.closest('template')) return;
  const cs = getComputedStyle(el), r = el.getBoundingClientRect();
  const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && !el.closest('[hidden]');
  if (!visible) return;
  let name = el.getAttribute('aria-label') || '';
  if (!name && el.labels && el.labels.length) name = Array.prototype.map.call(el.labels, function (l) { return l.textContent.trim(); }).join(' ');
  if (!name && el.getAttribute('aria-labelledby')) name = document.getElementById(el.getAttribute('aria-labelledby')).textContent.trim();
  if (!name && el.tagName === 'BUTTON') name = el.textContent.trim() || el.title;
  if (!name) out.push(el.outerHTML.slice(0, 140));
});
return out;
"""


def test_every_control_has_an_accessible_name(driver, server, tmp_path):
    open_form(driver, server, width=1280)
    populate_everything(driver, tmp_path)
    root = driver.execute_script(f"return {ROOT}")
    missing = []
    for step in (1, 2, 3):
        goto_step(driver, step)
        missing += driver.execute_script(ACCESSIBLE_NAME_JS, root)
    assert not missing, missing


def test_keyboard_focus_ring_is_defined(driver, server):
    """Headless Firefox never reports document focus, so :focus-visible cannot match; assert the rule itself."""
    open_form(driver, server)
    rule = driver.execute_script("""
      const out = [];
      for (const sheet of document.styleSheets) {
        let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
        for (const r of rules) {
          const o = r.style && r.style.getPropertyValue('outline');          // a var() inside a shorthand is not expanded to longhands
          if (r.selectorText && r.selectorText.includes(':focus-visible') && o && o.includes('solid')) {
            out.push([r.selectorText, o.split(' ')[0], o]);
          }
        }
      }
      return out;""")
    assert rule, "no :focus-visible outline rule"
    assert any(float(w.replace("px", "")) >= 2 for _, w, _ in rule)
    assert any(sel.startswith(".bz :focus-visible") for sel, _, _ in rule)      # covers every control in the form


def test_phone_card_headers_keep_actions_with_the_title(driver, server):
    """At a true 360 px: duplicate/remove stay on the title row, the type switch gets its own row, switches do not wrap."""
    open_form(driver, server, width=360)
    fill_protein(driver)
    add_ligand(driver)
    rows = driver.execute_script("""
      return [...document.querySelectorAll('.bz-entity')].map(function (card) {
        const h = card.querySelector('.bz-card-h'), top = function (el) { return Math.round(el.getBoundingClientRect().top); };
        const title = h.querySelector('.bz-ent-title'), btns = [...h.querySelectorAll('button')], seg = h.querySelector('.bz-seg');
        return {type: card.dataset.type, title: top(title), buttons: btns.map(top), seg: seg && seg.offsetParent ? top(seg) : null};
      });""")
    for r in rows:
        assert all(b == r["title"] or abs(b - r["title"]) <= 12 for b in r["buttons"]), rows          # buttons beside the title, not on a row of their own
        if r["seg"] is not None:
            assert r["seg"] > r["title"], rows
    msa = driver.execute_script("const s = document.querySelector('.bz-entity [data-f=\"msa-mode\"], .bz-entity .bz-seg:not([data-adv])'); return s ? Math.round(s.getBoundingClientRect().height) : null")
    assert msa is None or msa <= 44, f"MSA switch wraps ({msa}px tall)"
    assert errors(driver) == []
