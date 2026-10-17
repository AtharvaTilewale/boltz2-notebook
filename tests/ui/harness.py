"""Serve the real form with a Colab shim that routes ``invokeFunction`` to the real Python callbacks."""
from __future__ import annotations

import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from boltz2nb.ui.callbacks import CALLBACKS
from boltz2nb.ui.render import render_form

SHIM = """<script>
window.__errs = [];
window.addEventListener('error', function (e) { window.__errs.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errs.push('unhandled: ' + String(e.reason)); });
window.__rpc = [];
(function () {
  var wrap = new URLSearchParams(location.search).get('wrap') === '1';
  window.google = { colab: { kernel: { invokeFunction: function (name, args) {
    window.__rpc.push(name);
    return fetch('/rpc/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args) })
      .then(function (r) { return r.json(); })
      .then(function (j) { return wrap ? { data: { 'application/json': j } } : j; });
  } } } };
})();
</script>"""

FONT_FACES = """
@font-face{font-family:"Inter";font-weight:400;src:url(/fonts/inter-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:"Inter";font-weight:500;src:url(/fonts/inter-latin-500-normal.woff2) format("woff2")}
@font-face{font-family:"Inter";font-weight:600;src:url(/fonts/inter-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:"Inter";font-weight:700;src:url(/fonts/inter-latin-700-normal.woff2) format("woff2")}
@font-face{font-family:"JetBrains Mono";font-weight:400;src:url(/fonts/jetbrains-mono-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:"JetBrains Mono";font-weight:500;src:url(/fonts/jetbrains-mono-latin-500-normal.woff2) format("woff2")}
@font-face{font-family:"JetBrains Mono";font-weight:600;src:url(/fonts/jetbrains-mono-latin-600-normal.woff2) format("woff2")}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{fonts}html,body{margin:0;background:{bg}}body{padding:12px}</style></head><body>{shim}{form}</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path.startswith("/fonts/"):
            fdir = os.environ.get("BZ_FONT_DIR")
            f = Path(fdir or ".") / Path(self.path).name
            if not fdir or not f.is_file():
                self.send_error(404)
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "font/woff2")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/frame"):
            fq = parse_qs(urlparse(self.path).query)
            width = fq.pop("w", ["390"])[0]
            inner = "/?" + "&".join(f"{k}={v[0]}" for k, v in fq.items())
            body = (f'<!doctype html><html><body style="margin:0;background:#8a8f9c"><iframe id="f" src="{inner}" '
                    f'style="width:{int(width)}px;height:100vh;border:0;display:block;background:#fff"></iframe></body></html>').encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        q = parse_qs(urlparse(self.path).query)
        mode = q.get("mode", ["advanced"])[0]
        theme = q.get("theme", ["light"])[0]
        form = render_form(mode=mode, uid="t", fonts=False, theme=theme if theme in ("light", "dark") else None)
        bg = "#0b1020" if theme == "dark" else "#ffffff"
        body = PAGE.replace("{fonts}", FONT_FACES if os.environ.get("BZ_FONT_DIR") else "").replace("{bg}", bg).replace("{shim}", SHIM).replace("{form}", form).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        name = self.path.rsplit("/", 1)[-1]
        n = int(self.headers.get("Content-Length", 0))
        args = json.loads(self.rfile.read(n) or b"[]")
        try:
            out = CALLBACKS[name](*args)
        except Exception as exc:  # noqa: BLE001
            out = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
        body = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        os.environ["BOLTZ2NB_BASE_DIR"] = str(self.base_dir)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()

    def url(self, **q) -> str:
        qs = "&".join(f"{k}={v}" for k, v in q.items())
        return f"http://127.0.0.1:{self.port}/?{qs}"

    def frame_url(self, width: int, **q) -> str:
        """The same page inside an iframe of exactly ``width`` px (headless Firefox will not make a window narrower than 500 px)."""
        qs = "&".join(f"{k}={v}" for k, v in {"w": width, **q}.items())
        return f"http://127.0.0.1:{self.port}/frame?{qs}"

    def reset_files(self):
        for p in self.base_dir.glob("*"):
            shutil.rmtree(p) if p.is_dir() else p.unlink()


def find_firefox() -> tuple[str | None, str | None]:
    ff = os.environ.get("BZ_FIREFOX") or shutil.which("firefox")
    gd = os.environ.get("BZ_GECKODRIVER") or shutil.which("geckodriver")
    # /usr/bin/firefox on some distros is a snap stub that cannot run headless
    if ff and Path(ff).is_file():
        try:
            if "snap install" in Path(ff).read_text(errors="ignore")[:400]:
                ff = None
        except Exception:  # noqa: BLE001
            pass
    return ff, gd
