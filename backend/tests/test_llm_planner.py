import dataclasses

import pytest

from app.connectors.base import ColumnInfo, TableInfo
from app.llm.context import SampleContext, SchemaContext
from app.llm.planner import PlanGenerationError, generate_plan
from tests.test_plan_schema import VALID_PLAN


class FakeLLMClient:
    def __init__(self, response: dict):
        self._response = response
        self.last_call = None

    def call_tool(self, system, user_message, tool_name, tool_description, input_schema):
        self.last_call = {
            "system": system,
            "user_message": user_message,
            "tool_name": tool_name,
            "input_schema": input_schema,
        }
        return self._response


def _schema_and_samples():
    schema = SchemaContext(
        tables=[
            TableInfo(
                name="orders",
                schema="public",
                columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            )
        ]
    )
    samples = SampleContext(samples={"public.orders": [{"id": 1}]})
    return schema, samples


def test_generate_plan_returns_validated_plan_draft():
    client = FakeLLMClient(response=VALID_PLAN)
    schema, samples = _schema_and_samples()

    plan = generate_plan("join orders and customers", schema, samples, client=client)

    assert plan.output_alias == "result"
    assert client.last_call["tool_name"] == "propose_transformation_plan"


def test_generate_plan_sends_schema_and_request_in_prompt_not_raw_objects():
    client = FakeLLMClient(response=VALID_PLAN)
    schema, samples = _schema_and_samples()

    generate_plan("join orders and customers", schema, samples, client=client)

    assert "join orders and customers" in client.last_call["user_message"]
    assert "public.orders" in client.last_call["user_message"]


def test_malformed_tool_response_raises_plan_generation_error():
    client = FakeLLMClient(response={"summary": "incomplete"})  # missing required fields
    schema, samples = _schema_and_samples()

    with pytest.raises(PlanGenerationError):
        generate_plan("join orders and customers", schema, samples, client=client)


def test_schema_and_sample_context_have_no_credential_fields():
    # Structural guarantee: these dataclasses simply cannot carry a secret,
    # since generate_plan()'s signature only accepts these two types.
    schema_fields = {f.name for f in dataclasses.fields(SchemaContext)}
    sample_fields = {f.name for f in dataclasses.fields(SampleContext)}
    for forbidden in ("password", "secret", "credential", "token", "connection"):
        assert forbidden not in schema_fields
        assert forbidden not in sample_fields
