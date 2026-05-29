"""In-memory fallback for Rubika send-confirm (when JSON/SQLite state is stale)."""

from __future__ import annotations

from typing import Optional

_pending_confirm: dict[int, dict] = {}


def set_pending_confirm(user_id: int, task: dict) -> None:
    _pending_confirm[int(user_id)] = dict(task)


def get_pending_confirm(user_id: int) -> Optional[dict]:
    return _pending_confirm.get(int(user_id))


def pop_pending_confirm(user_id: int) -> Optional[dict]:
    return _pending_confirm.pop(int(user_id), None)
