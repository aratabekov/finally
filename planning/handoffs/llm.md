# LLM / Chat Handoff — `backend/chat/`

`POST /api/chat` is complete: portfolio context -> LLM (LiteLLM -> OpenRouter ->
Cerebras, structured output) -> auto-executed trades and watchlist changes ->
persisted turn -> one JSON response. `LLM_MOCK=true` swaps the model for a
deterministic parser with zero network calls.

## Wiring (Backend API Engineer)

```python
from chat.routes import router as chat_router
app.include_router(chat_router)
```

The router is `APIRouter(prefix="/api")`. It reads
`request.app.state.price_cache` (needs `await cache.snapshot()`), so it only
works once the lifespan handler has set that up — which `main.py` already does.

## Endpoints

### `POST /api/chat`

Request:

```json
{ "message": "buy 5 AAPL" }
```

`{"content": "..."}` is accepted as an alias. An empty/whitespace message is a
`400`.

Response (always `200` once the message is non-empty — failed actions are
reported in the body, never as an HTTP error):

```json
{
  "message": "Executing buy 5 AAPL at the current market price.",
  "trades": [
    {
      "success": true,
      "error": null,
      "ticker": "AAPL",
      "side": "buy",
      "quantity": 5.0,
      "price": 190.0,
      "executed_at": "2026-08-09T12:00:00+00:00",
      "cash_balance": 9050.0,
      "total_value": 10000.0,
      "trade_id": "uuid"
    }
  ],
  "watchlist_changes": [
    { "ticker": "PYPL", "action": "add", "success": true, "changed": true, "error": null }
  ],
  "errors": []
}
```

- `trades[]` is `db.portfolio.TradeResult.as_dict()`. On a **failed** trade
  `success` is `false`, `error` holds the DB layer's message, and
  `ticker`/`side`/`quantity` are filled back in with what was attempted (the
  other fields stay `null`).
- `watchlist_changes[].changed` is `false` when the ticker was already in that
  state (add of an existing ticker, remove of an absent one). `success` is still
  `true` — it is idempotent, not an error.
- `errors[]` lists the failed trades' error strings.
- Every error in `errors[]` is also appended to `message` as a separate
  paragraph: `"\n\nCould not complete: {error}"`. The frontend can render
  `message` verbatim and still show failures.
- `{"trades", "watchlist_changes", "errors"}` is stored verbatim as the
  assistant message's `actions` JSON, so `GET /api/chat/history` replays inline
  confirmations.

### `GET /api/chat/history?limit=20`

Extra beyond PLAN §8, for restoring the chat panel on page load:
`{"messages": [{"role","content","actions","created_at"}, ...]}`, oldest first.
`actions` is `null` on user messages.

## Structured output schema (PLAN §9)

`chat.schema.AssistantReply` is passed straight to LiteLLM as `response_format`:

```json
{
  "message": "required conversational text",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}
```

`side` is `"buy"|"sell"`, `action` is `"add"|"remove"`, tickers are uppercased on
parse. Both arrays default to empty.

`parse_reply()` degrades in three steps: strict validation, then salvage the
`message` from any JSON object (dropping malformed actions rather than
half-executing them), then treat the raw text as the message. A blank or
non-object payload yields `"I could not read a usable response from the model.
Please try again."`

## LLM_MOCK behaviors (Integration Tester: assert against these exactly)

`LLM_MOCK=true` -> `chat.mock.mock_reply`. No network, no API key, no
randomness. Rules, applied independently and composably to the raw user message:

1. **Trade intent** — regex `\b(buy|sell)\s+(\d+(\.\d+)?)\s+(shares\s+(of\s+)?)?([a-z]{1,5})\b`,
   case-insensitive, every match becomes a trade. So `buy 5 AAPL`,
   `sell 2.5 shares of TSLA`, `sell 4 shares MSFT` all work.
   Message fragment: `"Executing buy 5 AAPL at the current market price."`
   (quantity formatted `%g`, ticker uppercased).
2. **Watchlist intent** — only when the message contains the word `watchlist`:
   regex `\b(add|remove)\s+([a-z]{1,5})\b`, every match becomes a change.
   Fragments: `"Adding PYPL to the watchlist."` /
   `"Removing AAPL from the watchlist."`
3. **Neither** — one canned analysis line built from live portfolio state:
   `"Mock analysis: total value $10,000.00, cash $10,000.00, 0 open positions, unrealized P&L $0.00."`
   (`$` amounts are `,.2f`.) On a fresh DB that string is exact.

Multiple fragments are joined with a single space, so
`"buy 2 TSLA and add PYPL to the watchlist"` returns both actions and the
message `"Executing buy 2 TSLA at the current market price. Adding PYPL to the watchlist."`

Mock trades go through the **real** `execute_trade`, so validation is real:
`buy 1000 AAPL` on a fresh $10k account returns `success: false` with
`"Insufficient cash: need $190,000.00, have $10,000.00"`, and the message gains
a `"Could not complete: ..."` paragraph. Same for an unpriced ticker
(`"No price available for ZZZZ"`).

## Live path

`openrouter/openai/gpt-oss-120b`, `extra_body={"provider": {"order": ["cerebras"]}}`,
`reasoning_effort="low"`, `response_format=AssistantReply`, via the **async**
`litellm.acompletion` (a sync call would block the event loop and stall the SSE
stream). `litellm` is imported lazily inside `chat.llm._completion`, so mock mode
never pays its ~1s import cost.

Verified live against the real API on 2026-08-09: analysis questions return no
actions, `"buy 5 shares of AAPL"` returns a `trades` entry, `"add PYPL to my
watchlist"` returns a `watchlist_changes` entry. Structured outputs are honored
by this model/provider combination.

## Files

```
chat/schema.py    ChatRequest, AssistantReply + tolerant parse_reply
chat/context.py   build_context(prices) / format_context — portfolio + watchlist
chat/prompt.py    SYSTEM_PROMPT + build_messages (system, context, history, new)
chat/mock.py      deterministic LLM_MOCK replies
chat/llm.py       generate_reply — mock dispatch or Cerebras call
chat/actions.py   apply_actions (auto-execution) + compose_message
chat/routes.py    POST /api/chat, GET /api/chat/history
tests/test_chat.py
```

Dependency added: `litellm`, `pydantic` in `backend/pyproject.toml` + `uv.lock`.

## Tests

```bash
cd backend && uv run pytest -q          # 120 passed (21 of them chat)
```

Deterministic, no network, no API key. `DB_PATH` is monkeypatched to a tmp dir
and the tests build their own `FastAPI()` app with a fake price cache, so they do
not depend on `main.py` or on the Backend API Engineer's work landing first.
