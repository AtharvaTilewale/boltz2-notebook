"""Assemble self-contained HTML for the notebook front-end (no build step, no external scripts)."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .. import __version__
from ..run_params import DEFAULTS, PAIRING_STRATEGIES, PROFILES, RANGES
from .icons import brand_mark, icon, sprite
from .theme import resolve, theme_button, theme_js

ASSETS = Path(__file__).parent / "assets"
FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500;600&display=swap">'
)
MODE_LABELS = {"standard": "Standard", "advanced": "Advanced"}


def read_asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def expand_icons(html: str) -> str:
    return re.sub(r"@@ICON:([a-z0-9-]+)@@", lambda m: icon(m.group(1)), html)


def client_config(mode: str) -> dict:
    """Constants shared with the browser so the form and the Python validators cannot drift."""
    defaults = {k: v for k, v in DEFAULTS.items() if v is None or isinstance(v, (bool, int, float, str))}
    return {
        "mode": mode,
        "version": __version__,
        "defaults": defaults,
        "profiles": PROFILES,
        "ranges": {k: list(v) for k, v in RANGES.items()},
        "pairing": list(PAIRING_STRATEGIES),
        "msaChoices": [32, 64, 128, 256, 512, 1024, 2048, 4096, 8192],
        "subsampleChoices": [4, 8, 16, 32, 64, 128, 256, 512, 1024],
    }


CONFIG_MARK = "/*@@CONFIG@@*/ {}"


def script_json(obj) -> str:
    """JSON that is safe to place inside an inline <script>: no '<' (so no '</script>' or '<!--'), no line separators."""
    return (json.dumps(obj, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render_form(mode: str = "advanced", uid: str | None = None, fonts: bool = True, theme: str | None = None) -> str:
    """HTML for the input builder. ``standard`` hides DNA/RNA and the advanced-modelling step.

    ``theme`` (``"light"`` / ``"dark"``) overrides the session's theme, which is light unless the user switched it."""
    if mode not in MODE_LABELS:
        raise ValueError(f"mode must be one of {sorted(MODE_LABELS)}")
    uid = uid or uuid.uuid4().hex[:8]
    markup = read_asset("form.html")
    markup = (markup.replace("@@UID@@", uid).replace("@@MODE@@", mode).replace("@@MODE_LABEL@@", MODE_LABELS[mode])
              .replace("@@VERSION@@", __version__).replace("@@SPRITE@@", sprite()).replace("@@MARK@@", brand_mark(uid))
              .replace("@@THEME@@", resolve(theme)).replace("@@THEME_BUTTON@@", theme_button(theme)))
    markup = expand_icons(markup)
    css = read_asset("theme.css") + "\n" + read_asset("form.css")
    js = read_asset("form.js").replace("@@UID@@", uid)
    assert CONFIG_MARK in js, "form.js lost its config placeholder"
    js = js.replace(CONFIG_MARK, script_json(client_config(mode)))
    return f"{FONT_LINKS if fonts else ''}<style>{css}</style>{markup}<script>{theme_js()}\n{js}</script>"
