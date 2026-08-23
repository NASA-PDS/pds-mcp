# Experiment outputs

Each run should write immutable JSONL predictions and trajectories under a
directory named by system, model snapshot, dataset hash, and repetition. Failed
runs remain in the logs with a failure classification and empty predictions.

Aggregated tables and figures must be regenerated from these logs rather than
edited by hand.
