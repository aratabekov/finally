"""Watchlist CRUD.

Removing a ticker the user holds does not touch the position — it stays priced
because `reads.load_active_tickers()` unions the watchlist with open positions.
"""

from __future__ import annotations

from .connection import DEFAULT_USER_ID, get_connection
from .util import new_id, normalize_ticker, utc_now_iso


def list_watchlist(user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Watchlist tickers in the order they were added."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (user_id,),
        ).fetchall()
        return [r["ticker"] for r in rows]
    finally:
        conn.close()


def add_watchlist(user_id: str, ticker: str) -> bool:
    """Add a ticker. Idempotent — returns True if it was newly added, False if
    it was already on the watchlist."""
    ticker = normalize_ticker(ticker)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, ticker) DO NOTHING",
            (new_id(), user_id, ticker, utc_now_iso()),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def remove_watchlist(user_id: str, ticker: str) -> bool:
    """Remove a ticker. Returns True if a row was actually removed."""
    ticker = normalize_ticker(ticker)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
