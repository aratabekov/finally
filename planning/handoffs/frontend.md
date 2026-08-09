# Frontend handoff

Next.js 16 (App Router, TypeScript) static export, Tailwind CSS 4, Recharts.
Everything lives in `frontend/`. No backend files were touched.

## Build and run

```bash
cd frontend
npm install
npm run build      # -> frontend/out/   (static export, this is what FastAPI serves)
npm run lint       # eslint, clean
npm test           # vitest run, 24 tests
npm run dev        # dev server on :3000, proxies /api -> http://127.0.0.1:8000
```

- **Static export output: `frontend/out/`** (`index.html`, `404.html`, `_next/`).
  Production builds set `output: "export"`; there is no server runtime.
- `npm run dev` is the one exception: in development `next.config.ts` skips the
  export and rewrites `/api/*` to the local backend so the two can run on
  separate ports. Override the target with `BACKEND_ORIGIN`.

### For DevOps

Copy `frontend/out/` into whatever directory `main.py` mounts (per TEAM.md,
`backend/static/`). Everything is same-origin `/api/*`, so no env var, no base
URL, no CORS.

**Build-stage network requirement:** fonts come from `next/font/google`
(IBM Plex Mono + Archivo). Next downloads and self-hosts them at build time, so
the Docker build stage needs network access (it already does, for `npm ci`), but
the running container does not.

## Layout

Fixed-viewport terminal, no page scroll; each panel scrolls internally.

```
header: FINALLY | net liq | unrealized P&L | cash | clock | status dot
[ watchlist 280px ][ chart / exposure + equity / positions ][ Ally chat 360px ]
order rail: SYMBOL | QUANTITY | ESTIMATED | BUY | SELL | last fill
```

Collapsing the chat (`chat-collapse`) shrinks the third column to a vertical
`ALLY` strip (`chat-expand`).

## data-testid map

| testid | Element |
|---|---|
| `portfolio-total` | Header net liquidation (live, cash + positions at live prices) |
| `portfolio-pl` | Header unrealized P&L, dollars and percent |
| `cash-balance` | Header cash |
| `clock` | Header wall clock |
| `connection-dot` | Status dot; `data-status` is `connected` / `reconnecting` / `disconnected` |
| `watchlist` | Watchlist panel |
| `watchlist-row-{TICKER}` | One row; `data-selected="true"` on the selected row; click selects |
| `price-{TICKER}` | Price cell; `data-flash` is `up` / `down` / `none`, class `flash-up` / `flash-down` |
| `change-{TICKER}` | Change percent vs the prior session close |
| `watchlist-remove-{TICKER}` | Row remove button (visible on hover, always in the DOM) |
| `watchlist-input` / `watchlist-add` | Add-symbol field and button |
| `watchlist-error` | Message shown when an add is rejected |
| `main-chart` | Selected-ticker chart panel (panel title is the ticker) |
| `main-chart-price` | Last price in the chart header |
| `range-LIVE` / `range-30D` / `range-90D` | Timeframe buttons; 90D is the default |
| `heatmap` | Exposure treemap panel |
| `pnl-chart` | Equity curve panel |
| `positions` / `positions-table` | Positions panel and table |
| `position-row-{TICKER}` | Position row; click selects the ticker |
| `position-price-{TICKER}` | Live price cell (flashes like the watchlist) |
| `position-pl-{TICKER}` | Unrealized P&L cell |
| `trade-bar` | Order rail |
| `trade-ticker` / `trade-quantity` | Order inputs (symbol tracks the selected ticker) |
| `trade-estimate` | Quantity times live price |
| `trade-buy` / `trade-sell` | Submit buttons; no confirmation dialog |
| `trade-status` | Fill echo `HH:MM:SS BUY 3 NVDA at $127.23`, or the rejection reason |
| `chat-panel` | Assistant panel |
| `chat-messages` | Scrolling transcript |
| `chat-message-user` / `chat-message-assistant` | One message (multiple matches) |
| `chat-action` | One executed or rejected action, rendered under the reply |
| `chat-loading` | Present only while a reply is in flight |
| `chat-input` / `chat-send` | Composer |
| `chat-collapse` / `chat-expand` | Sidebar toggles |

The transcript is restored from `GET /api/chat/history` on mount, so a reload
resumes the conversation with its inline actions intact. The client greeting
stays at the top; anything typed while that request is still in flight is kept.

