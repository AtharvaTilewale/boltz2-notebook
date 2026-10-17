"""The light / dark switch on every panel, in a real browser: form, run panel, result card and report."""
import re

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from boltz2nb.analysis import load_job, summary_dict
from boltz2nb.ui.live import RunState, render_live
from boltz2nb.ui.results import render_report_document
from boltz2nb.ui.theme import get_theme

from .test_form_browser import click, open_form, q
from .test_results_browser import CDN, CTX, STUB_3DMOL, open_page, parts  # noqa: F401  (parts is a fixture)

BG = "return getComputedStyle(document.querySelector('.bz')).backgroundColor"
LIGHT_BG, DARK_BG = "rgb(244, 246, 251)", "rgb(10, 18, 38)"


def rgb(css):
    return tuple(int(x) for x in re.findall(r"\d+", css)[:3])


def luminance(css):
    return sum(rgb(css)) / 3


def theme_of(driver, i=0):
    return driver.execute_script("return document.querySelectorAll('.bz')[arguments[0]].getAttribute('data-theme')", i)


def switch(driver):
    return driver.find_element(By.CSS_SELECTOR, '[data-act="theme"]')


def shown_icon(driver):
    return driver.execute_script("""
      const vis = c => getComputedStyle(document.querySelector('[data-act="theme"] .bz-ico--' + c)).display !== 'none';
      return vis('moon') ? (vis('sun') ? 'both' : 'moon') : (vis('sun') ? 'sun' : 'none');""")


@pytest.mark.parametrize("which", ["live", "card", "report"])
def test_panel_starts_light_and_the_switch_flips_it(driver, parts, which):   # noqa: F811
    open_page(driver, parts, parts[which].replace(CDN, STUB_3DMOL), f"theme-{which}")
    assert theme_of(driver) == "light" and driver.execute_script(BG) == LIGHT_BG
    assert driver.execute_script("return document.documentElement.getAttribute('data-bz-theme')") == "light"
    btn = switch(driver)
    assert btn.is_displayed() and btn.size["width"] >= 32 and btn.get_attribute("aria-label") == "Switch to dark theme"
    assert shown_icon(driver) == "moon"                              # the moon invites dark mode

    btn.click()
    assert theme_of(driver) == "dark" and driver.execute_script(BG) == DARK_BG
    assert switch(driver).get_attribute("aria-label") == "Switch to light theme" and shown_icon(driver) == "sun"

    switch(driver).click()
    assert theme_of(driver) == "light" and driver.execute_script(BG) == LIGHT_BG and shown_icon(driver) == "moon"


def test_form_starts_light_and_the_switch_flips_it(driver, server):
    open_form(driver, server, theme="light")
    assert theme_of(driver) == "light" and luminance(driver.execute_script(BG)) > 200 and shown_icon(driver) == "moon"
    click(driver, '[data-act="theme"]')
    assert theme_of(driver) == "dark" and luminance(driver.execute_script(BG)) < 40 and shown_icon(driver) == "sun"
    assert q(driver, '[data-act="theme"]').get_attribute("aria-label") == "Switch to light theme"


def test_one_switch_moves_every_panel_on_the_page(driver, parts):   # noqa: F811
    open_page(driver, parts, parts["live"] + parts["card"].replace(CDN, STUB_3DMOL), "theme-shared")
    n = driver.execute_script("return document.querySelectorAll('.bz').length")
    assert n == 3 and [theme_of(driver, i) for i in range(n)] == ["light"] * n
    driver.find_elements(By.CSS_SELECTOR, '[data-act="theme"]')[-1].click()           # the result card's switch
    assert [theme_of(driver, i) for i in range(n)] == ["dark"] * n                       # run panels followed it
    assert {luminance(c) < 40 for c in driver.execute_script("return [...document.querySelectorAll('.bz')].map(e => getComputedStyle(e).backgroundColor)")} == {True}


