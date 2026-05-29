"""RDAP/WHOIS-style lookup with rich IP formatting."""

from __future__ import annotations

import ipaddress
import json
import urllib.parse
import urllib.request
from datetime import datetime


def _read_json(url: str, *, timeout: float = 12.0) -> tuple[bool, dict | str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "telegramtorubika-toolkit/1"})
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            return True, json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return False, str(e)[:500]


def _flag_cc(cc: str) -> str:
    cc = (cc or "").strip().upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return chr(0x1F1E6 + ord(cc[0]) - ord("A")) + chr(0x1F1E6 + ord(cc[1]) - ord("A"))


def _ip_lookup_rich(ip: str) -> tuple[bool, str]:
    ok, data = _read_json(
        f"http://ip-api.com/json/{urllib.parse.quote(ip)}?fields=status,message,country,countryCode,regionName,city,isp,org,as,asname,mobile,proxy,hosting,query,timezone",
    )
    if not ok:
        return False, str(data)
    if not isinstance(data, dict) or data.get("status") != "success":
        return False, str(data.get("message") or "lookup_failed")
    cc = data.get("countryCode") or ""
    flag = _flag_cc(cc)
    country = data.get("country") or "—"
    asn_raw = str(data.get("as") or "")
    asn = asn_raw.split()[0] if asn_raw else "—"
    asn_name = data.get("asname") or (asn_raw.split(" ", 1)[1] if " " in asn_raw else "—")
    now = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
    lines = [
        "Whois IP/Domain",
        "",
        f"🌍 IP: {data.get('query') or ip}",
        f"├ ISP: {data.get('isp') or '—'}",
        f"├ ASN: {asn} {asn_name}".strip(),
        f"├ Country: {flag} {country}, {cc}".strip(),
        f"├ Region: {data.get('regionName') or '—'}",
        f"├ City: {data.get('city') or '—'}",
        f"├ Host: {data.get('query') or ip}",
        f"├ Mobile: {'Yes' if data.get('mobile') else 'No'}",
        f"├ Proxy: {'Yes' if data.get('proxy') else 'No'}",
        f"├ Hosting: {'Yes' if data.get('hosting') else 'No'}",
        f"└ Local time: {now}",
    ]
    return True, "\n".join(lines)


def _domain_rdap(query: str) -> tuple[bool, str]:
    url = f"https://rdap.org/domain/{urllib.parse.quote(query)}"
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
        event_lines.append(f"  {action}: {date}")

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
            entities.append(f"  {handle} ({roles or '-'})")

    name = data.get("ldhName") or data.get("name") or query
    lines = [
        "Whois IP/Domain",
        "",
        f"🌐 Domain: {name}",
        f"├ Handle: {data.get('handle') or '—'}",
        f"└ Status: {', '.join(data.get('status') or []) or '—'}",
    ]
    if nameservers:
        lines.append(f"\nNameservers:\n" + "\n".join(f"  • {n}" for n in nameservers))
    if entities:
        lines.append("\nEntities:\n" + "\n".join(entities))
    if event_lines:
        lines.append("\nEvents:\n" + "\n".join(event_lines))
    return True, "\n".join(lines)


def rdap_lookup(query: str) -> tuple[bool, str]:
    q = (query or "").strip().strip(".")
    if not q:
        return False, "empty_query"

    try:
        ipaddress.ip_address(q)
        return _ip_lookup_rich(q)
    except ValueError:
        pass

    host = q.lower().removeprefix("http://").removeprefix("https://").split("/")[0]
    if host:
        try:
            ipaddress.ip_address(host)
            return _ip_lookup_rich(host)
        except ValueError:
            return _domain_rdap(host)
    return False, "invalid_query"
