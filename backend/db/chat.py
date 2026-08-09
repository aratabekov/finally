"""Chat message history for the LLM assistant.

`actions` holds whatever the assistant did in that turn (executed trades,
watchlist changes). It is stored as a JSON string and returned parsed.
"""

from __future__ import annotations

import json

from .connection import DEFAULT_USER_ID, get_connection
from .util import new_id, utc_now_iso


def add_chat_message(
    user_id: str,
    role: str,
    content: str,
    actions=None,
) -> str:
    """Append a message to the conversation log. Returns the new message id."""
    message_id = new_id()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_id,
                user_id,
                role,
                content,
                json.dumps(actions) if actions is not None else None,
                utc_now_iso(),
            ),
        )
        conn.commit()
        return message_id
    finally:
        conn.close()


def get_recent_chat(user_id: str = DEFAULT_USER_ID, limit: int = 20) -> list[dict]:
    """The most recent `limit` messages in chronological order (oldest first),
    ready to append to an LLM prompt."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "actions": json.loads(r["actions"]) if r["actions"] else None,
                "created_at": r["created_at"],
            }
            for r in rows[::-1]
        ]
    finally:
        conn.close()
