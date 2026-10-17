"""WCAG 2.1 contrast of every colour pair the design system uses, in light and dark."""
import re
from pathlib import Path

import pytest

CSS = (Path(__file__).resolve().parents[2] / "boltz2nb" / "ui" / "assets" / "theme.css").read_text()


def _tokens(block: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"(--bz-[a-z0-9-]+)\s*:\s*([^;]+);", block)}


def _blocks():
    light = re.search(r"\.bz\{(.*?)\n\}", CSS, re.S).group(1)
    dark = re.search(r'\.bz\[data-theme="dark"\],\s*html\[data-bz-theme="dark"\] \.bz:not\(\[data-theme\]\)\{(.*?)\n\}', CSS, re.S).group(1)
    return _tokens(light), _tokens(dark)


LIGHT, DARK = _blocks()


def _lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


TEXT_PAIRS = [
    ("--bz-text", "--bz-bg"), ("--bz-text", "--bz-surface"), ("--bz-text", "--bz-surface-2"), ("--bz-text", "--bz-surface-3"),
    ("--bz-text-2", "--bz-surface"), ("--bz-text-2", "--bz-surface-2"), ("--bz-text-2", "--bz-surface-3"), ("--bz-text-2", "--bz-bg"),
    ("--bz-text-3", "--bz-surface"), ("--bz-text-3", "--bz-surface-2"), ("--bz-text-3", "--bz-bg"),
    ("--bz-on-primary", "--bz-primary"),
    ("--bz-link", "--bz-surface"), ("--bz-link", "--bz-primary-soft"), ("--bz-link", "--bz-surface-2"),
    ("--bz-primary", "--bz-primary-soft"),
    ("--bz-ok", "--bz-ok-soft"), ("--bz-warn", "--bz-warn-soft"), ("--bz-err", "--bz-err-soft"), ("--bz-info", "--bz-info-soft"),
    ("--bz-ok", "--bz-surface"), ("--bz-err", "--bz-surface"), ("--bz-err", "--bz-surface-2"),
    ("--bz-protein", "--bz-protein-soft"), ("--bz-dna", "--bz-dna-soft"), ("--bz-rna", "--bz-rna-soft"), ("--bz-ligand", "--bz-ligand-soft"),
    ("--bz-text", "--bz-ok-soft"), ("--bz-text", "--bz-warn-soft"), ("--bz-text", "--bz-err-soft"), ("--bz-text", "--bz-info-soft"),
]
UI_PAIRS = [  # non-text UI boundaries need 3:1 (WCAG 1.4.11)
    ("--bz-field-border", "--bz-surface"), ("--bz-field-border", "--bz-surface-2"), ("--bz-primary", "--bz-surface"),
]


@pytest.mark.parametrize("name,tokens", [("light", LIGHT), ("dark", DARK)])
@pytest.mark.parametrize("fg,bg", TEXT_PAIRS)
def test_text_contrast(name, tokens, fg, bg):
    assert ratio(tokens[fg], tokens[bg]) >= 4.5, f"{name}: {fg} on {bg} = {ratio(tokens[fg], tokens[bg]):.2f}"


@pytest.mark.parametrize("name,tokens", [("light", LIGHT), ("dark", DARK)])
@pytest.mark.parametrize("fg,bg", UI_PAIRS)
def test_ui_component_contrast(name, tokens, fg, bg):
    assert ratio(tokens[fg], tokens[bg]) >= 3.0, f"{name}: {fg} on {bg} = {ratio(tokens[fg], tokens[bg]):.2f}"


def test_hero_and_gradient_text_contrast():
    # navy text on both ends of the brand gradient (active step badge)
    for end in ("#7C8CFF", "#63E6FF"):
        assert ratio("#0E1B32", end) >= 4.5
    # hero subtitle on the navy gradient
    assert ratio("#B9C5E3", "#111E3F") >= 4.5
