# Research artifacts

This directory contains the benchmark and results for the evaluation described
in the [main README](../README.md).

## Final benchmark

[`data/main-300-live.jsonl`](data/main-300-live.jsonl) contains 300 independent
questions with typed query plans, live API requests, fully paginated target
identifier sets, difficulty labels, and provenance.

## Final conditions

All three conditions use GPT-5.6 Luna:

1. Closed book with no PDS access.
2. Live PDS MCP access limited to one call.
3. Multistep live PDS MCP access.

Raw predictions, aggregate metrics, graph-ready tables, and figures are under
[`results/`](results/). The primary comparison is available as
[`three-condition-comparison.md`](results/three-condition-comparison.md).

## Reproduction

See [`DEVELOPMENT.md`](../DEVELOPMENT.md) for installation, validation, scoring,
and evaluator commands.
