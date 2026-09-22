"""Temporary stand-in for llm/client.py's LLMClient, using Groq (OpenAI-
compatible API) instead of Claude. Exists only because no ANTHROPIC_API_KEY
was available to smoke-test the plan-generation pipeline end-to-end - the
approved architecture (build plan) still targets Claude as the production
planner LLM. Implements the same `call_tool()` interface as LLMClient so
llm/planner.py's `generate_plan(..., client=...)` accepts it as a drop-in.

Never hold or log the API key beyond what the `openai` SDK needs internally -
read it from an environment variable only, never hardcode it here.
"""
from __future__ import annotations

import json
import os

import openai
from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.llm.errors import LLMToolCallError

DEFAULT_MODEL = "openai/gpt-oss-120b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class ToolNotCalledError(LLMToolCallError):
    def __init__(self, tool_name: str, detail: str = ""):
        msg = f"Groq model did not call the required '{tool_name}' tool"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class GroqLLMClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        self._client = OpenAI(api_key=key, base_url=GROQ_BASE_URL)
        self._model = model

    @retry(
        retry=retry_if_exception_type((openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)),
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
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool_description,
                            "parameters": input_schema,
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": tool_name}},
            )
        except openai.BadRequestError as exc:
            # The provider rejected the tool call as not matching input_schema
            # (e.g. it used the wrong field names) - not retryable as-is.
            raise ToolNotCalledError(tool_name, detail=str(exc)) from exc

        message = response.choices[0].message
        if not message.tool_calls:
            raise ToolNotCalledError(tool_name)
        call = message.tool_calls[0]
        if call.function.name != tool_name:
            raise ToolNotCalledError(tool_name)
        try:
            return json.loads(call.function.arguments)
        except json.JSONDecodeError as exc:
            raise ToolNotCalledError(tool_name, detail="tool arguments were not valid JSON") from exc
