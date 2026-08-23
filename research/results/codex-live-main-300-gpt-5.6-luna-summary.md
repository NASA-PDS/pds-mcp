# Live PDS MCP evaluation — GPT-5.6 Luna

The run completed all 300 questions against the original live NASA PDS MCP
server. One execution failure is retained in all aggregate denominators.

| Metric | Result |
|---|---:|
| Macro precision | 98.18% |
| Macro recall | 97.97% |
| Macro F1 | 98.02% |
| Exact result-set match | 95.67% (287/300) |
| nDCG | 98.25% |
| Execution failures | 1/300 |
| Mean latency | 47.24 seconds |
| Total reported input tokens | 44,106,997 |
| Total reported output tokens | 405,649 |

## Key strata

| Stratum | N | Macro F1 | Exact match |
|---|---:|---:|---:|
| Archive retrieval | 294 | 98.32% | 95.92% |
| Context discovery | 6 | 83.33% | 83.33% |
| Multihop | 225 | 98.01% | 96.44% |
| Single constraint | 75 | 98.03% | 93.33% |
| Two constraints | 112 | 99.05% | 98.21% |
| Three constraints | 113 | 96.98% | 94.69% |

These results establish performance on the live-query-derived synthetic
benchmark. They do not by themselves establish usability for planetary
scientists or generalization to independently authored questions.

## Tool-call analysis

The agent used a mean of 5.28 and median of 5 MCP calls per question, with a
range of 1–15. Only 3 of 300 questions completed with one call. Exact-match
accuracy was 100% for two, five, and six-call groups, then became less stable
among the longest trajectories. Tool-call count was observational rather than
randomized: longer trajectories may reflect harder questions or correction
attempts, and small high-call groups have substantial uncertainty. These values
therefore describe agent behavior but do not establish a causal effect of
additional calls.
