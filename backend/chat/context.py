"""Portfolio context handed to the LLM on every turn.

Live prices come from the caller (`await app.state.price_cache.snapshot()`) so
this module stays free of any market-cache import, exactly like the DB layer.
"""

from __future__ import annotations

from db.connection import DEFAULT_USER_ID
from db.portfolio import get_portfolio
from db.watchlist import list_watchlist


def _price_value(value) -> float:
    """Accept a raw float or a PriceTick-like object with a `.price`."""
    return float(getattr(value, "price", value))


def build_context(prices: dict, user_id: str = DEFAULT_USER_ID) -> dict:
    """Cash, positions with P&L, total value, and the watchlist with live prices."""
    portfolio = get_portfolio(prices, user_id)
    watchlist = [
        {
            "ticker": ticker,
            "price": _price_value(prices[ticker]) if ticker in prices else None,
        }
        for ticker in list_watchlist(user_id)
    ]
    return {**portfolio, "watchlist": watchlist}


def format_context(context: dict) -> str:
    """Render the context as a compact text block for the prompt."""
    lines = [
        "PORTFOLIO",
        f"cash: ${context['cash']:,.2f}",
        f"positions value: ${context['positions_value']:,.2f}",
        f"total value: ${context['total_value']:,.2f}",
        f"unrealized P&L: ${context['unrealized_pl']:,.2f}",
    ]

    positions = context["positions"]
    if positions:
        lines.append("POSITIONS (ticker, qty, avg cost, price, unrealized P&L, pct)")
        lines += [
            f"{p['ticker']} {p['quantity']:g} ${p['avg_cost']:,.2f} "
            f"${p['current_price']:,.2f} ${p['unrealized_pl']:,.2f} "
            f"{p['pct_change']:+.2f}%"
            for p in positions
        ]
    else:
        lines.append("POSITIONS: none — the portfolio is all cash")

    lines.append("WATCHLIST (ticker, price)")
    lines += [
        f"{w['ticker']} " + (f"${w['price']:,.2f}" if w["price"] is not None else "n/a")
        for w in context["watchlist"]
    ]
    return "\n".join(lines)
