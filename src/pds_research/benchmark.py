from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import BenchmarkRecord


def write_jsonl(records: Iterable[BenchmarkRecord], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w") as stream:
        for record in records:
            stream.write(record.model_dump_json() + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[BenchmarkRecord]:
    records: list[BenchmarkRecord] = []
    with path.open() as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip():
                try:
                    records.append(BenchmarkRecord.model_validate_json(line))
                except Exception as exc:
                    raise ValueError(f"invalid record at {path}:{line_number}: {exc}") from exc
    return records


def entity_split_key(record: BenchmarkRecord) -> str:
    entities = sorted(set(record.required_context_ids))
    if entities:
        return "|".join(entities)
    return json.dumps(record.intent, sort_keys=True, separators=(",", ":"))


def assert_no_entity_leakage(splits: dict[str, list[BenchmarkRecord]]) -> None:
    ownership: dict[str, str] = {}
    for split_name, records in splits.items():
        for record in records:
            key = entity_split_key(record)
            previous = ownership.setdefault(key, split_name)
            if previous != split_name:
                raise ValueError(
                    f"entity combination appears in both {previous} and {split_name}: {key}"
                )

