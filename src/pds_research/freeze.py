from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from .benchmark import read_jsonl


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze_pilot(dataset: Path, snapshot: Path, output: Path, review_waived: bool) -> dict:
    records = read_jsonl(dataset)
    if not all(
        row.validation.schema_valid
        and row.validation.executed
        and row.validation.fully_paginated
        for row in records
    ):
        raise ValueError("all records must pass executable validation before freezing")
    snapshot_files = sorted(path for path in snapshot.rglob("*") if path.is_file())
    manifest = {
        "format_version": "1.0",
        "frozen_at": datetime.now(UTC).isoformat(),
        "dataset": str(dataset),
        "dataset_sha256": file_sha256(dataset),
        "record_count": len(records),
        "snapshot": str(snapshot),
        "snapshot_files_sha256": {
            str(path.relative_to(snapshot)): file_sha256(path) for path in snapshot_files
        },
        "manual_review": "waived_by_project_owner" if review_waived else "required",
        "limitations": [
            "NLQ naturalness and semantic alignment were not manually reviewed."
        ] if review_waived else [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
