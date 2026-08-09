"""POST /api/chat — one complete assistant turn (PLAN.md section 9).

Load portfolio context and history, call the LLM for a structured reply,
auto-execute its trades and watchlist changes, persist both sides of the turn,
and return the whole thing in one JSON response. No token streaming.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from db.chat import add_chat_message, get_recent_chat
from db.connection import DEFAULT_USER_ID

from .actions import apply_actions, compose_message
from .context import build_context
from .llm import generate_reply
from .schema import ChatRequest

router = APIRouter(prefix="/api")

HISTORY_LIMIT = 20


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    user_message = payload.text
    if not user_message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    prices = await request.app.state.price_cache.snapshot()
    context = build_context(prices, DEFAULT_USER_ID)
    # Read history before storing the new message so it is not duplicated.
    history = get_recent_chat(DEFAULT_USER_ID, limit=HISTORY_LIMIT)
    add_chat_message(DEFAULT_USER_ID, "user", user_message)

    reply = await generate_reply(user_message, context, history)
    actions = apply_actions(reply, prices, DEFAULT_USER_ID)
    message = compose_message(reply.message, actions["errors"])
    add_chat_message(DEFAULT_USER_ID, "assistant", message, actions=actions)

    return {"message": message, **actions}


@router.get("/chat/history")
async def chat_history(limit: int = HISTORY_LIMIT):
    """Past conversation, oldest first — lets the frontend restore the panel."""
    return {"messages": get_recent_chat(DEFAULT_USER_ID, limit=max(1, limit))}
