"""Google Drive transfer adapter (per-user service account or OAuth)."""

from __future__ import annotations

from typing import Any, Optional


class GoogleDriveTransferAdapter:
    def validate_account(self, user_ctx: dict) -> bool:
        return bool(user_ctx.get("drive_linked"))

    def healthcheck(
        self,
        *,
        service_account_path: Optional[str] = None,
        oauth_token_path: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        if not folder_id:
            return False, "Drive folder_id not set for this user"
        has_sa = bool(service_account_path)
        has_oauth = bool(oauth_token_path)
        if not has_sa and not has_oauth:
            return False, "Drive credentials not set (service account or OAuth)"
        mode = "oauth" if has_oauth else "service_account"
        try:
            from v2.transfer.drive_client import list_files

            ok, detail = list_files(
                service_account_path=service_account_path,
                oauth_token_path=oauth_token_path,
                folder_id=folder_id,
                limit=1,
            )
            if ok:
                return True, f"mode={mode} folder_id={folder_id} — API OK"
            return False, f"mode={mode} folder_id={folder_id} — API error: {detail}"
        except Exception as e:
            return False, f"folder_id={folder_id} — healthcheck error: {e}"

    def resolve_source(self, task: dict) -> Any:
        return task.get("source", {})

    def download(self, source_ref: Any, tmp_path: str) -> dict:
        from v2.transfer.drive_client import download_file

        file_id = source_ref.get("file_id") if isinstance(source_ref, dict) else str(source_ref)
        sa = oauth = None
        if isinstance(source_ref, dict):
            sa = source_ref.get("service_account_path")
            oauth = source_ref.get("oauth_token_path")
        ok, detail = download_file(
            file_id,
            tmp_path,
            service_account_path=sa,
            oauth_token_path=oauth,
        )
        return {"ok": ok, "path": detail} if ok else {"ok": False, "error": detail}

    def upload(self, local_path: str, destination_ref: Any) -> dict:
        from v2.transfer.drive_client import upload_file

        sa = folder = name = oauth = None
        if isinstance(destination_ref, dict):
            sa = destination_ref.get("service_account_path")
            oauth = destination_ref.get("oauth_token_path")
            folder = destination_ref.get("folder_id")
            name = destination_ref.get("file_name")
        ok, msg, meta = upload_file(
            local_path,
            file_name=name,
            service_account_path=sa,
            oauth_token_path=oauth,
            folder_id=folder,
        )
        if not ok:
            return {"ok": False, "error": msg}
        return {"ok": True, "provider_id": meta.get("id", ""), "webViewLink": msg, "metadata": meta}
