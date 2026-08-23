from datetime import UTC, datetime

import pytest

from pds_research.benchmark import assert_no_entity_leakage
from pds_research.models import (
    BenchmarkRecord,
    Difficulty,
    Provenance,
    QueryPlan,
    Selectivity,
    Track,
    Validation,
)


def record(identifier: str, entity: str) -> BenchmarkRecord:
    return BenchmarkRecord(
        id=identifier,
        question="Find a collection",
        question_variant="explicit",
        query_family="archive_by_target",
        track=Track.ARCHIVE_RETRIEVAL,
        intent={},
        reference_query_plan=QueryPlan(terminal_product_class="Product_Collection"),
        reference_api_request={},
        required_context_ids=[entity],
        relevant_product_ids=[],
        difficulty=Difficulty(constraint_count=1, reasoning_depth="single", selectivity=Selectivity.EMPTY),
        snapshot_version="test",
        provenance=Provenance(
            generated_at=datetime.now(UTC),
            api_base_url="https://example.test",
            request_sha256="a",
            response_sha256="b",
        ),
        validation=Validation(schema_valid=True, executed=True, fully_paginated=True),
    )


def test_entity_leakage_is_rejected() -> None:
    with pytest.raises(ValueError):
        assert_no_entity_leakage({"train": [record("a", "moon")], "test": [record("b", "moon")]})
