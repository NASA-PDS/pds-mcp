from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .baselines import lexical_score
from .evaluation import Prediction
from .frozen import FrozenSnapshotExecutor
from .model_backends import StructuredModelResult
from .models import BenchmarkRecord, QueryPlan
from .sampler import ContextEntity, entities_from_records


class StructuredBackend(Protocol):
    def generate_structured(self, **kwargs: object) -> StructuredModelResult: ...


class SinglePassStructuredQuerySystem:
    """One model call from NLQ plus retrieved candidates to a typed query plan."""

    name = "single_pass_structured_query"

    def __init__(self, snapshot: Path, backend: StructuredBackend, candidate_count: int = 20) -> None:
        self.backend = backend
        self.executor = FrozenSnapshotExecutor(snapshot)
        self.candidate_count = candidate_count
        self.entities: list[ContextEntity] = []
        for path in sorted((snapshot / "context").glob("*.json")):
            self.entities.extend(entities_from_records(path.stem, json.loads(path.read_text())))

    def _candidates(self, question: str) -> list[dict[str, str]]:
        ranked = sorted(
            self.entities,
            key=lambda entity: (-lexical_score(question, entity.title), entity.identifier),
        )[: self.candidate_count]
        return [
            {"role": entity.role, "title": entity.title, "identifier": entity.identifier}
            for entity in ranked
        ]

    def predict(self, record: BenchmarkRecord, repetition: int) -> Prediction:
        candidates = self._candidates(record.question)
        result = self.backend.generate_structured(
            instructions=(
                "Translate the user's PDS request into one typed query plan. Use only supplied "
                "context identifiers. Search Product_Context for a context lookup and "
                "Product_Collection for archive retrieval. Reference fields are "
                "ref_lid_investigation, ref_lid_target, ref_lid_instrument, and "
                "ref_lid_instrument_host. Return no prose."
            ),
            input_text=json.dumps(
                {"question": record.question, "context_candidates": candidates},
                sort_keys=True,
            ),
            schema_name="pds_query_plan",
            schema=QueryPlan.model_json_schema(),
            max_output_tokens=1200,
            seed=repetition,
        )
        plan = QueryPlan.model_validate(result.value)
        identifiers = self.executor.execute(plan)
        context_ids = sorted(
            {
                str(constraint.value)
                for constraint in plan.constraints
                if constraint.semantic_role in {
                    "investigation", "target", "instrument", "instrument_host", "facility"
                }
                and str(constraint.value).startswith("urn:nasa:pds:context:")
            }
        )
        return Prediction(
            id=record.id,
            system=self.name,
            repetition=repetition,
            predicted_product_ids=identifiers,
            predicted_context_ids=context_ids,
            canonical_query_valid=True,
            tool_calls=0,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            estimated_cost_usd=result.usage.estimated_cost_usd,
            predicted_query_plan=plan.model_dump(mode="json"),
        )
