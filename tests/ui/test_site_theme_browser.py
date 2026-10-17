"""The website's light / dark switch in a real browser: dark stays the default, light is readable, nothing overflows."""
import re
import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("selenium", reason="selenium is not installed")
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parents[2]
PAGES = {"index": "index.html", "faq": "docs/faq.html", "usecases": "docs/use-cases.html"}
FREEZE = ("var st=document.createElement('style');st.textContent='*,*::before,*::after{transition:none!important;animation:none!important}';"
          "document.head.appendChild(st);document.querySelectorAll('.reveal').forEach(function(e){e.classList.add('visible')});")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """A copy of the site without third-party scripts (analytics, fonts, 3Dmol) so the pages load offline and without WebGL."""
    dst = tmp_path_factory.mktemp("site")
    (dst / "docs").mkdir()
    shutil.copytree(ROOT / "assets", dst / "assets", ignore=shutil.ignore_patterns("pdb", "pred_data", "ui"))
    for rel in PAGES.values():
        html = (ROOT / rel).read_text(encoding="utf-8")
        html = re.sub(r'<script[^>]*src="https?://[^"]*"[^>]*></script>', "", html)
        html = re.sub(r'<link[^>]*href="https?://(fonts|3Dmol)[^"]*"[^>]*>', "", html)
        html = re.sub(r"<script>\s*\(function \(c, l, a, r, i, t, y\).*?</script>", "", html, flags=re.S)
        (dst / rel).write_text(html, encoding="utf-8")
    return dst


def open_site(driver, site, key, theme=None, width=None):
    """Load a page with a clean slate (``theme`` = the saved choice, or none). Narrow widths use an exact-width iframe."""
    url = f"file://{site / PAGES[key]}"
    driver.switch_to.default_content()
    driver.set_window_size(1280, 900)
    driver.get(url)
    driver.execute_script("window.localStorage.clear()")
    if theme == "light":
        driver.execute_script("window.localStorage.setItem('bz-site-theme', 'light')")
    if width and width < 520:
        outer = site / f"frame_{key}_{width}.html"
        outer.write_text(f"<!doctype html><body style='margin:0;background:#777'><iframe id=f src='{url}' style='width:{width}px;height:800px;border:0'></iframe>")
        driver.get(f"file://{outer}")
        driver.switch_to.frame("f")
        assert driver.execute_script("return innerWidth") == width
    else:
        driver.set_window_size(width or 1280, 900)
        driver.get(url)
    time.sleep(0.4)
    driver.execute_script(FREEZE)
    return driver


def attr(driver):
    return driver.execute_script("return document.documentElement.getAttribute('data-theme')")


def body_lum(driver):
    return driver.execute_script("""const c = getComputedStyle(document.body).backgroundColor.match(/[\\d.]+/g).map(Number);
        return (c[0] + c[1] + c[2]) / 3""")


def switch(driver):
    return driver.find_element(By.CSS_SELECTOR, '[data-act="theme"]')


@pytest.mark.parametrize("key", PAGES)
def test_dark_is_the_default_and_the_switch_flips_the_page(driver, site, key):
    open_site(driver, site, key)
    assert attr(driver) is None
    btn = switch(driver)
    assert btn.is_displayed() and btn.size["width"] >= 40 and btn.get_attribute("aria-label") == "Switch to light theme"
    dark_bg = driver.execute_script("return getComputedStyle(document.body).backgroundImage")
    assert "gradient" in dark_bg and driver.execute_script("return document.querySelector('meta[name=theme-color]').content") == "#0b1020"
    assert driver.execute_script("return getComputedStyle(document.querySelector('.theme-toggle .ico-sun')).display") != "none"

    btn.click()
    assert attr(driver) == "light" and body_lum(driver) > 235
    assert switch(driver).get_attribute("aria-label") == "Switch to dark theme"
    assert driver.execute_script("return getComputedStyle(document.querySelector('.theme-toggle .ico-moon')).display") != "none"
    assert driver.execute_script("return getComputedStyle(document.querySelector('.theme-toggle .ico-sun')).display") == "none"
    assert driver.execute_script("return document.querySelector('meta[name=theme-color]').content") == "#f4f7fc"

    switch(driver).click()
    assert attr(driver) is None and switch(driver).get_attribute("aria-label") == "Switch to light theme"


def test_the_choice_is_remembered_across_pages_and_reloads(driver, site):
    open_site(driver, site, "index")
    switch(driver).click()
    assert attr(driver) == "light"
    for key in ("faq", "usecases", "index"):
        driver.get(f"file://{site / PAGES[key]}")                         # navigate: the saved choice applies straight away
        assert attr(driver) == "light", f"{key} did not open in the saved theme"
    switch(driver).click()
    driver.get(f"file://{site / PAGES['faq']}")
    assert attr(driver) is None


