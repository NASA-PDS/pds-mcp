from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .evaluation import Prediction
from .models import BenchmarkRecord


class SearchSystem(Protocol):
    """Provider-independent interface selected systems must implement."""

    name: str

    def predict(self, record: BenchmarkRecord, repetition: int) -> Prediction: ...


class ExperimentRunner:
    def __init__(self, output: Path) -> None:
        self.output = output

    def _completed(self) -> set[tuple[str, int]]:
        if not self.output.exists():
            return set()
        completed = set()
        with self.output.open() as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    completed.add((row["id"], int(row["repetition"])))
        return completed

    def run(
        self,
        system: SearchSystem,
        records: list[BenchmarkRecord],
        repetitions: int,
    ) -> list[Prediction]:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        completed = self._completed()
        emitted: list[Prediction] = []
        with self.output.open("a") as stream:
            for repetition in range(repetitions):
                for record in records:
                    if (record.id, repetition) in completed:
                        continue
                    started = time.monotonic()
                    try:
                        prediction = system.predict(record, repetition)
                    except Exception as exc:
                        prediction = Prediction(
                            id=record.id,
                            system=system.name,
                            repetition=repetition,
                            predicted_product_ids=[],
                            predicted_context_ids=[],
                            latency_seconds=time.monotonic() - started,
                            failure=f"{type(exc).__name__}: {exc}",
                        )
                    stream.write(json.dumps(asdict(prediction), sort_keys=True) + "\n")
                    stream.flush()
                    emitted.append(prediction)
        return emitted


class ReferenceReplaySystem:
    """Fixture-only oracle used to test the evaluation pipeline, never a baseline."""

    name = "reference_replay_oracle"

    def predict(self, record: BenchmarkRecord, repetition: int) -> Prediction:
        return Prediction(
            id=record.id,
            system=self.name,
            repetition=repetition,
            predicted_product_ids=record.relevant_product_ids,
            predicted_context_ids=record.required_context_ids,
            canonical_query_valid=True,
        )

