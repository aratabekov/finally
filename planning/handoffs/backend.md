# Backend API — Handoff

Portfolio, watchlist, and snapshot endpoints on top of the market-data
subsystem and the DB contract (`planning/DB_CONTRACT.md`).

## What was built

```
backend/main.py            # routers + lifespan (market feed, snapshot task, static mount)
backend/portfolio/routes.py  # GET /api/portfolio, POST /api/portfolio/trade, GET /api/portfolio/history
backend/watchlist/routes.py  # GET/POST /api/watchlist, DELETE /api/watchlist/{ticker}
backend/snapshots/task.py    # SnapshotTask — records portfolio value every 30s
backend/tests/test_portfolio_routes.py
backend/tests/test_watchlist_routes.py
```

Every route reads live prices from `request.app.state.price_cache.snapshot()`
and delegates all persistence to `db.*`. The DB layer is synchronous sqlite, so
each call runs via `asyncio.to_thread` to keep the event loop (and the SSE
stream) responsive.

## Endpoints

### `GET /api/portfolio` -> 200

`db.portfolio.get_portfolio` verbatim:

```json
{
  "cash": 8000.0,
  "positions_value": 2000.0,
  "total_value": 10000.0,
  "cost_basis": 2000.0,
  "unrealized_pl": 0.0,
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": 10.0,
      "avg_cost": 200.0,
      "current_price": 200.0,
      "market_value": 2000.0,
      "cost_basis": 2000.0,
      "unrealized_pl": 0.0,
      "pct_change": 0.0
    }
  ]
}
```

`positions` is `[]` when nothing is held. A position whose ticker has no cached
price is valued at its average cost (reads flat, never zero).

### `POST /api/portfolio/trade`

Request: `{"ticker": "AAPL", "quantity": 10, "side": "buy"}` (`side` is
`"buy"` or `"sell"`; `quantity` supports fractions). Market order, instant fill
at the cached price, no fees.

**200 on success** — `TradeResult.as_dict()`, `error` is `null`:

```json
{
  "success": true,
  "error": null,
  "ticker": "AAPL",
  "side": "buy",
  "quantity": 10.0,
  "price": 200.0,
  "executed_at": "2026-08-09T12:00:00+00:00",
  "cash_balance": 8000.0,
  "total_value": 10000.0,
  "trade_id": "uuid"
}
```

**400 on a validation failure** — the *same body shape*, with `success: false`
and a user-facing `error` (all other fields `null`). Show `error` directly:

| Cause | `error` |
|---|---|
| quantity <= 0 | `Quantity must be greater than zero` |
| bad side | `Side must be 'buy' or 'sell'` |
| unpriced ticker | `No price available for ZZZZ` |
| buy > cash | `Insufficient cash: need $X.XX, have $Y.YY` |
| sell > held | `Insufficient shares: tried to sell N AAPL, hold M` |

**422** for a malformed body (missing/non-numeric field) — standard FastAPI
validation, `{"detail": [...]}`.

A successful trade also records a `portfolio_snapshots` row, so
`/api/portfolio/history` updates immediately after each trade.

### `GET /api/portfolio/history` -> 200

Bare array, chronological (oldest first), chart-ready. `[]` before the first
snapshot:

```json
[{"total_value": 10000.0, "recorded_at": "2026-08-09T12:00:00+00:00"}]
```

### `GET /api/watchlist` -> 200

Bare array in the order tickers were added, joined with the latest cached tick:

```json
[
  {
    "ticker": "AAPL",
    "price": 200.0,
    "previous_price": 199.0,
    "direction": "up",
    "timestamp": "2026-08-09T12:00:00+00:00"
  },
  {
    "ticker": "PYPL",
    "price": null,
    "previous_price": null,
    "direction": "flat",
    "timestamp": null
  }
]
```

A just-added ticker has no cached tick until the feed's next poll, so its price
fields are `null` — render it as pending rather than assuming it is missing.
Field names match the SSE `PriceTick` frames, so the same row renderer works for
both the initial load and live updates.

### `POST /api/watchlist`

Request `{"ticker": "pypl"}` (trimmed and uppercased server-side).

- **200** `{"ticker": "PYPL", "added": true}` — `added` is `false` when the
  ticker was already on the list (idempotent, not an error).
- **400** `{"detail": "Ticker is required"}` for a blank ticker.

### `DELETE /api/watchlist/{ticker}` -> 200

`{"ticker": "TSLA", "removed": true}`. `removed` is `false` if it was not on the
list (no 404). Removing a ticker you hold a position in is allowed — the
position stays priced via `load_active_tickers()`.

A removed ticker you do **not** hold stops being priced within one feed cycle
(the feed evicts it from the cache), so a subsequent trade for it returns
**400 `No price available for {TICKER}`** rather than filling at a stale price.

### Unchanged, for reference

`GET /api/health`, `GET /api/stream/prices` (SSE), `GET /api/history/{ticker}`
are as before. `POST /api/chat` is the LLM Engineer's.

## Background snapshot task

`snapshots.task.SnapshotTask` records one snapshot on start and then every 30s
(`SNAPSHOT_INTERVAL_SECONDS`), valuing the portfolio from the price cache. It is
started and stopped in the `main.py` lifespan alongside the market feed and is
exposed as `app.state.snapshot_task`. Failures are logged and the loop
continues.

## main.py notes

- Routers: market, portfolio, watchlist, then `chat.routes.router` — the chat
  import is wrapped in `try/except ImportError` (logs a warning) so the app
  still boots while `backend/chat/` is being written. Once it lands the router
  is included automatically; no change needed.
- Static frontend: `backend/static/` is mounted at `/` with `html=True`, **only
  if the directory exists**. The Dockerfile populates it; locally the mount is
  simply skipped, so `uv run uvicorn main:app --reload` works with no build.
  The mount is registered after all routers, so `/api/*` always wins.

## Run / test

```bash
cd backend
uv run uvicorn main:app --reload    # http://localhost:8000
uv run pytest -q                    # 99 passed
```

Tests swap `app.state.price_cache` for a stub with fixed prices after startup
and monkeypatch `db.connection.DB_PATH` to a tmp dir, so they are deterministic
and need no network or API key. They also no-op `SnapshotTask.start` so snapshot
rows come only from the trades under test.
