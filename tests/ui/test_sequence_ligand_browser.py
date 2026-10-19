"""Sequence typing is filtered as it happens; a ligand is checked as soon as it is entered (SMILES by RDKit, CCD codes against the PDB
component dictionary); both are checked through the reply Colab really sends."""
import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from boltz2nb import ligand

from .test_colab_reply import assert_no_junk
from .test_form_browser import ASPIRIN, click, errors, fill_protein, goto_step, last_card, open_form, q, wait

PASTE_JS = """
const ta = arguments[0], dt = new DataTransfer();
dt.setData('text', arguments[1]);
const ev = new Event('paste', {bubbles: true, cancelable: true}); ev.clipboardData = dt;
ta.dispatchEvent(ev);
"""


def seq_box(driver):
    return last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="seq"]')


def note(driver):
    # textContent, not .text: a card that has just been added is still fading in and Selenium reports text of a transparent element as empty
    return last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="seq-meta"]').get_attribute("textContent")


def set_type(driver, kind):
    driver.execute_script("arguments[0].click()", last_card(driver).find_element(By.CSS_SELECTOR, f'input[name^="ty-"][value="{kind}"]'))


# ------------------------------------------------------------------------------------------------ sequence typing
def test_typing_makes_capitals_and_drops_spaces(driver, server):
    open_form(driver, server)
    ta = fill_protein(driver, "mkta yiak qrqi sfv")
    assert ta.get_attribute("value") == "MKTAYIAKQRQISFV"
    assert note(driver) == ""                                        # spaces and case are not worth a warning
    assert errors(driver) == []


def test_typing_refuses_letters_that_are_not_amino_acids_and_says_so(driver, server):
    open_form(driver, server)
    ta = fill_protein(driver, "MKTBAJYOUZ12*IAK")
    assert ta.get_attribute("value") == "MKTAYIAK"
    text = note(driver)
    assert text.startswith("Ignored 8 characters") and all(c in text for c in "B J O U Z 1 2 *".split()), text
    assert "Protein" in text


def test_the_enter_key_adds_no_line_break(driver, server):
    open_form(driver, server)
    ta = fill_protein(driver, "MKT")
    ta.send_keys(Keys.ENTER)
    ta.send_keys("AYI")
    assert ta.get_attribute("value") == "MKTAYI"


@pytest.mark.parametrize(("kind", "typed", "kept", "refused"), [
    ("dna", "acgt un", "ACGTN", "U"),
    ("rna", "acgu tn", "ACGUN", "T"),
    ("protein", "acdefghiklmnpqrstvwyx", "ACDEFGHIKLMNPQRSTVWYX", ""),
])
def test_each_chain_type_accepts_only_its_own_letters(driver, server, kind, typed, kept, refused):
    open_form(driver, server)
    set_type(driver, kind)
    ta = fill_protein(driver, typed)
    assert ta.get_attribute("value") == kept
    assert (refused in note(driver)) if refused else note(driver) == ""


def test_typing_in_the_middle_keeps_the_caret_where_it_was(driver, server):
    open_form(driver, server)
    ta = fill_protein(driver, "MKTAYI")
    driver.execute_script("arguments[0].setSelectionRange(3, 3)", ta)
    ta.send_keys("g")                                                # lower case, in the middle
    ta.send_keys("b")                                                # refused
    ta.send_keys("h")
    assert ta.get_attribute("value") == "MKTGHAYI"
    assert driver.execute_script("return arguments[0].selectionStart", ta) == 5


def test_pasted_text_is_cleaned_and_a_fasta_record_still_splits(driver, server):
    open_form(driver, server)
    ta = seq_box(driver)
    driver.execute_script(PASTE_JS, ta, ">sp|P1|ONE first\nmkta yiak 12 bz*\n>sp|P2|TWO second\nGSHMLEER\n")
    assert ta.get_attribute("value") == "MKTAYIAK"                  # digits, spaces, B and Z are gone, the header is not part of the sequence
    assert note(driver) == "Ignored 2 characters that cannot be in a Protein sequence: B Z."
    assert "2 FASTA records" in last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="split-msg"]').get_attribute("textContent")


