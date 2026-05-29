"""Google Drive upload/download via per-user service account or OAuth token."""

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


def _resolve_service_account_path(path: Optional[str | Path]) -> Optional[Path]:
    if path is None:
        return _service_account_path()
    p = Path(path)
    if p.is_file():
        return p
    if not p.is_absolute():
        base = Path(__file__).resolve().parents[2]
        candidate = base / p
        if candidate.is_file():
            return candidate
    return p if p.is_file() else None


def _resolve_oauth_token_path(path: Optional[str | Path]) -> Optional[Path]:
    if not path:
        return None
    p = Path(path)
    if p.is_file():
        return p
    if not p.is_absolute():
        base = Path(__file__).resolve().parents[2]
        candidate = base / p
        if candidate.is_file():
            return candidate
    return None


def _folder_id() -> str:
    return (os.getenv("GOOGLE_DRIVE_FOLDER_ID") or "").strip()


def drive_configured() -> bool:
    """Legacy global env check (prefer per-user :func:`user_has_drive`)."""
    return _service_account_path() is not None and bool(_folder_id())


def _build_drive_service(
    *,
    service_account_path: Optional[str | Path] = None,
    oauth_token_path: Optional[str | Path] = None,
    readonly: bool = False,
) -> tuple[Any, str]:
    scope = (
        "https://www.googleapis.com/auth/drive.readonly"
        if readonly
        else "https://www.googleapis.com/auth/drive.file"
    )
    oauth_p = _resolve_oauth_token_path(oauth_token_path)
    if oauth_p:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            from v2.toolkit.drive_oauth_light import refresh_token_file

            refresh_token_file(oauth_p)
            creds = Credentials.from_authorized_user_file(str(oauth_p), scopes=[scope])
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return build("drive", "v3", credentials=creds, cache_discovery=False), ""
        except ImportError:
            return None, "install google-api-python-client and google-auth on server"
        except Exception as e:
            return None, str(e)[:900]

    sa_path = _resolve_service_account_path(service_account_path)
    if not sa_path or not sa_path.is_file():
        return None, "Drive credentials missing (service account or OAuth token)"
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=[scope],
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False), ""
    except ImportError:
        return None, "install google-api-python-client and google-auth on server"
    except Exception as e:
        return None, str(e)[:900]


def upload_file(
    local_path: str | Path,
    *,
    file_name: Optional[str] = None,
    service_account_path: Optional[str | Path] = None,
    oauth_token_path: Optional[str | Path] = None,
    folder_id: Optional[str] = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Upload to Drive folder. Returns ``(ok, message, metadata)``."""
    fid = (folder_id or _folder_id()).strip()
    if not fid:
        return False, "Drive folder_id missing for this user", {}
    path = Path(local_path)
    if not path.is_file():
        return False, "local file not found", {}
    service, err = _build_drive_service(
        service_account_path=service_account_path,
        oauth_token_path=oauth_token_path,
        readonly=False,
    )
    if not service:
        return False, err, {}
    name = (file_name or path.name)[:240]
    try:
        from googleapiclient.http import MediaFileUpload

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
    oauth_token_path: Optional[str | Path] = None,
) -> tuple[bool, str]:
    """Download Drive file by id to ``dest_path``."""
    service, err = _build_drive_service(
        service_account_path=service_account_path,
        oauth_token_path=oauth_token_path,
        readonly=True,
    )
    if not service:
        return False, err
    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io

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


def list_files(
    *,
    service_account_path: Optional[str | Path] = None,
    oauth_token_path: Optional[str | Path] = None,
    folder_id: Optional[str] = None,
    limit: int = 20,
) -> tuple[bool, str]:
    """List files visible in the configured Drive folder."""
    fid = (folder_id or _folder_id()).strip()
    if not fid:
        return False, "Drive folder_id missing for this user"
    service, err = _build_drive_service(
        service_account_path=service_account_path,
        oauth_token_path=oauth_token_path,
        readonly=True,
    )
    if not service:
        return False, err
    try:
        q = f"'{fid}' in parents and trashed = false"
        res = (
            service.files()
            .list(
                q=q,
                pageSize=max(1, min(int(limit), 100)),
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = res.get("files") or []
        if not files:
            return True, "No files found."
        lines = []
        for item in files:
            size = item.get("size") or "-"
            lines.append(f"{item.get('name')} — `{item.get('id')}` — {size} bytes")
        return True, "\n".join(lines)
    except Exception as e:
        return False, str(e)[:900]
