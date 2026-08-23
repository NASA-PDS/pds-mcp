import asyncio

from pds_research.models import QueryPlan
from pds_research.snapshot import PDSClient, split_kvp_values


def test_split_kvp_values_expands_pipe_delimited_fields() -> None:
    assert split_kvp_values("urn:a|urn:b") == ["urn:a", "urn:b"]


def test_execute_plan_uses_search_after(monkeypatch) -> None:
    client = PDSClient(page_size=2)
    seen = []

    async def fake_get_json(path, params):
        seen.append(params)
        if "search-after" not in params:
            return {"data": [{"lid": "a"}, {"lid": "b"}]}
        return {"data": [{"lid": "c"}]}

    monkeypatch.setattr(client, "get_json", fake_get_json)
    _, pages = asyncio.run(
        client.execute_plan(QueryPlan(terminal_product_class="Product_Context"))
    )
    assert len(pages) == 2
    assert "start" not in seen[0]
    assert seen[0]["sort"] == "lid"
    assert seen[1]["search-after"] == "b"
