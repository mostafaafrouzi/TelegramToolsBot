"""RDAP/WHOIS-style lookup helpers without external binaries."""

from __future__ import annotations

import ipaddress
import json
import urllib.parse
import urllib.request


def _read_json(url: str, *, timeout: float = 12.0) -> tuple[bool, dict | str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "telegramtorubika-toolkit/1"})
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            return True, json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return False, str(e)[:500]


def rdap_lookup(query: str) -> tuple[bool, str]:
    q = (query or "").strip().strip(".")
    if not q:
        return False, "empty_query"

    try:
        ipaddress.ip_address(q)
        url = f"https://rdap.org/ip/{urllib.parse.quote(q)}"
    except ValueError:
        url = f"https://rdap.org/domain/{urllib.parse.quote(q)}"

    ok, data = _read_json(url)
    if not ok:
        return False, str(data)
    if not isinstance(data, dict):
        return False, "bad_response"

    events = data.get("events") or []
    event_lines = []
    for item in events[:5]:
        action = item.get("eventAction") or "event"
        date = item.get("eventDate") or "-"
        event_lines.append(f"{action}: {date}")

    nameservers = []
    for ns in (data.get("nameservers") or [])[:8]:
        name = ns.get("ldhName") or ns.get("unicodeName")
        if name:
            nameservers.append(str(name))

    entities = []
    for ent in (data.get("entities") or [])[:5]:
        roles = ",".join(ent.get("roles") or [])
        handle = ent.get("handle") or "-"
        if roles or handle != "-":
            entities.append(f"{handle} ({roles or '-'})")

    lines = [
        f"Object: {data.get('ldhName') or data.get('name') or data.get('handle') or q}",
        f"Handle: {data.get('handle') or '-'}",
        f"Status: {', '.join(data.get('status') or []) or '-'}",
    ]
    if nameservers:
        lines.append("Nameservers: " + ", ".join(nameservers))
    if entities:
        lines.append("Entities: " + "; ".join(entities))
    if event_lines:
        lines.append("Events:\n" + "\n".join(event_lines))
    return True, "\n".join(lines)
