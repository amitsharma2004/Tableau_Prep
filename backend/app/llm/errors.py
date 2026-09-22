class LLMToolCallError(RuntimeError):
    """Raised by any LLMClient implementation (client.py, groq_client.py, ...)
    when the model/provider fails to produce a valid tool call - the tool
    wasn't called at all, or the provider's own schema validation rejected
    the arguments. llm/planner.py catches this alongside pydantic's
    ValidationError and wraps both into PlanGenerationError, so a malformed
    LLM response always surfaces as a clean 422, never a raw 500."""
