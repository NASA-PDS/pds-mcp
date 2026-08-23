from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import httpx

from .models import QueryPlan, SnapshotManifest
from .query import compile_request, constraint, normalize_lid
from .schema import (
    CONTEXT_LID_PREFIXES,
    REFERENCE_FIELDS,
    parse_properties,
    searchable_capabilities,
)


DEFAULT_API_BASE = "https://pds.nasa.gov/api/search/1"


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def extract_data(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def extract_ids(payloads: Iterable[Any]) -> list[str]:
    identifiers: set[str] = set()
    for payload in payloads:
        for item in extract_data(payload):
            identifier = item.get("lid") or item.get("id") or item.get("lidvid")
            if identifier:
                identifiers.add(normalize_lid(str(identifier)))
    return sorted(identifiers)


def split_kvp_values(value: Any) -> list[str]:
    """Expand the PDS KVP representation of a multi-valued property."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(value)]


class PDSClient:
    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE,
        timeout: float = 60.0,
        page_size: int = 100,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_size = page_size

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/kvp+json"}
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(
                f"{self.base_url}/{path.lstrip('/')}", params=params, headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def execute_plan(self, plan: QueryPlan) -> tuple[dict[str, Any], list[Any]]:
        _, params = compile_request(plan, self.base_url)
        page_size = min(plan.result_limit or self.page_size, self.page_size)
        # The current public deployment rejects the older `start` parameter even
        # though it appears in some API specifications. Cursor pagination with a
        # plain field name (not asc(field)) is accepted by the deployment.
        if not params.get("sort"):
            params["sort"] = "lid"
        pages: list[Any] = []
        fetched = 0
        search_after: str | None = None
        while True:
            page_params = {**params, "limit": page_size}
            if search_after is not None:
                page_params["search-after"] = search_after
            payload = await self.get_json("products", page_params)
            pages.append(payload)
            data = extract_data(payload)
            if len(data) < page_size:
                break
            fetched += len(data)
            if plan.result_limit is not None and fetched >= plan.result_limit:
                break
            last = data[-1].get("lid") or data[-1].get("id")
            if not last or str(last) == search_after:
                raise RuntimeError("PDS cursor pagination did not advance")
            search_after = str(last)
        return params, pages


class SnapshotWriter:
    def __init__(self, output_dir: Path, client: PDSClient) -> None:
        self.output_dir = output_dir
        self.client = client
        self.responses_dir = output_dir / "responses"

    def _write_json(self, relative: str, payload: Any) -> str:
        path = self.output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return stable_hash(payload)

    async def discover(
        self,
        snapshot_id: str,
        include_context: bool = False,
        include_relationships: bool = False,
    ) -> SnapshotManifest:
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        manifest = SnapshotManifest(
            snapshot_id=snapshot_id,
            created_at=datetime.now(UTC),
            api_base_url=self.client.base_url,
        )
        discovered: dict[str, Any] = {}
        for name, path in (("classes", "classes"), ("properties", "properties")):
            payload = await self.client.get_json(path)
            discovered[name] = payload
            digest = self._write_json(f"{name}.json", payload)
            manifest.requests.append(
                {"name": name, "path": path, "response_sha256": digest}
            )
        properties = parse_properties(discovered["properties"])
        capabilities = searchable_capabilities(properties)
        digest = self._write_json("capabilities.json", capabilities)
        manifest.requests.append(
            {
                "name": "derived_capabilities",
                "path": None,
                "response_sha256": digest,
            }
        )
        if include_context:
            for role, prefix in CONTEXT_LID_PREFIXES.items():
                plan = QueryPlan(
                    terminal_product_class="Product_Context",
                    constraints=[constraint(role, "lid", f"{prefix}*", "like")],
                    # Product_Context subclasses do not share every descriptive
                    # field. Request the universally supported projection here;
                    # subclass enrichment is a separate, schema-checked stage.
                    fields=["lid", "title"],
                )
                recorded = await self.record_plan(plan)
                response_path = f"responses/{recorded['request_sha256']}.json"
                pages = json.loads((self.output_dir / response_path).read_text())
                records = [item for page in pages for item in extract_data(page)]
                digest = self._write_json(f"context/{role}.json", records)
                manifest.requests.append(
                    {
                        "name": f"context_{role}",
                        "path": "products",
                        "request_sha256": recorded["request_sha256"],
                        "response_sha256": recorded["response_sha256"],
                        "derived_sha256": digest,
                        "result_count": len(recorded["result_ids"]),
                    }
                )
        if include_relationships:
            relationship_fields = sorted(set(REFERENCE_FIELDS.values()))
            plan = QueryPlan(
                terminal_product_class="Product_Collection",
                fields=["lid", "title", *relationship_fields],
            )
            recorded = await self.record_plan(plan)
            response_path = f"responses/{recorded['request_sha256']}.json"
            pages = json.loads((self.output_dir / response_path).read_text())
            records = [item for page in pages for item in extract_data(page)]
            records_digest = self._write_json("archive/collections.json", records)
            edges: list[dict[str, str]] = []
            role_by_field = {field: role for role, field in REFERENCE_FIELDS.items()}
            for record in records:
                source = record.get("lid") or record.get("id")
                if not source:
                    continue
                for field in relationship_fields:
                    for value in split_kvp_values(record.get(field)):
                        edges.append(
                            {
                                "source": normalize_lid(str(source)),
                                "relationship": role_by_field[field],
                                "target": normalize_lid(str(value)),
                            }
                        )
            edges.sort(key=lambda row: (row["source"], row["relationship"], row["target"]))
            edges_digest = self._write_json("relationships.json", edges)
            manifest.requests.append(
                {
                    "name": "collection_relationships",
                    "path": "products",
                    "request_sha256": recorded["request_sha256"],
                    "response_sha256": recorded["response_sha256"],
                    "records_sha256": records_digest,
                    "edges_sha256": edges_digest,
                    "result_count": len(recorded["result_ids"]),
                    "edge_count": len(edges),
                }
            )
        self._write_json("manifest.json", manifest.model_dump(mode="json"))
        return manifest

    async def record_plan(self, plan: QueryPlan) -> dict[str, Any]:
        _, expected_params = compile_request(plan, self.client.base_url)
        if not expected_params.get("sort"):
            expected_params["sort"] = "lid"
        request_hash = stable_hash(expected_params)
        cached_path = self.responses_dir / f"{request_hash}.json"
        if cached_path.exists():
            pages = json.loads(cached_path.read_text())
            return {
                "request": expected_params,
                "request_sha256": request_hash,
                "response_sha256": stable_hash(pages),
                "result_ids": extract_ids(pages),
                "page_count": len(pages),
                "cache_hit": True,
            }
        params, pages = await self.client.execute_plan(plan)
        request_hash = stable_hash(params)
        response_hash = stable_hash(pages)
        self._write_json(f"responses/{request_hash}.json", pages)
        return {
            "request": params,
            "request_sha256": request_hash,
            "response_sha256": response_hash,
            "result_ids": extract_ids(pages),
            "page_count": len(pages),
            "cache_hit": False,
        }


def discover_snapshot(
    output_dir: Path,
    snapshot_id: str,
    base_url: str,
    include_context: bool = False,
    include_relationships: bool = False,
) -> None:
    writer = SnapshotWriter(output_dir, PDSClient(base_url=base_url))
    asyncio.run(
        writer.discover(
            snapshot_id,
            include_context=include_context,
            include_relationships=include_relationships,
        )
    )
