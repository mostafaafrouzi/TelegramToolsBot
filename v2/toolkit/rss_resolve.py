"""Resolve social URLs to RSS feed URLs where possible."""

from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

_YT_CHANNEL = re.compile(
    r"(?:youtube\.com/(?:channel/|c/)|youtu\.be/)([A-Za-z0-9_-]{10,})",
    re.I,
)
_YT_HANDLE = re.compile(r"youtube\.com/@([A-Za-z0-9_.-]+)", re.I)
_X_STATUS = re.compile(r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})(?:/|$)", re.I)


def _rsshub_base() -> str:
    return (os.getenv("RSSHUB_BASE_URL") or "https://rsshub.app").strip().rstrip("/")


def resolve_feed_url(url: str) -> tuple[str, str, str]:
    """
    Return (resolved_url, feed_kind, hint).

    feed_kind: rss | youtube | twitter | other
    hint: empty or user-facing note
    """
    raw = (url or "").strip()
    if not raw:
        return "", "other", "empty"
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    low = raw.lower()

    m = _YT_CHANNEL.search(low)
    if m:
        cid = m.group(1)
        if cid.startswith("UC") or len(cid) >= 20:
            rss = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            return rss, "youtube", ""

    m = _YT_HANDLE.search(low)
    if m:
        handle = m.group(1)
        return (
            raw,
            "youtube",
            f"برای @{handle} اگر فید کار نکرد، لینک کانال با channel/UC… را بفرست.",
        )

    if "youtube.com/playlist" in low:
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        plist = (qs.get("list") or [None])[0]
        if plist:
            rss = f"https://www.youtube.com/feeds/videos.xml?playlist_id={plist}"
            return rss, "youtube", ""

    m = _X_STATUS.search(low)
    if m:
        user = m.group(1)
        rss = f"{_rsshub_base()}/twitter/user/{user}"
        return rss, "twitter", ""

    return raw, "rss", ""
