from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable

from .models import QueryPlan
from .query import constraint
from .schema import REFERENCE_FIELDS


@dataclass(frozen=True)
class ContextEntity:
    role: str
    identifier: str
    title: str
    aliases: tuple[str, ...] = ()
    description: str = ""


def entities_from_records(role: str, records: Iterable[dict[str, Any]]) -> list[ContextEntity]:
    entities: list[ContextEntity] = []
    for record in records:
        identifier = record.get("lid") or record.get("id")
        title = record.get("title")
        if not identifier or not title:
            continue
        aliases = record.get("pds:Alias.pds:alternate_title", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        entities.append(
            ContextEntity(
                role=role,
                identifier=str(identifier).split("::", 1)[0],
                title=str(title),
                aliases=tuple(str(value) for value in aliases),
                description=str(record.get("description", "")),
            )
        )
    return entities


class QuerySampler:
    def __init__(self, seed: int = 20260822) -> None:
        self.random = random.Random(seed)

    def context_lookup(self, entity: ContextEntity) -> QueryPlan:
        prefix = entity.identifier.rsplit(":", 1)[0] + ":*"
        return QueryPlan(
            terminal_product_class="Product_Context",
            constraints=[constraint(entity.role, "lid", prefix, "like")],
            fields=["lid", "title"],
        )

    def archive_by_context(
        self, entities: Iterable[ContextEntity], product_class: str = "Product_Collection"
    ) -> QueryPlan:
        selected = list(entities)
        return QueryPlan(
            terminal_product_class=product_class,
            constraints=[
                constraint(entity.role, REFERENCE_FIELDS[entity.role], entity.identifier)
                for entity in selected
                if entity.role in REFERENCE_FIELDS
            ],
            fields=["lid", "title", *sorted({REFERENCE_FIELDS[e.role] for e in selected if e.role in REFERENCE_FIELDS})],
        )

    def candidate_combinations(
        self, pools: dict[str, list[ContextEntity]], maximum_constraints: int = 3
    ) -> Iterable[list[ContextEntity]]:
        roles = [role for role in sorted(pools) if role in REFERENCE_FIELDS and pools[role]]
        for width in range(1, min(maximum_constraints, len(roles)) + 1):
            for chosen_roles in combinations(roles, width):
                yield [self.random.choice(pools[role]) for role in chosen_roles]

