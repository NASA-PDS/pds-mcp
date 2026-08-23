from pds_research.baselines import lexical_score


def test_lexical_score_prefers_exact_title() -> None:
    question = "Find collections from the Cassini Orbiter targeting Titan"
    assert lexical_score(question, "Cassini Orbiter") == 1.0
    assert lexical_score(question, "Mars Reconnaissance Orbiter") < 1.0
