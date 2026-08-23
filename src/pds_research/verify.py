from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from .benchmark import read_jsonl, write_jsonl
from .models import BenchmarkRecord, Difficulty, Provenance, Validation, classify_selectivity
from .snapshot import DEFAULT_API_BASE, PDSClient, SnapshotWriter


async def verify_records(
    input_path: Path,
    output_path: Path,
    snapshot_path: Path,
    base_url: str = DEFAULT_API_BASE,
) -> list[BenchmarkRecord]:
    records = read_jsonl(input_path)
    writer = SnapshotWriter(snapshot_path, PDSClient(base_url=base_url))
    verified: list[BenchmarkRecord] = []
    for record in records:
        execution = await writer.record_plan(record.reference_query_plan)
        live_ids = execution["result_ids"]
        notes = list(record.validation.notes)
        notes = [note for note in notes if "frozen" not in note.lower()]
        if live_ids != record.relevant_product_ids:
            notes.append(
                "Executable result set replaced the locally derived draft denotation."
            )
        verified.append(
            record.model_copy(
                update={
                    "reference_api_request": execution["request"],
                    "relevant_product_ids": live_ids,
                    "difficulty": Difficulty(
                        constraint_count=record.difficulty.constraint_count,
                        reasoning_depth=record.difficulty.reasoning_depth,
                        selectivity=classify_selectivity(len(live_ids)),
                    ),
                    "snapshot_version": f"live-{datetime.now(UTC).date().isoformat()}",
                    "provenance": Provenance(
                        generated_at=datetime.now(UTC),
                        api_base_url=base_url,
                        request_sha256=execution["request_sha256"],
                        response_sha256=execution["response_sha256"],
                    ),
                    "validation": Validation(
                        schema_valid=True,
                        executed=True,
                        fully_paginated=True,
                        manually_reviewed=record.validation.manually_reviewed,
                        notes=[*notes, "Ground truth executed against the live PDS Registry."],
                    ),
                }
            )
        )
    write_jsonl(verified, output_path)
    return verified


def verify_dataset(
    input_path: Path,
    output_path: Path,
    snapshot_path: Path,
    base_url: str = DEFAULT_API_BASE,
) -> list[BenchmarkRecord]:
    return asyncio.run(verify_records(input_path, output_path, snapshot_path, base_url))
