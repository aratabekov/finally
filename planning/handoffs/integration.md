# Integration / E2E Handoff

Playwright suite in `test/`, run against the production container.

**Status: green. 32 passed, 0 skipped, 0 failed**, stable across three
consecutive fresh-build runs after the round-1 fixes. All four bugs from round 1
are verified fixed end to end.

## How it was run

**Docker** (the preferred mode in PLAN section 12). `docker build` from the repo
root succeeds end to end — no DevOps blocker.

`test/docker-compose.test.yml` builds the root `Dockerfile` and runs it with
`LLM_MOCK=true`, `SIM_SEED=42`, `SSE_PUSH_SECONDS=0.5`, port 8000. **No volume
is mounted**, so every run starts from a freshly seeded database ($10,000 cash,
10 default tickers, no positions) and nothing is written to the repo's `db/`
directory (verified: `db/` still contains only `.gitkeep`, `git status` clean of
any `finally.db`).

```bash
cd test && npm install && npx playwright install chromium
npm run e2e        # build, start, wait for /api/health, test, tear down
```

Browsers stay out of the production image — Playwright runs on the host against
the container. `playwright.config.ts` pins `workers: 1` and
`fullyParallel: false` because the suite shares one server-side database; specs
run in filename order and the fresh-seed scenarios come first.

## Results

| Scenario (PLAN section 12) | Spec | Result |
|---|---|---|
| Fresh start: 10 tickers, $10k, streaming | `01-fresh-start` | PASS (3/3) |
| Prices flash green/red on tick | `01-fresh-start` | PASS |
| Ticker selection drives chart + order rail | `01-fresh-start` | PASS |
| Mocked AI analysis (exact string) | `02-chat-analysis` | PASS (2/2) |
| Add / remove a watchlist ticker | `03-watchlist` | PASS (5/5) |
| Buy: cash down, position appears | `04-trading` | PASS (3/3) |
| Sell: cash up, position reduced | `04-trading` | PASS |
| Heatmap renders position rectangles | `05-portfolio-viz` | PASS (4/4) |
| P&L chart has plotted data | `05-portfolio-viz` | PASS |
| AI chat executes trades inline | `06-chat-actions` | PASS (6/6) |
| AI chat restores transcript on reload | `06-chat-actions` | PASS |
| SSE resilience / reconnect | `07-sse-resilience` | PASS (2/2) |
| Trade rejections surfaced to the user | `08-trade-validation` | PASS (7/7) |
| Full sell closes the position | `08-trade-validation` | PASS |

Also verified, no defects found:

- `GET /` serves the Next.js export from the container. The open item in
  `devops.md` ("`GET /` returns 404") is **resolved**.
- Every documented `LLM_MOCK` string in `llm.md` matches byte for byte,
  including the fresh-book analysis line, the compound
  `"Executing sell 2 AAPL at the current market price. Removing PYPL from the
  watchlist."`, and the `"\n\nCould not complete: ..."` paragraph.
- Watchlist adds, positions, cash and the chat transcript all survive a reload.
- Zero browser console errors and zero unexpected 4xx/5xx on the happy paths
  (asserted in `01` and `04` via `watchForErrors`).
- Net liquidation is conserved across a market order (no fees leaking in).

## Round-1 bugs — all verified fixed

| Bug | Owner | Verified by |
|---|---|---|
| BUG-1 (HIGH) trade rejection reasons never reached the user | frontend | `08` now asserts the rail shows the server's `error` verbatim for insufficient cash, insufficient shares, and an unpriced ticker. `api.ts` `request()` reads `detail` or `error`; the backend envelope was left unchanged, as agreed. |
| BUG-2 fill echo used the client's last-seen price | frontend | `08` "the fill echo reports the price the server actually filled at" now compares `trade-status` against the `price` in the trade response. |
| BUG-3 chat transcript lost on reload | frontend | `06` "the transcript is restored on reload" — `test.fixme` removed, runs for real; asserts restored user turns and that executed actions come back with the turn that produced them. |
| BUG-4 de-watchlisted tickers stayed tradeable at a frozen price | backend | `08` "a ticker removed from the watchlist is no longer tradeable" — after eviction the order returns 400 `No price available for VWXY`. |

Three suite changes were needed to match the new behaviour, none of them
masking anything:

- Restoring history re-renders past `chat-action` entries, so `06` now scopes
  action assertions to the reply under test (`chat()` returns a `Reply` with an
  `actions` locator) rather than counting globally. `02` asserts on the newest
  user message for the same reason.
- The old fill-echo test proved its point by trading a de-watchlisted ticker,
  which BUG-4's fix correctly blocks. It was rewritten to compare the echo
  against the server's fill price on a normal ticker, and the de-watchlisted
  path became the BUG-4 regression test.

## Open observations (informational, no fix requested)

### OBS-1 — No symbol validation anywhere — `backend-engineer`

`POST /api/watchlist` accepts any string, and `market/gbm.py` `_ensure()` falls
back to `DEFAULT_SEED` with a random 0.5-2.0 jitter for anything not in `SEEDS`.
A typo like `WXYZ` therefore streams a plausible fake price around $50-200 and
is fully tradeable. Deliberate for the simulator, but it means the UI cannot
distinguish a real ticker from a typo. Covered by a passing test that documents
the behaviour (`03-watchlist`, "an unknown symbol is accepted and the simulator
invents a price"), so a future decision to validate will surface there.

### OBS-2 — Connection dot tracks socket state, not data freshness — `frontend-engineer`

`usePriceStream.ts` derives the status purely from `EventSource` readyState. If
the transport stalls without closing, the dot stays green while no ticks arrive.
This is why `07-sse-resilience` restarts the container instead of using
`context.setOffline(true)` — Chromium's offline emulation leaves the established
SSE connection open and the dot never changes. A staleness timeout (no tick in N
seconds -> reconnecting) would make the indicator honest. Not a blocker.

## Notes for anyone extending the suite

Price cells render `--` before mount and `0.00` between mount and the first SSE
flush, so `expect(cell).not.toHaveText("--")` passes vacuously twice over — and
a negated matcher on an element that has not rendered yet passes as well. Use
`expectPriced()` from `tests/helpers.ts`, which polls for a non-zero number.
Both traps produced false greens during the first round.

`placeOrder()` returns the raw `/api/portfolio/trade` response, so a scenario
can assert the server contract and the rendered UI independently.
