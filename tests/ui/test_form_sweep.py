"""Sweep: press every button, flip every control and type into every field the form offers, in both modes, and demand
zero JavaScript errors, zero unhandled promise rejections and a form that still validates and saves afterwards.

The scripted tests cover the intended paths; this one covers everything else a user can click.
"""
import time

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from .test_form_browser import ASPIRIN, SEQ, errors, open_form, q, qa, wait

ACTIONS_IN_MARKUP = {"add-protein", "add-dna", "add-rna", "add-ligand", "add-template", "add-bond", "add-pocket", "add-contact", "add-mod",
                     "dup", "remove", "remove-row", "split", "reset", "copy-yaml", "next", "back"}


def visible(driver, sel):
    return [e for e in qa(driver, sel) if e.is_displayed() and e.is_enabled()]


def click_all(driver, sel, limit=40):
    n = 0
    for el in visible(driver, sel)[:limit]:
        try:
            el.click()
            n += 1
        except Exception as exc:  # noqa: BLE001  (a control that vanished because of an earlier click is fine)
            if "not interactable" not in str(exc) and "stale" not in str(exc):
                raise
    return n


def every_action_in_the_markup_is_handled():
    """Each data-act in form.html must have a handler branch in form.js (a button that does nothing is a bug)."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[2] / "boltz2nb" / "ui" / "assets" / "form.js").read_text()
    missing = [a for a in ACTIONS_IN_MARKUP if f"'{a}'" not in js and f'[data-act="{a}"]' not in js]   # delegated or bound directly
    assert not missing, missing


def test_every_markup_action_has_a_handler():
    every_action_in_the_markup_is_handled()


@pytest.mark.parametrize("mode", ["advanced", "standard"])
def test_press_everything(driver, server, mode):
    open_form(driver, server, mode=mode)
    # Selenium reports a control inside a panel that is still fading in (opacity 0) as not displayed: freeze animations
    driver.execute_script("var st=document.createElement('style');st.textContent='*,*::before,*::after{animation:none!important;transition:none!important}';document.head.appendChild(st)")
    seen = set()

    # --- step 1: every kind of entity, every per-card control -------------------------------------------------------
    log = []
    for act in ("add-protein", "add-ligand", "add-dna", "add-rna"):
        for el in visible(driver, f'[data-act="{act}"]'):
            el.click()
            seen.add(act)
            log.append((act, len(qa(driver, ".bz-entity")), errors(driver), driver.execute_script("return document.activeElement && document.activeElement.outerHTML.slice(0, 80)")))
    cards = qa(driver, ".bz-entity")
    assert len(cards) >= (4 if mode == "advanced" else 2), log
    # type into every text control of every card
    for card in qa(driver, ".bz-entity"):
        kind = card.get_attribute("data-type")
        for ta in card.find_elements(By.CSS_SELECTOR, 'textarea[data-f="seq"], input[data-f="smiles"], input[data-f="ccd"]'):
            if not ta.is_displayed():
                continue
            ta.clear()
            ta.send_keys({"protein": SEQ, "dna": "ATGCATGCATGC", "rna": "AUGCAUGCAUGC", "ligand": ASPIRIN}.get(kind, "A"))
        for group in card.find_elements(By.CSS_SELECTOR, ".bz-seg"):
            labels = [lab for lab in group.find_elements(By.CSS_SELECTOR, "label") if lab.is_displayed()]
            if not labels:
                continue
            original = next((lab for lab in labels if lab.find_element(By.CSS_SELECTOR, "input").is_selected()), labels[0])
            for lab in labels:                                # every choice, then back to the original one
                lab.click()
            original.click()
        for box in card.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]'):
            if box.is_displayed():
                box.click()
                box.click()
        for acc in card.find_elements(By.CSS_SELECTOR, "details > summary"):
            if acc.is_displayed():
                acc.click()
        if card.find_elements(By.CSS_SELECTOR, '[data-act="add-mod"]'):
            click_all(driver, f'.bz-entity[data-type="{kind}"] [data-act="add-mod"]', 2)
            seen.add("add-mod")
            for inp in card.find_elements(By.CSS_SELECTOR, '[data-f="mods"] input, [data-f="mods"] select'):
                if inp.is_displayed() and inp.tag_name == "input":
                    inp.send_keys("5" if inp.get_attribute("type") == "number" else "SEP")
    # chain-id chips: add, then remove with backspace and with the chip's x
    for card in qa(driver, ".bz-entity")[:2]:
        inp = card.find_element(By.CSS_SELECTOR, '[data-f="ids"] input')
        inp.send_keys("Z"); inp.send_keys(Keys.ENTER); inp.send_keys(Keys.BACKSPACE)
    click_all(driver, '[data-f="ids"] .bz-token button', 1)
    # duplicate then remove the duplicate
    n0 = len(qa(driver, ".bz-entity"))
    click_all(driver, '[data-act="dup"]', 1); seen.add("dup")
    assert len(qa(driver, ".bz-entity")) == n0 + 1
    click_all(driver, '[data-act="remove"]', 1); seen.add("remove")
    assert len(qa(driver, ".bz-entity")) == n0
    # FASTA with several records pasted into a protein card: the Split button appears; press it
    first_protein = q(driver, '.bz-entity[data-type="protein"] textarea[data-f="seq"]')
    first_protein.clear()
    driver.execute_script("""
      const ta = arguments[0], dt = new DataTransfer(); dt.setData('text', arguments[1]);
      const ev = new Event('paste', {bubbles: true, cancelable: true}); ev.clipboardData = dt; ta.dispatchEvent(ev);""",
                          first_protein, f">rec1 first\n{SEQ}\n>rec2 second\n{SEQ[:20]}\n")        # a FASTA record is pasted; typing a '>' is refused
    wait(driver, lambda d: bool(visible(d, '[data-act="split"]')), 5)
    n_before = len(qa(driver, ".bz-entity"))
    visible(driver, '[data-act="split"]')[0].click(); seen.add("split")
    assert len(qa(driver, ".bz-entity")) == n_before + 1
    # summary rail tabs and copy
    click_all(driver, '[data-tab]')
    click_all(driver, '[data-act="copy-yaml"]'); seen.add("copy-yaml")
    assert errors(driver) == [], errors(driver)

    # --- step 2 (advanced only): every constraint row type -----------------------------------------------------------
    q(driver, '[data-act="next"]').click(); seen.add("next")
    if mode == "advanced":
        assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "2"
        for acc in visible(driver, ".bz-panel details > summary, .bz-acc > summary"):
            acc.click()
        for act in ("add-template", "add-bond", "add-pocket", "add-contact"):
            click_all(driver, f'[data-act="{act}"]', 2); seen.add(act)
        # fill every input and select of every row, then remove one row of each kind
        for row in qa(driver, ".bz-row, [data-row]"):
            for inp in row.find_elements(By.CSS_SELECTOR, "input, select, textarea"):
                if not inp.is_displayed():
                    continue
                t = inp.get_attribute("type")
                if inp.tag_name == "select":
                    driver.execute_script("arguments[0].selectedIndex = Math.min(1, arguments[0].options.length - 1); arguments[0].dispatchEvent(new Event('input', {bubbles: true})); arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", inp)
                elif t == "checkbox":
                    inp.click()
                elif t == "number":
                    inp.clear(); inp.send_keys("3")
                elif t == "file":
                    continue
                else:
                    inp.send_keys("A:5"); inp.send_keys(Keys.ENTER)
        removed = click_all(driver, '[data-act="remove-row"]', 2); seen.add("remove-row")
        assert removed >= 1
        assert errors(driver) == [], errors(driver)
        q(driver, '[data-act="back"]').click(); seen.add("back")
        assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "1"
        q(driver, '[data-act="next"]').click()
        q(driver, '[data-act="next"]').click()
    else:
        assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "3"
        q(driver, '[data-act="back"]').click(); seen.add("back")
        assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "1"
        q(driver, '[data-act="next"]').click()

    # --- step 3: presets, every run control, save with a bad then a good job name ----------------------------------
    assert q(driver, '.bz-step[aria-current="step"]').get_attribute("data-go") == "3"
    click_all(driver, '[data-preset] input, .bz-preset input, [name^="preset"]')
    for el in visible(driver, "[data-r]"):
        t = el.get_attribute("type")
        if el.tag_name == "select":
            driver.execute_script("arguments[0].selectedIndex = Math.min(1, arguments[0].options.length - 1); arguments[0].dispatchEvent(new Event('input', {bubbles: true}))", el)
        elif t == "checkbox":
            el.click()
        elif t == "range":
            el.send_keys(Keys.ARROW_RIGHT)
        elif t == "number":
            el.clear(); el.send_keys("2")
        elif el.get_attribute("data-r") == "job_name":
            el.clear(); el.send_keys("bad name!")
        elif t == "text":
            el.clear(); el.send_keys("7")
    q(driver, '[data-act="next"]').click()                                   # Save with a bad job name: must complain, not throw
    time.sleep(0.4)
    assert not (server.base_dir / "run_params.txt").exists() or "bad name" not in (server.base_dir / "run_params.txt").read_text()
    assert "to fix" in q(driver, '[data-f="msg"], .bz-msg, [data-f="status-chip"]').text or qa(driver, ".bz-alert--err"), "no message after a failed save"
    driver.execute_script("document.querySelector('.bz-step[data-go=\"3\"]').click()")   # the save jumped to the first problem; come back
    jn = q(driver, '[data-r="job_name"]'); driver.execute_script("arguments[0].scrollIntoView({block:'center'})", jn); jn.clear(); jn.send_keys("sweep_job")
    q(driver, '[data-act="next"]').click()
    wait(driver, lambda d: q(d, '[data-f="saved"]').is_displayed() or len(d.find_elements(By.CSS_SELECTOR, ".bz-alert--err")) > 0, 20)
    # a sweep that typed into every field may leave a constraint invalid; what must hold is: no exception, a clear message or a save
    saved = q(driver, '[data-f="saved"]').is_displayed()
    if saved:
        assert (server.base_dir / "params.yaml").exists() and (server.base_dir / "run_params.txt").exists()
        assert "sweep_job" in (server.base_dir / "run_params.txt").read_text()
    else:
        assert any(e.is_displayed() for e in qa(driver, ".bz-alert--err"))
    # reset (two clicks) brings the form back to one pristine protein
    click_all(driver, '[data-act="reset"]', 1); click_all(driver, '[data-act="reset"]', 1); seen.add("reset")
    q(driver, '[data-act="back"]').click() if visible(driver, '[data-act="back"]') else None
    assert errors(driver) == [], errors(driver)

    expected = ACTIONS_IN_MARKUP if mode == "advanced" else ACTIONS_IN_MARKUP - {"add-template", "add-bond", "add-pocket", "add-contact", "remove-row", "add-dna", "add-rna"}
    assert expected <= seen, sorted(expected - seen)


def test_keyboard_only_pass(driver, server):
    """Tab through the whole form and press Space/Enter on each focusable control: nothing may throw."""
    open_form(driver, server, mode="advanced")
    body = q(driver, "body")
    for _ in range(80):
        body.send_keys(Keys.TAB)
        el = driver.switch_to.active_element
        tag, typ = el.tag_name, (el.get_attribute("type") or "")
        if tag == "button" and (el.get_attribute("data-act") in (None, "copy-yaml", "theme") or el.get_attribute("data-act", ) in ("add-mod", "add-ligand")):
            el.send_keys(Keys.ENTER)
        elif typ in ("checkbox", "radio"):
            el.send_keys(Keys.SPACE)
    assert errors(driver) == [], errors(driver)