def test_text_that_arrives_without_a_keystroke_is_cleaned_too(driver, server):
    """Drag and drop, autofill or an input method fire only an input event; the same filter applies and the caret stays by its letter."""
    open_form(driver, server)
    ta = seq_box(driver)
    driver.execute_script("""
      const ta = arguments[0]; ta.focus(); ta.value = 'mk1ta*yi'; ta.setSelectionRange(5, 5);
      ta.dispatchEvent(new Event('input', {bubbles: true}));""", ta)
    assert ta.get_attribute("value") == "MKTAYI"
    assert driver.execute_script("return arguments[0].selectionStart", ta) == 4      # after "MKTA": the two refused characters before the caret are gone


def test_dropped_fasta_is_treated_like_a_paste(driver, server):
    open_form(driver, server)
    ta = seq_box(driver)
    driver.execute_script("""
      const ta = arguments[0], dt = new DataTransfer(); dt.setData('text', '>x header words\\nacde fghik\\n');
      const ev = new Event('drop', {bubbles: true, cancelable: true}); ev.dataTransfer = dt; ta.dispatchEvent(ev);""", ta)
    assert ta.get_attribute("value") == "ACDEFGHIK"


def test_a_sequence_kept_while_changing_type_is_reported_not_erased(driver, server):
    open_form(driver, server)
    ta = fill_protein(driver, "MKTAYIAK")
    set_type(driver, "rna")
    ta.send_keys(Keys.TAB)
    err = last_card(driver).find_element(By.CSS_SELECTOR, '[data-e="seq"]')
    wait(driver, lambda d: err.is_displayed())
    assert ta.get_attribute("value") == "MKTAYIAK" and "Not valid in RNA" in err.text


# ------------------------------------------------------------------------------------------------ ligand checks
def status(driver):
    return last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="val-status"]')


def value_box(driver):
    return last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="value"]')


def preview(driver):
    return last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="preview"]')


def new_ligand(driver, text, kind="smiles"):
    click(driver, '[data-act="add-ligand"]')
    card = last_card(driver)
    if kind == "ccd":
        driver.execute_script("arguments[0].click()", card.find_element(By.CSS_SELECTOR, 'input[name^="lk-"][value="ccd"]'))
    card.find_element(By.CSS_SELECTOR, '[data-f="value"]').send_keys(text)
    return card


def settled(driver, state, timeout=10):
    wait(driver, lambda d: status(d).get_attribute("data-state") == state, timeout)
    return status(driver).text


def test_a_valid_smiles_is_confirmed_and_drawn(driver, server):
    open_form(driver, server)
    new_ligand(driver, ASPIRIN)
    text = settled(driver, "ok")
    assert text.startswith("Valid SMILES: C9H8O4") and "13 heavy atoms" in text
    assert value_box(driver).get_attribute("data-valid") == "true"
    assert preview(driver).find_elements(By.CSS_SELECTOR, "svg"), "the 2-D drawing is missing"
    assert_no_junk(driver)
    assert errors(driver) == []


@pytest.mark.parametrize(("smiles", "words"), [
    ("CC(=O)Oc1ccccc1C(=O", "never closed"),
    ("c1ccccc", "Ring label 1"),
    ("CC(=O)O aspirin", "cannot contain spaces"),
    ("CN(C)(C)(C)C", "chemically invalid"),
    ("C1=CC=CC=C1)", "no matching"),
])
def test_an_invalid_smiles_says_what_is_wrong(driver, server, smiles, words):
    open_form(driver, server)
    new_ligand(driver, smiles)
    text = settled(driver, "bad")
    assert words in text, text
    assert value_box(driver).get_attribute("data-valid") == "false"
    assert not preview(driver).find_elements(By.CSS_SELECTOR, "svg")
    assert "No preview" in preview(driver).text
    assert last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="sub"]').text == "Not a valid SMILES"
    assert errors(driver) == []


def try_to_save(driver, server):
    goto_step(driver, 3)
    q(driver, '[data-r="job_name"]').send_keys("check_1")
    click(driver, '[data-act="next"]')
    wait(driver, lambda d: "issue" in q(d, '[data-f="action-msg"]').text or q(d, '[data-f="saved"]').is_displayed(), 15)
    return (server.base_dir / "params.yaml").exists()


def page_text(driver):
    return driver.execute_script("return document.getElementById('bz-root-t').innerText")


