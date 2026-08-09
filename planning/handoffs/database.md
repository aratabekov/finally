# Handoff — Database Engineer

**Status: done.** `backend/db/` is complete and tested. Wave 2 (Backend API, LLM)
is unblocked.

The authoritative API reference is **`planning/DB_CONTRACT.md`** — exact
signatures, return shapes, and error strings. This file is just the summary.

## What was built

| File | Contents |
|---|---|
| `backend/db/connection.py` | *(extended)* added `trades`, `portfolio_snapshots`, `chat_messages` tables + indexes to `_SCHEMA`. Existing tables, seeding, and lazy init untouched. |
| `backend/db/util.py` | `utc_now_iso()`, `new_id()`, `normalize_ticker()` |
| `backend/db/portfolio.py` | `get_profile`, `get_positions`, `compute_valuation`, `get_portfolio`, `execute_trade`, `get_trades`, `TradeResult` |
| `backend/db/snapshots.py` | `record_snapshot`, `get_snapshots`, `insert_snapshot` (connection-scoped) |
| `backend/db/watchlist.py` | `list_watchlist`, `add_watchlist`, `remove_watchlist` |
| `backend/db/chat.py` | `add_chat_message`, `get_recent_chat` |
| `backend/tests/test_db_portfolio.py` | 24 tests |
| `backend/tests/test_db_watchlist_chat.py` | 9 tests |

`backend/db/reads.py` is unchanged.

## Things to know before you write against it

1. **Pass a price map, don't expect the DB to fetch prices.** The layer never
   imports the market cache. Both `dict[str, float]` and the
   `dict[str, PriceTick]` from `await cache.snapshot()` work — a `.price`
   attribute is read off the value when present.

   ```python
   prices = await request.app.state.price_cache.snapshot()
   portfolio = get_portfolio(prices)                       # GET /api/portfolio
   result = execute_trade("default", ticker, side, qty, prices)
   ```

2. **`execute_trade` never raises on validation failure.** Check
   `result.success` and surface `result.error` (already user-readable, e.g.
   `"Insufficient cash: need $1,234.00, have $900.00"`). Map to HTTP 400 in the
   API; hand it back to the LLM verbatim in chat.

3. **`execute_trade` already records a portfolio snapshot** using post-trade
   valuation, inside the same transaction. The 30s background task only needs
   its own `record_snapshot("default", total_value)` on a timer — do not
   double-record after a trade.

4. **A full sell deletes the position row.** `get_positions()` returns open
   positions only, consistent with `load_active_tickers()`.

5. **Everything is sync `sqlite3`.** Safe to call directly from `def` endpoints
   (FastAPI runs them in a threadpool). From `async def` endpoints the calls are
   sub-millisecond against a local file, so calling them inline is fine.

6. **Tickers are normalized to uppercase** on write in trades and watchlist —
   the API does not need to pre-uppercase, but reads are case-sensitive so
   normalize before comparing.

7. **Fresh DBs seed themselves** on the first `get_connection()`: `$10,000` cash
   and the 10 default tickers. No migration step.

## Validate

```bash
cd backend && uv run pytest -q     # 82 passed
```

DB tests monkeypatch `connection.DB_PATH` to `tmp_path`, so the suite never
creates a stray `finally.db`. No network, no API key, deterministic.
