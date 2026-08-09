# FinAlly Build — Agent Team Coordination

This is the shared contract for the team building the remainder of FinAlly on top
of the completed market-data subsystem. Read `planning/PLAN.md` (full spec) and
`planning/MARKET_DATA_SUMMARY.md` (what already exists) first.

The team lead (orchestrator) owns this file and integration verification. Team
members own disjoint file sets so we never collide on the same file.

## Roster & File Ownership

| Member | Owns (may edit) | Must NOT edit |
|---|---|---|
| **Database Engineer** | `backend/db/**` | anything outside `backend/db/` |
| **Backend API Engineer** | `backend/main.py`, `backend/portfolio/**`, `backend/watchlist/**`, `backend/snapshots/**` | `backend/db/**`, `backend/chat/**`, `backend/market/**` |
| **LLM Engineer** | `backend/chat/**` | `backend/main.py`, everything else outside `backend/chat/` |
| **Frontend Engineer** | `frontend/**` | backend |
| **DevOps Engineer** | `Dockerfile`, `docker-compose.yml`, `scripts/**`, `.dockerignore` | app source |
| **Integration Tester** | `test/**` | app source (reports bugs back instead of fixing) |

Shared/existing files (`config.py`, `market/**`, `pyproject.toml`) are edited only
by the team lead or on explicit request routed through the lead.

## Dependency Waves

- **Wave 1 (parallel):** Database Engineer, Frontend Engineer, DevOps Engineer.
- **Wave 2 (parallel, after DB contract published):** Backend API Engineer, LLM Engineer.
- **Wave 3:** Integration Tester (E2E), then a fix loop routed to the owners.

## DB Contract (Database Engineer implements; Backend API + LLM consume)

Extend `backend/db/connection.py` `_SCHEMA` — ADD these tables (keep the existing
`users_profile`, `watchlist`, `positions` untouched; they are relied on by the
market feed): `trades`, `portfolio_snapshots`, `chat_messages` exactly as
specified in PLAN.md section 7.

Expose these functions (final names/signatures are the DB Engineer's call, but
must match what is published in `planning/DB_CONTRACT.md` — publish that file as
your Wave-1 deliverable). Target surface:

```python
# Profile & positions (raw reads)
get_profile(user_id="default") -> {"cash_balance": float, ...}
get_positions(user_id="default") -> list[{"ticker","quantity","avg_cost", ...}]

# Pure valuation helper (NO cache import; callers pass a live price map)
compute_valuation(positions, prices: dict[str, float]) -> {
    "total_value": float, "cash": float, "positions": [ {..., "current_price",
    "market_value", "unrealized_pl", "pct_change"} ], ...
}
# NOTE: cash is added by the caller or read inside; document which.

# Trade execution — one atomic transaction. `prices` is the full live price map
# (from `await cache.snapshot()`), fill price is prices[ticker]. Validates
# sufficient cash on buy / sufficient shares on sell. On success it also records
# a portfolio_snapshots row using post-trade valuation. Returns a result object
# with success flag + error string on failure (does NOT raise on validation
# failure — return the error so the API/LLM can surface it).
execute_trade(user_id, ticker, side, quantity, prices) -> TradeResult

# Snapshots
record_snapshot(user_id, total_value) -> None
get_snapshots(user_id="default") -> list[{"total_value","recorded_at"}]

# Watchlist mutation
add_watchlist(user_id, ticker) -> None          # idempotent
remove_watchlist(user_id, ticker) -> None
list_watchlist(user_id="default") -> list[str]

# Chat history
add_chat_message(user_id, role, content, actions=None) -> None
get_recent_chat(user_id="default", limit=20) -> list[{"role","content","actions","created_at"}]
```

Keep DB code sync (sqlite3), no async, no cache imports — that is what keeps this
layer usable by both consumers with zero coupling between them.

## Backend integration points (Backend API Engineer)

- `backend/main.py` is the ONLY place routers are included and background tasks
  start. Include the chat router via `from chat.routes import router as chat_router`
  (LLM Engineer must expose exactly that).
- Serve the built frontend: mount static files from `backend/static/` **if the
  directory exists** (it won't during local dev; the Dockerfile populates it).
  Fall back gracefully when absent so `uv run uvicorn main:app` still works.
- Snapshot background task: record a portfolio snapshot every 30s (PLAN §7).
- Endpoints to implement: `GET /api/portfolio`, `POST /api/portfolio/trade`,
  `GET /api/portfolio/history`, `GET /api/watchlist`, `POST /api/watchlist`,
  `DELETE /api/watchlist/{ticker}` (all per PLAN §8). Read live prices from
  `request.app.state.price_cache`.

## Chat contract (LLM Engineer)

- Expose `backend/chat/routes.py` with `router = APIRouter(prefix="/api")` and
  `POST /api/chat` per PLAN §8/§9. Do NOT touch main.py.
- Use the `cerebras` skill: LiteLLM -> OpenRouter, model
  `openrouter/openai/gpt-oss-120b`, Cerebras provider, structured outputs.
- Honor `LLM_MOCK=true` (config.settings.llm_mock) with deterministic responses.
- Auto-execute trades/watchlist_changes by calling the DB contract functions
  (`execute_trade`, `add_watchlist`, `remove_watchlist`). Fetch live prices from
  `request.app.state.price_cache`. Surface validation errors back in the reply.
- Persist user + assistant messages via `add_chat_message`.

## Global rules (all members)

- Use `uv` only: `uv run ...`, `uv add ...`. Never bare `python`/`pip`.
- No emojis anywhere in code, logs, or prints.
- Simple, incremental, no defensive over-engineering. Latest library APIs.
- Ship unit tests for your own code (`backend/tests/` follows existing patterns;
  frontend uses its own runner). Tests must be deterministic and need no network
  or API key (`LLM_MOCK=true`, `SIM_SEED` for reproducibility).
- When done, write a short handoff file `planning/handoffs/<role>.md` (what you
  built, how to run/test it, anything the next wave needs) and report back.