Note for E2E: the terminal renders immediately and fills in as data arrives, so
assert on a testid appearing rather than on a fixed load order. Prices only
flash while ticks are arriving.

## What it does with each endpoint

| Call | When |
|---|---|
| `GET /api/stream/prices` (SSE, EventSource) | On mount. Ticks are buffered and flushed every 250ms; each ticker keeps a rolling 240-point series for its sparkline. |
| `GET /api/portfolio` | On mount, every 15s, and after every trade or chat action. |
| `GET /api/portfolio/history` | On mount and every 30s (matches the backend snapshot cadence). |
| `GET /api/watchlist` | On mount, every 15s, after add/remove. |
| `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}` | Add-symbol form and row remove button. |
| `POST /api/portfolio/trade` | Buy/Sell in the order rail. Body `{ticker, quantity, side}`. The rail echoes the `price` from the response, never the client's last-seen tape price. |
| `GET /api/history/{ticker}?days=90` | When the chart's ticker changes. |
| `GET /api/history/{ticker}?days=5` | Once per ticker, for the prior-session close behind the CHG column. |
| `POST /api/chat` | Chat send. Body `{message}`. |
| `GET /api/chat/history?limit=20` | On chat mount, to restore the transcript across reloads. Stored `actions` replay as the same inline confirmations. |

## Assumptions about the API (please confirm or correct)

These are the places PLAN.md section 8 left room, and what the client does:

1. **`GET /api/portfolio` cash field.** TEAM.md shows `compute_valuation`
   returning `cash`, while PLAN's schema calls the column `cash_balance`. The
   client reads `cash` **or** `cash_balance`, and derives `total_value` from
   cash plus market value if the response omits it.
2. **Position fields.** Reads `current_price` (or `price`), `market_value`,
   `unrealized_pl` (or `unrealized_pnl`), `pct_change`. Any of the derived ones
   may be omitted and the client computes them from `quantity` / `avg_cost`.
   The tape always wins for display: positions are revalued against the live
   SSE price, so a stale REST price never shows.
3. **`GET /api/portfolio/history`** may be a bare array or `{snapshots: [...]}`;
   rows need `total_value` and `recorded_at`.
4. **`GET /api/watchlist`** may be `["AAPL", ...]`, `[{ticker, price}, ...]`, or
   `{tickers: [...]}`. Only the ticker is used; prices come from the stream.
5. **`POST /api/chat` response** is read as
   `{message, trades: [{ticker, side, quantity, error?}], watchlist_changes: [{ticker, action, error?}]}`.
   An `error` (or `detail`) on an entry renders it as a rejected action in red;
   otherwise it renders as executed. **If a trade fails validation, please keep
   the failed entry in the array with an error string** rather than dropping it,
   so the user sees what was refused.
6. **Errors** are read from a non-2xx body as `detail` **or** `error`, so both
   envelopes in use work: FastAPI's `{"detail": "..."}` (watchlist, chat) and
   `TradeResult`'s `{"success": false, "error": "..."}` (trade). That string is
   shown verbatim in the order rail or the add-symbol field. Resolved BUG-1;
   the backend envelope was left unchanged.
7. **`Bar.t` is Unix milliseconds** (confirmed against `backend/CLAUDE.md`), and
   `GET /api/history` ends its last bar at the live price. The CHG column uses
   the second-to-last bar as the prior session close, which depends on that
   behavior holding.

## Tests

`frontend/tests/`, run with `npm test` (Vitest + React Testing Library, jsdom).
31 tests: price flash up/down/unchanged and its 500ms decay, watchlist render
and CRUD and error surfacing, position revaluation math against the live tape,
chat transcript, loading state, inline actions, transport failure, and history
restore, plus the response readers for every ambiguity listed above, both
rejection envelopes, and the echoed fill price.

## Notes

- Colors are Tailwind 4 `@theme` tokens in `app/globals.css`: `accent` #ecad0a,
  `blue` #209dd7, `purple` #753991 (both submit buttons), `up` #2ecc8f,
  `down` #f2545b, over `bg` #0b0e14 / `panel` #11151e / `panel-hi` #1a1a2e.
- Type is monospace-first (IBM Plex Mono) for all data and chrome; Archivo is
  used only for assistant prose, so the AI reads as the one human voice.
- Sparklines are hand-rolled SVG rather than a chart component, since ten of
  them redraw several times a second.
- `prefers-reduced-motion` disables the flash and the pulsing status dot.
