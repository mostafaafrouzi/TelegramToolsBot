"""Google Drive OAuth2 (user login) — auth URL + code exchange."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

DRIVE_SCOPES = "https://www.googleapis.com/auth/drive.file"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def oauth_configured() -> bool:
    return bool(
        (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID") or "").strip()
        and (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET") or "").strip()
    )


def oauth_redirect_uri() -> str:
    base = (os.getenv("MINIAPP_BASE_URL") or os.getenv("GOOGLE_DRIVE_OAUTH_REDIRECT_URI") or "").strip()
    if not base:
        return ""
    return f"{base.rstrip('/')}/oauth/google/callback"


def build_auth_url(telegram_user_id: int) -> tuple[bool, str]:
    cid = (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID") or "").strip()
    redirect = oauth_redirect_uri()
    if not cid or not redirect:
        return False, "oauth_not_configured"
    params = {
        "client_id": cid,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": DRIVE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": str(int(telegram_user_id)),
    }
    return True, f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, *, redirect_uri: Optional[str] = None) -> tuple[bool, dict[str, Any] | str]:
    cid = (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID") or "").strip()
    secret = (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET") or "").strip()
    redir = (redirect_uri or oauth_redirect_uri()).strip()
    if not cid or not secret or not redir:
        return False, "oauth_not_configured"
    body = urllib.parse.urlencode(
        {
            "code": code.strip(),
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": redir,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return False, str(e)[:500]
    if "error" in data:
        return False, str(data.get("error_description") or data.get("error"))
    if not data.get("refresh_token") and not data.get("access_token"):
        return False, "no_token_in_response"
    return True, data


def save_token_file(path: Path, token_payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize to google-auth authorized_user format
    out = {
        "token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "token_uri": TOKEN_URL,
        "client_id": (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID") or "").strip(),
        "client_secret": (os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET") or "").strip(),
        "scopes": [DRIVE_SCOPES],
    }
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


def refresh_token_file(path: Path) -> tuple[bool, str]:
    """Refresh expired OAuth token in place."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        return False, "google-auth not installed"
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
        creds = Credentials.from_authorized_user_info(info)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            path.write_text(creds.to_json(), encoding="utf-8")
        return True, "ok"
    except Exception as e:
        return False, str(e)[:500]
