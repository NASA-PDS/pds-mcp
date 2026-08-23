from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlencode

from .models import Constraint, QueryPlan


class QueryValidationError(ValueError):
    """Raised when a query plan is incompatible with a PDS schema snapshot."""


@dataclass(frozen=True)
class PropertySpec:
    name: str
    data_type: str | None = None


def normalize_lid(identifier: str) -> str:
    return identifier.split("::", 1)[0].strip()


def _literal(value: str | int | float) -> str:
    if isinstance(value, str):
        return f'"{value.replace(chr(34), chr(92) + chr(34))}"'
    return str(value)


def compile_expression(plan: QueryPlan) -> str:
    clauses = [f'product_class eq {_literal(plan.terminal_product_class)}']
    clauses.extend(
        f"{constraint.field} {constraint.operator.value} {_literal(constraint.value)}"
        for constraint in plan.constraints
    )
    return f"({' and '.join(f'({clause})' for clause in clauses)})"


def compile_request(plan: QueryPlan, base_url: str) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {"q": compile_expression(plan)}
    if plan.fields:
        params["fields"] = ",".join(plan.fields)
    if plan.sort:
        params["sort"] = ",".join(plan.sort)
    if plan.result_limit is not None:
        params["limit"] = plan.result_limit
    return f"{base_url.rstrip('/')}/products?{urlencode(params)}", params


def canonical_plan(plan: QueryPlan) -> str:
    payload = plan.model_dump(mode="json")
    payload["constraints"] = sorted(
        payload["constraints"],
        key=lambda item: (item["field"], item["operator"], str(item["value"])),
    )
    payload["fields"] = sorted(set(payload["fields"]))
    payload["sort"] = list(payload["sort"])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def plan_hash(plan: QueryPlan) -> str:
    return sha256(canonical_plan(plan).encode()).hexdigest()


def validate_plan(
    plan: QueryPlan,
    properties: Mapping[str, PropertySpec | Mapping[str, Any]],
    product_classes: set[str],
) -> None:
    if plan.terminal_product_class not in product_classes:
        raise QueryValidationError(
            f"unknown product class: {plan.terminal_product_class}"
        )
    known_fields = set(properties) | {"product_class", "lid", "title"}
    unknown = sorted(
        {c.field for c in plan.constraints}.union(plan.fields).difference(known_fields)
    )
    if unknown:
        raise QueryValidationError(f"unknown PDS properties: {', '.join(unknown)}")


def constraint(
    semantic_role: str, field: str, value: str | int | float, operator: str = "eq"
) -> Constraint:
    return Constraint(
        semantic_role=semantic_role, field=field, operator=operator, value=value
    )
