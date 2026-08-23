from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import read_jsonl
from .baselines import run_deterministic_baseline
from .generate import generate_pilot
from .freeze import freeze_pilot
from .codex_smoke import run_codex_smoke
from .codex_mcp_agent import run_codex_mcp_batch, run_codex_mcp_smoke
from .codex_closed_book import run_closed_book_batch
from .metrics import macro_average, score_retrieval
from .review import write_review_report
from .snapshot import DEFAULT_API_BASE, discover_snapshot
from .verify import verify_dataset


def _snapshot(args: argparse.Namespace) -> None:
    discover_snapshot(
        Path(args.output),
        args.snapshot_id,
        args.base_url,
        args.include_context,
        args.include_relationships,
    )


def _validate(args: argparse.Namespace) -> None:
    records = read_jsonl(Path(args.dataset))
    ready = [
        record
        for record in records
        if record.validation.schema_valid
        and record.validation.executed
        and record.validation.fully_paginated
        and record.validation.manually_reviewed
    ]
    result = {"structurally_valid_records": len(records), "experiment_ready_records": len(ready)}
    print(json.dumps(result, indent=2))
    if args.require_ready and len(ready) != len(records):
        raise SystemExit(2)


def _generate_pilot(args: argparse.Namespace) -> None:
    records = generate_pilot(
        Path(args.snapshot), Path(args.output), args.size, args.seed
    )
    print(json.dumps({"generated_records": len(records), "output": args.output}, indent=2))


def _score(args: argparse.Namespace) -> None:
    records = {record.id: record for record in read_jsonl(Path(args.dataset))}
    predictions = {}
    with Path(args.predictions).open() as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                predictions[row["id"]] = row
    scores = [
        score_retrieval(
            (
                predictions.get(item_id, {}).get("predicted_context_ids", [])
                if record.track.value == "context_discovery"
                else predictions.get(item_id, {}).get("predicted_product_ids", [])
            ),
            record.relevant_product_ids,
            args.k,
        )
        for item_id, record in records.items()
    ]
    print(json.dumps(macro_average(scores).__dict__, indent=2))


def _verify_dataset(args: argparse.Namespace) -> None:
    records = verify_dataset(
        Path(args.dataset),
        Path(args.output),
        Path(args.snapshot),
        args.base_url,
    )
    print(json.dumps({"executed_records": len(records), "output": args.output}, indent=2))


def _review_report(args: argparse.Namespace) -> None:
    result = write_review_report(Path(args.dataset), Path(args.output))
    print(json.dumps({**result, "output": args.output}, indent=2))


def _run_baseline(args: argparse.Namespace) -> None:
    emitted = run_deterministic_baseline(
        Path(args.dataset), Path(args.snapshot), Path(args.output)
    )
    print(json.dumps({"emitted_predictions": emitted, "output": args.output}, indent=2))


def _freeze_pilot(args: argparse.Namespace) -> None:
    manifest = freeze_pilot(
        Path(args.dataset), Path(args.snapshot), Path(args.output), args.waive_manual_review
    )
    print(json.dumps({
        "record_count": manifest["record_count"],
        "dataset_sha256": manifest["dataset_sha256"],
        "manual_review": manifest["manual_review"],
        "output": args.output,
    }, indent=2))


def _codex_smoke(args: argparse.Namespace) -> None:
    if not args.acknowledge_development_only:
        raise SystemExit("pass --acknowledge-development-only to run Codex smoke tests")
    count = run_codex_smoke(
        Path(args.dataset), Path(args.snapshot), Path(args.output), args.model, args.item_id
    )
    print(json.dumps({"smoke_predictions": count, "output": args.output}, indent=2))


def _codex_mcp_smoke(args: argparse.Namespace) -> None:
    if not args.acknowledge_development_only:
        raise SystemExit("pass --acknowledge-development-only to run Codex smoke tests")
    count = run_codex_mcp_smoke(
        Path(args.dataset), Path(args.output),
        Path(args.trajectories), args.model, args.item_id,
        Path(args.question_config) if args.question_config else None,
    )
    print(json.dumps({"smoke_predictions": count, "output": args.output}, indent=2))


def _codex_mcp_batch(args: argparse.Namespace) -> None:
    count = run_codex_mcp_batch(
        Path(args.dataset), Path(args.output), Path(args.trajectories),
        args.model, args.repetitions, args.max_items, args.max_tool_calls, args.workers,
    )
    print(json.dumps({"new_predictions": count, "output": args.output}, indent=2))


