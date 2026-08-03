"""Per-user Cloudflare API helpers (read + optional DNS write)."""

from __future__ import annotations

from typing import Any, Optional

import requests

CF_API = "https://api.cloudflare.com/client/v4"


def _normalize_token(token: str) -> str:
    """Cloudflare API tokens are ASCII; strip whitespace and non-ASCII paste noise."""
    raw = (token or "").strip()
    if not raw:
        return ""
    return "".join(ch for ch in raw if ord(ch) < 128).strip()


def _headers(token: str) -> dict[str, str]:
    tok = _normalize_token(token)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _request(
    token: str,
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> tuple[bool, dict | str]:
    tok = _normalize_token(token)
    if not tok:
        return False, "missing_token"
    try:
        r = requests.request(
            method.upper(),
            f"{CF_API}{path}",
            headers=_headers(tok),
            params=params,
            json=json_body,
            timeout=25,
        )
        data = r.json() if r.content else {}
        if r.ok and data.get("success"):
            return True, data
        errors = data.get("errors") or []
        detail = ", ".join(str(e.get("message") or e) for e in errors) or r.text or f"HTTP {r.status_code}"
        return False, detail[:900]
    except requests.RequestException as e:
        return False, str(e)[:900]


def _get(token: str, path: str, *, params: dict | None = None) -> tuple[bool, dict | str]:
    return _request(token, "GET", path, params=params)


def verify_token(token: str) -> tuple[bool, str]:
    ok, data = _get(token, "/user/tokens/verify")
    if not ok:
        return False, str(data)
    result = data.get("result") if isinstance(data, dict) else {}
    return True, str(result.get("status") or "active")


def list_zones_rows(token: str, *, limit: int = 20) -> tuple[bool, list[dict] | str]:
    ok, data = _get(token, "/zones", params={"per_page": min(max(limit, 1), 50)})
    if not ok:
        return False, str(data)
    zones = (data.get("result") or []) if isinstance(data, dict) else []
    rows: list[dict] = []
    for z in zones[:limit]:
        rows.append(
            {
                "id": str(z.get("id") or ""),
                "name": str(z.get("name") or ""),
                "status": str(z.get("status") or "-"),
            }
        )
    return True, rows


def list_zones(token: str, *, limit: int = 20) -> tuple[bool, str]:
    ok, rows = list_zones_rows(token, limit=limit)
    if not ok:
        return False, str(rows)
    if not rows:
        return True, "No zones found."
    lines = [f"{z.get('name')} — `{z.get('id')}` — {z.get('status') or '-'}" for z in rows]
    return True, "\n".join(lines)


def list_dns_records_rows(
    token: str, zone_id: str, *, name: str = "", limit: int = 30
) -> tuple[bool, list[dict] | str]:
    params: dict[str, Any] = {"per_page": min(max(limit, 1), 100)}
    if name:
        params["name"] = name
    ok, data = _get(token, f"/zones/{zone_id}/dns_records", params=params)
    if not ok:
        return False, str(data)
    records = (data.get("result") or []) if isinstance(data, dict) else []
    rows: list[dict] = []
    for r in records[:limit]:
        rows.append(
            {
                "id": str(r.get("id") or ""),
                "type": str(r.get("type") or ""),
                "name": str(r.get("name") or ""),
                "content": str(r.get("content") or ""),
                "ttl": r.get("ttl"),
                "proxied": bool(r.get("proxied")),
            }
        )
    return True, rows


def list_dns_records(token: str, zone_id: str, *, name: str = "", limit: int = 30) -> tuple[bool, str]:
    ok, rows = list_dns_records_rows(token, zone_id, name=name, limit=limit)
    if not ok:
        return False, str(rows)
    if not rows:
        return True, "No DNS records found."
    lines = []
    for r in rows:
        proxied = "proxied" if r.get("proxied") else "dns-only"
        lines.append(
            f"{r.get('type')} {r.get('name')} -> {r.get('content')} "
            f"TTL={r.get('ttl')} {proxied} id=`{r.get('id')}`"
        )
    return True, "\n".join(lines)


def create_dns_record(
    token: str,
    zone_id: str,
    *,
    type_: str,
    name: str,
    content: str,
    ttl: int = 1,
    proxied: Optional[bool] = None,
) -> tuple[bool, str]:
    body: dict[str, Any] = {
        "type": (type_ or "").strip().upper(),
        "name": (name or "").strip(),
        "content": (content or "").strip(),
        "ttl": int(ttl) if ttl else 1,
    }
    if proxied is not None and body["type"] in ("A", "AAAA", "CNAME"):
        body["proxied"] = bool(proxied)
    ok, data = _request(token, "POST", f"/zones/{zone_id}/dns_records", json_body=body)
    if not ok:
        return False, str(data)
    result = data.get("result") if isinstance(data, dict) else {}
    rid = (result or {}).get("id") if isinstance(result, dict) else ""
    return True, f"created id=`{rid}` {body['type']} {body['name']} -> {body['content']}"


def delete_dns_record(token: str, zone_id: str, record_id: str) -> tuple[bool, str]:
    rid = (record_id or "").strip()
    if not rid:
        return False, "missing_record_id"
    ok, data = _request(token, "DELETE", f"/zones/{zone_id}/dns_records/{rid}")
    if not ok:
        return False, str(data)
    return True, f"deleted id=`{rid}`"
