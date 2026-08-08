# FinAlly Backend — Market Data subsystem

This directory contains the FinAlly FastAPI backend. The **market data
subsystem** (`market/`) is implemented per `planning/MARKET_DATA_DESIGN.md`.

## Layout

```
backend/
├── pyproject.toml          # uv project + pytest config
├── config.py               # env-driven settings (single source of truth)
├── market/
│   ├── types.py            # PriceTick, Bar, Direction
│   ├── source.py           # MarketDataSource ABC (the unified interface)
│   ├── cache.py            # PriceCache (in-memory, lock-guarded)
│   ├── feed.py             # MarketFeed background writer
│   ├── factory.py          # make_source(): env -> source
│   ├── seeds.py            # per-ticker GBM seed params
│   ├── gbm.py              # SimEngine (correlated GBM + synthetic history)
│   ├── simulator.py        # SimulatedSource (default, no key)
│   ├── massive.py          # MassiveSource (live data via Massive/Polygon)
│   └── routes.py           # /api/stream/prices (SSE), /api/history/{ticker}
└── tests/                  # pytest unit tests (no network; httpx MockTransport)
```

## Source selection

`MASSIVE_API_KEY` set and non-empty → `MassiveSource` (REST snapshot polling).
Otherwise → `SimulatedSource` (in-process GBM simulator). Decided once at
startup in `market/factory.py`.

## Running the tests

```bash
uv sync --dev
uv run pytest
```

All tests are deterministic (fixed RNG seeds), require no API key, and make no
real network calls (Massive is exercised through `httpx.MockTransport`).

## Integration points owned by other agents

The market subsystem is self-contained behind two seams that the app-wiring and
database agents provide:

- **`main.py` lifespan wiring** — creates the `PriceCache`, calls
  `make_source()`, starts the `MarketFeed`, and mounts `market.routes.router`.
  See `planning/MARKET_DATA_DESIGN.md` §10.1 for the exact snippet.
- **`db.reads.load_active_tickers`** — the callable passed to `MarketFeed`
  returning the union of watchlist tickers and held positions. The feed depends
  only on this callable, not on the DB layer, so it stays decoupled.
