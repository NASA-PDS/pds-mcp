from __future__ import annotations

import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import yaml

from .benchmark import read_jsonl
from .evaluation import Prediction


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


class CodexLiveMCPSystem:
    name = "codex_live_pds_mcp_multistep"

    def __init__(self, model: str, trajectory_dir: Path, max_tool_calls: int = 8) -> None:
        self.model = model
        self.trajectory_dir = trajectory_dir
        self.max_tool_calls = max_tool_calls
        self.name = (
            "codex_live_pds_mcp_single_call"
            if max_tool_calls == 1
            else "codex_live_pds_mcp_multistep"
        )
        self.python = Path(__file__).parents[2] / ".venv/bin/python"

    def predict(self, record, repetition: int) -> Prediction:
        self.trajectory_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pds-codex-mcp-") as directory:
            root = Path(directory)
            schema_path = root / "final-schema.json"
            output_path = root / "final.json"
            schema_path.write_text(json.dumps(FINAL_SCHEMA))
            prompt = f"""You are evaluating natural-language search over NASA's live PDS Registry.
Use only tools from the pds_live MCP server. Do not use shell, files, web search,
or prior knowledge as a substitute for tools. Resolve exact PDS context identifiers
first, then search collections when the question asks for collections. For a context
lookup, put the answer in predicted_context_ids; for collection retrieval, put every
matching collection in predicted_product_ids. Use at most {self.max_tool_calls} MCP calls. A complete,
untruncated collection search is authoritative; do not inspect every returned
collection. Inspect only to resolve ambiguity or verify one representative result.
The reference answer is hidden.

USER QUESTION:
{record.question}
"""
            command = [
                "codex", "exec", "--ephemeral", "--ignore-user-config",
                "--skip-git-repo-check", "--approve-for-me", "--json",
                "--model", self.model,
                "--output-schema", str(schema_path),
                "--output-last-message", str(output_path),
                "-C", str(root),
                "-c", f'mcp_servers.pds_live.command="{self.python}"',
                "-c", 'mcp_servers.pds_live.args=["-m","pds_mcp_server"]',
                prompt,
            ]
            started = time.monotonic()
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=240, check=False
            )
            latency = time.monotonic() - started
            trajectory_path = self.trajectory_dir / f"{record.id}-r{repetition}.jsonl"
            trajectory_path.write_text(completed.stdout)
            if completed.returncode:
                detail = "\n".join(completed.stderr.strip().splitlines()[-12:])
                raise RuntimeError(f"codex MCP run failed:\n{detail}")
            payload = json.loads(output_path.read_text())
            events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
            tool_calls = sum(
                1
                for event in events
                if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "mcp_tool_call"
            )
            usage_event = next(
                (event for event in reversed(events) if "usage" in event), {}
            )
            usage = usage_event.get("usage", {}) if isinstance(usage_event, dict) else {}
            protocol_failure = tool_calls > self.max_tool_calls
            return Prediction(
                id=record.id,
                system=self.name,
                repetition=repetition,
                predicted_product_ids=([] if protocol_failure else sorted(set(payload["predicted_product_ids"]))),
                predicted_context_ids=([] if protocol_failure else sorted(set(payload["predicted_context_ids"]))),
                tool_calls=tool_calls,
                latency_seconds=latency,
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                failure=(
                    f"protocol violation: used {tool_calls} calls; maximum is {self.max_tool_calls}"
                    if protocol_failure
                    else (None if payload["completed"] else payload["notes"])
                ),
            )


def run_codex_mcp_smoke(
    dataset: Path,
    output: Path,
    trajectory_dir: Path,
    model: str,
    item_ids: list[str],
    question_config: Path | None = None,
) -> int:
    if not 1 <= len(item_ids) <= 3:
        raise ValueError("choose between one and three explicit pilot item IDs")
    by_id = {record.id: record for record in read_jsonl(dataset)}
    missing = sorted(set(item_ids).difference(by_id))
    if missing:
        raise ValueError(f"unknown pilot IDs: {', '.join(missing)}")
    if question_config:
        variants = yaml.safe_load(question_config.read_text()).get("variants", {})
        for item_id in item_ids:
            if item_id not in variants:
                raise ValueError(f"no question override for {item_id}")
            by_id[item_id] = by_id[item_id].model_copy(
                update={"question": str(variants[item_id]["question"])}
            )
    system = CodexLiveMCPSystem(model, trajectory_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as stream:
        for item_id in item_ids:
            prediction = system.predict(by_id[item_id], 0)
            stream.write(json.dumps({
                **asdict(prediction),
                "run_class": "development_smoke_not_formal_evidence",
                "model": model,
            }, sort_keys=True) + "\n")
    return len(item_ids)


def run_codex_mcp_batch(
    dataset: Path,
    output: Path,
    trajectory_dir: Path,
    model: str,
    repetitions: int = 1,
    max_items: int | None = None,
    max_tool_calls: int = 8,
    workers: int = 1,
) -> int:
    """Run a resumable live-MCP evaluation over a benchmark JSONL file."""
    records = read_jsonl(dataset)
    if max_items is not None:
        records = records[:max_items]
    completed: set[tuple[str, int]] = set()
    if output.exists():
        for line in output.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                completed.add((row["id"], int(row.get("repetition", 0))))
    system = CodexLiveMCPSystem(model, trajectory_dir, max_tool_calls=max_tool_calls)
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = [
        (record, repetition)
        for record in records
        for repetition in range(repetitions)
        if (record.id, repetition) not in completed
    ]

    def run_one(job):
        record, repetition = job
        try:
            prediction = system.predict(record, repetition)
            return {**asdict(prediction), "run_class": "main_live_evaluation", "model": model}
        except Exception as exc:  # Failed runs remain in the evaluation denominator.
            return {
                        "id": record.id,
                        "system": system.name,
                        "repetition": repetition,
                        "predicted_product_ids": [],
                        "predicted_context_ids": [],
                        "tool_calls": 0,
                        "latency_seconds": 0.0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "failure": f"{type(exc).__name__}: {exc}",
                        "run_class": "main_live_evaluation",
                        "model": model,
            }

    with output.open("a") as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(run_one, pending):
                stream.write(json.dumps(row, sort_keys=True) + "\n")
                stream.flush()
    return len(pending)
