"""Track bot-sent message IDs so users can clear chat history with the bot."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

_DB = Path(__file__).resolve().parents[2] / "queue" / "bot_messages.sqlite3"


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_messages (
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            ts REAL NOT NULL,
            PRIMARY KEY (chat_id, message_id)
        )
        """
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_bot_messages_user ON bot_messages(user_id, ts)"
    )
    return c


def track_message(user_id: int, chat_id: int, message_id: int) -> None:
    try:
        conn = _conn()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO bot_messages(user_id, chat_id, message_id, ts) VALUES (?,?,?,?)",
                (int(user_id), int(chat_id), int(message_id), time.time()),
            )
            # Cap per user to keep DB small
            conn.execute(
                """
                DELETE FROM bot_messages WHERE chat_id=? AND message_id IN (
                  SELECT message_id FROM bot_messages WHERE chat_id=?
                  ORDER BY ts DESC LIMIT -1 OFFSET 500
                )
                """,
                (int(chat_id), int(chat_id)),
            )
        conn.close()
    except Exception:
        pass


def list_message_ids(user_id: int, chat_id: int, *, limit: int = 500) -> list[int]:
    try:
        conn = _conn()
        rows = conn.execute(
            "SELECT message_id FROM bot_messages WHERE user_id=? AND chat_id=? ORDER BY ts DESC LIMIT ?",
            (int(user_id), int(chat_id), int(limit)),
        ).fetchall()
        conn.close()
        return [int(r[0]) for r in rows]
    except Exception:
        return []


def clear_tracked(user_id: int, chat_id: int) -> None:
    try:
        conn = _conn()
        with conn:
            conn.execute(
                "DELETE FROM bot_messages WHERE user_id=? AND chat_id=?",
                (int(user_id), int(chat_id)),
            )
        conn.close()
    except Exception:
        pass


async def track_reply(message: Any, sent: Any) -> Any:
    """Helper: track a Message returned from reply_*."""
    try:
        uid = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id if message.chat else 0
        mid = getattr(sent, "id", None) or getattr(sent, "message_id", None)
        if uid and chat_id and mid:
            track_message(uid, chat_id, int(mid))
    except Exception:
        pass
    return sent
