"""Navigation helpers (e.g. leave direct-send mode when user changes context)."""

from __future__ import annotations

from typing import Callable, Optional


def maybe_disable_direct_mode(
    user_id: int,
    get_direct_mode_target: Callable[[int], Optional[str]],
    set_direct_mode_target: Callable[[int, Optional[str]], None],
) -> bool:
    """Turn off direct-send if active. Returns True if it was disabled."""
    current = get_direct_mode_target(user_id)
    if current:
        set_direct_mode_target(user_id, None)
        return True
    return False
