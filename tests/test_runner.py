import json

from pds_research.runner import ExperimentRunner, ReferenceReplaySystem

from test_benchmark import record


def test_runner_is_resumable(tmp_path) -> None:
    output = tmp_path / "predictions.jsonl"
    runner = ExperimentRunner(output)
    item = record("one", "moon")
    assert len(runner.run(ReferenceReplaySystem(), [item], repetitions=2)) == 2
    assert len(runner.run(ReferenceReplaySystem(), [item], repetitions=2)) == 0
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(rows) == 2


def test_runner_records_failures(tmp_path) -> None:
    class Broken:
        name = "broken"

        def predict(self, benchmark_record, repetition):
            raise RuntimeError("boom")

    output = tmp_path / "predictions.jsonl"
    ExperimentRunner(output).run(Broken(), [record("one", "moon")], repetitions=1)
    row = json.loads(output.read_text())
    assert row["failure"] == "RuntimeError: boom"
    assert row["predicted_product_ids"] == []
