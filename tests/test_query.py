import pytest

from pds_research.models import QueryPlan
from pds_research.query import (
    QueryValidationError,
    canonical_plan,
    compile_expression,
    constraint,
    normalize_lid,
    validate_plan,
)


def test_normalize_lid_removes_version() -> None:
    assert normalize_lid("urn:nasa:pds:item::1.2") == "urn:nasa:pds:item"


def test_canonical_plan_ignores_constraint_order() -> None:
    one = QueryPlan(
        terminal_product_class="Product_Collection",
        constraints=[constraint("target", "ref_lid_target", "moon"), constraint("instrument", "ref_lid_instrument", "pse")],
    )
    two = QueryPlan(
        terminal_product_class="Product_Collection",
        constraints=list(reversed(one.constraints)),
    )
    assert canonical_plan(one) == canonical_plan(two)


def test_compile_expression_contains_product_class_and_constraints() -> None:
    plan = QueryPlan(
        terminal_product_class="Product_Collection",
        constraints=[constraint("target", "ref_lid_target", "urn:nasa:pds:moon")],
    )
    expression = compile_expression(plan)
    assert 'product_class eq "Product_Collection"' in expression
    assert 'ref_lid_target eq "urn:nasa:pds:moon"' in expression


def test_validate_plan_rejects_unknown_fields() -> None:
    plan = QueryPlan(
        terminal_product_class="Product_Collection",
        constraints=[constraint("target", "invented_field", "moon")],
    )
    with pytest.raises(QueryValidationError):
        validate_plan(plan, {"ref_lid_target": {}}, {"Product_Collection"})

