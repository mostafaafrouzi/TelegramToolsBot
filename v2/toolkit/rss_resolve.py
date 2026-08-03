"""Resolve social URLs to RSS feed URLs where possible."""

from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

_YT_CHANNEL = re.compile(
    r"youtube\.com/channel/(UC[A-Za-z0-9_-]{20,})",
    re.I,
)
_YT_HANDLE = re.compile(r"youtube\.com/@([A-Za-z0-9_.-]+)", re.I)
_X_STATUS = re.compile(r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})(?:/|$)", re.I)
_CHANNEL_ID_IN_HTML = re.compile(
    r'"channelId":"(UC[A-Za-z0-9_-]{20,})"|'
    r'<meta\s+itemprop="channelId"\s+content="(UC[A-Za-z0-9_-]{20,})"',
    re.I,
)


def _rsshub_base() -> str:
    return (os.getenv("RSSHUB_BASE_URL") or "https://rsshub.app").strip().rstrip("/")


def _resolve_youtube_handle(handle: str) -> Optional[str]:
    url = f"https://www.youtube.com/@{handle}"
    try:
        req = Request(url, headers={"User-Agent": "TelegramToolsBot/1.0"})
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        m = _CHANNEL_ID_IN_HTML.search(html)
        if not m:
            return None
        return m.group(1) or m.group(2)
    except Exception:
        return None


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

    m = _YT_CHANNEL.search(raw)
    if m:
        cid = m.group(1)
        rss = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        return rss, "youtube", ""

    m = _YT_HANDLE.search(raw)
    if m:
        handle = m.group(1)
        cid = _resolve_youtube_handle(handle)
        if cid:
            rss = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            return rss, "youtube", ""
        return (
            raw,
            "youtube",
            f"Could not resolve @{handle} to channel id; send a channel/UC… link.",
        )

    if "youtube.com/playlist" in low:
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        plist = (qs.get("list") or [None])[0]
        if plist:
            rss = f"https://www.youtube.com/feeds/videos.xml?playlist_id={plist}"
            return rss, "youtube", ""

    m = _X_STATUS.search(raw)
    if m:
        user = m.group(1)
        if user.lower() in ("home", "explore", "i", "intent", "share"):
            return raw, "rss", ""
        rss = f"{_rsshub_base()}/twitter/user/{user}"
        return rss, "twitter", ""

    return raw, "rss", ""
