"""Portfolio reads, valuation, and trade execution.

Market orders only: instant fill at the price the caller passes in, no fees,
no partial fills. The `prices` argument is a live price map — either
`{ticker: float}` or `{ticker: PriceTick}` as returned by
`await cache.snapshot()`. This module never imports the market cache itself.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass

from .connection import DEFAULT_USER_ID, get_connection
from .snapshots import insert_snapshot
from .util import new_id, normalize_ticker, utc_now_iso

# Quantities are floats, so "zero shares left" needs a tolerance.
ZERO = 1e-9


@dataclass(frozen=True)
class TradeResult:
    """Outcome of an `execute_trade` call. Validation failures come back as
    `success=False` with a user-facing `error` rather than an exception."""

    success: bool
    error: str | None = None
    ticker: str | None = None
    side: str | None = None
    quantity: float | None = None
    price: float | None = None
    executed_at: str | None = None
    cash_balance: float | None = None
    total_value: float | None = None
    trade_id: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _price_of(value) -> float:
    """Accept a raw float or a PriceTick-like object with a `.price`."""
    return float(getattr(value, "price", value))


def _lookup_price(prices: dict, ticker: str) -> float | None:
    if ticker not in prices:
        return None
    return _price_of(prices[ticker])


def _fail(error: str) -> TradeResult:
    return TradeResult(success=False, error=error)


def _read_profile(conn: sqlite3.Connection, user_id: str) -> dict:
    row = conn.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row)


def _read_positions(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
        "WHERE user_id = ? AND quantity > 0 ORDER BY ticker",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_profile(user_id: str = DEFAULT_USER_ID) -> dict:
    """The user's profile row: id, cash_balance, created_at."""
    conn = get_connection()
    try:
        return _read_profile(conn, user_id)
    finally:
        conn.close()


def get_positions(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Open positions (quantity > 0), ordered by ticker."""
    conn = get_connection()
    try:
        return _read_positions(conn, user_id)
    finally:
        conn.close()


def compute_valuation(positions: list[dict], prices: dict, cash: float) -> dict:
    """Value a set of positions against a live price map. Pure — no DB, no I/O.

    A position whose ticker is missing from `prices` is valued at its average
    cost, so it reads flat instead of dropping to zero.
    """
    valued = []
    positions_value = 0.0
    cost_basis = 0.0

    for position in positions:
        quantity = float(position["quantity"])
        avg_cost = float(position["avg_cost"])
        price = _lookup_price(prices, position["ticker"])
        if price is None:
            price = avg_cost

        market_value = quantity * price
        position_cost = quantity * avg_cost
        unrealized_pl = market_value - position_cost

        positions_value += market_value
        cost_basis += position_cost

        valued.append(
            {
                "ticker": position["ticker"],
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": price,
                "market_value": market_value,
                "cost_basis": position_cost,
                "unrealized_pl": unrealized_pl,
                "pct_change": (price / avg_cost - 1.0) * 100.0 if avg_cost else 0.0,
            }
        )

    return {
        "cash": float(cash),
        "positions_value": positions_value,
        "total_value": float(cash) + positions_value,
        "cost_basis": cost_basis,
        "unrealized_pl": positions_value - cost_basis,
        "positions": valued,
    }


def get_portfolio(prices: dict, user_id: str = DEFAULT_USER_ID) -> dict:
    """Full portfolio valuation — what `GET /api/portfolio` returns."""
    conn = get_connection()
    try:
        profile = _read_profile(conn, user_id)
        positions = _read_positions(conn, user_id)
    finally:
        conn.close()
    return compute_valuation(positions, prices, profile["cash_balance"])


def execute_trade(
    user_id: str,
    ticker: str,
    side: str,
    quantity: float,
    prices: dict,
) -> TradeResult:
    """Execute a market order in one atomic transaction.

    Validates cash on a buy and held shares on a sell, updates the position
    (weighted average cost on buys, average cost untouched on sells; a full
    sell deletes the row), logs the trade, adjusts cash, and records a
    post-trade portfolio snapshot — all committed together.
    """
    ticker = normalize_ticker(ticker)
    side = side.strip().lower()
    if side not in ("buy", "sell"):
        return _fail("Side must be 'buy' or 'sell'")

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return _fail("Quantity must be greater than zero")
    if not quantity > ZERO:
        return _fail("Quantity must be greater than zero")

    price = _lookup_price(prices, ticker)
    if price is None:
        return _fail(f"No price available for {ticker}")

    # BEGIN IMMEDIATE so the read of cash/shares and the writes that depend on
    # it are one unit. Any early return closes the connection without a commit,
    # which rolls the transaction back.
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cash = _read_profile(conn, user_id)["cash_balance"]
        row = conn.execute(
            "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()
        held = row["quantity"] if row else 0.0
        avg_cost = row["avg_cost"] if row else 0.0

        notional = quantity * price
        if side == "buy":
            if notional > cash + ZERO:
                return _fail(
                    f"Insufficient cash: need ${notional:,.2f}, have ${cash:,.2f}"
                )
            new_cash = cash - notional
            new_quantity = held + quantity
            new_avg_cost = (held * avg_cost + notional) / new_quantity
        else:
            if quantity > held + ZERO:
                return _fail(
                    f"Insufficient shares: tried to sell {quantity:g} {ticker}, "
                    f"hold {held:g}"
                )
            new_cash = cash + notional
            new_quantity = held - quantity
            new_avg_cost = avg_cost

        now = utc_now_iso()
        if new_quantity <= ZERO:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
        else:
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (user_id, ticker) DO UPDATE SET "
                "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
                "updated_at = excluded.updated_at",
                (new_id(), user_id, ticker, new_quantity, new_avg_cost, now),
            )

        trade_id = new_id()
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, user_id, ticker, side, quantity, price, now),
        )
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_cash, user_id),
        )

        valuation = compute_valuation(_read_positions(conn, user_id), prices, new_cash)
        insert_snapshot(conn, user_id, valuation["total_value"])
        conn.commit()
    finally:
        conn.close()

    return TradeResult(
        success=True,
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=price,
        executed_at=now,
        cash_balance=new_cash,
        total_value=valuation["total_value"],
        trade_id=trade_id,
    )


def get_trades(user_id: str = DEFAULT_USER_ID, limit: int = 50) -> list[dict]:
    """Most recent trades, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, ticker, side, quantity, price, executed_at FROM trades "
            "WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
