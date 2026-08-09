"""Portfolio value snapshots — the data behind the P&L chart.

Written every 30s by a background task and immediately after each trade
(see `portfolio.execute_trade`, which records its snapshot inside the trade
transaction).
"""

from __future__ import annotations

import sqlite3

from .connection import DEFAULT_USER_ID, get_connection
from .util import new_id, utc_now_iso


def insert_snapshot(conn: sqlite3.Connection, user_id: str, total_value: float) -> None:
    """Insert a snapshot on an existing connection, without committing, so a
    caller can record it as part of a larger transaction."""
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (new_id(), user_id, float(total_value), utc_now_iso()),
    )


def record_snapshot(user_id: str, total_value: float) -> None:
    """Record a portfolio value snapshot in its own transaction."""
    conn = get_connection()
    try:
        insert_snapshot(conn, user_id, total_value)
        conn.commit()
    finally:
        conn.close()


def get_snapshots(user_id: str = DEFAULT_USER_ID, limit: int | None = None) -> list[dict]:
    """Snapshots in chronological order (oldest first). With `limit`, the most
    recent `limit` rows, still chronological."""
    conn = get_connection()
    try:
        if limit is None:
            rows = conn.execute(
                "SELECT total_value, recorded_at FROM portfolio_snapshots "
                "WHERE user_id = ? ORDER BY recorded_at, rowid",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT total_value, recorded_at FROM portfolio_snapshots "
                "WHERE user_id = ? ORDER BY recorded_at DESC, rowid DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()[::-1]
        return [{"total_value": r["total_value"], "recorded_at": r["recorded_at"]} for r in rows]
    finally:
        conn.close()
