from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .query import normalize_lid


@dataclass(frozen=True)
class RetrievalMetrics:
    precision: float
    recall: float
    f1: float
    exact_match: float
    ndcg: float


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(normalize_lid(value) for value in values))


def score_retrieval(
    predicted: Sequence[str], relevant: Sequence[str], k: int | None = None
) -> RetrievalMetrics:
    ranked = _unique(predicted)
    if k is not None:
        ranked = ranked[:k]
    gold = set(_unique(relevant))
    predicted_set = set(ranked)
    true_positive = len(predicted_set & gold)
    precision = true_positive / len(predicted_set) if predicted_set else float(not gold)
    recall = true_positive / len(gold) if gold else float(not predicted_set)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = float(predicted_set == gold)

    dcg = sum(
        1.0 / math.log2(index + 2)
        for index, identifier in enumerate(ranked)
        if identifier in gold
    )
    ideal_hits = min(len(gold), len(ranked) if k is None else k)
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    ndcg = dcg / idcg if idcg else float(not gold and not ranked)
    return RetrievalMetrics(precision, recall, f1, exact, ndcg)


def macro_average(rows: Sequence[RetrievalMetrics]) -> RetrievalMetrics:
    if not rows:
        return RetrievalMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    count = len(rows)
    return RetrievalMetrics(
        precision=sum(row.precision for row in rows) / count,
        recall=sum(row.recall for row in rows) / count,
        f1=sum(row.f1 for row in rows) / count,
        exact_match=sum(row.exact_match for row in rows) / count,
        ndcg=sum(row.ndcg for row in rows) / count,
    )

