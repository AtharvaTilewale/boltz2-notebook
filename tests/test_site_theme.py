"""The website's light / dark switch: wiring and stylesheet structure (no browser needed)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = {"index.html": "assets", "docs/faq.html": "../assets", "docs/use-cases.html": "../assets"}
CSS = (ROOT / "assets" / "css" / "styles_v2.css").read_text(encoding="utf-8")
JS = (ROOT / "assets" / "js" / "theme-switch.js").read_text(encoding="utf-8")
LIGHT_MARK = "/* ---- Light theme"


def page(name):
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name,assets", PAGES.items())
def test_every_page_has_the_switch_and_applies_a_saved_choice_before_the_stylesheet(name, assets):
    html = page(name)
    header = re.search(r'<header class="topbar">.*?</header>', html, re.S).group(0)
    buttons = re.findall(r'<button[^>]*data-act="theme"[^>]*>', header)
    assert len(buttons) == 1 and 'aria-label="Switch to light theme"' in buttons[0], buttons
    assert 'class="ico-sun"' in header and 'class="ico-moon"' in header
    snippet = html.index('localStorage.getItem("bz-site-theme")')
    stylesheet = html.index(f'<link rel="stylesheet" href="{assets}/css/styles_v2.css"')
    assert snippet < stylesheet, "the saved theme must be applied before the stylesheet paints (otherwise the page flashes)"
    assert f'<script src="{assets}/js/theme-switch.js" defer></script>' in html
    assert (ROOT / "assets" / "js" / "theme-switch.js").is_file()


def test_the_snippet_and_the_script_use_the_same_storage_key():
    assert "bz-site-theme" in JS
    assert all('localStorage.getItem("bz-site-theme")' in page(n) for n in PAGES)


def test_no_inline_colour_that_would_vanish_on_the_light_page():
    html = page("index.html")
    assert not re.search(r'id="downloadAsBtn"[^>]*style=', html)
    for name in PAGES:
        for style in re.findall(r'style="([^"]*)"', page(name)):
            assert not re.search(r"color:\s*(#fff\b|#ffffff|white)", style), (name, style)


def test_every_light_rule_is_scoped_to_the_light_theme():
    """The dark design is the default and must stay exactly as it was: nothing after the light marker may match without
    html[data-theme="light"] (the only exceptions are the print rule and the keyframe-free media wrappers)."""
    head, _, light = CSS.partition("/* ---- Light theme")
    assert light, "light theme marker missing"
    light = re.sub(r"/\*.*?\*/", "", light.split("\n", 1)[1], flags=re.S)             # comments may contain commas and braces
    rules = re.findall(r"([^{}]+)\{[^{}]*\}", re.sub(r"@media[^{]*\{", "", light))
    assert len(rules) > 60, "the light layer was not parsed"
    for block in rules:
        for s in (x.strip() for x in block.split(",") if x.strip()):
            assert s.startswith('html[data-theme="light"]') or s == ".theme-toggle", f"unscoped selector in the light layer: {s}"


def hexes(block):
    return {k: v.strip() for k, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", block)}


def lum(h):
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_light_palette_text_tokens_are_readable_on_the_page_and_on_cards():
    block = re.search(r'html\[data-theme="light"\]\s*\{(.*?)\n\}', CSS, re.S).group(1)
    tok = hexes(block)
    for name in ("--text", "--muted", "--accent-ink"):
        for ground in ("#ffffff", "#f4f7fc", "#d6e6ff"):         # card, page, the bluest part of the hero gradient
            assert ratio(tok[name], ground) >= 4.5, f"{name} {tok[name]} on {ground} = {ratio(tok[name], ground):.2f}"


def test_site_theme_script_parses_and_keeps_to_two_themes():
    esprima = pytest.importorskip("esprima")
    esprima.parseScript(JS)
    assert "'light'" in JS and "'dark'" in JS and "http" not in JS


def test_print_is_light_and_the_switch_is_hidden_when_printing():
    assert "beforeprint" in JS and "afterprint" in JS
    assert re.search(r"@media print\s*\{\s*\.theme-toggle\s*\{\s*display:\s*none", CSS)
