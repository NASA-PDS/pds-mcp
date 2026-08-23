# Three-condition PDS retrieval comparison

All conditions use GPT-5.6 Luna and the same 300-question live-validated PDS
benchmark. Macro metrics weight each question equally. Failed and abstained
runs remain in the denominator.

| Condition | Macro precision | Macro recall | Macro F1 | Exact match | Micro F1 | Mean calls | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0.33% | 0.33% | 0.33% | 0.33% | 0.03% | 0.00 | 8.00 s |
| Single-call MCP | 13.62% | 11.71% | 12.29% | 8.33% | 27.85% | 1.01 | 29.86 s |
| Multistep MCP | 98.18% | 97.97% | 98.02% | 95.67% | 99.26% | 5.28 | 47.24 s |

| Condition | TP | FP | FN | Partial nonexact | Zero overlap | Failures/abstentions |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 1 | 31 | 6,841 | 0 | 299 | 0 |
| Single-call MCP | 1,111 | 25 | 5,731 | 17 | 258 | 36 |
| Multistep MCP | 6,749 | 8 | 93 | 8 | 5 | 1 |

The baseline—the same LLM without PDS-MCP or PDS search access—was effectively unable to retrieve exact PDS
identifiers. One MCP call improved overlap but remained highly incomplete. The
multistep system produced a large improvement in both partial-overlap and strict
exact-set metrics, at the cost of additional tool calls, latency, and tokens.
