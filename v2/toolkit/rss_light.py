"""RSS/Atom feed fetch with structured items (stdlib XML when feedparser missing)."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen


def _fetch_url(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": "TelegramToolsBot/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _item_id(item: dict) -> str:
    for key in ("id", "link", "title"):
        v = (item.get(key) or "").strip()
        if v:
            return v
    return ""


def _parse_items_xml(xml_text: str, limit: int = 8) -> list[dict]:
    root = ET.fromstring(xml_text)
    tag = _strip_ns(root.tag).lower()
    items: list[dict] = []

    if tag == "rss" or root.find("channel") is not None:
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            desc = re.sub(r"<[^>]+>", "", (item.findtext("description") or ""))[:200]
            pub = (item.findtext("pubDate") or "").strip()
            items.append(
                {
                    "id": guid or link or title,
                    "title": title,
                    "link": link,
                    "description": desc,
                    "published": pub,
                }
            )
        return items

    # Atom
    entries = [el for el in root.iter() if _strip_ns(el.tag).lower() == "entry"]
    for entry in entries[:limit]:
        title = ""
        link = ""
        eid = ""
        published = ""
        summary = ""
        for child in list(entry):
            ct = _strip_ns(child.tag).lower()
            if ct == "title":
                title = (child.text or "").strip()
            elif ct == "id":
                eid = (child.text or "").strip()
            elif ct == "published" or ct == "updated":
                if not published:
                    published = (child.text or "").strip()
            elif ct == "summary" or ct == "content":
                summary = re.sub(r"<[^>]+>", "", (child.text or ""))[:200]
            elif ct == "link":
                href = child.attrib.get("href") or (child.text or "")
                rel = child.attrib.get("rel", "alternate")
                if href and (rel == "alternate" or not link):
                    link = href.strip()
        items.append(
            {
                "id": eid or link or title,
                "title": title,
                "link": link,
                "description": summary,
                "published": published,
            }
        )
    return items


def _items_from_feedparser(url: str, limit: int) -> list[dict]:
    import feedparser

    parsed = feedparser.parse(url)
    items: list[dict] = []
    for e in parsed.entries[:limit]:
        title = getattr(e, "title", "") or ""
        link = getattr(e, "link", "") or ""
        eid = getattr(e, "id", None) or getattr(e, "guid", None) or link or title
        published = getattr(e, "published", "") or getattr(e, "updated", "") or ""
        summary = re.sub(r"<[^>]+>", "", getattr(e, "summary", "") or "")[:200]
        items.append(
            {
                "id": str(eid),
                "title": title,
                "link": link,
                "description": summary,
                "published": str(published),
            }
        )
    return items


def encode_seen_ids(items: list[dict], *, n: int = 12) -> str:
    ids = [_item_id(i) for i in items[:n] if _item_id(i)]
    return json.dumps(ids, ensure_ascii=False)


def decode_seen_ids(raw: str) -> list[str]:
    s = (raw or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [str(x) for x in data]
        except json.JSONDecodeError:
            return []
    # Legacy sha fingerprint — unknown id set
    return []


def items_fingerprint(items: list[dict], *, n: int = 8) -> str:
    """Legacy-compatible short hash (also used when JSON too long)."""
    ids = [_item_id(i) for i in items[:n] if _item_id(i)]
    raw = "\n".join(ids)
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def format_items_body(items: list[dict]) -> str:
    lines = []
    for i in items:
        title = (i.get("title") or "").strip()
        link = (i.get("link") or "").strip()
        if not title:
            continue
        lines.append(f"• {title}\n  {link}" if link else f"• {title}")
    return "\n\n".join(lines)


def fetch_feed_items(url: str, limit: int = 8) -> tuple[bool, list[dict], str]:
    """Return (ok, items, seen_ids_json)."""
    try:
        items: list[dict] = []
        try:
            items = _items_from_feedparser(url, limit)
        except ImportError:
            raw = _fetch_url(url)
            items = _parse_items_xml(raw, limit=limit)
        if not items:
            return False, [], ""
        return True, items, encode_seen_ids(items)
    except Exception:
        return False, [], ""


def fetch_feed(url: str, limit: int = 8) -> tuple[bool, str, str]:
    """Return (ok, body_text, seen_ids_json)."""
    ok, items, seen = fetch_feed_items(url, limit=limit)
    if not ok:
        return False, "no_entries" if not items else "parse_failed", ""
    body = format_items_body(items)
    if not body:
        return False, "no_entries", ""
    return True, body, seen


def new_items_since(prev_seen: str, items: list[dict], *, limit: int = 5) -> list[dict]:
    """Return items whose ids were not in the previous seen set."""
    prev_ids = set(decode_seen_ids(prev_seen))
    if not prev_seen:
        return []
    if not prev_ids:
        # Legacy hash: if fingerprint differs, announce top items once.
        if items_fingerprint(items) == prev_seen:
            return []
        return [i for i in items[:limit] if _item_id(i)]
    out = []
    for i in items:
        iid = _item_id(i)
        if iid and iid not in prev_ids:
            out.append(i)
        if len(out) >= limit:
            break
    return out
