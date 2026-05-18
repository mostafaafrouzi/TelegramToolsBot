"""Google Drive transfer adapter (MVP stub; OAuth worker hook in backlog)."""

from __future__ import annotations

import os
from typing import Any


class GoogleDriveTransferAdapter:
    def validate_account(self, user_ctx: dict) -> bool:
        return bool(user_ctx.get("drive_linked"))

    def healthcheck(self) -> tuple[bool, str]:
        cid = (os.getenv("GOOGLE_DRIVE_CLIENT_ID") or "").strip()
        secret = (os.getenv("GOOGLE_DRIVE_CLIENT_SECRET") or "").strip()
        if not cid or not secret:
            return False, "GOOGLE_DRIVE_CLIENT_ID/SECRET not set on server"
        return True, "Drive OAuth credentials present (OAuth flow: post-MVP)"

    def resolve_source(self, task: dict) -> Any:
        return task.get("source", {})

    def download(self, source_ref: Any, tmp_path: str) -> dict:
        return {"ok": False, "error": "drive_download_not_implemented"}

    def upload(self, local_path: str, destination_ref: Any) -> dict:
        from v2.transfer.drive_client import upload_file

        name = None
        if isinstance(destination_ref, dict):
            name = destination_ref.get("file_name")
        ok, msg, meta = upload_file(local_path, file_name=name)
        if not ok:
            return {"ok": False, "error": msg}
        return {"ok": True, "provider_id": meta.get("id", ""), "webViewLink": msg, "metadata": meta}
