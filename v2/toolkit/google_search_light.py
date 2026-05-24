"""Google Custom Search helper (EazyGoogle-style lightweight integration)."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _api_keys() -> list[str]:
    raw = (os.getenv("GOOGLE_CSE_API_KEYS") or os.getenv("GOOGLE_API_KEYS") or "").strip()
    if not raw:
        raw = (os.getenv("GOOGLE_CSE_API_KEY") or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            return [str(x).strip() for x in data if str(x).strip()]
        except Exception:
            pass
    return [x.strip() for x in raw.split(",") if x.strip()]


def _cx() -> str:
    return (os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_CX") or "").strip()


def google_search(query: str, *, image: bool = False, limit: int = 5, timeout: float = 12.0) -> tuple[bool, str]:
    q = (query or "").strip()
    keys = _api_keys()
    cx = _cx()
    if not q:
        return False, "empty_query"
    if not keys or not cx:
        return False, "missing_google_cse_config"
    num = max(1, min(int(limit), 10))
    last_error = ""
    for key in keys:
        params = {
            "key": key,
            "cx": cx,
            "q": q,
            "num": str(num),
        }
        if image:
            params["searchType"] = "image"
        url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "telegramtorubika-toolkit/1"})
            with urllib.request.urlopen(req, timeout=float(timeout)) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            items = data.get("items") or []
            if not items:
                return True, "No results."
            lines = []
            for idx, item in enumerate(items[:num], start=1):
                title = (item.get("title") or "-").strip()
                link = (item.get("link") or "-").strip()
                snippet = (item.get("snippet") or "").replace("\n", " ").strip()
                if image:
                    ctx = ((item.get("image") or {}).get("contextLink") or "").strip()
                    lines.append(f"{idx}. {title}\n{link}\n{ctx}".strip())
                else:
                    lines.append(f"{idx}. {title}\n{link}\n{snippet}".strip())
            return True, "\n\n".join(lines)
        except Exception as e:
            last_error = str(e)[:500]
            continue
    return False, last_error or "search_failed"
