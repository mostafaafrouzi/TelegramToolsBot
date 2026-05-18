"""Google Drive transfer adapter (per-user service account JSON)."""

from __future__ import annotations

from typing import Any, Optional


class GoogleDriveTransferAdapter:
    def validate_account(self, user_ctx: dict) -> bool:
        return bool(user_ctx.get("drive_linked"))

    def healthcheck(
        self,
        *,
        service_account_path: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        if not service_account_path or not folder_id:
            return False, "Drive service account or folder_id not set for this user"
        from pathlib import Path

        p = Path(service_account_path)
        if not p.is_file():
            return False, "service account file missing"
        return True, f"folder_id={folder_id}"

    def resolve_source(self, task: dict) -> Any:
        return task.get("source", {})

    def download(self, source_ref: Any, tmp_path: str) -> dict:
        return {"ok": False, "error": "drive_download_not_implemented"}

    def upload(self, local_path: str, destination_ref: Any) -> dict:
        from v2.transfer.drive_client import upload_file

        sa = folder = name = None
        if isinstance(destination_ref, dict):
            sa = destination_ref.get("service_account_path")
            folder = destination_ref.get("folder_id")
            name = destination_ref.get("file_name")
        ok, msg, meta = upload_file(
            local_path,
            file_name=name,
            service_account_path=sa,
            folder_id=folder,
        )
        if not ok:
            return {"ok": False, "error": msg}
        return {"ok": True, "provider_id": meta.get("id", ""), "webViewLink": msg, "metadata": meta}
