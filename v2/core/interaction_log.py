"""Append-only conversation / routing log for support and installer export."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
INTERACTION_LOG_FILE = BASE_DIR / "queue" / "bot_interactions.jsonl"


def log_interaction(event: str, *, user_id: int | None = None, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "ts": int(time.time()),
        "event": event,
    }
    if user_id is not None:
        payload["user_id"] = user_id
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, str) and len(value) > 4000:
            value = value[:4000] + "…"
        payload[key] = value
    try:
        INTERACTION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INTERACTION_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