CONTRAST_JS = r"""
const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(parseFloat); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
const over = (t, b) => { const a = t.a + b.a * (1 - t.a); return a === 0 ? {r: 0, g: 0, b: 0, a: 0} : {r: (t.r * t.a + b.r * b.a * (1 - t.a)) / a, g: (t.g * t.a + b.g * b.a * (1 - t.a)) / a, b: (t.b * t.a + b.b * b.a * (1 - t.a)) / a, a}; };
const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
function ground(el) {                       // what the text sits on; null when it sits on a gradient we cannot evaluate
  const layers = []; let acc = 0;
  for (let e = el; e; e = e.parentElement) {
    const cs = getComputedStyle(e), c = parse(cs.backgroundColor);
    if (c && c.a > 0) { layers.push(c); acc = acc + c.a * (1 - acc); }
    if (acc >= 0.99) break;
    if (cs.backgroundImage !== 'none' && !(c && c.a >= 0.99)) return null;
  }
  let base = {r: 255, g: 255, b: 255, a: 1};
  for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
  return base;
}
const bad = []; let checked = 0;
document.querySelectorAll('body *').forEach(el => {
  if (/^(SCRIPT|STYLE|NOSCRIPT|SVG|PATH|OPTION|CODE-SKIP)$/i.test(el.tagName) || !el.getClientRects().length) return;
  const own = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
  if (!own) return;
  const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return;
  const g = ground(el); if (!g) return;
  let fg = parse(cs.color); fg = over(fg, g);
  const l1 = lum(fg), l2 = lum(g), r = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  const size = parseFloat(cs.fontSize), large = size >= 24 || (size >= 18.66 && parseInt(cs.fontWeight) >= 700);
  checked++;
  if (r < (large ? 3 : 4.5)) bad.push({text: own.slice(0, 40), ratio: Math.round(r * 100) / 100, color: cs.color, tag: el.tagName + '.' + String(el.className).slice(0, 30)});
});
return {checked, bad: bad.slice(0, 12), nbad: bad.length};
"""


@pytest.mark.parametrize("key", PAGES)
def test_every_readable_text_meets_wcag_contrast_in_the_light_theme(driver, site, key):
    open_site(driver, site, key, theme="light")
    assert attr(driver) == "light"
    res = driver.execute_script(CONTRAST_JS)
    assert res["checked"] > 40, f"only {res['checked']} text elements were measured"
    assert not res["bad"], f"{res['nbad']} text elements are below WCAG AA on {key}: {res['bad']}"


def test_the_clear_button_label_is_readable_on_the_dark_page(driver, site):
    """The FAQ page's secondary buttons used the browser's default black label on dark glass."""
    open_site(driver, site, "faq")
    lum = driver.execute_script("""const c = getComputedStyle(document.querySelector('#faqResetButton, .faq-search-actions .btn-secondary')).color.match(/[\\d.]+/g).map(Number);
        return (c[0] + c[1] + c[2]) / 3""")
    assert lum > 200, "the Clear button label is dark on a dark page"


@pytest.mark.parametrize("theme", [None, "light"])
@pytest.mark.parametrize("width", [360, 414, 768, 1280])
@pytest.mark.parametrize("key", PAGES)
def test_no_sideways_scroll_in_either_theme(driver, site, key, width, theme):
    open_site(driver, site, key, theme=theme, width=width)
    over = driver.execute_script("return document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 1, f"{key} scrolls sideways by {over}px at {width}px ({theme or 'dark'})"


@pytest.mark.parametrize("width", [320, 360, 390, 414, 600, 760])
def test_the_header_fits_on_phones(driver, site, width):
    open_site(driver, site, "index", width=width)
    r = driver.execute_script("""const q = s => document.querySelector(s).getBoundingClientRect(), a = q('.brand'), t = q('.theme-toggle'), n = q('#navToggle');
        const hit = (x, y) => !(x.right <= y.left || y.right <= x.left || x.bottom <= y.top || y.bottom <= x.top);
        return {brandTheme: hit(a, t), themeBurger: hit(t, n), w: t.width, right: Math.max(t.right, n.right), vw: innerWidth}""")
    assert not r["brandTheme"] and not r["themeBurger"] and r["w"] >= 40 and r["right"] <= r["vw"]


def test_the_switch_works_without_opening_the_phone_menu(driver, site):
    open_site(driver, site, "index", width=390)
    assert not driver.execute_script("return document.getElementById('navMenu').classList.contains('open')")
    switch(driver).click()
    assert attr(driver) == "light"
    driver.find_element(By.ID, "navToggle").click()
    menu_bg = driver.execute_script("return getComputedStyle(document.getElementById('navMenu')).backgroundColor")
    assert menu_bg == "rgb(255, 255, 255)"


def test_code_boxes_and_viewers_stay_dark_in_the_light_theme(driver, site):
    open_site(driver, site, "index", theme="light")
    lums = driver.execute_script("""return ['.terminal-card', '.bibtex-block'].map(s => { const el = document.querySelector(s); if (!el) return null;
        const c = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number); return (c[0] + c[1] + c[2]) / 3; })""")
    assert [x for x in lums if x is not None] and all(x < 40 for x in lums if x is not None), lums


def test_printing_is_always_light_and_the_screen_theme_returns(driver, site):
    open_site(driver, site, "index")
    driver.execute_script("window.dispatchEvent(new Event('beforeprint'))")
    assert attr(driver) == "light"
    driver.execute_script("window.dispatchEvent(new Event('afterprint'))")
    assert attr(driver) is None                                              # back to the dark screen theme
    switch(driver).click()
    driver.execute_script("window.dispatchEvent(new Event('beforeprint')); window.dispatchEvent(new Event('afterprint'))")
    assert attr(driver) == "light"
    assert driver.execute_script("return getComputedStyle(document.querySelector('.theme-toggle')).display") != "none"
