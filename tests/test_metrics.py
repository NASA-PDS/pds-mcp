from pds_research.metrics import macro_average, score_retrieval


def test_retrieval_metrics() -> None:
    score = score_retrieval(["a", "b"], ["b", "c"])
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.f1 == 0.5
    assert score.exact_match == 0.0


def test_empty_prediction_and_gold_is_exact_success() -> None:
    score = score_retrieval([], [])
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.exact_match == 1.0


def test_macro_average() -> None:
    average = macro_average([score_retrieval(["a"], ["a"]), score_retrieval([], ["a"])])
    assert average.f1 == 0.5

