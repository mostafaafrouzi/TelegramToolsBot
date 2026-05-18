"""Google Drive upload via service account (shared folder)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional


def _service_account_path() -> Optional[Path]:
    raw = (os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_file():
        return p
    base = Path(__file__).resolve().parents[2]
    candidate = base / raw
    return candidate if candidate.is_file() else None


def _folder_id() -> str:
    return (os.getenv("GOOGLE_DRIVE_FOLDER_ID") or "").strip()


def drive_configured() -> bool:
    """Legacy global env check (prefer per-user :func:`user_has_drive`)."""
    return _service_account_path() is not None and bool(_folder_id())


def upload_file(
    local_path: str | Path,
    *,
    file_name: Optional[str] = None,
    service_account_path: Optional[str | Path] = None,
    folder_id: Optional[str] = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Upload to Drive folder. Returns ``(ok, message, metadata)``."""
    sa_path = Path(service_account_path) if service_account_path else _service_account_path()
    fid = (folder_id or _folder_id()).strip()
    if not sa_path or not sa_path.is_file() or not fid:
        return False, "Drive service account JSON or folder_id missing for this user", {}
    path = Path(local_path)
    if not path.is_file():
        return False, "local file not found", {}
    name = (file_name or path.name)[:240]
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return False, "install google-api-python-client and google-auth on server", {}

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        metadata: dict[str, Any] = {"name": name, "parents": [fid]}
        media = MediaFileUpload(str(path), resumable=True)
        created = (
            service.files()
            .create(body=metadata, media_body=media, fields="id, name, webViewLink")
            .execute()
        )
        link = created.get("webViewLink") or created.get("id") or ""
        return True, str(link), dict(created)
    except Exception as e:
        return False, str(e)[:900], {}


def download_file(
    file_id: str,
    dest_path: str | Path,
    *,
    service_account_path: Optional[str | Path] = None,
) -> tuple[bool, str]:
    """Download Drive file by id to ``dest_path``."""
    sa_path = Path(service_account_path) if service_account_path else _service_account_path()
    if not sa_path or not sa_path.is_file():
        return False, "Drive service account JSON missing for this user"
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io
    except ImportError:
        return False, "install google-api-python-client and google-auth on server"

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        request = service.files().get_media(fileId=file_id)
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with io.FileIO(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return True, dest.name
    except Exception as e:
        return False, str(e)[:900]
