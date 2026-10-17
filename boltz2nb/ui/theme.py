"""Colour theme shared by every panel (input builder, run panel, result card, report): light by default, one switch.

The browser keeps the choice (``assets/theme.js``); this module keeps it for the Python session so panels drawn later - the run
panel, the result card, the inline report - start in the theme the user last picked.  ``BOLTZ2NB_THEME=dark`` changes the default.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .icons import icon

THEMES = ("light", "dark")
DEFAULT_THEME = "light"
_choice: str | None = None


def _clean(value: Any) -> str | None:
    text = str(value).strip().lower() if value is not None else ""
    return text if text in THEMES else None


def get_theme() -> str:
    """Theme new panels are drawn in: the last choice made this session, else ``BOLTZ2NB_THEME``, else light."""
    return _choice or _clean(os.environ.get("BOLTZ2NB_THEME")) or DEFAULT_THEME


def set_theme(value: Any) -> str:
    global _choice
    theme = _clean(value)
    if theme is None:
        raise ValueError(f"theme must be one of {list(THEMES)}, got {value!r}")
    _choice = theme
    return theme


def reset_theme() -> None:
    """Forget the session's choice (back to the default)."""
    global _choice
    _choice = None


def resolve(theme: str | None) -> str:
    """An explicit theme argument wins; otherwise the session's theme."""
    if theme is not None and _clean(theme) is None:
        raise ValueError(f"theme must be one of {list(THEMES)}, got {theme!r}")
    return _clean(theme) or get_theme()


def theme_attr(theme: str | None = None, hint: bool = True) -> str:
    """The ``data-theme`` attribute of a panel root. Omitted (``hint=False``) when the browser should decide: refreshes of the run
    panel and standalone report files, where the preference lives in the page, not in Python."""
    return f' data-theme="{resolve(theme)}"' if hint else ""


def theme_button(theme: str | None = None) -> str:
    """The light / dark switch; both icons are present and CSS shows the one for the target theme."""
    label = "Switch to light theme" if resolve(theme) == "dark" else "Switch to dark theme"
    return (f'<button type="button" class="bz-btn bz-btn--icon bz-themebtn" data-act="theme" title="{label}" aria-label="{label}">'
            f'<span class="bz-ico bz-ico--moon">{icon("moon")}</span><span class="bz-ico bz-ico--sun">{icon("sun")}</span></button>')


def theme_js() -> str:
    return (Path(__file__).parent / "assets" / "theme.js").read_text(encoding="utf-8")


def theme_script() -> str:
    """The switch's behaviour as an inline script; idempotent, so every panel can include it."""
    return f"<script>{theme_js()}</script>"
