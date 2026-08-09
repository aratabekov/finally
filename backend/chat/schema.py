"""Request body and the LLM structured-output schema (PLAN.md section 9)."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

FALLBACK_MESSAGE = "I could not read a usable response from the model. Please try again."


class ChatRequest(BaseModel):
    """POST /api/chat body. `message` is canonical; `content` is accepted too."""

    message: str | None = None
    content: str | None = None

    @property
    def text(self) -> str:
        return (self.message or self.content or "").strip()


class TradeInstruction(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.strip().upper()


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.strip().upper()


class AssistantReply(BaseModel):
    """What the LLM must return. `message` is the only required field."""

    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


def parse_reply(raw: str | None) -> AssistantReply:
    """Parse the model's structured output, degrading gracefully.

    A malformed `trades`/`watchlist_changes` payload is dropped rather than
    half-executed: we keep the conversational message and run no actions.
    """
    try:
        return AssistantReply.model_validate_json(raw)
    except (ValidationError, TypeError):
        pass

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return AssistantReply(message=(raw or "").strip() or FALLBACK_MESSAGE)

    if isinstance(data, dict):
        message = str(data.get("message") or "").strip()
        return AssistantReply(message=message or FALLBACK_MESSAGE)
    return AssistantReply(message=FALLBACK_MESSAGE)
