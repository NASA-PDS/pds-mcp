# Research data

`main-300-live.jsonl` is the final benchmark used by the reported experiments.
It contains 300 unique natural-language questions, typed reference query plans,
live PDS API requests, fully paginated ground-truth identifier sets, difficulty
metadata, and provenance.

The raw API response cache used while constructing ground truth is intentionally
not retained. It can be regenerated from the reference queries in the benchmark.
The final benchmark is self-contained for scoring the committed prediction files.
