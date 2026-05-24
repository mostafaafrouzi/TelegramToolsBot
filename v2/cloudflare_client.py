"""Per-user Cloudflare API helpers (read-only by default)."""

from __future__ import annotations

import requests

CF_API = "https://api.cloudflare.com/client/v4"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.strip()}", "Content-Type": "application/json"}


def _get(token: str, path: str, *, params: dict | None = None) -> tuple[bool, dict | str]:
    tok = (token or "").strip()
    if not tok:
        return False, "missing_token"
    try:
        r = requests.get(f"{CF_API}{path}", headers=_headers(tok), params=params, timeout=20)
        data = r.json() if r.content else {}
        if r.ok and data.get("success"):
            return True, data
        errors = data.get("errors") or []
        detail = ", ".join(str(e.get("message") or e) for e in errors) or r.text or f"HTTP {r.status_code}"
        return False, detail[:900]
    except requests.RequestException as e:
        return False, str(e)[:900]


def verify_token(token: str) -> tuple[bool, str]:
    ok, data = _get(token, "/user/tokens/verify")
    if not ok:
        return False, str(data)
    result = data.get("result") if isinstance(data, dict) else {}
    return True, str(result.get("status") or "active")


def list_zones(token: str, *, limit: int = 20) -> tuple[bool, str]:
    ok, data = _get(token, "/zones", params={"per_page": min(max(limit, 1), 50)})
    if not ok:
        return False, str(data)
    zones = (data.get("result") or []) if isinstance(data, dict) else []
    if not zones:
        return True, "No zones found."
    lines = []
    for z in zones[:limit]:
        lines.append(f"{z.get('name')} — `{z.get('id')}` — {z.get('status') or '-'}")
    return True, "\n".join(lines)


def list_dns_records(token: str, zone_id: str, *, name: str = "", limit: int = 30) -> tuple[bool, str]:
    params = {"per_page": min(max(limit, 1), 100)}
    if name:
        params["name"] = name
    ok, data = _get(token, f"/zones/{zone_id}/dns_records", params=params)
    if not ok:
        return False, str(data)
    records = (data.get("result") or []) if isinstance(data, dict) else []
    if not records:
        return True, "No DNS records found."
    lines = []
    for r in records[:limit]:
        proxied = "proxied" if r.get("proxied") else "dns-only"
        lines.append(
            f"{r.get('type')} {r.get('name')} -> {r.get('content')} "
            f"TTL={r.get('ttl')} {proxied} id=`{r.get('id')}`"
        )
    return True, "\n".join(lines)
