# Market Data Backend — Code Review

**Reviewer:** Coding Agent (comprehensive review)
**Date:** 2026-08-08
**Scope:** `backend/market/`, `backend/config.py`, `backend/main.py`, `backend/db/`, and `backend/tests/`
**Verdict:** ✅ **Approved.** The subsystem is well-designed, cleanly layered, and matches the specs in `PLAN.md` / `planning/archive/`. All 32 tests pass. The findings below are refinements and hardening opportunities — none are release blockers for a single-user simulated demo.

---

## 1. Test run

```
cd backend && uv sync && uv run pytest -v
```

**Result: 32 passed, 1 warning in 0.94s** (Python 3.13.7, pytest 9.1.1, pytest-asyncio 1.4.0).

- No network calls (Massive mocked via `httpx.MockTransport`).
- No API key required; deterministic via seeded RNG.
- Tests do **not** create a stray `finally.db` — DB-touching tests correctly `monkeypatch` `DB_PATH` to `tmp_path`.

The one warning is third-party and harmless:
`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` — originates from FastAPI's `TestClient`, not our code.

---

## 2. What is done well

- **Clean layering.** `source → feed → cache → routes` is a genuinely decoupled pipeline. The `MarketDataSource` ABC is minimal (`get_prices`, `get_history`, `aclose`), and both implementations satisfy it. Swapping sources really is the one-line change the design promised (`factory.make_source`).
- **Defense in depth on failures.** `MassiveSource` catches `HTTPStatusError` (429/401/403) and `HTTPError` (transport) and returns `{}`/`[]`; `MarketFeed._tick_once` *also* wraps `get_prices` in a try/except ("belt-and-suspenders"). A source hiccup can never kill the feed loop — the cache simply holds its last values. Well tested.
- **No empty-cache race.** `feed.prime()` runs one synchronous fill before `feed.start()`, so the first SSE/portfolio request always has data even on a 15s Massive cadence. This is exactly right.
- **Decoupled cadences.** Feed polls at the source's interval; SSE flushes at `sse_push_seconds`. The SSE loop dedups by timestamp (`last_sent`), so a slow Massive poll doesn't spam identical ticks, and a fast simulator still streams smoothly.
- **Correct GBM.** Correlation weights are consistent (`0.5² + 0.4² + √0.59² = 1.0`, unit variance), the drift/diffusion decomposition is textbook, and `max(price, 0.01)` guards the rounding edge. Determinism, positivity, correlation, and lazy-seeding are all covered by focused unit tests.
- **Config centralization.** `config.py` is the single place env vars are read, with sensible overrides (`MASSIVE_POLL_SECONDS`, `SIM_SEED`, `SSE_PUSH_SECONDS`). `_clean` trims whitespace so a stray-spaces key doesn't silently mis-route source selection.
- **Thoughtful SSE headers.** `Cache-Control: no-cache`, `X-Accel-Buffering: no` (nginx), a `retry: 2000` hint, and periodic `: keepalive` comments — all the right touches for a long-lived EventSource behind a proxy.
- **Off-loop DB reads.** `_tick_once` runs the synchronous SQLite read via `asyncio.to_thread`, so a slow disk read can't stall connected SSE clients.

---

## 3. Findings

### Medium

**M1 — Simulated history is non-deterministic across process restarts (and ignores `SIM_SEED`).**
`SimEngine.history` seeds its RNG with `random.Random(hash((ticker, days)) & 0xFFFFFFFF)` (`gbm.py:83`). Python salts `str`/`tuple` hashing per process (unless `PYTHONHASHSEED` is fixed), so the same ticker renders a *different* past on each restart. Verified:

```
$ python -c "print(hash(('AAPL', 90)))"   # -6063440565192957370
$ python -c "print(hash(('AAPL', 90)))"   #  2693844997386973154
```

This contradicts the docstring ("a given symbol always renders the same past — stable across chart reopens") and means `SIM_SEED` — the documented lever for reproducible E2E runs (`MARKET_DATA_SUMMARY.md`) — has **no effect on history**, only on live ticks. The test `test_history_deterministic_per_ticker` passes only because it compares two calls *within one process*, so it doesn't catch this.
**Fix:** derive the history RNG from the engine's configured seed, e.g. `random.Random((self._seed_int or 0) ^ zlib.crc32(ticker.encode()) ^ days)`, storing the int seed on the engine. Then add a cross-process determinism assertion (or set `PYTHONHASHSEED=0` in the test env, which is a weaker guarantee).

### Low

**L1 — No bounds on the `days` query parameter (`routes.py:61`).**
`GET /api/history/{ticker}?days=100000` makes the simulator loop 100k times building bars (CPU/allocation) on a single request; a negative `days` yields an empty/odd series. Clamp to a sane range, e.g. `days = max(1, min(days, 365*5))`.

