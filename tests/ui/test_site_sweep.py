"""Sweep of the website's own scripts: every button, link target, select, accordion and form on the three pages, with
zero JavaScript errors. 3Dmol is replaced by a stub that records the calls the viewer controls make."""
import re
import shutil
from pathlib import Path

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

ROOT = Path(__file__).resolve().parents[2]
PAGES = {"index": "index.html", "faq": "docs/faq.html", "usecases": "docs/use-cases.html"}
COLLECT = ("<script>window.__errs=[];window.__calls=[];"
           "window.addEventListener('error',function(e){window.__errs.push(String(e.message))});"
           "window.addEventListener('unhandledrejection',function(e){window.__errs.push('unhandled: '+String(e.reason))});"
           "Object.defineProperty(navigator,'clipboard',{value:{writeText:function(t){window.__calls.push(['clipboard',String(t).length]);return Promise.resolve();}},configurable:true});"
           "window.$3Dmol={SurfaceType:{VDW:1},createViewer:function(el,o){window.__calls.push(['createViewer']);var v={};"
           "['addModel','setStyle','addSurface','removeAllSurfaces','removeAllModels','zoomTo','zoom','render','spin','setBackgroundColor','setViewStyle','rotate','clear','resize','addStyle','center']"
           ".forEach(function(m){v[m]=function(){window.__calls.push([m]);return v;}});return v;},"
           "download:function(q,v,o,cb){window.__calls.push(['download',q]);if(cb){setTimeout(cb,0);}}};</script>")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dst = tmp_path_factory.mktemp("site_sweep")
    (dst / "docs").mkdir()
    shutil.copytree(ROOT / "assets", dst / "assets", ignore=shutil.ignore_patterns("pdb", "pred_data", "ui"))
    for rel in PAGES.values():
        html = (ROOT / rel).read_text(encoding="utf-8")
        html = re.sub(r'<script[^>]*src="https?://[^"]*"[^>]*></script>', "", html)
        html = re.sub(r'<link[^>]*href="https?://(fonts|3Dmol)[^"]*"[^>]*>', "", html)
        html = re.sub(r"<script>\s*\(function \(c, l, a, r, i, t, y\).*?</script>", "", html, flags=re.S)
        html = html.replace("<head>", "<head>" + COLLECT, 1)
        (dst / rel).write_text(html, encoding="utf-8")
    return dst


def errs(driver):
    return driver.execute_script("return window.__errs")


def calls(driver):
    return driver.execute_script("return window.__calls")


def open_page(driver, site, key, width=1280):
    driver.switch_to.default_content()
    driver.set_window_size(width, 900)
    driver.get(f"file://{site / PAGES[key]}")
    driver.execute_script("window.localStorage.clear(); var st=document.createElement('style');st.textContent='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}';document.head.appendChild(st);document.querySelectorAll('.reveal').forEach(function(e){e.classList.add('visible')})")


def clickable(driver):
    sel = "button, [role=button], summary, .faq-category-chip, .toolbar-btn, .control-btn, .usecases-jump a, a[href^='#']"
    return [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed() and e.is_enabled()]


@pytest.mark.parametrize("key", PAGES)
def test_press_everything_on_the_page(driver, site, key):
    open_page(driver, site, key)
    assert errs(driver) == [], errs(driver)
    pressed = 0
    for el in clickable(driver):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
            el.click()
            pressed += 1
        except Exception as exc:  # noqa: BLE001
            if "not interactable" in str(exc) or "stale" in str(exc) or "obscured" in str(exc):
                continue
            raise
        assert errs(driver) == [], (el.get_attribute("outerHTML")[:120], errs(driver))
    assert pressed > 8, pressed
    for sel in driver.find_elements(By.CSS_SELECTOR, "select"):
        if sel.is_displayed():
            s = Select(sel)
            for i in range(len(s.options)):
                s.select_by_index(i)
                assert errs(driver) == [], errs(driver)
    for inp in driver.find_elements(By.CSS_SELECTOR, "input[type=text], input[type=search], input:not([type])"):
        if inp.is_displayed():
            inp.clear()
            inp.send_keys("batch")
            inp.send_keys(Keys.ENTER)
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    assert errs(driver) == [], errs(driver)


