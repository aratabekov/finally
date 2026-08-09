"""Deterministic stand-in for the LLM, used when LLM_MOCK=true.

No network, no API key, no randomness — the same message and the same portfolio
state always produce the same reply. E2E tests assert against these strings.
"""

from __future__ import annotations

import re

from .schema import AssistantReply, TradeInstruction, WatchlistChange

# "buy 5 AAPL", "sell 2.5 shares of TSLA"
TRADE_RE = re.compile(
    r"\b(buy|sell)\s+(\d+(?:\.\d+)?)\s+(?:shares\s+(?:of\s+)?)?([a-z]{1,5})\b",
    re.IGNORECASE,
)
# "add PYPL to the watchlist", "remove AAPL from my watchlist"
WATCHLIST_RE = re.compile(r"\b(add|remove)\s+([a-z]{1,5})\b", re.IGNORECASE)


def _analysis(context: dict) -> str:
    return (
        f"Mock analysis: total value ${context['total_value']:,.2f}, "
        f"cash ${context['cash']:,.2f}, {len(context['positions'])} open positions, "
        f"unrealized P&L ${context['unrealized_pl']:,.2f}."
    )


def mock_reply(user_message: str, context: dict) -> AssistantReply:
    """Parse simple buy/sell and watchlist intents; otherwise canned analysis."""
    trades = [
        TradeInstruction(ticker=ticker, side=side.lower(), quantity=float(quantity))
        for side, quantity, ticker in TRADE_RE.findall(user_message)
    ]
    changes = (
        [
            WatchlistChange(ticker=ticker, action=action.lower())
            for action, ticker in WATCHLIST_RE.findall(user_message)
        ]
        if "watchlist" in user_message.lower()
        else []
    )

    parts = [
        f"Executing {t.side} {t.quantity:g} {t.ticker} at the current market price."
        for t in trades
    ]
    parts += [
        f"Adding {c.ticker} to the watchlist."
        if c.action == "add"
        else f"Removing {c.ticker} from the watchlist."
        for c in changes
    ]
    if not parts:
        parts.append(_analysis(context))

    return AssistantReply(
        message=" ".join(parts), trades=trades, watchlist_changes=changes
    )
