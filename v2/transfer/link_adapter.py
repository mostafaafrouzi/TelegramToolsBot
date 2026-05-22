"""HTTP / link side of the transfer contract.

Bot-side probe/download: ``v2.transfer.link_direct``.
Worker ``direct_url`` in ``rub.py`` remains for legacy queued URL tasks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from v2.transfer.link_direct import download_to_path, probe_metadata


class HttpLinkTransferAdapter:
    """Link metadata probe and server download (used by link-direct menu / direct-send)."""

    def validate_account(self, user_ctx: dict) -> bool:
        return True

    def healthcheck(self) -> tuple[bool, str]:
        return True, "link_direct"

    def resolve_source(self, task: dict) -> Any:
        src = task.get("source") if isinstance(task.get("source"), dict) else {}
        return src.get("ref") or task.get("url")

    def probe(self, url: str) -> dict:
        meta = probe_metadata(url)
        return {
            "ok": meta.downloadable,
            "url": meta.url,
            "link_type": meta.link_type,
            "title": meta.title,
            "size_bytes": meta.size_bytes,
            "detail": meta.detail,
        }

    def download(self, source_ref: Any, tmp_path: str) -> dict:
        dest = Path(tmp_path).parent
        try:
            path = download_to_path(str(source_ref), dest)
            size = path.stat().st_size
            return {
                "ok": True,
                "provider_id": "http",
                "reason": "",
                "checksum": "",
                "size_bytes": size,
                "metadata": {"path": str(path)},
            }
        except Exception as e:
            return {
                "ok": False,
                "provider_id": "http",
                "reason": str(e),
                "checksum": "",
                "size_bytes": 0,
                "metadata": {"source_ref": source_ref},
            }

    def upload(self, local_path: str, destination_ref: Any) -> dict:
        return {
            "ok": False,
            "provider_id": "http",
            "reason": "legacy_worker_path",
            "checksum": "",
            "size_bytes": 0,
            "metadata": {"local_path": local_path, "destination_ref": destination_ref},
        }
