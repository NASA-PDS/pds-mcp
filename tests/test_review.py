from pds_research.review import quality_flags

from test_benchmark import record


def test_quality_flags_schema_leakage_and_broad_results() -> None:
    item = record("one", "moon")
    item.question = "Find ref_lid_target urn:nasa:pds:moon"
    item.relevant_product_ids = [str(index) for index in range(51)]
    codes = {flag.code for flag in quality_flags(item)}
    assert {"ontology_leakage", "schema_leakage", "broad_denotation"} <= codes