def test_saving_is_refused_while_a_ligand_is_not_valid(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    new_ligand(driver, "CC(=O)Oc1ccccc1C(=O")
    settled(driver, "bad")
    assert not try_to_save(driver, server)
    assert "never closed" in page_text(driver)
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "1"       # back at the molecule that needs fixing


def test_saving_is_refused_for_a_ccd_code_that_does_not_exist(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    new_ligand(driver, "ZZZQ", kind="ccd")
    settled(driver, "bad")
    assert not try_to_save(driver, server)
    assert "not in the PDB Chemical Component Dictionary" in page_text(driver)


def test_saving_goes_ahead_when_the_component_service_is_unreachable(driver, server, ccd_service):
    ccd_service.offline = True
    open_form(driver, server)
    fill_protein(driver)
    new_ligand(driver, "ATP", kind="ccd")
    settled(driver, "warn")
    assert try_to_save(driver, server)
    assert "ATP" in (server.base_dir / "params.yaml").read_text()


def test_spaces_typed_into_a_ccd_code_are_dropped(driver, server):
    open_form(driver, server)
    new_ligand(driver, "a t p", kind="ccd")
    assert value_box(driver).get_attribute("value") == "ATP"
    settled(driver, "ok")


def test_a_valid_ccd_code_is_confirmed_with_its_name_and_drawn(driver, server, ccd_service):
    open_form(driver, server)
    new_ligand(driver, "sah", kind="ccd")
    assert value_box(driver).get_attribute("value") == "SAH"
    text = settled(driver, "ok")
    assert text.startswith("Valid CCD code: SAH - S-ADENOSYL-L-HOMOCYSTEINE") and "C14H20N6O5S" in text
    assert preview(driver).find_elements(By.CSS_SELECTOR, "svg"), "a CCD component gets its drawing too"
    assert ccd_service.calls == ["SAH"]
    assert last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="sub"]').text.startswith("SAH - S-ADENOSYL")
    assert_no_junk(driver)


def test_a_ccd_code_that_does_not_exist_is_rejected(driver, server, ccd_service):
    open_form(driver, server)
    new_ligand(driver, "zzzq", kind="ccd")
    text = settled(driver, "bad")
    assert "ZZZQ is not in the PDB Chemical Component Dictionary" in text
    assert value_box(driver).get_attribute("data-valid") == "false"


@pytest.mark.parametrize("typed", ["AB-12", "TOOLONGCODE", "A.B"])
def test_text_that_cannot_be_a_ccd_code_is_rejected_without_asking_the_service(driver, server, ccd_service, typed):
    open_form(driver, server)
    new_ligand(driver, typed, kind="ccd")
    text = settled(driver, "bad")
    assert "is not a CCD code" in text, text
    assert ccd_service.calls == [], "format errors are decided in the page, no request is needed"


def test_an_unreachable_service_is_a_warning_not_an_error(driver, server, ccd_service):
    ccd_service.offline = True
    open_form(driver, server)
    new_ligand(driver, "ATP", kind="ccd")
    text = settled(driver, "warn")
    assert "could not be reached" in text and "ATP" in text
    assert value_box(driver).get_attribute("data-valid") is None
    assert not last_card(driver).find_element(By.CSS_SELECTOR, '[data-e="value"]').is_displayed()


def test_switching_between_smiles_and_ccd_rechecks_the_text(driver, server, ccd_service):
    open_form(driver, server)
    card = new_ligand(driver, "ATP", kind="ccd")
    settled(driver, "ok")
    driver.execute_script("arguments[0].click()", card.find_element(By.CSS_SELECTOR, 'input[name^="lk-"][value="smiles"]'))
    text = settled(driver, "bad")                                    # "ATP" read as a SMILES is not valid chemistry for this check
    assert text, text


def test_without_rdkit_the_text_checks_still_work_and_the_rest_is_a_warning(driver, server, monkeypatch):
    monkeypatch.setattr(ligand, "_rdkit", lambda: None)
    open_form(driver, server)
    new_ligand(driver, "CC(=O)Oc1ccccc1C(=O)O")
    assert "RDKit is not installed in this runtime" in settled(driver, "warn")
    card = new_ligand(driver, "C1CC")
    assert "Ring label 1" in settled(driver, "bad")                    # found without RDKit
    assert card is not None


def test_the_ligand_checks_survive_a_runtime_that_answers_in_the_old_plain_format(driver, server):
    open_form(driver, server, rpc="plain")
    new_ligand(driver, ASPIRIN)
    text = settled(driver, "warn")
    assert "could not be checked" in text and "Restart" in text or "unexpected format" in text
    assert_no_junk(driver)
