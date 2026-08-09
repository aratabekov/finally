"""LLM call: LiteLLM -> OpenRouter with Cerebras as the inference provider."""

from __future__ import annotations

from config import settings

from .mock import mock_reply
from .prompt import build_messages
from .schema import AssistantReply, parse_reply

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


async def _completion(**kwargs):
    # Imported lazily: litellm is slow to import and mock mode never needs it.
    from litellm import acompletion

    return await acompletion(**kwargs)


async def generate_reply(
    user_message: str, context: dict, history: list[dict]
) -> AssistantReply:
    """The assistant's structured reply for this turn."""
    if settings.llm_mock:
        return mock_reply(user_message, context)

    response = await _completion(
        model=MODEL,
        messages=build_messages(user_message, context, history),
        response_format=AssistantReply,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
        api_key=settings.openrouter_api_key or None,
    )
    return parse_reply(response.choices[0].message.content)
