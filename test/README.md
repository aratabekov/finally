# E2E tests

Playwright suite covering PLAN.md section 12, run against the real container.

## Run

```bash
cd test
npm install
npx playwright install chromium
npm run e2e            # build image, start container, run suite, tear down
```

`run-e2e.sh` is idempotent: it stops any previous container, rebuilds the image
from the root `Dockerfile`, waits for `/api/health`, runs Playwright, and tears
the container down again on exit.

Against an app you started yourself:

```bash
npm test                                   # expects http://localhost:8000
BASE_URL=http://localhost:3000 npm test
```

## How the app is run

`docker-compose.test.yml` builds the production image and runs it with
`LLM_MOCK=true` (deterministic replies, no network, no API key) and
`SIM_SEED=42`. **No volume is mounted**, so every run starts from a freshly
seeded database — $10,000 cash, the 10 default tickers, no positions. Nothing is
written to the repo's `db/` directory.

## Layout

The suite mutates one shared server-side database, so `playwright.config.ts`
pins `workers: 1` and `fullyParallel: false`. Specs run in filename order and
the ones that depend on the fresh seed come first.

| Spec | Covers |
|---|---|
| `01-fresh-start` | 10 default tickers, $10,000 seed, live stream and flash, ticker selection |
| `02-chat-analysis` | the exact `LLM_MOCK` analysis line, which is only exact on an untraded book |
| `03-watchlist` | add, persistence across reload, remove, blank input, unvalidated symbols |
| `04-trading` | buy opens a position and debits cash, partial sell, persistence |
| `05-portfolio-viz` | exposure treemap cells, equity curve path, positions table |
| `06-chat-actions` | mocked trade / watchlist / compound / rejected instructions, transcript restore, panel toggle |
| `07-sse-resilience` | reconnect after the server drops the stream, and after a reload |
| `08-trade-validation` | insufficient cash and shares, unpriced ticker, evicted ticker, fill echo, full sell |

The resilience spec restarts the container (`E2E_CONTAINER`, set by
`run-e2e.sh`) because Chromium's offline emulation leaves an already-established
SSE connection open. It skips when that variable is absent.

## Writing assertions here

Price cells render `--` before mount and `0.00` between mount and the first SSE
flush, so `expect(cell).not.toHaveText("--")` passes vacuously twice over. Use
`expectPriced()` from `tests/helpers.ts`, which polls for a non-zero number.

`placeOrder()` returns the raw `/api/portfolio/trade` response, so spec 08 can
assert the server contract and the rendered UI independently.

The chat transcript is restored from `GET /api/chat/history` on mount, so
earlier turns re-render their own `chat-action` entries. Scope action
assertions to the reply under test via the `actions` locator that `chat()`
returns, never to a global `chat-action` count.

## Results

See `planning/handoffs/integration.md` for the latest run and the bug list.
