# Research data

[`main-300-live.jsonl`](main-300-live.jsonl) is the final benchmark used by the
[reported evaluation](../../README.md#evaluation-study). It contains 300 unique
natural-language questions, typed reference query plans, live PDS API requests,
fully paginated ground-truth identifier sets, difficulty metadata, and
provenance.

The main README provides concise sections for the
[benchmark design](../../README.md#benchmark),
[data engine](../../README.md#data-engine), and
[evaluation results](../../README.md#results).

## Benchmark data engine

The benchmark is produced by the [`pds_research` data engine](../../src/pds_research/):

- [`sampler.py`](../../src/pds_research/sampler.py) represents and samples PDS
  context entities and their relationships.
- [`generate.py`](../../src/pds_research/generate.py) assembles benchmark
  records from compatible entities and query families.
- [`query.py`](../../src/pds_research/query.py) validates typed query plans and
  compiles them into PDS Search API requests.
- [`nlq.py`](../../src/pds_research/nlq.py) derives natural-language questions
  from validated intents.
- [`verify.py`](../../src/pds_research/verify.py) executes and verifies reference
  queries against the live API.
- [`models.py`](../../src/pds_research/models.py) defines the benchmark record
  and query-plan schemas.
- [`benchmark.py`](../../src/pds_research/benchmark.py) reads and writes the
  JSONL benchmark format.

See the [`research/config`](../config/) directory for benchmark configurations
and [`DEVELOPMENT.md`](../../DEVELOPMENT.md) for validation, scoring, and
evaluation commands.

## Ground truth

The raw API response cache used while constructing ground truth is intentionally
not retained. It can be regenerated from the reference queries in the benchmark.
The final benchmark is self-contained for scoring the committed prediction files.

Return to the [research artifact index](../README.md) or view the
[saved experiment results](../results/).
