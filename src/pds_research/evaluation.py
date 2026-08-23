from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Callable, Sequence
from typing import Any

from .metrics import score_retrieval
from .models import BenchmarkRecord


@dataclass(frozen=True)
class Prediction:
    id: str
    system: str
    repetition: int
    predicted_product_ids: list[str]
    predicted_context_ids: list[str]
    canonical_query_valid: bool | None = None
    tool_calls: int = 0
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    predicted_query_plan: dict[str, Any] | None = None
    failure: str | None = None


def score_predictions(
    records: Sequence[BenchmarkRecord], predictions: Sequence[Prediction]
) -> list[dict[str, object]]:
    by_id = {record.id: record for record in records}
    rows: list[dict[str, object]] = []
    for prediction in predictions:
        record = by_id[prediction.id]
        terminal = score_retrieval(
            prediction.predicted_product_ids, record.relevant_product_ids
        )
        context = score_retrieval(
            prediction.predicted_context_ids, record.required_context_ids
        )
        rows.append(
            {
                **asdict(prediction),
                "track": record.track.value,
                "query_family": record.query_family,
                "precision": terminal.precision,
                "recall": terminal.recall,
                "f1": terminal.f1,
                "exact_match": terminal.exact_match,
                "ndcg": terminal.ndcg,
                "entity_f1": context.f1,
            }
        )
    return rows


def paired_bootstrap_difference(
    left: Sequence[float], right: Sequence[float], seed: int = 20260822, samples: int = 10_000
) -> tuple[float, float, float]:
    if len(left) != len(right) or not left:
        raise ValueError("paired samples must have equal nonzero length")
    differences = [a - b for a, b in zip(left, right, strict=True)]
    rng = random.Random(seed)
    draws = sorted(
        mean(rng.choice(differences) for _ in differences) for _ in range(samples)
    )
    return mean(differences), draws[int(samples * 0.025)], draws[int(samples * 0.975)]


def write_run_log(predictions: Sequence[Prediction], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        for prediction in predictions:
            stream.write(json.dumps(asdict(prediction), sort_keys=True) + "\n")
