"""Extra network toolkit helpers (HTTP, SSL, port, subnet, DNSBL)."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import time
from typing import Optional
from urllib.parse import urlparse

import requests

from v2.toolkit.dns_light import normalized_toolkit_host

_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; Tele2Rub-Toolkit/1.0; +https://github.com/telegramtorubika)"
)


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def http_headers_report(url: str, *, timeout: float = 15.0) -> tuple[bool, str]:
    target = _normalize_url(url)
    if not target:
        return False, "empty_url"
    try:
        t0 = time.time()
        resp = requests.get(
            target,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": _DEFAULT_UA},
            stream=True,
        )
        resp.close()
        elapsed = int((time.time() - t0) * 1000)
        host = urlparse(resp.url).hostname or urlparse(target).hostname or "?"
        ip = ""
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            ip = "—"
        lines = [
            f"URL: {resp.url}",
            f"IP: {ip}",
            f"Status: {resp.status_code} {resp.reason}",
            f"Time: {elapsed} ms",
            "",
        ]
        for k in ("Content-Type", "Server", "Date", "Connection"):
            if resp.headers.get(k):
                lines.append(f"{k}: {resp.headers.get(k)}")
        lines.append("")
        for k, v in resp.headers.items():
            lines.append(f"{k.lower()}: {v}")
        return True, "\n".join(lines)[:3900]
    except requests.RequestException as e:
        return False, str(e)[:500]


def website_status_report(url: str, *, timeout: float = 15.0) -> tuple[bool, str]:
    target = _normalize_url(url)
    if not target:
        return False, "empty_url"
    try:
        t0 = time.time()
        resp = requests.get(
            target,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": _DEFAULT_UA},
        )
        ms = int((time.time() - t0) * 1000)
        host = urlparse(resp.url).hostname or "?"
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            ip = "—"
        up = 200 <= resp.status_code < 400
        icon = "✅" if up else "❌"
        lines = [
            f"{icon} Website Status: {'UP' if up else 'DOWN'}",
            f"URL: {resp.url}",
            f"IP: {ip}",
            "",
            f"Status Code: {resp.status_code}",
            f"Response Time: {ms}ms",
            f"Server: {resp.headers.get('Server', '—')}",
            f"Content-Type: {resp.headers.get('Content-Type', '—')}",
        ]
        return True, "\n".join(lines)
    except requests.RequestException as e:
        return False, str(e)[:500]


def port_check_report(host: str, port: int, *, timeout: float = 5.0) -> tuple[bool, str]:
    h = normalized_toolkit_host(host)
    p = int(port)
    if not h:
        return False, "invalid_hostname"
    if not (1 <= p <= 65535):
        return False, "invalid_port"
    t0 = time.time()
    try:
        socket.create_connection((h, p), timeout=float(timeout))
        ms = int((time.time() - t0) * 1000)
        svc = {80: "HTTP", 443: "HTTPS", 22: "SSH", 21: "FTP"}.get(p, "")
        svc_txt = f" ({svc})" if svc else ""
        body = (
            f"✅ Port Open\n"
            f"Host: {h}\n"
            f"Port: {p}{svc_txt}\n"
            f"Latency: ~{ms} ms\n\n"
            "Server is accepting connections."
        )
        return True, body
    except OSError as e:
        return True, (
            f"❌ Port Closed\n"
            f"Host: {h}\n"
            f"Port: {p}\n\n"
            f"{e}"
        )


def subnet_calc_report(cidr: str) -> tuple[bool, str]:
    raw = (cidr or "").strip()
    if not raw:
        return False, "empty_cidr"
    try:
        net = ipaddress.ip_network(raw, strict=False)
    except ValueError as e:
        return False, str(e)
    hosts = list(net.hosts())
    first_host = str(hosts[0]) if hosts else "—"
    last_host = str(hosts[-1]) if hosts else "—"
    total = net.num_addresses
    usable = max(0, total - (2 if net.version == 4 and net.prefixlen < 31 else 0))
    private = net.is_private
    body = (
        f"📡 Network Calculator\n"
        f"Input: {net.with_prefixlen}\n\n"
        f"Network: {net.network_address}\n"
        f"Broadcast: {net.broadcast_address}\n"
        f"Netmask: {net.netmask}\n"
        f"Wildcard: {net.hostmask}\n"
        f"CIDR: /{net.prefixlen}\n"
        f"Total Addresses: {total}\n"
        f"Usable Hosts: {usable}\n"
        f"First Host: {first_host}\n"
        f"Last Host: {_host_safe(last_host)}\n"
        f"IP Version: IPv{net.version}\n"
        f"Private: {'Yes' if private else 'No'}"
    )
    return True, body


def _host_safe(s: str) -> str:
    return s


def blacklist_check_report(ip: str, *, timeout: float = 4.0) -> tuple[bool, str]:
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return False, "invalid_ip"
    if addr.version != 4:
        return False, "ipv4_only"
    rev = ".".join(reversed(str(addr).split(".")))
    lists = [
        ("Spamhaus ZEN", f"{rev}.zen.spamhaus.org"),
        ("SpamCop", f"{rev}.bl.spamcop.net"),
        ("Barracuda", f"{rev}.b.barracudacentral.org"),
        ("SORBS", f"{rev}.dnsbl.sorbs.net"),
        ("UCEPROTECT L1", f"{rev}.dnsbl-1.uceprotect.net"),
        ("PSBL", f"{rev}.psbl.surriel.com"),
    ]
    lines = [f"🛡 IP Blacklist Check {addr}"]
    clean = 0
    for name, qname in lists:
        listed = False
        try:
            socket.gethostbyname(qname)
            listed = True
        except socket.gaierror:
            listed = False
        except OSError:
            listed = False
        if listed:
            lines.append(f"  ❌ Listed — {name}")
        else:
            lines.append(f"  ✅ Clean — {name}")
            clean += 1
    total = len(lists)
    if clean == total:
        lines.append(f"\n🟢 Reputation: Clean ({clean}/{total} lists clear)")
        lines.append("This IP has no blacklist entries.")
    else:
        lines.append(f"\n🟡 Reputation: {clean}/{total} lists clear")
    return True, "\n".join(lines)


def ssl_cert_report(domain: str, *, timeout: float = 8.0) -> tuple[bool, str]:
    host = normalized_toolkit_host(domain)
    if not host:
        return False, "invalid_hostname"
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        if not cert:
            return False, "no_cert"
        subj = dict(x[0] for x in cert.get("subject", ()))
        issuer = dict(x[0] for x in cert.get("issuer", ()))
        cn = subj.get("commonName", host)
        org = issuer.get("organizationName", issuer.get("commonName", "—"))
        not_before = cert.get("notBefore", "—")
        not_after = cert.get("notAfter", "—")
        sans = [v for (kind, v) in cert.get("subjectAltName", ()) if kind == "DNS"][:12]
        alt = ", ".join(sans[:8]) if sans else "—"
        more = f"\n  ... and {len(sans) - 8} more" if len(sans) > 8 else ""
        body = (
            f"🔒 SSL/TLS Certificate\n"
            f"Domain: {host}\n\n"
            f"Status: ✅ Valid (see dates)\n"
            f"Issued To: {cn}\n"
            f"Issued By: {org}\n"
            f"Valid From: {not_before}\n"
            f"Expires: {not_after}\n"
            f"Alt Names: {alt}{more}"
        )
        return True, body
    except Exception as e:
        return False, str(e)[:500]
