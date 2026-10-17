"""Live run panel: turns Boltz's raw log into a phase tracker with an elapsed timer.

``RunState`` is fed log lines, ``render_live`` returns the HTML for the current state and
``LivePanel`` pushes updates to a Jupyter/Colab display handle (throttled).  Outside IPython
``LivePanel`` degrades to printing one line per log message.
"""
from __future__ import annotations

import html
import re
import time
from collections import deque
from dataclasses import dataclass, field

from .icons import brand_mark, icon, sprite
from .render import FONT_LINKS, read_asset
from .theme import theme_attr, theme_button, theme_script

PHASES = [("prepare", "Prepare input"), ("msa", "Alignments"), ("fold", "Fold"), ("affinity", "Affinity"), ("finish", "Finish")]
_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_PCT = re.compile(r"(\d{1,3})%\|")
_FRAC = re.compile(r"\b(\d+)/(\d+)\b")


@dataclass
class RunState:
    job_name: str = "job"
    has_affinity: bool = False
    msa_server: bool = True
    gpu: str = ""
    engine: str = ""
    samples: int = 1
    status: str = "running"            # running | completed | failed
    phase: str = "prepare"
    progress: float | None = None      # 0..1 for the current phase when the log reports it
    started: float = field(default_factory=time.time)
    finished: float | None = None
    lines: deque = field(default_factory=lambda: deque(maxlen=14))
    cause: str = ""
    fix: str = ""
    command: str = ""                  # shown in a collapsed block for troubleshooting

    # ---- derived
    def phases(self) -> list[tuple[str, str]]:
        out = []
        for key, label in PHASES:
            if key == "affinity" and not self.has_affinity:
                continue
            if key == "msa" and not self.msa_server:
                continue
            out.append((key, label))
        return out

    def elapsed(self, now: float | None = None) -> float:
        return max(0.0, (self.finished or now or time.time()) - self.started)

    def _advance(self, key: str) -> None:
        order = [k for k, _ in PHASES]
        if order.index(key) > order.index(self.phase):
            self.phase = key
            self.progress = None

    def feed(self, raw: str) -> None:
        line = _ANSI.sub("", raw).replace("\r", "").strip()
        if not line:
            return
        low = line.lower()
        is_bar = bool(_PCT.search(line)) or "━" in line or "it/s" in low or "s/it" in low
        if "predicting property: affinity" in low or "running affinity prediction" in low or "checking input data for affinity" in low:
            self._advance("affinity")
        elif "calling msa server" in low or "msa server url" in low:
            self._advance("msa")
        elif "running structure prediction" in low or low.startswith("predicting"):
            self._advance("fold")
        elif "checking input data" in low or low.startswith("processing"):
            self._advance("prepare")
        if is_bar:
            m = _PCT.search(line)
            if m:
                self.progress = min(1.0, int(m.group(1)) / 100)
            else:
                f = _FRAC.search(line)
                if f and int(f.group(2)):
                    self.progress = min(1.0, int(f.group(1)) / int(f.group(2)))
            return  # progress bars are shown graphically, not as log lines
        if len(line) > 220:
            line = line[:217] + "..."
        if not self.lines or self.lines[-1] != line:
            self.lines.append(line)

    def finish(self, ok: bool, cause: str = "", fix: str = "") -> None:
        self.status = "completed" if ok else "failed"
        self.finished = time.time()
        self.cause, self.fix = cause, fix
        if ok:
            self.phase = "finish"
            self.progress = 1.0


def _fmt_time(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}" if s < 3600 else f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def render_styles() -> str:
    """Fonts + design-system CSS; emitted once per output area, then reused by every refresh."""
    return FONT_LINKS + "<style>" + read_asset("theme.css") + "\n" + read_asset("results.css") + "</style>"