def test_landing_page_citation_tools(driver, site):
    open_page(driver, site, "index")
    sel = Select(driver.find_element(By.ID, "citationFormatSelect"))
    texts = set()
    for i in range(len(sel.options)):
        sel.select_by_index(i)
        texts.add(driver.find_element(By.ID, "citationText").text.strip())
    assert len(texts) == len(sel.options) and all(texts), "each citation format must render its own text"
    before = len(calls(driver))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click()", driver.find_element(By.ID, "copyCitationBtn"))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click()", driver.find_element(By.ID, "copyBibBtn"))
    import time
    time.sleep(0.3)
    copied = [c for c in calls(driver)[before:] if c[0] == "clipboard"]
    assert len(copied) == 2 and all(c[1] > 50 for c in copied), copied
    assert "copied" in driver.find_element(By.ID, "citationCopyStatus").text and "copied" in driver.find_element(By.ID, "copyStatus").text
    btn = driver.find_element(By.ID, "downloadAsBtn")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
    btn.click()
    menu = driver.find_element(By.ID, "downloadAsMenu")
    assert menu.is_displayed() and btn.get_attribute("aria-expanded") == "true"
    items = menu.find_elements(By.CSS_SELECTOR, "li")
    assert len(items) >= 2
    driver.execute_script("window.__dl=[];HTMLAnchorElement.prototype.click=function(){window.__dl.push([this.download,this.href.slice(0,30)]);}")
    items[0].click()
    assert driver.execute_script("return window.__dl") and driver.execute_script("return window.__dl")[0][0].endswith((".bib", ".ris", ".txt", ".enw", ".json"))
    assert errs(driver) == [], errs(driver)


def test_faq_search_filters_and_clears(driver, site):
    open_page(driver, site, "faq")
    total = int(re.search(r"(\d+)", driver.find_element(By.ID, "faqResultCount").text).group(1))
    assert total >= 20
    box = driver.find_element(By.ID, "faqSearchInput")
    box.send_keys("batch")
    box.send_keys(Keys.ENTER)
    shown = int(re.search(r"(\d+)", driver.find_element(By.ID, "faqResultCount").text).group(1))
    assert 0 < shown < total, (shown, total)
    box.clear(); box.send_keys("zzzzqqqq"); box.send_keys(Keys.ENTER)
    assert driver.find_element(By.ID, "faqEmptyState").is_displayed()
    driver.find_element(By.ID, "faqResetButton").click()
    assert int(re.search(r"(\d+)", driver.find_element(By.ID, "faqResultCount").text).group(1)) == total
    chips = driver.find_elements(By.CSS_SELECTOR, ".faq-category-chip")
    chips[2].click()
    assert "active" in chips[2].get_attribute("class")
    assert 0 < int(re.search(r"(\d+)", driver.find_element(By.ID, "faqResultCount").text).group(1)) < total
    assert errs(driver) == [], errs(driver)


def test_landing_page_without_the_3d_library_degrades_quietly(driver, site):
    """The library comes from a CDN; when it is unavailable the page must not throw."""
    page = site / "index.html"
    html = page.read_text(encoding="utf-8").replace("window.$3Dmol=", "window.$3DmolUnused=")
    alt = site / "index_no3dmol.html"
    alt.write_text(html, encoding="utf-8")
    driver.get(f"file://{alt}")
    import time
    time.sleep(1.2)
    assert errs(driver) == [], errs(driver)
    # the hero's background viewer is simply absent without the library; the (currently disabled) main viewer would say why
    assert driver.execute_script("return document.getElementById('bgViewer') ? document.getElementById('bgViewer').children.length : 0") == 0