def _codex_closed_book(args: argparse.Namespace) -> None:
    count = run_closed_book_batch(
        Path(args.dataset), Path(args.output), Path(args.trajectories), args.model, args.workers
    )
    print(json.dumps({"new_predictions": count, "output": args.output}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    snapshot = subparsers.add_parser("snapshot", help="discover and freeze PDS schema")
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--snapshot-id", required=True)
    snapshot.add_argument("--base-url", default=DEFAULT_API_BASE)
    snapshot.add_argument(
        "--include-context",
        action="store_true",
        help="also fully paginate core context-product inventories",
    )
    snapshot.add_argument(
        "--include-relationships",
        action="store_true",
        help="fully paginate collections and derive context-reference edges",
    )
    snapshot.set_defaults(handler=_snapshot)

    validate = subparsers.add_parser("validate", help="validate benchmark JSONL")
    validate.add_argument("dataset")
    validate.add_argument(
        "--require-ready",
        action="store_true",
        help="fail unless every item was executed, paginated, and manually reviewed",
    )
    validate.set_defaults(handler=_validate)

    generate = subparsers.add_parser(
        "generate-pilot", help="generate a draft pilot from a frozen snapshot"
    )
    generate.add_argument("--snapshot", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--size", type=int, default=30)
    generate.add_argument("--seed", type=int, default=20260822)
    generate.set_defaults(handler=_generate_pilot)

    score = subparsers.add_parser("score", help="score prediction JSONL")
    score.add_argument("dataset")
    score.add_argument("predictions")
    score.add_argument("--k", type=int)
    score.set_defaults(handler=_score)

    verify = subparsers.add_parser(
        "verify-dataset", help="execute and fully paginate every reference query"
    )
    verify.add_argument("dataset")
    verify.add_argument("--output", required=True)
    verify.add_argument("--snapshot", required=True)
    verify.add_argument("--base-url", default=DEFAULT_API_BASE)
    verify.set_defaults(handler=_verify_dataset)

    review = subparsers.add_parser(
        "review-report", help="create a human NLQ review worksheet with quality flags"
    )
    review.add_argument("dataset")
    review.add_argument("--output", required=True)
    review.set_defaults(handler=_review_report)

    baseline = subparsers.add_parser(
        "run-baseline", help="run the deterministic lexical/native-graph baseline"
    )
    baseline.add_argument("dataset")
    baseline.add_argument("--snapshot", required=True)
    baseline.add_argument("--output", required=True)
    baseline.set_defaults(handler=_run_baseline)

    freeze = subparsers.add_parser(
        "freeze-pilot", help="hash the executable pilot and frozen response fixtures"
    )
    freeze.add_argument("dataset")
    freeze.add_argument("--snapshot", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument(
        "--waive-manual-review",
        action="store_true",
        help="record an explicit review waiver as a study limitation",
    )
    freeze.set_defaults(handler=_freeze_pilot)

    codex_smoke = subparsers.add_parser(
        "codex-smoke", help="run 1-3 isolated development queries through local Codex"
    )
    codex_smoke.add_argument("dataset")
    codex_smoke.add_argument("--snapshot", required=True)
    codex_smoke.add_argument("--output", required=True)
    codex_smoke.add_argument("--model", required=True)
    codex_smoke.add_argument("--item-id", action="append", required=True)
    codex_smoke.add_argument("--acknowledge-development-only", action="store_true")
    codex_smoke.set_defaults(handler=_codex_smoke)

    codex_mcp = subparsers.add_parser(
        "codex-mcp-smoke", help="run 1-3 multistep Codex trials over the live PDS MCP server"
    )
    codex_mcp.add_argument("dataset")
    codex_mcp.add_argument("--output", required=True)
    codex_mcp.add_argument("--trajectories", required=True)
    codex_mcp.add_argument("--model", required=True)
    codex_mcp.add_argument("--item-id", action="append", required=True)
    codex_mcp.add_argument(
        "--question-config", help="optional YAML with development-only NLQ overrides"
    )
    codex_mcp.add_argument("--acknowledge-development-only", action="store_true")
    codex_mcp.set_defaults(handler=_codex_mcp_smoke)

    codex_batch = subparsers.add_parser(
        "codex-mcp-batch", help="run or resume a live PDS MCP benchmark"
    )
    codex_batch.add_argument("dataset")
    codex_batch.add_argument("--output", required=True)
    codex_batch.add_argument("--trajectories", required=True)
    codex_batch.add_argument("--model", required=True)
    codex_batch.add_argument("--repetitions", type=int, default=1)
    codex_batch.add_argument("--max-items", type=int)
    codex_batch.add_argument("--max-tool-calls", type=int, default=8)
    codex_batch.add_argument("--workers", type=int, default=1, choices=range(1, 9))
    codex_batch.set_defaults(handler=_codex_mcp_batch)

    closed_book = subparsers.add_parser(
        "codex-closed-book", help="run or resume the same-model no-tools baseline"
    )
    closed_book.add_argument("dataset")
    closed_book.add_argument("--output", required=True)
    closed_book.add_argument("--trajectories", required=True)
    closed_book.add_argument("--model", required=True)
    closed_book.add_argument("--workers", type=int, default=1, choices=range(1, 9))
    closed_book.set_defaults(handler=_codex_closed_book)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
