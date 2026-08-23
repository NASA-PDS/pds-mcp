from pds_research.nlq import template_questions
from pds_research.sampler import ContextEntity, QuerySampler
from pds_research.schema import parse_properties, searchable_capabilities


def test_property_discovery_and_capability_groups() -> None:
    properties = parse_properties(
        [
            {"property": "ref_lid_target", "type": "keyword"},
            {"property": "pds:Time.pds:start_date_time", "type": "date"},
            {"property": "pds:Geometry.pds:latitude", "type": "double"},
        ]
    )
    capabilities = searchable_capabilities(properties)
    assert capabilities["reference_fields"] == ["ref_lid_target"]
    assert "pds:Time.pds:start_date_time" in capabilities["temporal_fields"]
    assert "pds:Geometry.pds:latitude" in capabilities["spatial_fields"]


def test_sampler_builds_archive_plan_and_nlq() -> None:
    target = ContextEntity(
        role="target",
        identifier="urn:nasa:pds:context:target:satellite.earth.moon",
        title="Moon",
    )
    plan = QuerySampler().archive_by_context([target])
    assert plan.constraints[0].field == "ref_lid_target"
    questions = template_questions("collections", [target])
    assert "Moon" in questions["natural"]
