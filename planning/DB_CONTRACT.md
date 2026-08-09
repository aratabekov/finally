# DB Contract — `backend/db/`

The database layer for FinAlly. Owned by the Database Engineer; consumed by the
Backend API Engineer and the LLM Engineer.

**Rules of engagement**

- Everything here is **synchronous** `sqlite3`. No async, no `await`.
- The DB layer never imports the market cache. Callers that need live prices read
  `app.state.price_cache` themselves and pass the price map in.
- Every function opens and closes its own connection. Nothing is shared or
  long-lived, so calls are safe from FastAPI threadpool endpoints (`def`) and
  from `async def` endpoints alike.
- Schema init + seeding stays lazy: the first `get_connection()` for a given
  `DB_PATH` creates all tables and seeds the default profile + watchlist.
- All functions take `user_id` (default `"default"`).

## The price map

`compute_valuation`, `get_portfolio`, and `execute_trade` take a `prices`
argument. Pass either:

- `dict[str, float]` — plain ticker -> price, or
- `dict[str, PriceTick]` — exactly what `await cache.snapshot()` returns.

Both are accepted; the layer reads `.price` off the value when present. So this
is the normal call from a route:

```python
prices = await request.app.state.price_cache.snapshot()
result = execute_trade("default", "AAPL", "buy", 10, prices)
```

---

## `db.connection`

```python
DB_PATH: Path              # <repo>/db/finally.db
DEFAULT_USER_ID = "default"
DEFAULT_WATCHLIST: list[str]   # the 10 seed tickers

get_connection() -> sqlite3.Connection
```

Tables: `users_profile`, `watchlist`, `positions`, `trades`,
`portfolio_snapshots`, `chat_messages` (PLAN.md section 7).

---

## `db.portfolio`

```python
get_profile(user_id: str = "default") -> dict
```
Returns `{"id": str, "cash_balance": float, "created_at": str}`.

```python
get_positions(user_id: str = "default") -> list[dict]
```
Open positions only (`quantity > 0`), ordered by ticker. Each row:
`{"ticker": str, "quantity": float, "avg_cost": float, "updated_at": str}`.

```python
compute_valuation(positions: list[dict], prices: dict, cash: float) -> dict
```
Pure function — no DB, no I/O. `cash` is passed in by the caller.
Returns:

```python
{
    "cash": float,
    "positions_value": float,      # sum of market values
    "total_value": float,          # cash + positions_value
    "cost_basis": float,           # sum of quantity * avg_cost
    "unrealized_pl": float,        # positions_value - cost_basis
    "positions": [
        {
            "ticker": str,
            "quantity": float,
            "avg_cost": float,
            "current_price": float,
            "market_value": float,
            "cost_basis": float,
            "unrealized_pl": float,
            "pct_change": float,   # vs avg_cost, in percent
        },
        ...
    ],
}
```
If a position's ticker is missing from `prices`, its `avg_cost` is used as the
current price (so it shows flat rather than vanishing or reading zero).

```python
get_portfolio(prices: dict, user_id: str = "default") -> dict
```
Convenience: `get_profile` + `get_positions` + `compute_valuation`. This is the
one call `GET /api/portfolio` needs. Same return shape as `compute_valuation`.

```python
execute_trade(user_id: str, ticker: str, side: str, quantity: float,
              prices: dict) -> TradeResult
```
One atomic sqlite transaction (`BEGIN IMMEDIATE`). Fill price is
`prices[ticker]` — market order, instant fill, no fees. Ticker is uppercased.

On success it: inserts a `trades` row, upserts `positions` (weighted average cost
on buys; avg cost unchanged on sells), updates `users_profile.cash_balance`,
and inserts a `portfolio_snapshots` row using the **post-trade** valuation
computed from the same `prices` map. All of that commits or rolls back together.

`TradeResult` (frozen dataclass, `db.portfolio.TradeResult`):

```python
success: bool
error: str | None          # set only when success is False
ticker: str | None
side: str | None           # "buy" | "sell"
quantity: float | None
price: float | None        # fill price
executed_at: str | None    # ISO 8601 UTC
cash_balance: float | None # post-trade cash
total_value: float | None  # post-trade portfolio total
trade_id: str | None
```

`TradeResult.as_dict()` returns the same fields as a plain dict (drop `error` in
API responses when `success` is True).

**Validation failures return `TradeResult(success=False, error=...)` — they do
not raise.** Error strings (stable, safe to surface to the user or the LLM):

| Condition | `error` |
|---|---|
| quantity <= 0 or not a number | `"Quantity must be greater than zero"` |
| side not buy/sell | `"Side must be 'buy' or 'sell'"` |
| ticker has no price in `prices` | `"No price available for {TICKER}"` |
| buy costs more than cash | `"Insufficient cash: need $X.XX, have $Y.YY"` |
| sell exceeds shares held | `"Insufficient shares: tried to sell N {TICKER}, hold M"` |

**Full sell deletes the position row** (rather than leaving a zero-quantity row).
This keeps `get_positions` and `load_active_tickers` (which filters
`quantity > 0`) consistent. Fractional quantities are supported throughout; a
sell is treated as closing the position when the remaining quantity is within
1e-9 of zero.

```python
get_trades(user_id: str = "default", limit: int = 50) -> list[dict]
```
Trade log, newest first:
`{"id","ticker","side","quantity","price","executed_at"}`. Not required by any
PLAN endpoint — useful for the chat assistant's context or a history panel.

---

## `db.snapshots`

```python
record_snapshot(user_id: str, total_value: float) -> None
get_snapshots(user_id: str = "default", limit: int | None = None) -> list[dict]
```
`get_snapshots` returns `[{"total_value": float, "recorded_at": str}, ...]` in
chronological order (oldest first) — chart-ready. With `limit`, returns the most
recent `limit` rows, still chronological.

`execute_trade` already records a snapshot, so the 30s background task only needs
to call `record_snapshot` on its own timer.

---

## `db.watchlist`

```python
list_watchlist(user_id: str = "default") -> list[str]     # ordered by added_at
add_watchlist(user_id: str, ticker: str) -> bool          # True if newly added
remove_watchlist(user_id: str, ticker: str) -> bool       # True if a row was removed
```
Tickers are uppercased and stripped. `add_watchlist` is idempotent — adding an
existing ticker is a no-op returning `False`. Removing a ticker you hold a
position in is allowed; the position stays priced via `load_active_tickers()`.

---

## `db.chat`

```python
add_chat_message(user_id: str, role: str, content: str, actions=None) -> str
get_recent_chat(user_id: str = "default", limit: int = 20) -> list[dict]
```
`role` is `"user"` or `"assistant"`. `actions` is any JSON-serializable value
(dict or list) or `None`; it is stored as a JSON string and returned parsed.
`add_chat_message` returns the new message id.

`get_recent_chat` returns the most recent `limit` messages in **chronological
order** (oldest first), ready to append to an LLM prompt:
`[{"role","content","actions","created_at"}, ...]`.

---

## `db.reads` (pre-existing, unchanged)

```python
load_active_tickers(user_id: str = "default") -> list[str]
```
Union of watchlist tickers and tickers with an open position.
