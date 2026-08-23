import json
from pathlib import Path

from pds_research.benchmark import read_jsonl


ROOT = Path(__file__).parents[1]
DATASET = ROOT / "research/data/main-300-live.jsonl"
PREDICTIONS = (
    "codex-baseline-main-300-gpt-5.6-luna.jsonl",
    "codex-live-single-call-main-300-gpt-5.6-luna.jsonl",
    "codex-live-main-300-gpt-5.6-luna.jsonl",
)


def test_final_dataset_is_complete_and_live_validated() -> None:
    records = read_jsonl(DATASET)
    assert len(records) == 300
    assert len({record.id for record in records}) == 300
    assert all(record.snapshot_version.startswith("live-") for record in records)
    assert all(record.validation.executed for record in records)
    assert all(record.validation.fully_paginated for record in records)


def test_final_prediction_files_cover_the_dataset() -> None:
    expected = {record.id for record in read_jsonl(DATASET)}
    for filename in PREDICTIONS:
        path = ROOT / "research/results" / filename
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        assert len(rows) == 300
        assert {row["id"] for row in rows} == expected
