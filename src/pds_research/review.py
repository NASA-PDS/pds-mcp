from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .benchmark import read_jsonl
from .models import BenchmarkRecord


@dataclass(frozen=True)
class QualityFlag:
    code: str
    message: str


def quality_flags(record: BenchmarkRecord) -> list[QualityFlag]:
    flags: list[QualityFlag] = []
    question = record.question
    words = re.findall(r"\b\w+[\w-]*\b", question)
    if len(words) > 35:
        flags.append(QualityFlag("long_question", f"Question has {len(words)} words."))
    if "urn:" in question.lower():
        flags.append(QualityFlag("ontology_leakage", "Question exposes a raw PDS URN."))
    if any(token in question for token in ("ref_lid_", "product_class", "pds:")):
        flags.append(QualityFlag("schema_leakage", "Question exposes a PDS field name."))
    if "does the PDS have collected by" in question:
        flags.append(QualityFlag("awkward_grammar", "Rewrite the generated 'have collected by' construction."))
    if len(record.relevant_product_ids) > 50:
        flags.append(
            QualityFlag(
                "broad_denotation",
                f"Reference query returns {len(record.relevant_product_ids)} products; check whether exact-set scoring is meaningful.",
            )
        )
    if record.track.value == "archive_retrieval" and not record.required_context_ids:
        flags.append(QualityFlag("missing_context", "Archive question has no context ground truth."))
    return flags


def write_review_report(dataset: Path, output: Path) -> dict[str, int]:
    records = read_jsonl(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    flagged = 0
    lines = [
        "# Pilot NLQ Review Worksheet",
        "",
        "Review each question for naturalness, unambiguous intent, and semantic alignment with the returned identifiers. Automated flags are triage aids, not domain judgments.",
        "",
    ]
    for record in records:
        flags = quality_flags(record)
        flagged += bool(flags)
        lines.extend(
            [
                f"## {record.id}",
                "",
                f"- **Question:** {record.question}",
                f"- **Track/family:** `{record.track.value}` / `{record.query_family}`",
                f"- **Constraints:** {record.difficulty.constraint_count}",
                f"- **Reference results:** {len(record.relevant_product_ids)}",
                f"- **Automated flags:** {', '.join(f'`{flag.code}`' for flag in flags) if flags else 'None'}",
                "- **Reviewer decision:** [ ] Accept  [ ] Rewrite  [ ] Reject",
                "- **Reviewer notes:**",
                "",
            ]
        )
        for flag in flags:
            lines.append(f"  - {flag.message}")
        lines.append("")
    output.write_text("\n".join(lines) + "\n")
    return {"records": len(records), "flagged_records": flagged}