**L2 — `float()`/`int()` env parsing can crash at import (`config.py:31-32`).**
`float(_clean("MASSIVE_POLL_SECONDS", "15"))` raises `ValueError` at module import if the var is non-numeric, taking down the whole app before FastAPI starts, with a bare traceback. Consider a tolerant parse that falls back to the default and logs a warning.

**L3 — `Bar.v` type mismatch.** `Bar.v` is annotated `float`, but the simulator sets `v=round(rng.uniform(1e6, 5e7))`, and `round()` with no `ndigits` returns an `int` (verified). Harmless over JSON, but inconsistent with the dataclass contract and with `MassiveSource` (which casts `float(...)`). Use `round(..., 2)` or `float(round(...))`.

**L4 — `last_sent` dict in the SSE generator grows unbounded (`routes.py:26`).**
Tickers removed from the watchlist leave stale entries in the per-connection `last_sent` map. Negligible at 10 tickers / short sessions, but worth a note if watchlists ever churn heavily on a long-lived connection.

**L5 — Synthetic history spaces bars by calendar days, including weekends (`gbm.py:99-104`).**
`ms_per_day = 86_400_000` steps every calendar day, so simulated "daily" bars include Saturdays/Sundays, whereas real Massive bars skip them. Cosmetic for a demo chart, but the two sources produce subtly different x-axes.

### Nits

- **N1 — `market/__init__.py` and `db/__init__.py` are empty** while the packages are imported as `market.x` / `db.x`. This works (implicit namespace / regular package via the file's presence), but confirm the Docker build and `uv` packaging pick them up as intended; an explicit empty file is fine, just flagging for awareness.
- **N2 — Redundant `@pytest.mark.asyncio`** on tests while `asyncio_mode = "auto"` is set in `pyproject.toml`. Harmless; could be dropped for consistency.
- **N3 — `MassiveSource` history date window** uses `int(days * 1.5) + 5` calendar days to cover `days` trading days then slices `[-days:]`. Reasonable heuristic; on very long holidays it could under-fill, but fine for 90-day charts.

---

## 4. Test coverage assessment

Strong where it counts (GBM math, Massive parsing/fallback/errors, feed resilience, cache semantics, factory selection, DB union logic). Gaps worth closing later:

1. **No test for the live SSE endpoint** `/api/stream/prices`. It's an infinite generator, but a smoke test that opens the stream, reads one `data:` frame, and asserts the `PriceTick` JSON shape would guard the frontend contract. (`test_routes.py` covers `/api/health` and `/api/history` only.)
2. **No cross-process/`SIM_SEED` determinism test for history** — see M1; current test can't catch the randomized-hash issue.
3. **No explicit ABC-conformance test** ("both sources implement the interface"). Instantiation implicitly checks it (ABCs raise on missing methods), but an explicit parametrized test documents the contract.
4. **`MassiveSource.get_history` URL/params not asserted** — the mock returns a fixed body regardless of the request, so the date-range construction and `[-days:]` slice aren't verified against the request that was actually sent.

---

## 5. Spec conformance

| PLAN requirement | Status |
|---|---|
| One interface, two implementations, env-selected | ✅ `factory.make_source` via `MASSIVE_API_KEY` |
| GBM simulator, ~500ms, correlated, events, seedable | ✅ `gbm.py` (events at 0.5%, sector correlation, `SIM_SEED`) |
| Massive REST snapshot poller, one call/all tickers, 15s free tier | ✅ `massive.py`, configurable interval |
| Shared in-memory cache, single writer | ✅ `PriceCache` + `MarketFeed` |
| SSE `/api/stream/prices` with ticker/price/prev/direction/timestamp | ✅ `routes.py` + `PriceTick` |
| Active tickers = watchlist ∪ open positions | ✅ `db/reads.load_active_tickers` |
| Lazy SQLite init + seed | ✅ `db/connection.py` |
| Source failures never crash the feed | ✅ double-guarded |
| Deterministic tests, no network, no key | ✅ (except history determinism — M1) |

Note: `GET /api/history/{ticker}` is an addition beyond the PLAN §8 endpoint table (documented in `MARKET_DATA_SUMMARY.md` / `MARKET_INTERFACE.md`). It's a sensible one — the detail chart needs backfill — just not reflected in PLAN's table.

---

## 6. Recommendation

Ship it. Address **M1** before relying on `SIM_SEED` for deterministic E2E chart tests (it's the only finding with functional impact on the stated testing strategy). **L1** (bound `days`) and **L2** (tolerant env parse) are cheap hardening wins. Everything else is polish that can ride along with the portfolio/chat work that builds on this layer.
