"""Build public Mini App URLs from ``MINIAPP_BASE_URL``."""

from __future__ import annotations


def miniapp_page_url(base_url: str, page: str = "index.html") -> str:
    """Return ``https://host/.../miniapp/<page>`` or empty if base unset."""
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return ""
    page = (page or "index.html").strip().lstrip("/")
    if page.startswith("miniapp/"):
        return f"{base}/{page}"
    return f"{base}/miniapp/{page}"
