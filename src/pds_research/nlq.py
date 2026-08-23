from __future__ import annotations

from .sampler import ContextEntity


def template_questions(
    product_label: str, entities: list[ContextEntity]
) -> dict[str, str]:
    names = {entity.role: entity.title for entity in entities}
    parts = []
    if "investigation" in names:
        parts.append(f"from {names['investigation']}")
    if "instrument" in names:
        parts.append(f"collected by {names['instrument']}")
    if "instrument_host" in names:
        parts.append(f"hosted on {names['instrument_host']}")
    if "target" in names:
        parts.append(f"targeting {names['target']}")
    suffix = " ".join(parts)
    explicit = f"Find PDS {product_label} {suffix}.".replace("  ", " ")
    natural = f"Which PDS {product_label} match observations {suffix}?".replace("  ", " ")
    return {"explicit": explicit, "natural": natural}
