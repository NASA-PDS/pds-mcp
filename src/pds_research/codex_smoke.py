from __future__ import annotations

import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from .benchmark import read_jsonl
from .codex_backend import CodexCliBackend
from .single_pass import SinglePassStructuredQuerySystem


def run_codex_smoke(
    dataset: Path,
    snapshot: Path,
    output: Path,
    model: str,
    item_ids: list[str],
) -> int:
    if not 1 <= len(item_ids) <= 3:
        raise ValueError("choose between one and three explicit pilot item IDs")
    by_id = {record.id: record for record in read_jsonl(dataset)}
    missing = sorted(set(item_ids).difference(by_id))
    if missing:
        raise ValueError(f"unknown pilot IDs: {', '.join(missing)}")
    backend = CodexCliBackend(model=model, max_requests=len(item_ids))
    system = SinglePassStructuredQuerySystem(snapshot, backend)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as stream:
        for item_id in item_ids:
            started = time.monotonic()
            prediction = system.predict(by_id[item_id], repetition=0)
            prediction = replace(prediction, latency_seconds=time.monotonic() - started)
            row = {
                **asdict(prediction),
                "run_class": "development_smoke_not_formal_evidence",
                "model": model,
            }
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    return len(item_ids)
