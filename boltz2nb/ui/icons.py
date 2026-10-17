"""Inline SVG icon set (stroke icons on a 24x24 grid, drawn for this project).

Icons are emitted once per output as a hidden sprite and referenced with
``<svg class="i"><use href="#bz-i-NAME"/></svg>`` so no icon font or CDN is needed.
"""
from __future__ import annotations

ICONS: dict[str, str] = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "check": '<path d="m20 6-11 11-5-5"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "arrow-left": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    "trash": '<path d="M3 6h18M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14M10 11v6M14 11v6"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/>',
    "alert": '<path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="9.5"/><path d="M12 16v-4.5M12 8h.01"/>',
    "check-circle": '<circle cx="12" cy="12" r="9.5"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/>',
    "x-circle": '<circle cx="12" cy="12" r="9.5"/><path d="m15 9-6 6M9 9l6 6"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "file": '<path d="M14 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8z"/><path d="M14 2.5V8h5.5"/>',
    "link": '<path d="M10 13.5a4.5 4.5 0 0 0 6.4.4l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2M14 10.5a4.5 4.5 0 0 0-6.4-.4l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/>',
    "target": '<circle cx="12" cy="12" r="9.5"/><circle cx="12" cy="12" r="5.5"/><circle cx="12" cy="12" r="1.5"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1.5 14h5M9.5 8h5M17.5 16h5"/>',
    "play": '<path d="M7 4.5v15l12.5-7.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20.5 13A8.5 8.5 0 1 1 11 3.5a6.5 6.5 0 0 0 9.5 9.5z"/>',
    "sparkles": '<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
    "layers": '<path d="m12 2.5-9.5 5 9.5 5 9.5-5zM2.5 12.5l9.5 5 9.5-5M2.5 17.5l9.5 5 9.5-5"/>',
    "clock": '<circle cx="12" cy="12" r="9.5"/><path d="M12 6.5V12l3.5 2"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.2L3 16M3 21v-5h5"/>',
    "zap": '<path d="M13 2.5 4 14h7l-1 7.5L20 10h-7z"/>',
    "scale": '<path d="M12 3v18M5 21h14M7 7H3.5L2 13a3.5 3.5 0 0 0 7 0L7.5 7zM17 7h3.5L22 13a3.5 3.5 0 0 1-7 0L16.5 7zM7 7l10 0"/>',
    "flask": '<path d="M9.5 3h5M10.5 3v6L4.7 19a2 2 0 0 0 1.7 3h11.2a2 2 0 0 0 1.7-3L13.5 9V3M7.5 15h9"/>',
    "dna": '<path d="M5 3c0 6 14 6 14 12s-0 6-0 6M19 3c0 6-14 6-14 12v6M7.4 6h9.2M7.4 18h9.2M5.8 12h12.4"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8"/>',
    "code": '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "cpu": '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
}


def sprite() -> str:
    """Hidden ``<svg>`` holding every icon as a ``<symbol>``."""
    symbols = "".join(
        f'<symbol id="bz-i-{name}" viewBox="0 0 24 24">{body}</symbol>' for name, body in ICONS.items()
    )
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">{symbols}</svg>'


def icon(name: str, cls: str = "") -> str:
    if name not in ICONS:
        raise KeyError(f"unknown icon {name!r}")
    extra = f" {cls}" if cls else ""
    return f'<svg class="i{extra}" aria-hidden="true"><use href="#bz-i-{name}"/></svg>'


# Brand mark (same artwork as assets/boltz2-mark.svg), id-prefixed so several can share a page.
def brand_mark(uid: str = "m") -> str:
    return (
        '<svg class="bz-mark" viewBox="0 0 128 128" fill="none" aria-hidden="true">'
        f'<defs><linearGradient id="bzbg-{uid}" x1="13" y1="12" x2="118" y2="121" gradientUnits="userSpaceOnUse">'
        '<stop stop-color="#0E1B32"/><stop offset="1" stop-color="#111E3F"/></linearGradient>'
        f'<linearGradient id="bzarc-{uid}" x1="79" y1="23" x2="111" y2="55" gradientUnits="userSpaceOnUse">'
        '<stop stop-color="#7C8CFF"/><stop offset="1" stop-color="#63E6FF"/></linearGradient></defs>'
        f'<rect x="8" y="8" width="112" height="112" rx="30" fill="url(#bzbg-{uid})" stroke="rgba(255,255,255,.14)"/>'
        '<path d="M34 35H67C81.3594 35 91 42.2929 91 54.5C91 63.3891 85.8643 69.0918 77.5 71.5C87.0557 73.4609 93 '
        '79.8848 93 89C93 102.5 82.0182 111 65 111H34V35ZM50.5 48V66H63C70.8242 66 75.5 62.9492 75.5 57C75.5 '
        '51.0508 70.8242 48 63 48H50.5ZM50.5 78V98H65C73.4609 98 78.5 94.5273 78.5 88C78.5 81.4727 73.4609 78 65 '
        '78H50.5Z" fill="white"/>'
        f'<path d="M79 23C96.6731 23 111 37.3269 111 55" stroke="url(#bzarc-{uid})" stroke-width="8" stroke-linecap="round"/>'
        '<circle cx="111" cy="55" r="5" fill="#63E6FF"/></svg>'
    )
