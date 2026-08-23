from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Operator, QueryPlan
from .query import PropertySpec, QueryValidationError, normalize_lid, validate_plan


def _values(row: dict[str, Any], field: str) -> list[Any]:
    value = row.get(field)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class FrozenSnapshotExecutor:
    """Validate and evaluate supported query plans over immutable snapshot tables."""

    def __init__(self, snapshot: Path) -> None:
        self.snapshot = snapshot
        property_rows = json.loads((snapshot / "properties.json").read_text())
        self.properties = {
            str(row["property"]): PropertySpec(
                str(row["property"]), str(row.get("type")) if row.get("type") else None
            )
            for row in property_rows
            if row.get("property")
        }
        class_payload = json.loads((snapshot / "classes.json").read_text())
        self.product_classes = self._class_names(class_payload)
        self.rows: dict[str, list[dict[str, Any]]] = {
            "Product_Collection": json.loads(
                (snapshot / "archive/collections.json").read_text()
            )
        }
        self.relationships: dict[str, dict[str, list[str]]] = {}
        for edge in json.loads((snapshot / "relationships.json").read_text()):
            self.relationships.setdefault(str(edge["source"]), {}).setdefault(
                str(edge["relationship"]), []
            ).append(str(edge["target"]))
        context_rows: list[dict[str, Any]] = []
        for path in sorted((snapshot / "context").glob("*.json")):
            context_rows.extend(json.loads(path.read_text()))
        self.rows["Product_Context"] = context_rows

    @staticmethod
    def _class_names(payload: Any) -> set[str]:
        rows = payload if isinstance(payload, list) else payload.get("data", payload.get("classes", []))
        names: set[str] = set()
        for row in rows:
            if isinstance(row, str):
                names.add(row)
            elif isinstance(row, dict):
                value = row.get("title") or row.get("name") or row.get("class")
                if value:
                    names.add(str(value))
        # Snapshot tables are definitive even if the API class endpoint changes shape.
        names.update({"Product_Context", "Product_Collection"})
        return names

    def execute(self, plan: QueryPlan) -> list[str]:
        validate_plan(plan, self.properties, self.product_classes)
        if plan.terminal_product_class not in self.rows:
            raise QueryValidationError(
                f"product class is not available for frozen replay: {plan.terminal_product_class}"
            )
        matches = [row for row in self.rows[plan.terminal_product_class] if self._matches(row, plan)]
        identifiers = sorted(
            {normalize_lid(str(row["lid"])) for row in matches if row.get("lid")}
        )
        return identifiers[: plan.result_limit] if plan.result_limit is not None else identifiers

    def _matches(self, row: dict[str, Any], plan: QueryPlan) -> bool:
        for constraint in plan.constraints:
            values = _values(row, constraint.field)
            if constraint.field.startswith("ref_lid_") and row.get("lid"):
                role = constraint.field.removeprefix("ref_lid_")
                values = self.relationships.get(normalize_lid(str(row["lid"])), {}).get(
                    role, values
                )
            expected = constraint.value
            if constraint.operator == Operator.EQ and not any(str(v) == str(expected) for v in values):
                return False
            if constraint.operator == Operator.NE and any(str(v) == str(expected) for v in values):
                return False
            if constraint.operator == Operator.LIKE and not any(
                str(expected).lower() in str(v).lower() for v in values
            ):
                return False
            if constraint.operator in {Operator.GT, Operator.GE, Operator.LT, Operator.LE}:
                comparisons = {
                    Operator.GT: lambda value: value > expected,
                    Operator.GE: lambda value: value >= expected,
                    Operator.LT: lambda value: value < expected,
                    Operator.LE: lambda value: value <= expected,
                }
                if not any(comparisons[constraint.operator](value) for value in values):
                    return False
        return True
