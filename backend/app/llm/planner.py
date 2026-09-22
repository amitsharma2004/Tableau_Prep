"""NL request -> structured PlanDraft. This is the only entry point the rest
of the app should call - it never sees a Connection or secret, only the
credential-free SchemaContext/SampleContext DTOs (see llm/context.py)."""
from __future__ import annotations

from pydantic import ValidationError

from app.core.errors import DomainError
from app.llm.client import LLMClient
from app.llm.context import SampleContext, SchemaContext
from app.llm.errors import LLMToolCallError
from app.llm.plan_schema import PlanDraft
from app.llm.prompts import SYSTEM_PROMPT, build_user_message

TOOL_NAME = "propose_transformation_plan"
TOOL_DESCRIPTION = "Propose a structured data transformation plan for the user's request."


class PlanGenerationError(DomainError):
    """Raised when Claude's response cannot be parsed into a valid PlanDraft."""


def generate_plan(
    nl_request: str,
    schema: SchemaContext,
    samples: SampleContext,
    client: LLMClient | None = None,
    existing_plan: PlanDraft | None = None,
) -> PlanDraft:
    from app.config import settings
    from app.llm.groq_client import GroqLLMClient
    from app.llm.heuristic_planner import generate_heuristic_plan

    existing_plan_json = existing_plan.model_dump_json(indent=2) if existing_plan else None

    # If an explicit client is provided (e.g. in tests), use it directly
    if client is not None:
        user_message = build_user_message(nl_request, schema, samples, existing_plan_json=existing_plan_json)
        try:
            raw_input = client.call_tool(
                system=SYSTEM_PROMPT,
                user_message=user_message,
                tool_name=TOOL_NAME,
                tool_description=TOOL_DESCRIPTION,
                input_schema=PlanDraft.model_json_schema(),
            )
        except LLMToolCallError as exc:
            raise PlanGenerationError(f"The LLM failed to produce a usable plan: {exc}") from exc
        try:
            return PlanDraft.model_validate(raw_input)
        except ValidationError as exc:
            raise PlanGenerationError(
                f"The LLM returned a plan that failed validation against the plan schema: {exc}"
            ) from exc

    # 1. Use Groq if GROQ_API_KEY is available
    if settings.groq_api_key:
        try:
            groq_c = GroqLLMClient(api_key=settings.groq_api_key, model=settings.groq_model)
            user_message = build_user_message(nl_request, schema, samples, existing_plan_json=existing_plan_json)
            raw_input = groq_c.call_tool(
                system=SYSTEM_PROMPT,
                user_message=user_message,
                tool_name=TOOL_NAME,
                tool_description=TOOL_DESCRIPTION,
                input_schema=PlanDraft.model_json_schema(),
            )
            return PlanDraft.model_validate(raw_input)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Groq call failed, falling back: %s", exc)

    # 2. Use Anthropic if valid key exists
    if settings.anthropic_api_key and "mock" not in settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-..."):
        try:
            client = client or LLMClient()
            user_message = build_user_message(nl_request, schema, samples)
            raw_input = client.call_tool(
                system=SYSTEM_PROMPT,
                user_message=user_message,
                tool_name=TOOL_NAME,
                tool_description=TOOL_DESCRIPTION,
                input_schema=PlanDraft.model_json_schema(),
            )
            return PlanDraft.model_validate(raw_input)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Anthropic call failed, falling back: %s", exc)

    # 3. Fallback to smart heuristic planner
    return generate_heuristic_plan(nl_request, schema, samples)

    try:
        return PlanDraft.model_validate(raw_input)
    except ValidationError as exc:
        raise PlanGenerationError(
            f"The LLM returned a plan that failed validation against the plan schema: {exc}"
        ) from exc
