"""Simple email validation + MX check."""

from __future__ import annotations

import re
import socket

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_email(addr: str) -> tuple[bool, str]:
    email = (addr or "").strip().lower()
    if not email:
        return False, "empty"
    if not _EMAIL_RE.match(email):
        return False, "invalid_format"
    domain = email.split("@", 1)[1]
    lines = [f"Email: {email}", "Format: ✅ valid"]
    try:
        mx = socket.getaddrinfo(domain, None)
        lines.append(f"Domain resolves: ✅ ({len(mx)} record(s))")
    except socket.gaierror:
        lines.append("Domain resolves: ❌ NXDOMAIN / no DNS")
    return True, "\n".join(lines)
