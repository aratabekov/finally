# Backend — Developer Guide

FastAPI app managed as a `uv` project. The market data subsystem is complete;
portfolio, chat, and watchlist-mutation endpoints are still to be built on top of
it. See `planning/MARKET_DATA_SUMMARY.md` for the subsystem contract and
`planning/archive/` for the design rationale behind each decision.

## Setup

```bash
cd backend
uv sync                       # installs runtime + dev deps (pytest, pytest-asyncio)
```

## Run

```bash
cd backend
uv run uvicorn main:app --reload    # serves on http://localhost:8000
```

`main.py` calls `load_dotenv()` before importing `config`, so `.env` in the
project root is picked up automatically. On startup the lifespan handler builds
the source/feed/cache, `prime()`s the cache once (so the first request always has
data), then starts the background feed loop.

## Layout

```
main.py       # FastAPI app + lifespan wiring; GET /api/health
config.py     # Settings — the ONLY place env vars are read (load_settings/settings)
db/
  connection.py  # lazy sqlite init + seed at db/finally.db
  reads.py       # load_active_tickers() — watchlist ∪ open positions
market/
  types.py       # PriceTick, Bar, Direction
  source.py      # MarketDataSource ABC: get_prices, get_history, aclose
  cache.py       # PriceCache — async, lock-guarded, one PriceTick per ticker
  feed.py        # MarketFeed — single background writer into the cache
  factory.py     # make_source() — env-driven source selection
  seeds.py       # per-ticker GBM seed params (the 10 default tickers)
  gbm.py         # SimEngine — correlated GBM + synthetic history
  simulator.py   # SimulatedSource (default, no key needed)
  massive.py     # MassiveSource (used when MASSIVE_API_KEY is set)
  routes.py      # GET /api/stream/prices (SSE), GET /api/history/{ticker}
tests/           # pytest + pytest-asyncio; deterministic, no network, no key
```

## Key APIs

```python
from market.cache import PriceCache
from market.factory import make_source
from market.feed import MarketFeed
from market.types import PriceTick, Bar
from db.reads import load_active_tickers
from config import settings
```

- **`PriceCache`** (async, in-memory, single instance on `app.state.price_cache`):
  - `await cache.snapshot() -> dict[str, PriceTick]` — consistent copy for valuation
  - `await cache.get(ticker) -> PriceTick | None`
  - `await cache.update(tick)` — feed-only; consumers read, never write
  - `await cache.retain(tickers)` — feed-only; evicts everything outside the
    active set each cycle, so a de-watchlisted ticker stops being priced (and
    therefore stops being tradeable) instead of freezing at its last price

- **`PriceTick`** — frozen dataclass: `ticker`, `price`, `previous_price`,
  `direction` ("up"/"down"/"flat"), `timestamp` (ISO 8601 UTC). Serialized as-is
  over SSE.

- **`Bar`** — frozen OHLCV candle: `t` (Unix ms), `o`, `h`, `low`, `c`, `v`.
  Note the field is `low` in Python but serialized as `"l"` in `/api/history`.

- **`MarketDataSource`** ABC — `get_prices(tickers) -> {ticker: price}`,
  `get_history(ticker, days=90) -> list[Bar]`, `aclose()`. Never call a source
  directly from feature code; read the cache instead.

- **`make_source()`** — returns `MassiveSource` when `MASSIVE_API_KEY` is set and
  non-empty, else `SimulatedSource`. Downstream code stays source-agnostic.

- **`load_active_tickers()`** — union of watchlist tickers and tickers with an
  open position (`quantity > 0`), so a de-watchlisted holding stays priced.

## Consuming the market data (portfolio / chat / frontend agents)

- **Live prices**: read `app.state.price_cache`; use `snapshot()` for valuation.
- **History**: `GET /api/history/{ticker}?days=90` → `{ticker, bars:[{t,o,h,l,c,v}]}`.
  `days` is clamped to `[1, 1825]`.
- **Live stream**: `GET /api/stream/prices` (SSE); each `data:` frame is a
  `PriceTick` JSON object.
- **DB**: `db/reads.py` only exposes reads used by the feed. Extend
  `db/connection.py`'s schema (trades, portfolio_snapshots, chat_messages, full
  watchlist/position CRUD) rather than replacing it — the feed already relies on
  the `watchlist` and `positions` tables.

## Config

All env vars are read in `config.py` and exposed via `settings`
(`load_settings()`): `MASSIVE_API_KEY`, `MASSIVE_POLL_SECONDS`, `SIM_SEED`,
`SSE_PUSH_SECONDS`, `OPENROUTER_API_KEY`, `LLM_MOCK`. Malformed numeric values
log a warning and fall back to the default instead of crashing at import. Set
`SIM_SEED` for a fully deterministic simulator (live ticks *and* history).

## Demo

`demo.py` is a standalone rich terminal dashboard for the simulator — it drives
the real `SimulatedSource` (no server, DB, or API key) and renders live prices,
per-ticker sparklines, session P&L, sector grouping, and `⚡` shock events.

```bash
cd backend
uv run python demo.py                     # 10 default tickers, Ctrl+C to quit
uv run python demo.py --seed 42           # deterministic (mirrors SIM_SEED)
uv run python demo.py --steps 40 --interval 0.1
uv run python demo.py --tickers AAPL,NVDA,TSLA
uv run python demo.py --plain --no-color  # append frames (pipe/CI friendly)
```

## Tests

```bash
cd backend
uv run pytest            # all tests: deterministic, no network, no API key
uv run pytest -v
```

Massive is exercised via `httpx.MockTransport`; DB-touching tests monkeypatch
`DB_PATH` to a tmp dir, so running the suite never creates a stray `finally.db`.
`asyncio_mode = "auto"` is set, so async tests need no explicit marker.
