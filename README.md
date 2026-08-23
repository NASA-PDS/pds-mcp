# Agentic Search for the NASA Planetary Data System

An MCP server and reproducible evaluation of multistep natural-language search
over the [NASA Planetary Data System (PDS) Registry](https://nasa-pds.github.io/pds-api/) -- the digital data archive for all of NASA's planetary missions, flight and ground-based observations, and laboratory
experiments from the 1960s to the present. With more than **1.85 petabytes** from **70+
missions, 4,500 datasets, and 700 instruments** all peer-reviewed by JPL and other research institutions.

**[Evaluation study](#evaluation-study) · [Results](#results) · [Benchmark and reproducibility](#benchmark-and-reproducibility) · [MCP server](#mcp-server) · [Development guide](DEVELOPMENT.md)**

https://github.com/user-attachments/assets/1d6b7035-c07a-4ca3-8bd2-9c19d68c3d5c

## Abstract

The NASA Planetary Data System (PDS) serves as a high-quality, hand-curated data source for the whole community of planetary research. However, searching the PDS Registry is difficult, requiring knowledge of exact PDS4 ontology fields and context identifiers to manually construct queries for its public search APIs.  The research chain of scientific question -> experimentation -> findings/results is thus bottlenecked by current PDS search capabilities.

We introduce **PDS-MCP**, an agentic search interface on top of the NASA PDS Registry.
From natural language questions, our agent can iteratively resolve PDS entities, inspect relationships, construct valid filters, and retrieve matching products autonomously constructing PDS API queries with no manual human intervention. We evaluate this on our 300-question benchmark, constructed from our scalable data engine, achieving **98.02% macro F1** and **95.67%
exact result-set match** on our full system, compared with 12.29% and 8.33% for single-call MCP and
0.33% on both metrics without PDS access, demonstrating that it can reliably bridge
natural-language questions and structured PDS retrieval.

By releasing **PDS-MCP** publically, we aim to support the researchers of the Planetary Data Science community by making it easier to access NASA PDS data. Our goal is to provide enhanced search capabilities that enable more effective data exploration and improve accessibility for future research endeavors.


## Evaluation study

### Research question

Can a language-model agent reliably translate natural-language planetary-data
requests into complete PDS Registry result sets, and does multistep MCP search
outperform the same model with one or zero PDS tool calls?

### Benchmark

The benchmark contains 300 independent questions:

- 225 multihop questions with two or three context constraints.
- 75 single-constraint controls.
- 294 archive-collection retrieval questions and 6 context lookups.
- Target sets ranging from 1 to 98 PDS identifiers.

Ground truth was constructed before question answering. Each typed query plan
was compiled, executed against the live PDS API, fully paginated, and normalized
to PDS logical identifiers. Natural-language questions were then derived from
the validated intents. During evaluation, every question ran in an independent
ephemeral Codex process with no access to other questions or reference answers.

### Conditions

| Condition | Model | PDS access | Purpose |
|---|---|---|---|
| Closed book | GPT-5.6 Luna | None | Tests whether exact identifiers can be produced from model knowledge alone. |
| Single-call MCP | GPT-5.6 Luna | At most one live MCP call | Tests whether tool availability without iterative search is sufficient. |
| Multistep MCP | GPT-5.6 Luna | Iterative live MCP calls | Tests entity resolution, refinement, and collection retrieval. |

Returned identifier sets were scored with macro precision, recall, F1, and
exact result-set match. F1 awards partial credit for overlap; exact match
requires the complete returned set to equal the ground-truth set. Failed runs
and abstentions remain in the denominator.

## Results

![Same-model PDS retrieval performance across closed-book, single-call MCP, and multistep MCP conditions](research/results/figures/pds-performance-comparison.png)

| Condition | Macro precision | Macro recall | Macro F1 | Exact match | Micro F1 | Mean calls | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Closed book | 0.33% | 0.33% | 0.33% | 0.33% | 0.03% | 0.00 | 8.00 s |
| Single-call MCP | 13.62% | 11.71% | 12.29% | 8.33% | 27.85% | 1.01 | 29.86 s |
| **Multistep MCP** | **98.18%** | **97.97%** | **98.02%** | **95.67%** | **99.26%** | 5.28 | 47.24 s |

The single-call condition was conservative: it produced few false positives
but missed most relevant identifiers. Multistep MCP search recovered 6,749 true
positive identifiers with 8 false positives and 93 false negatives. Across the
multistep run, the agent used a mean of 5.28 and a median of 5 tool calls per
question, demonstrating that the evaluated behavior was generally iterative
rather than a one-call lookup.

## How multistep search works

A request such as:

> Find PDS collections from the New Horizons Kuiper Belt Extended Mission 1,
> collected by the Radio Science Experiment, targeting Arrokoth.

requires the agent to resolve several ontology objects before retrieving data:

1. Resolve the KEM1 investigation identifier.
2. Resolve the New Horizons REX instrument identifier.
3. Resolve Arrokoth and its PDS target identifier.
4. Search collections using the compatible investigation, instrument, and
   target constraints.
5. Return the complete normalized collection-identifier set.

This mirrors the work a user would otherwise perform manually when discovering
PDS4 context identifiers and exact Registry filters.

## Benchmark and reproducibility

| Artifact | Description |
|---|---|
| [`main-300-live.jsonl`](research/data/main-300-live.jsonl) | Questions, typed query plans, API requests, ground-truth identifiers, difficulty labels, and provenance. |
| [`codex-closed-book-main-300-gpt-5.6-luna.jsonl`](research/results/codex-closed-book-main-300-gpt-5.6-luna.jsonl) | Raw closed-book predictions. |
| [`codex-live-single-call-main-300-gpt-5.6-luna.jsonl`](research/results/codex-live-single-call-main-300-gpt-5.6-luna.jsonl) | Raw single-call predictions. |
| [`codex-live-main-300-gpt-5.6-luna.jsonl`](research/results/codex-live-main-300-gpt-5.6-luna.jsonl) | Raw multistep predictions. |
| [`three-condition-comparison.csv`](research/results/three-condition-comparison.csv) | Graph-ready aggregate comparison. |
| [`three-condition-comparison.json`](research/results/three-condition-comparison.json) | Machine-readable metrics and resource measurements. |
| [`tool-call analysis`](research/results/codex-live-main-300-tool-call-analysis.csv) | Multistep hop-count distribution and exact accuracy by call count. |

Recompute identifier-set metrics with:

```bash
.venv/bin/pds-research score \
  research/data/main-300-live.jsonl \
  research/results/codex-live-main-300-gpt-5.6-luna.jsonl
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for environment setup, server execution,
MCP client configuration, and test commands.

## Limitations

- Questions were synthetically derived from executable query plans; the study
  does not establish usefulness to planetary scientists.
- The benchmark emphasizes collection retrieval and contains only six direct
  context-discovery questions.
- Each condition was run once with one model, so run-to-run and cross-model
  generalization remain unmeasured.
- Ground truth captures live Registry behavior at benchmark-construction time;
  later Registry updates may produce different result sets.
- Longer trajectories are associated with harder cases or recovery attempts;
  tool-call count should not be interpreted as a causal performance factor.

## MCP server

The FastMCP server in [`src/pds_mcp_server.py`](src/pds_mcp_server.py) exposes
live PDS Registry operations for:

- Investigation, target, instrument-host, and instrument search.
- Context-product traversal.
- Collection search by investigation, target, instrument, and host.
- Detailed product retrieval by PDS identifier.

The server can be used from Claude Desktop, Cursor, Codex, or another
MCP-compatible host. Setup instructions are in [DEVELOPMENT.md](DEVELOPMENT.md).

## Example research queries

- Find Apollo 17 collections produced by the Lunar Surface Experiments Package
  Heat Flow Experiment and targeting the Moon.
- Find InSight collections produced by the Auxiliary Payload Sensor Subsystem
  temperature and wind sensor and targeting Mars.
- Find Cassini collections produced by the Imaging Science Subsystem Wide Angle
  camera and hosted on the Cassini Orbiter.
- Find New Horizons KEM1 radio-science collections targeting Arrokoth.

These examples are drawn from the released benchmark; the complete set is
available in [`main-300-live.jsonl`](research/data/main-300-live.jsonl).

## License

Code is released under the [MIT License](LICENSE).

## Support

- PDS Registry API: contact `pds-operator@jpl.nasa.gov` or open an issue in the
  [PDS API repository](https://github.com/NASA-PDS/pds-api).
- This server and study: open an issue in this repository.
