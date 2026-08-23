from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .benchmark import write_jsonl
from .models import (
    BenchmarkRecord,
    Difficulty,
    Provenance,
    QueryPlan,
    Track,
    Validation,
    classify_selectivity,
)
from .nlq import template_questions
from .query import compile_request, constraint, normalize_lid
from .sampler import ContextEntity, entities_from_records
from .schema import REFERENCE_FIELDS
from .snapshot import DEFAULT_API_BASE, stable_hash


def _load(path: Path) -> Any:
    return json.loads(path.read_text())


def _context(snapshot: Path) -> dict[str, dict[str, ContextEntity]]:
    result: dict[str, dict[str, ContextEntity]] = {}
    for path in sorted((snapshot / "context").glob("*.json")):
        role = path.stem
        result[role] = {
            entity.identifier: entity
            for entity in entities_from_records(role, _load(path))
        }
    return result


def _collection_edges(snapshot: Path) -> dict[str, dict[str, set[str]]]:
    result: dict[str, dict[str, set[str]]] = {}
    for edge in _load(snapshot / "relationships.json"):
        result.setdefault(edge["source"], {}).setdefault(edge["relationship"], set()).add(
            edge["target"]
        )
    return result


def _matching_collections(
    edges: dict[str, dict[str, set[str]]], selected: list[ContextEntity]
) -> list[str]:
    return sorted(
        collection
        for collection, relationships in edges.items()
        if all(entity.identifier in relationships.get(entity.role, set()) for entity in selected)
    )


def _record(
    identifier: str,
    question: str,
    variant: str,
    family: str,
    track: Track,
    plan: QueryPlan,
    context_ids: list[str],
    result_ids: list[str],
    snapshot_id: str,
    api_base: str,
) -> BenchmarkRecord:
    _, params = compile_request(plan, api_base)
    return BenchmarkRecord(
        id=identifier,
        question=question,
        question_variant=variant,
        query_family=family,
        track=track,
        intent={
            "terminal_product_class": plan.terminal_product_class,
            "semantic_roles": [item.semantic_role for item in plan.constraints],
        },
        reference_query_plan=plan,
        reference_api_request=params,
        required_context_ids=context_ids,
        relevant_product_ids=result_ids,
        difficulty=Difficulty(
            constraint_count=len(plan.constraints),
            reasoning_depth="multi_hop" if len(plan.constraints) > 1 else "single",
            selectivity=classify_selectivity(len(result_ids)),
        ),
        snapshot_version=snapshot_id,
        provenance=Provenance(
            generated_at=datetime.now(UTC),
            api_base_url=api_base,
            request_sha256=stable_hash(params),
            response_sha256=stable_hash(result_ids),
        ),
        validation=Validation(
            schema_valid=True,
            executed=False,
            fully_paginated=False,
            manually_reviewed=False,
            notes=[
                "Draft denotation generated from the fully paginated frozen collection inventory; execute the compiled query before acceptance."
            ],
        ),
    )


def generate_pilot(
    snapshot: Path, output: Path, size: int = 30, seed: int = 20260822
) -> list[BenchmarkRecord]:
    manifest = _load(snapshot / "manifest.json")
    snapshot_id = manifest["snapshot_id"]
    api_base = manifest.get("api_base_url", DEFAULT_API_BASE)
    contexts = _context(snapshot)
    edges = _collection_edges(snapshot)
    rng = random.Random(seed)
    records: list[BenchmarkRecord] = []

    # Six direct entity tasks ensure the entity-resolution layer is represented.
    context_candidates: list[ContextEntity] = []
    for role, count in (("investigation", 2), ("target", 2), ("instrument", 1), ("instrument_host", 1)):
        role_candidates = list(contexts.get(role, {}).values())
        rng.shuffle(role_candidates)
        context_candidates.extend(role_candidates[:count])
    for entity in context_candidates[: min(6, size)]:
        plan = QueryPlan(
            terminal_product_class="Product_Context",
            constraints=[constraint(entity.role, "lid", entity.identifier)],
            fields=["lid", "title"],
        )
        records.append(
            _record(
                f"pilot-{len(records) + 1:03d}",
                f"Find the PDS context record for {entity.title}.",
                "explicit",
                "direct_context_lookup",
                Track.CONTEXT_DISCOVERY,
                plan,
                [entity.identifier],
                [entity.identifier],
                snapshot_id,
                api_base,
            )
        )

    # Archive tasks are sampled from real collection relationships, so every
    # positive combination is executable and has known frozen denotation.
    collection_ids = list(edges)
    rng.shuffle(collection_ids)
    seen: set[tuple[tuple[str, str], ...]] = set()
    for collection_id in collection_ids:
        relationships = edges[collection_id]
        available = [
            contexts[role][value]
            for role in sorted(relationships)
            for value in sorted(relationships[role])
            if role in REFERENCE_FIELDS and value in contexts.get(role, {})
        ]
        rng.shuffle(available)
        for width in (3, 2, 1):
            selected: list[ContextEntity] = []
            used_roles: set[str] = set()
            for entity in available:
                if entity.role not in used_roles:
                    selected.append(entity)
                    used_roles.add(entity.role)
                if len(selected) == width:
                    break
            if len(selected) != width:
                continue
            key = tuple(sorted((entity.role, entity.identifier) for entity in selected))
            if key in seen:
                continue
            result_ids = _matching_collections(edges, selected)
            if not result_ids or len(result_ids) > 100:
                continue
            seen.add(key)
            plan = QueryPlan(
                terminal_product_class="Product_Collection",
                constraints=[
                    constraint(entity.role, REFERENCE_FIELDS[entity.role], entity.identifier)
                    for entity in selected
                ],
                fields=["lid", "title", *sorted(REFERENCE_FIELDS[e.role] for e in selected)],
            )
            questions = template_questions("collections", selected)
            variant = "natural" if len(records) % 2 else "explicit"
            records.append(
                _record(
                    f"pilot-{len(records) + 1:03d}",
                    questions[variant],
                    variant,
                    "combined_context_constraints" if width > 1 else f"archive_by_{selected[0].role}",
                    Track.ARCHIVE_RETRIEVAL,
                    plan,
                    [entity.identifier for entity in selected],
                    result_ids,
                    snapshot_id,
                    api_base,
                )
            )
            if len(records) >= size:
                write_jsonl(records, output)
                return records
    raise RuntimeError(f"could only generate {len(records)} of {size} requested pilot records")
