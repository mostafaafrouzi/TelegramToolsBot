"""Global network probe + shared ``queue/network.json`` snapshot."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_SNAPSHOT: dict[str, Any] = {
    "mode": "unknown",
    "reason": "",
    "updated_at": 0,
}


def probe_global_network() -> tuple[str, str]:
    """Return ``(mode, reason)`` — mode is ``normal`` or ``degraded``."""
    try:
        resp = requests.get("https://github.com", timeout=8)
        if resp.status_code < 500:
            return "normal", ""
        return "degraded", f"github_http_{resp.status_code}"
    except Exception as e:
        return "degraded", str(e)[:200]


def load_network_snapshot(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULT_SNAPSHOT, **data}
    except Exception:
        pass
    return dict(DEFAULT_SNAPSHOT)


def write_network_snapshot(path: Path, mode: str, reason: str = "") -> dict[str, Any]:
    data = {
        "mode": mode,
        "reason": reason,
        "updated_at": int(time.time()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def refresh_network_snapshot(path: Path) -> dict[str, Any]:
    mode, reason = probe_global_network()
    return write_network_snapshot(path, mode, reason)