def test_run_panel_keeps_the_choice_through_its_one_second_refreshes(driver, parts):   # noqa: F811
    open_page(driver, parts, parts["live"], "theme-refresh")
    switch(driver).click()
    assert theme_of(driver) == "dark"
    state = RunState(job_name="kinase_aspirin", has_affinity=True, gpu="Tesla T4", samples=3)
    state.feed("Checking input data.")
    refresh = render_live(state, standalone_css=False, hint=False)             # what the notebook sends every ~0.9 s
    # 1) the front-end inserts the new HTML but has not yet re-run its scripts: the page-level preference must already paint it dark
    driver.execute_script("document.querySelector('.bz-live').outerHTML = arguments[0]", re.sub(r"<script>.*?</script>", "", refresh, flags=re.S))
    assert driver.execute_script("return document.querySelector('.bz-live').hasAttribute('data-theme')") is False
    assert driver.execute_script(BG) == DARK_BG, "a refreshed run panel flashed back to light"
    # 2) after its scripts ran it is explicitly dark, and its own switch (a new element) still works
    driver.execute_script("window.__bzTheme.apply()")
    assert theme_of(driver) == "dark"
    switch(driver).click()
    assert theme_of(driver) == "light" and driver.execute_script(BG) == LIGHT_BG


def test_standalone_report_remembers_the_reader_s_choice(driver, tmp_path, example_pred_dir):
    summary = summary_dict(load_job(example_pred_dir))
    f = tmp_path / "report.html"
    f.write_text(render_report_document(summary, {"models": {}}, None, CTX, None, 90).replace(CDN, STUB_3DMOL))
    driver.set_window_size(1100, 900)
    driver.get(f"file://{f}")
    driver.execute_script("window.localStorage.removeItem('bz-theme')")
    driver.get(f"file://{f}")
    assert theme_of(driver) == "light" and driver.execute_script("return getComputedStyle(document.body).backgroundColor") == "rgb(244, 246, 251)"
    switch(driver).click()
    assert theme_of(driver) == "dark" and driver.execute_script("return getComputedStyle(document.body).backgroundColor") == "rgb(7, 13, 29)"
    driver.get(f"file://{f}")                                                    # open it again later
    assert theme_of(driver) == "dark", "the report did not remember the choice"
    driver.execute_script("window.localStorage.removeItem('bz-theme')")


def test_printing_is_always_light_and_the_screen_theme_returns(driver, parts):   # noqa: F811
    open_page(driver, parts, parts["card"].replace(CDN, STUB_3DMOL), "theme-print")
    switch(driver).click()
    assert theme_of(driver) == "dark"
    driver.execute_script("window.dispatchEvent(new Event('beforeprint'))")
    assert theme_of(driver) == "light" and driver.execute_script(BG) == LIGHT_BG
    driver.execute_script("window.dispatchEvent(new Event('afterprint'))")
    assert theme_of(driver) == "dark"
    assert driver.execute_script("return getComputedStyle(document.querySelector('.bz-themebtn')).display") != "none"


def test_switch_is_hidden_when_printing_the_report(driver, parts):   # noqa: F811
    open_page(driver, parts, parts["report"].replace(CDN, STUB_3DMOL), "theme-printcss")
    hidden = driver.execute_script("""
      for (const s of document.styleSheets) for (const r of s.cssRules)
        if (r.type === CSSRule.MEDIA_RULE && /print/.test(r.conditionText || r.media.mediaText))
          for (const x of r.cssRules) if (x.selectorText && x.selectorText.includes('.bz-themebtn')) return x.style.display;
      return null;""")
    assert hidden == "none"


def test_python_session_hears_the_switch_so_later_panels_match(driver, server):
    open_form(driver, server, theme="light")
    assert get_theme() == "light"
    click(driver, '[data-act="theme"]')
    WebDriverWait(driver, 10).until(lambda d: get_theme() == "dark")
    assert 'data-theme="dark"' in render_live(RunState(job_name="next"))      # the run panel drawn next starts dark
    click(driver, '[data-act="theme"]')
    WebDriverWait(driver, 10).until(lambda d: get_theme() == "light")
