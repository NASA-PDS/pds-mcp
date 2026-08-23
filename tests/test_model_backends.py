import json

import httpx
import pytest

from pds_research.model_backends import (
    BudgetExceededError,
    OpenAIResponsesBackend,
    TokenPrices,
    strict_json_schema,
)


def make_client(captured: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "model": "gpt-test-2026-08-01",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"ok":true}'}],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 20},
            },
            request=request,
        )

    return httpx.Client(base_url="https://api.openai.com/v1", transport=httpx.MockTransport(handler))


def test_structured_response_and_usage_are_logged() -> None:
    captured: list[dict] = []
    backend = OpenAIResponsesBackend(
        api_key="test-only",
        model="gpt-test-2026-08-01",
        prices=TokenPrices(input_per_million=1.0, output_per_million=10.0),
        max_requests=2,
        max_cost_usd=1.0,
        client=make_client(captured),
    )
    result = backend.generate_structured(
        instructions="Return a plan.",
        input_text="Find lunar data.",
        schema_name="query_plan",
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        seed=7,
    )

    assert result.value == {"ok": True}
    assert result.usage.estimated_cost_usd == pytest.approx(0.0003)
    assert captured[0]["store"] is False
    assert captured[0]["text"]["format"]["strict"] is True
    assert captured[0]["metadata"] == {"experiment_seed": "7"}


def test_request_and_cost_guards_prevent_network_calls() -> None:
    captured: list[dict] = []
    backend = OpenAIResponsesBackend(
        api_key="test-only",
        model="gpt-test-2026-08-01",
        prices=TokenPrices(input_per_million=1.0, output_per_million=10.0),
        max_requests=1,
        max_cost_usd=0.00001,
        client=make_client(captured),
    )
    with pytest.raises(BudgetExceededError):
        backend.generate_structured(
            instructions="x",
            input_text="y",
            schema_name="x",
            schema={"type": "object"},
            max_output_tokens=100,
        )
    assert captured == []


def test_unpinned_model_is_rejected_by_default() -> None:
    with pytest.raises(ValueError, match="dated snapshot"):
        OpenAIResponsesBackend(
            api_key="test-only",
            model="latest-model-alias",
            prices=TokenPrices(1, 1),
            max_requests=1,
            max_cost_usd=1,
        )


def test_strict_schema_closes_objects_and_requires_defaulted_fields() -> None:
    schema = strict_json_schema({
        "type": "object",
        "properties": {
            "constraints": {"type": "array", "items": {"type": "object", "properties": {"x": {"type": "string"}}}},
            "sort": {"type": "array", "items": {"type": "string"}},
        },
    })
    assert schema["required"] == ["constraints", "sort"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["constraints"]["items"]["required"] == ["x"]
