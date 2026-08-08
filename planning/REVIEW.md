# Review — Market Data Documentation

Review of changes since the last commit (`6b568a9`). Scope: three new planning
documents plus two pre-existing file deletions.

## Changes reviewed

| Change | Type | Notes |
|--------|------|-------|
| `planning/MASSIVE_API.md` | Added | Massive (ex-Polygon.io) API reference with code examples |
| `planning/MARKET_INTERFACE.md` | Added | Unified `MarketDataSource` interface design |
| `planning/MARKET_SIMULATOR.md` | Added | GBM simulator approach and code structure |
| `.claude/agents/change-reviewer.md` | Deleted | Pre-existing (present at session start), not authored this session |
| `.claude/commands/doc-review.md` | Deleted | Pre-existing (present at session start), not authored this session |

The two deletions were already staged in the working tree when the session
began; they are unrelated to the documentation work and are noted here only for
completeness.

## Consistency with PLAN.md

Verified the three docs against the contract in `PLAN.md`:

- Env-var selection (`MASSIVE_API_KEY` set -> Massive, else simulator) — matches.
- REST polling, not WebSocket — matches (WebSocket documented only as a rejected
  alternative).
- Free tier 5 req/min -> 15s poll interval — matches.
- Simulator: GBM, ~500ms updates, correlated moves, random events, realistic
  seed prices, in-process background task — all matches.
- Shared in-memory price cache with latest/previous price and timestamp; SSE
  reads from cache — matches.
- Default 10 tickers (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX) —
  all present in `SEEDS`.
- Code style: async-native, httpx over the sync client, `uv`-friendly, no
  emojis, non-defensive — matches user/global instructions.

No contradictions with PLAN.md were found.

## Findings

These are documentation-design notes, not code defects (no application code
exists yet). Severity is advisory.

1. **[Low] Snapshot data freshness on the free tier.** `MASSIVE_API.md` correctly
   states the free tier is EOD + 15-min delayed, but the interface doc presents
   Massive as "live". For the default (no-key) user this is moot, but a
   free-tier key holder will see delayed/stale prices with little in-UI signal.
   Consider noting in the interface doc that free-tier Massive is not truly
   realtime and the simulator may be the better demo experience.

2. **[Low] Watchlist fetched every feed cycle from SQLite.** `MARKET_INTERFACE.md`
   has `MarketFeed` call `get_watchlist()` each loop; for the simulator that is a
   DB read every 500ms. Fine for single-user SQLite, but worth a one-line note
   that the callable should be cheap (or cached with short TTL) so the doc does
   not imply a hot DB query is free.

3. **[Low] Massive `poll_interval_seconds` is hardcoded to 15s.** PLAN.md says
   paid tiers can poll every 2-15s. The current design fixes 15s. Acceptable
   default (safe for free tier), but the doc could mention making it
   env-configurable for paid users. Not blocking.

4. **[Info] Two snapshot endpoints documented (v2 full-market vs v3 unified).**
   The docs pick v2 and clearly mark v3 as an alternative with the field mapping.
   This is a deliberate, well-justified choice — no action needed, just
   confirming it is intentional and won't confuse the implementer.

5. **[Info] Correlation weights are illustrative.** The one-factor-per-sector
   weights (0.5/0.4/idiosyncratic) in `MARKET_SIMULATOR.md` are reasonable but
   unvalidated against any target correlation. Fine for a demo simulator; the
   testing section already calls for a same-sign correlation check.

## Correctness spot-checks

- GBM step formula and the `dt = 0.5 / (252*6.5*3600)` scaling are dimensionally
  correct (annualized mu/sigma with a 500ms step).
- `max(price, 0.01)` positivity guard and `round(..., 2)` cent rounding are sound.
- Snapshot response parsing prefers `lastTrade.p` then falls back to `day.c` then
  `prevDay.c` — correct given the endpoint's documented shape and closed-market
  behavior.
- Timestamp units are stated correctly (nanoseconds for trades/quotes,
  milliseconds for aggregate bars).

## Verdict

The three documents are internally consistent, agree with PLAN.md, and are ready
to serve as the implementation contract for the market data layer. Findings above
are minor and can be folded in during implementation rather than blocking. No
required changes.
