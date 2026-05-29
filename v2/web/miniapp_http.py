"""Serve static mini-app HTML and optional OAuth callback routes."""

from __future__ import annotations

import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional

from v2.web.miniapp_api import dispatch_miniapp_api


OAuthCallbackFn = Callable[[int, str], tuple[bool, str]]


def start_miniapp_server(
    web_root: Path,
    *,
    host: str = "0.0.0.0",
    port: int = 8788,
    google_oauth_callback: Optional[OAuthCallbackFn] = None,
) -> None:
    root = Path(web_root).resolve()
    oauth_fn = google_oauth_callback

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format, *args):
            pass

        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            super().end_headers()

        def _send_api(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if "/miniapp/api/" in parsed.path:
                status, ctype, body = dispatch_miniapp_api(parsed.path, parsed.query)
                self._send_api(status, ctype, body)
                return
            if path in ("/miniapp", "/miniapp/"):
                self.send_response(302)
                self.send_header("Location", "/miniapp/index.html")
                self.end_headers()
                return
            if parsed.path.rstrip("/") == "/oauth/google/callback" and oauth_fn:
                qs = urllib.parse.parse_qs(parsed.query)
                code = (qs.get("code") or [""])[0]
                state = (qs.get("state") or [""])[0]
                err = (qs.get("error") or [""])[0]
                if err:
                    self._html(400, "OAuth denied", f"Error: {err}")
                    return
                try:
                    uid = int(state)
                except ValueError:
                    self._html(400, "Invalid state", "Missing telegram user id in state.")
                    return
                if not code:
                    self._html(400, "Missing code", "No authorization code received.")
                    return
                ok, detail = oauth_fn(uid, code)
                if ok:
                    self._html(
                        200,
                        "Google Drive connected",
                        "You can close this tab and return to Telegram.",
                    )
                else:
                    self._html(500, "Connection failed", detail or "unknown error")
                return
            return super().do_GET()

        def _html(self, status: int, title: str, body: str) -> None:
            content = (
                f"<!DOCTYPE html><html><head><meta charset=utf-8>"
                f"<title>{title}</title></head><body><h1>{title}</h1><p>{body}</p></body></html>"
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def _run():
        httpd = ThreadingHTTPServer((host, port), Handler)
        httpd.serve_forever()

    t = threading.Thread(target=_run, name="miniapp-http", daemon=True)
    t.start()
