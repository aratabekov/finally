"""Auto-execution of the actions the assistant returned.

Trades go through exactly the same `db.portfolio.execute_trade` validation as a
manual trade. A rejected trade is reported, not raised: the error string is
attached to the action and echoed back in the chat response so the user (and the
assistant, on the next turn) sees why it failed.
"""

from __future__ import annotations

from db.portfolio import execute_trade
from db.watchlist import add_watchlist, remove_watchlist

from .schema import AssistantReply, TradeInstruction, WatchlistChange


def _run_trade(instruction: TradeInstruction, prices: dict, user_id: str) -> dict:
    result = execute_trade(
        user_id, instruction.ticker, instruction.side, instruction.quantity, prices
    )
    action = result.as_dict()
    if not result.success:
        # A validation failure carries only the error; restate what was attempted.
        action.update(
            ticker=instruction.ticker,
            side=instruction.side,
            quantity=instruction.quantity,
        )
    return action


def _run_watchlist_change(change: WatchlistChange, user_id: str) -> dict:
    if change.action == "add":
        changed = add_watchlist(user_id, change.ticker)
    else:
        changed = remove_watchlist(user_id, change.ticker)
    return {
        "ticker": change.ticker,
        "action": change.action,
        "success": True,
        "changed": changed,   # False when it was already in that state
        "error": None,
    }


def apply_actions(reply: AssistantReply, prices: dict, user_id: str) -> dict:
    """Execute the reply's trades and watchlist changes, in that order."""
    trades = [_run_trade(t, prices, user_id) for t in reply.trades]
    changes = [
        _run_watchlist_change(c, user_id) for c in reply.watchlist_changes if c.ticker
    ]
    errors = [t["error"] for t in trades if not t["success"]]
    return {"trades": trades, "watchlist_changes": changes, "errors": errors}


def compose_message(message: str, errors: list[str]) -> str:
    """Append failed actions to the reply so the user always sees them."""
    if not errors:
        return message
    return "\n\n".join([message] + [f"Could not complete: {e}" for e in errors])
