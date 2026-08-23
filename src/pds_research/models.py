from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Operator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    LIKE = "like"


class Track(StrEnum):
    CONTEXT_DISCOVERY = "context_discovery"
    ARCHIVE_RETRIEVAL = "archive_retrieval"


class Selectivity(StrEnum):
    EMPTY = "empty"
    SINGLETON = "singleton"
    SMALL = "small"
    MEDIUM = "medium"
    BROAD = "broad"


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic_role: str = Field(min_length=1)
    field: str = Field(min_length=1)
    operator: Operator
    value: str | int | float


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terminal_product_class: str = Field(min_length=1)
    constraints: list[Constraint] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=lambda: ["lid", "title"])
    sort: list[str] = Field(default_factory=list)
    result_limit: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def unique_constraints(self) -> "QueryPlan":
        keys = [(c.field, c.operator, str(c.value)) for c in self.constraints]
        if len(keys) != len(set(keys)):
            raise ValueError("query plan contains duplicate constraints")
        return self


class Difficulty(BaseModel):
    constraint_count: int = Field(ge=0)
    reasoning_depth: str
    selectivity: Selectivity


class Provenance(BaseModel):
    generated_at: datetime
    api_base_url: str
    api_version: str = "1"
    request_sha256: str
    response_sha256: str


class Validation(BaseModel):
    schema_valid: bool
    executed: bool
    fully_paginated: bool
    manually_reviewed: bool = False
    notes: list[str] = Field(default_factory=list)


class BenchmarkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    question_variant: str
    query_family: str
    track: Track
    intent: dict[str, Any]
    reference_query_plan: QueryPlan
    reference_api_request: dict[str, Any]
    required_context_ids: list[str]
    relevant_product_ids: list[str]
    difficulty: Difficulty
    snapshot_version: str
    provenance: Provenance
    validation: Validation


class SnapshotManifest(BaseModel):
    schema_version: str = "1.0"
    snapshot_id: str
    created_at: datetime
    api_base_url: str
    api_version: str = "1"
    requests: list[dict[str, Any]] = Field(default_factory=list)


def classify_selectivity(count: int) -> Selectivity:
    if count == 0:
        return Selectivity.EMPTY
    if count == 1:
        return Selectivity.SINGLETON
    if count <= 10:
        return Selectivity.SMALL
    if count <= 100:
        return Selectivity.MEDIUM
    return Selectivity.BROAD

