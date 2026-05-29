"""JSON API for Telegram Mini App (server-side tools that need no browser CORS)."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from v2.toolkit.net_extra_light import http_headers_report, website_status_report
from v2.toolkit.whois_light import rdap_lookup


def _q(params: dict[str, list[str]], key: str) -> str:
    vals = params.get(key) or [""]
    return (vals[0] if vals else "").strip()


def _json_response(ok: bool, *, text: str = "", error: str = "") -> tuple[int, bytes]:
    body: dict[str, Any] = {"ok": ok}
    if ok:
        body["text"] = text
    else:
        body["error"] = error or text or "error"
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return 200 if ok else 400, raw


def dispatch_miniapp_api(path: str, query_string: str) -> tuple[int, str, bytes]:
    """
    Handle ``/miniapp/api/<action>?...``.

    Returns ``(http_status, content_type, body_bytes)``.
    """
    sub = (path or "").strip("/")
    prefix = "miniapp/api/"
    if sub.startswith(prefix):
        action = sub[len(prefix) :].split("/")[0].lower()
    else:
        action = sub.split("/")[-1].lower() if "/api/" in sub else ""

    params = urllib.parse.parse_qs(query_string or "", keep_blank_values=False)

    if action == "headers":
        url = _q(params, "url")
        if not url:
            status, body = _json_response(False, error="missing_url")
            return status, "application/json; charset=utf-8", body
        ok, detail = http_headers_report(url)
        status, body = _json_response(ok, text=detail if ok else "", error=detail if not ok else "")
        return status, "application/json; charset=utf-8", body

    if action == "status":
        url = _q(params, "url")
        if not url:
            status, body = _json_response(False, error="missing_url")
            return status, "application/json; charset=utf-8", body
        ok, detail = website_status_report(url)
        status, body = _json_response(ok, text=detail if ok else "", error=detail if not ok else "")
        return status, "application/json; charset=utf-8", body

    if action == "whois":
        query = _q(params, "q") or _q(params, "url") or _q(params, "host")
        if not query:
            status, body = _json_response(False, error="missing_query")
            return status, "application/json; charset=utf-8", body
        ok, detail = rdap_lookup(query)
        status, body = _json_response(ok, text=detail if ok else "", error=detail if not ok else "")
        return status, "application/json; charset=utf-8", body

    err = json.dumps({"ok": False, "error": "unknown_action"}).encode("utf-8")
    return 404, "application/json; charset=utf-8", err
