"""The form against the reply Colab really sends (the harness applies IPython's display formatter to what each registered callback
returns, exactly as Colab does), including the ways a kernel can answer wrongly.

A plain ``dict`` returned from a callback reaches the page only as its Python repr, next to the execution's own ``status: 'ok'``.
A form that looked at that ``status`` showed ``undefined`` in the YAML tab and threw ``reading 'filter'`` on structure import.
"""
import time

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By

from .test_form_browser import ASPIRIN, ASSETS, SEQ, errors, fill_protein, last_card, open_form, q, qa, upload, wait

JUNK = ("undefined", "[object Object]", "NaN", "null")


def page_text(driver):
    return driver.execute_script("return document.getElementById('bz-root-t').textContent")


def assert_no_junk(driver):
    text = page_text(driver)
    found = [j for j in JUNK if j in text]
    assert not found, f"{found} appears in the form: " + ", ".join(
        text[max(0, text.index(j) - 40): text.index(j) + 40].replace("\n", " ") for j in found)


def yaml_text(driver):
    return q(driver, '[data-f="yaml"]').get_attribute("textContent")


def test_yaml_tab_shows_the_yaml_the_kernel_returned(driver, server):
    open_form(driver, server)
    fill_protein(driver)
    wait(driver, lambda d: yaml_text(d).startswith("version: 1"))
    text = yaml_text(driver)
    assert "sequence: " + SEQ in text.replace("\n    ", "\n    ") or SEQ[:20] in text
    assert_no_junk(driver)
    assert errors(driver) == []


def test_structure_import_works_with_the_colab_reply(driver, server):
    open_form(driver, server)
    upload(driver, q(driver, '[data-f="structure-file"]'), ASSETS / "pdb" / "prot_lig_dna.pdb")
    wait(driver, lambda d: "entities found" in q(d, '[data-f="import-result"]').text)
    assert "3 entities found" in q(driver, '[data-f="import-result"]').text
    assert not qa(driver, '[data-f="import-result"] .bz-alert--err')
    assert_no_junk(driver)


def test_a_real_protein_structure_imports_and_fills_the_form(driver, server, tmp_path):
    """A structure with several chains, a ligand, a water and an ion, as downloaded from the PDB."""
    pdb = (ASSETS / "pdb" / "prot_lig.pdb").read_text()
    f = tmp_path / "1abc.pdb"
    f.write_text(pdb)
    open_form(driver, server)
    upload(driver, q(driver, '[data-f="structure-file"]'), f)
    wait(driver, lambda d: "entit" in q(d, '[data-f="import-result"]').text)
    click_add = q(driver, '[data-imp="all"]')
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", click_add)
    click_add.click()
    seq = last_card(driver).find_element(By.CSS_SELECTOR, '[data-f="seq"]').get_attribute("value")
    assert len(seq) > 100
    wait(driver, lambda d: yaml_text(d).startswith("version: 1"))
    assert_no_junk(driver)


def test_ligand_smiles_gets_its_depiction_and_properties(driver, server):
    open_form(driver, server)
    driver.execute_script("arguments[0].click()", q(driver, '[data-act="add-ligand"]'))
    card = last_card(driver)
    card.find_element(By.CSS_SELECTOR, '[data-f="value"]').send_keys(ASPIRIN)
    wait(driver, lambda d: card.find_elements(By.CSS_SELECTOR, '[data-f="preview"] svg'), 10)
    props = card.find_element(By.CSS_SELECTOR, '[data-f="props"]').get_attribute("textContent")
    assert "C9H8O4" in props and "MW" in props and "heavy atoms" in props
    assert_no_junk(driver)


def test_a_kernel_that_replies_with_a_plain_dict_is_reported_not_shown_as_undefined(driver, server):
    """An old runtime (callbacks still returning dicts) must give an instruction, never 'undefined' or a TypeError."""
    open_form(driver, server, rpc="plain")
    fill_protein(driver)
    wait(driver, lambda d: "unexpected format" in yaml_text(d))
    assert "Restart the session" in yaml_text(driver)
    upload(driver, q(driver, '[data-f="structure-file"]'), ASSETS / "pdb" / "prot_lig_dna.pdb")
    wait(driver, lambda d: q(d, '[data-f="import-result"]').find_elements(By.CSS_SELECTOR, ".bz-alert--err"))
    assert "unexpected format" in q(driver, '[data-f="import-result"]').text
    assert_no_junk(driver)


def test_an_exception_in_the_kernel_is_shown_as_a_message(driver, server):
    """Colab reports a Python exception as {ename, evalue, traceback} (not an Error): the text must not be 'undefined'."""
    open_form(driver, server, rpc="raise")
    fill_protein(driver)
    wait(driver, lambda d: "ValueError: boom from the kernel" in yaml_text(d))
    time.sleep(0.2)
    assert_no_junk(driver)


@pytest.mark.parametrize("mode", ["standard", "advanced"])
def test_save_works_with_the_colab_reply(driver, server, mode):
    open_form(driver, server, mode=mode)
    fill_protein(driver)
    q(driver, '[data-act="next"]').click()
    if mode == "advanced":
        q(driver, '[data-act="next"]').click()
    jn = q(driver, '[data-r="job_name"]')
    jn.send_keys("colab_reply")
    q(driver, '[data-act="next"]').click()
    wait(driver, lambda d: q(d, '[data-f="saved"]').is_displayed(), 15)
    assert (server.base_dir / "params.yaml").read_text().startswith("version: 1")
    assert 'job_name = "colab_reply"' in (server.base_dir / "run_params.txt").read_text()
    assert_no_junk(driver)
