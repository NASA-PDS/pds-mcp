from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx


class BudgetExceededError(RuntimeError):
    """Raised before a request that would exceed the configured run ceiling."""


def strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a model schema to the closed, fully-required OpenAI subset."""
    normalized = json.loads(json.dumps(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties)
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(normalized)
    return normalized


@dataclass(frozen=True)
class TokenPrices:
    """Explicit USD prices per million tokens; freeze these with every run."""

    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class StructuredModelResult:
    value: dict[str, Any]
    response_id: str
    model: str
    usage: ModelUsage
    raw_status: str


class OpenAIResponsesBackend:
    """Small, testable adapter for schema-constrained Responses API calls.

    The adapter deliberately does not choose a model or pricing assumptions.
    Both are experimental controls and must be supplied by the frozen protocol.
    """

    _SNAPSHOT_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prices: TokenPrices,
        max_requests: int,
        max_cost_usd: float,
        client: httpx.Client | None = None,
        allow_unpinned_model: bool = False,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        if max_requests < 1 or max_cost_usd < 0:
            raise ValueError("budget limits must be non-negative and allow a request")
        if not allow_unpinned_model and not self._SNAPSHOT_SUFFIX.search(model):
            raise ValueError("model must be a dated snapshot (or explicitly overridden)")
        self.model = model
        self.prices = prices
        self.max_requests = max_requests
        self.max_cost_usd = max_cost_usd
        self.requests_made = 0
        self.cost_usd = 0.0
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "OpenAIResponsesBackend":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _estimate(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.prices.input_per_million
            + output_tokens * self.prices.output_per_million
        ) / 1_000_000

    def _reserve(self, input_text: str, max_output_tokens: int) -> None:
        if self.requests_made >= self.max_requests:
            raise BudgetExceededError("request ceiling reached")
        # Conservative, deterministic preflight estimate; actual usage replaces it.
        estimated_input = max(1, (len(input_text) + 3) // 4)
        upper_bound = self._estimate(estimated_input, max_output_tokens)
        if self.cost_usd + upper_bound > self.max_cost_usd:
            raise BudgetExceededError("estimated request would exceed cost ceiling")

    def generate_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        max_output_tokens: int = 1200,
        seed: int | None = None,
    ) -> StructuredModelResult:
        self._reserve(instructions + input_text, max_output_tokens)
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": strict_json_schema(schema),
                }
            },
        }
        if seed is not None:
            # Kept out of the wire request: Responses does not currently expose a
            # universal seed control. It remains logged by the experiment runner.
            body["metadata"] = {"experiment_seed": str(seed)}

        response = self.client.post("/responses", json=body)
        response.raise_for_status()
        payload = response.json()
        self.requests_made += 1

        output_text = payload.get("output_text")
        if output_text is None:
            output_text = self._extract_output_text(payload)
        value = json.loads(output_text)
        if not isinstance(value, dict):
            raise ValueError("structured response must decode to a JSON object")

        raw_usage = payload.get("usage") or {}
        input_tokens = int(raw_usage.get("input_tokens", 0))
        output_tokens = int(raw_usage.get("output_tokens", 0))
        cost = self._estimate(input_tokens, output_tokens)
        self.cost_usd += cost
        return StructuredModelResult(
            value=value,
            response_id=str(payload.get("id", "")),
            model=str(payload.get("model", self.model)),
            usage=ModelUsage(input_tokens, output_tokens, cost),
            raw_status=str(payload.get("status", "unknown")),
        )

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content["text"])
        raise ValueError("response contained no output_text")
