from __future__ import annotations

from typing import Any, Iterable

from .query import PropertySpec


KNOWN_PRODUCT_CLASSES = {
    "Product_Bundle",
    "Product_Collection",
    "Product_Context",
    "Product_Observational",
}

CONTEXT_LID_PREFIXES = {
    "investigation": "urn:nasa:pds:context:investigation:",
    "target": "urn:nasa:pds:context:target:",
    "instrument": "urn:nasa:pds:context:instrument:",
    "instrument_host": "urn:nasa:pds:context:instrument_host:",
    "facility": "urn:nasa:pds:context:facility:",
}

REFERENCE_FIELDS = {
    "investigation": "ref_lid_investigation",
    "target": "ref_lid_target",
    "instrument": "ref_lid_instrument",
    "instrument_host": "ref_lid_instrument_host",
}


def parse_properties(payload: Iterable[dict[str, Any]]) -> dict[str, PropertySpec]:
    parsed: dict[str, PropertySpec] = {}
    for row in payload:
        name = row.get("property")
        if name:
            parsed[str(name)] = PropertySpec(
                name=str(name), data_type=str(row.get("type")) if row.get("type") else None
            )
    return parsed


def searchable_capabilities(properties: Iterable[str]) -> dict[str, list[str]]:
    names = sorted(set(properties))
    return {
        "reference_fields": [name for name in names if name.startswith("ref_lid_")],
        "temporal_fields": [
            name for name in names if any(token in name.lower() for token in ("date", "time"))
        ],
        "spatial_fields": [
            name
            for name in names
            if any(token in name.lower() for token in ("latitude", "longitude", "coordinate"))
        ],
        "science_fields": [
            name
            for name in names
            if any(token in name.lower() for token in ("science", "discipline", "processing_level"))
        ],
    }