def render_live(state: RunState, uid: str = "live", now: float | None = None, standalone_css: bool = True,
                theme: str | None = None, hint: bool = True) -> str:
    """The run panel. The first drawing (``hint=True``) carries the theme script and the session's theme; refreshes (``hint=False``)
    leave the theme to the page, so a switch made mid-run is not undone."""
    now = now or time.time()
    keys = [k for k, _ in state.phases()]
    cur = keys.index(state.phase) if state.phase in keys else len(keys) - 1
    steps = []
    for i, (_key, label) in enumerate(state.phases()):
        if state.status == "completed" or i < cur:
            st = "done"
        elif i == cur and state.status == "running":
            st = "active"
        elif i == cur and state.status == "failed":
            st = "error"
        else:
            st = "todo"
        glyph = icon("check") if st == "done" else ("!" if st == "error" else ('<span class="bz-spin"></span>' if st == "active" else str(i + 1)))
        steps.append(f'<li class="bz-phase" data-state="{st}"><span class="bz-phase-n">{glyph}</span><span>{html.escape(label)}</span></li>')
    chip = {"running": '<span class="bz-chip bz-chip--info"><span class="bz-spin"></span>Running</span>',
            "completed": f'<span class="bz-chip bz-chip--ok">{icon("check")}Completed</span>',
            "failed": f'<span class="bz-chip bz-chip--err">{icon("x-circle")}Failed</span>'}[state.status]
    pct = state.progress
    bar = ""
    if state.status == "running":
        if pct is not None and 0 < pct < 1:
            bar = f'<div class="bz-bar bz-bar--lg" role="progressbar" aria-valuenow="{int(pct * 100)}" aria-valuemin="0" aria-valuemax="100"><i style="width:{pct * 100:.0f}%"></i></div>'
        else:
            bar = '<div class="bz-bar bz-bar--lg bz-bar--busy" role="progressbar" aria-label="Working"><i></i></div>'
    elapsed = state.elapsed(now)
    timer = f'<span class="bz-num" data-bz-e0="{elapsed:.1f}">{_fmt_time(elapsed)}</span>'
    tick = ""
    if state.status == "running":
        tick = ("<script>(function(){if(window.__bzTick){clearInterval(window.__bzTick);}var el=document.querySelector('[data-bz-e0]');"
                "if(!el){return;}var e0=parseFloat(el.getAttribute('data-bz-e0')),t0=Date.now();function f(){var s=Math.round(e0+(Date.now()-t0)/1000),"
                "m=Math.floor(s/60);el.textContent=(m>=60?Math.floor(m/60)+':'+String(m%60).padStart(2,'0'):m)+':'+String(s%60).padStart(2,'0');}"
                "f();window.__bzTick=setInterval(f,1000);})();</script>")
    meta = [f"{icon('clock')}<span>{timer}</span>"]
    if state.gpu:
        meta.append(f"{icon('cpu')}<span>{html.escape(state.gpu)}</span>")
    if state.engine:
        meta.append(f"{icon('box')}<span>{html.escape(state.engine)}</span>")
    meta.append(f"{icon('layers')}<span>{state.samples} sample{'s' if state.samples != 1 else ''}</span>")
    err = ""
    if state.status == "failed":
        err = (f'<div class="bz-alert bz-alert--err" style="margin-top:14px">{icon("x-circle")}<div><strong>{html.escape(state.cause or "The run failed.")}</strong>'
               f'{"<br>" + html.escape(state.fix) if state.fix else ""}</div></div>')
    log = ""
    if state.lines:
        body = html.escape("\n".join(state.lines))
        log = (f'<details class="bz-acc" style="margin-top:14px"{" open" if state.status != "completed" else ""}><summary style="padding:10px 14px">'
               f'<span class="bz-acc-t" style="font-size:13px">Log</span><span class="bz-acc-d">last {len(state.lines)} lines</span>'
               f'<span class="bz-chev">{icon("chevron-down")}</span></summary><pre class="bz-pre" style="border:0;border-top:1px solid var(--bz-border);'
               f'border-radius:0 0 13px 13px;max-height:230px">{body}</pre></details>')
    if state.command:
        log += (f'<details class="bz-acc" style="margin-top:10px"><summary style="padding:10px 14px"><span class="bz-acc-t" style="font-size:13px">Command</span>'
                f'<span class="bz-acc-d">exact boltz invocation</span><span class="bz-chev">{icon("chevron-down")}</span></summary>'
                f'<pre class="bz-pre" style="border:0;border-top:1px solid var(--bz-border);border-radius:0 0 13px 13px;white-space:pre-wrap">{html.escape(state.command)}</pre></details>')
    css = render_styles() if standalone_css else ""
    return (f'{css}<div class="bz bz-live"{theme_attr(theme, hint)} id="bz-live-{uid}">{sprite()}'
            f'<div class="bz-live-h">{brand_mark("l" + uid)}<div style="min-width:0"><h2>Boltz-2 prediction</h2>'
            f'<p><code>{html.escape(state.job_name)}</code></p></div><div class="bz-inline" style="margin-left:auto;gap:8px">{chip}{theme_button(theme)}</div></div>'
            f'<div class="bz-live-b"><ol class="bz-phases">{"".join(steps)}</ol>{bar}'
            f'<div class="bz-live-meta">{"".join(f"<span>{m}</span>" for m in meta)}</div>{err}{log}</div></div>{tick}{theme_script() if hint else "<script>if(window.__bzTheme){window.__bzTheme.apply();}</script>"}')


class LivePanel:
    """Pushes ``render_live`` updates to a display handle; plain ``print`` when IPython is absent."""

    def __init__(self, state: RunState, interval: float = 0.9):
        self.state = state
        self.interval = interval
        self._last = 0.0
        self._handle = None
        self._display = None
        self._HTML = None
        try:
            from IPython import get_ipython
            from IPython.display import HTML, display
            if get_ipython() is not None:
                self._display, self._HTML = display, HTML
        except Exception:  # noqa: BLE001
            pass

    @property
    def rich(self) -> bool:
        return self._display is not None

    def start(self) -> None:
        if self.rich:
            self._display(self._HTML(render_styles()))
            self._handle = self._display(self._HTML(render_live(self.state, standalone_css=False)), display_id=True)
            self._last = time.time()

    def feed(self, line: str) -> None:
        before = (self.state.phase, len(self.state.lines))
        self.state.feed(line)
        if not self.rich:
            clean = _ANSI.sub("", line).strip()
            if clean and not (_PCT.search(clean) or "━" in clean):
                print(clean[:300])
            return
        changed = before[0] != self.state.phase
        if changed or time.time() - self._last >= self.interval:
            self._push()

    def _push(self) -> None:
        if self._handle is not None:
            self._handle.update(self._HTML(render_live(self.state, standalone_css=False, hint=False)))
            self._last = time.time()

    def finish(self, ok: bool, cause: str = "", fix: str = "") -> None:
        self.state.finish(ok, cause, fix)
        if self.rich:
            self._push()
        else:
            print(f"[{'ok' if ok else 'failed'}] {self.state.job_name} in {_fmt_time(self.state.elapsed())}")
            if not ok and cause:
                print(f"Likely cause: {cause}\nSuggested fix: {fix}")
