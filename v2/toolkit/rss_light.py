"""RSS/Atom feed fetch (stdlib XML when feedparser missing)."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.request import Request, urlopen


def _fetch_url(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": "TelegramToolsBot/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_items_rss(xml_text: str, limit: int = 8) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = re.sub(r"<[^>]+>", "", (item.findtext("description") or ""))[:200]
        items.append({"title": title, "link": link, "description": desc})
    return items


def fetch_feed(url: str, limit: int = 8) -> tuple[bool, str, str]:
    """Return (ok, body_text, content_hash)."""
    try:
        try:
            import feedparser

            parsed = feedparser.parse(url)
            entries = parsed.entries[:limit]
            if not entries:
                return False, "no_entries", ""
            lines = []
            for e in entries:
                title = getattr(e, "title", "") or ""
                link = getattr(e, "link", "") or ""
                lines.append(f"• {title}\n  {link}")
            body = "\n\n".join(lines)
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
            return True, body, h
        except ImportError:
            raw = _fetch_url(url)
            items = _parse_items_rss(raw, limit=limit)
            if not items:
                return False, "parse_failed", ""
            lines = [f"• {i['title']}\n  {i['link']}" for i in items if i.get("title")]
            body = "\n\n".join(lines)
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
            return True, body, h
    except Exception as e:
        return False, str(e)[:400], ""
