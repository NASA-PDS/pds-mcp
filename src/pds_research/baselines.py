from __future__ import annotations

import json
import re
from pathlib import Path

from .evaluation import Prediction
from .models import BenchmarkRecord, Track
from .runner import ExperimentRunner
from .sampler import ContextEntity, entities_from_records


STOPWORDS = {
    "a", "an", "and", "by", "data", "find", "for", "from", "have", "in",
    "match", "observations", "of", "on", "pds", "record", "the", "to", "what",
    "which", "with", "collections", "collection", "context", "targeting", "hosted",
    "collected",
}


def tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS and len(token) > 1
    }


def lexical_score(question: str, title: str) -> float:
    question_tokens = tokens(question)
    title_tokens = tokens(title)
    if not title_tokens:
        return 0.0
    normalized_title = " ".join(re.findall(r"[a-z0-9]+", title.lower()))
    normalized_question = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    if normalized_title and normalized_title in normalized_question:
        return 1.0
    return len(question_tokens & title_tokens) / len(title_tokens)


class DeterministicLexicalSystem:
    """Question-only lexical entity resolver plus native PDS graph traversal."""

    name = "deterministic_lexical_graph"

    def __init__(self, snapshot: Path, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.entities: dict[str, list[ContextEntity]] = {}
        for path in (snapshot / "context").glob("*.json"):
            self.entities[path.stem] = entities_from_records(
                path.stem, json.loads(path.read_text())
            )
        self.collections = {
            row["lid"]: row
            for row in json.loads((snapshot / "archive/collections.json").read_text())
            if row.get("lid")
        }
        self.edges: dict[str, dict[str, set[str]]] = {}
        for edge in json.loads((snapshot / "relationships.json").read_text()):
            self.edges.setdefault(edge["source"], {}).setdefault(
                edge["relationship"], set()
            ).add(edge["target"])

    def _rank_entities(self, question: str) -> list[tuple[float, ContextEntity]]:
        ranked = [
            (lexical_score(question, entity.title), entity)
            for role_entities in self.entities.values()
            for entity in role_entities
        ]
        return sorted(ranked, key=lambda item: (-item[0], item[1].identifier))

    def predict(self, record: BenchmarkRecord, repetition: int) -> Prediction:
        ranked = self._rank_entities(record.question)
        matches: dict[str, ContextEntity] = {}
        for score, entity in ranked:
            if score < self.threshold:
                break
            matches.setdefault(entity.role, entity)

        if record.track == Track.CONTEXT_DISCOVERY:
            context_ids = [
                entity.identifier for score, entity in ranked[:10] if score >= self.threshold
            ]
            return Prediction(
                id=record.id,
                system=self.name,
                repetition=repetition,
                predicted_product_ids=context_ids,
                predicted_context_ids=context_ids,
            )

        product_ids = sorted(
            collection_id
            for collection_id, relationships in self.edges.items()
            if matches
            and all(
                entity.identifier in relationships.get(role, set())
                for role, entity in matches.items()
                if role in relationships
            )
            and any(role in relationships for role in matches)
        )
        return Prediction(
            id=record.id,
            system=self.name,
            repetition=repetition,
            predicted_product_ids=product_ids,
            predicted_context_ids=[entity.identifier for entity in matches.values()],
        )


def run_deterministic_baseline(
    dataset: Path, snapshot: Path, output: Path
) -> int:
    from .benchmark import read_jsonl

    records = read_jsonl(dataset)
    emitted = ExperimentRunner(output).run(
        DeterministicLexicalSystem(snapshot), records, repetitions=1
    )
    return len(emitted)

