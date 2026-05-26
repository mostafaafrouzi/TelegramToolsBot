"""Serve static mini-app HTML (HTTPS required by Telegram WebApp in production)."""

from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def start_miniapp_server(web_root: Path, *, host: str = "0.0.0.0", port: int = 8788) -> None:
    root = Path(web_root).resolve()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format, *args):
            pass

    def _run():
        httpd = ThreadingHTTPServer((host, port), Handler)
        httpd.serve_forever()

    t = threading.Thread(target=_run, name="miniapp-http", daemon=True)
    t.start()
