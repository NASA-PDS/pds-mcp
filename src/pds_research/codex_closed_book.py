from __future__ import annotations

import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .benchmark import read_jsonl


FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "predicted_product_ids": {"type": "array", "items": {"type": "string"}},
        "predicted_context_ids": {"type": "array", "items": {"type": "string"}},
        "completed": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["predicted_product_ids", "predicted_context_ids", "completed", "notes"],
    "additionalProperties": False,
}


def _predict_closed_book(record, trajectory_dir: Path, model: str) -> dict:
    started = time.monotonic()
    row = {
                "id": record.id,
                "system": "codex_closed_book_no_tools",
                "repetition": 0,
                "predicted_product_ids": [],
                "predicted_context_ids": [],
                "tool_calls": 0,
                "latency_seconds": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "failure": None,
                "run_class": "closed_book_baseline",
                "model": model,
    }
    try:
                with tempfile.TemporaryDirectory(prefix="pds-closed-book-") as directory:
                    root = Path(directory)
                    schema_path = root / "schema.json"
                    answer_path = root / "answer.json"
                    schema_path.write_text(json.dumps(FINAL_SCHEMA))
                    prompt = f"""Answer the PDS search question using only knowledge encoded in
the model. Do not use tools, files, shell commands, MCP, web search, or external data.
For a context-record question, return exact identifiers in predicted_context_ids.
For a collection question, return every exact collection LID in predicted_product_ids.
Do not invent an identifier when you do not know it; return an empty list instead.

USER QUESTION:
{record.question}
"""
                    command = [
                        "codex", "exec", "--ephemeral", "--ignore-user-config",
                        "--skip-git-repo-check", "--sandbox", "read-only", "--json",
                        "--model", model, "--output-schema", str(schema_path),
                        "--output-last-message", str(answer_path), "-C", str(root), prompt,
                    ]
                    result = subprocess.run(
                        command, capture_output=True, text=True, timeout=180, check=False
                    )
                    trajectory_dir.joinpath(f"{record.id}-r0.jsonl").write_text(result.stdout)
                    if result.returncode:
                        raise RuntimeError("codex closed-book run failed: " + result.stderr[-1500:])
                    answer = json.loads(answer_path.read_text())
                    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
                    usage_event = next((event for event in reversed(events) if "usage" in event), {})
                    usage = usage_event.get("usage", {}) if isinstance(usage_event, dict) else {}
                    row.update(
                        predicted_product_ids=sorted(set(answer["predicted_product_ids"])),
                        predicted_context_ids=sorted(set(answer["predicted_context_ids"])),
                        input_tokens=int(usage.get("input_tokens", 0)),
                        output_tokens=int(usage.get("output_tokens", 0)),
                        failure=None if answer["completed"] else answer["notes"],
                    )
    except Exception as exc:
        row["failure"] = f"{type(exc).__name__}: {exc}"
    row["latency_seconds"] = time.monotonic() - started
    return row


def run_closed_book_batch(
    dataset: Path,
    output: Path,
    trajectory_dir: Path,
    model: str,
    workers: int = 1,
) -> int:
    """Run a resumable NLQ-only baseline with no PDS or MCP access."""
    records = read_jsonl(dataset)
    completed_ids: set[str] = set()
    if output.exists():
        completed_ids = {
            json.loads(line)["id"] for line in output.read_text().splitlines() if line.strip()
        }
    pending = [record for record in records if record.id not in completed_ids]
    output.parent.mkdir(parents=True, exist_ok=True)
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    with output.open("a") as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        rows = pool.map(lambda record: _predict_closed_book(record, trajectory_dir, model), pending)
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
    return len(pending)
