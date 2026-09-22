"""Thin wrapper around the Anthropic SDK. Isolated here so planner.py never
touches the SDK directly, and so tests can substitute a fake client without
monkeypatching the anthropic module itself."""
from __future__ import annotations

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.llm.errors import LLMToolCallError

MODEL = "claude-sonnet-5"


class ToolNotCalledError(LLMToolCallError):
    def __init__(self, tool_name: str):
        super().__init__(f"Claude did not call the required '{tool_name}' tool")


class LLMClient:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @retry(
        retry=retry_if_exception_type(
            (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def call_tool(
        self,
        system: str,
        user_message: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
    ) -> dict:
        try:
            response = self._client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user_message}],
                tools=[{"name": tool_name, "description": tool_description, "input_schema": input_schema}],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except anthropic.APIStatusError as exc:
            # e.g. the model's tool call didn't validate against input_schema,
            # or another non-retryable 4xx - never re-raise as a raw SDK
            # exception, planner.py only knows how to catch LLMToolCallError.
            raise ToolNotCalledError(tool_name) from exc

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        raise ToolNotCalledError(tool_name)
