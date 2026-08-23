#!/usr/bin/env python3
"""Regenerate supporting evaluation figures from committed metric files."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research" / "results"
FIGURES = RESULTS / "figures"


def svg_start(title: str, description: str, width: int = 1200, height: int = 700) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{title}</title><desc>{description}</desc>",
        "<style>text{font-family:Arial,sans-serif;fill:#172033}.title{font-size:28px;font-weight:700}.sub{font-size:15px;fill:#526070}.label{font-size:16px}.value{font-size:14px;font-weight:700}.grid{stroke:#dfe4ea;stroke-width:1}.axis{stroke:#8792a2;stroke-width:1.5}</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="70" y="55">{title}</text>',
        f'<text class="sub" x="70" y="82">{description}</text>',
    ]


def write_svg(name: str, parts: list[str]) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    (FIGURES / name).write_text("\n".join(parts + ["</svg>"]) + "\n")


def difficulty_figure(metrics: dict) -> None:
    groups = [
        ("Single-constraint", metrics["by_reasoning_depth"]["single"]),
        ("Multihop questions", metrics["by_reasoning_depth"]["multi_hop"]),
        ("1 constraint", metrics["by_constraint_count"]["1"]),
        ("2 constraints", metrics["by_constraint_count"]["2"]),
        ("3 constraints", metrics["by_constraint_count"]["3"]),
    ]
    p = svg_start(
        "Full multistep MCP system by question difficulty",
        "Macro F1 and exact result-set match; sample size is shown beneath each group.",
    )
    left, top, bottom, chart_h = 120, 130, 570, 440
    for tick in range(0, 101, 20):
        y = bottom - chart_h * tick / 100
        p += [f'<line class="grid" x1="{left}" y1="{y}" x2="1130" y2="{y}"/>', f'<text x="70" y="{y+5}" class="label">{tick}%</text>']
    p.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{bottom}"/>')
    colors = {"f1": "#1677ff", "exact": "#16a085"}
    for i, (label, values) in enumerate(groups):
        x = 175 + i * 190
        for j, (key, display) in enumerate((("macro_f1", "F1"), ("exact_match", "Exact"))):
            value = values[key] * 100
            h = chart_h * value / 100
            bx = x + j * 55
            p += [f'<rect x="{bx}" y="{bottom-h:.1f}" width="42" height="{h:.1f}" rx="4" fill="{colors["f1" if key == "macro_f1" else "exact"]}"/>', f'<text class="value" text-anchor="middle" x="{bx+21}" y="{bottom-h-8:.1f}">{value:.1f}%</text>']
        p += [f'<text class="label" text-anchor="middle" x="{x+49}" y="605">{label}</text>', f'<text class="sub" text-anchor="middle" x="{x+49}" y="630">n={values["n"]}</text>']
    p += ['<rect x="430" y="660" width="16" height="16" fill="#1677ff"/><text class="label" x="453" y="674">Macro F1</text>', '<rect x="565" y="660" width="16" height="16" fill="#16a085"/><text class="label" x="588" y="674">Exact match</text>']
    write_svg("pds-performance-by-difficulty.svg", p)


def calls_figure(analysis: dict) -> None:
    distribution = {int(k): v for k, v in analysis["tool_calls"]["distribution"].items()}
    exact = {int(k): v["exact_match"] for k, v in analysis["exact_match_by_tool_calls"].items()}
    p = svg_start(
        "Multistep MCP trajectory length",
        "Question count by number of PDS tool calls; dots show exact-match rate within each group.",
    )
    left, bottom, chart_h = 100, 570, 410
    max_n = max(distribution.values())
    for tick in range(0, 101, 20):
        y = bottom - chart_h * tick / 100
        count_tick = round(max_n * tick / 100)
        p += [f'<line class="grid" x1="{left}" y1="{y}" x2="1120" y2="{y}"/>', f'<text class="label" x="45" y="{y+5}">{tick}%</text>', f'<text class="label" x="1135" y="{y+5}">{count_tick}</text>']
    calls = sorted(distribution)
    step = 960 / (len(calls) - 1)
    points = []
    for i, call in enumerate(calls):
        x = 125 + i * step
        h = chart_h * distribution[call] / max_n
        p += [f'<rect x="{x-20:.1f}" y="{bottom-h:.1f}" width="40" height="{h:.1f}" rx="3" fill="#8fbaf5"/>', f'<text class="value" text-anchor="middle" x="{x:.1f}" y="{bottom-h-7:.1f}">{distribution[call]}</text>', f'<text class="label" text-anchor="middle" x="{x:.1f}" y="600">{call}</text>']
        y = bottom - chart_h * exact[call]
        points.append(f"{x:.1f},{y:.1f}")
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#d9485f"/>')
    p += [f'<polyline points="{" ".join(points)}" fill="none" stroke="#d9485f" stroke-width="3"/>', '<text class="sub" transform="rotate(-90 20 365)" text-anchor="middle" x="20" y="365">Exact-match rate</text>', '<text class="sub" transform="rotate(90 1180 365)" text-anchor="middle" x="1180" y="365">Question count</text>', '<text class="label" text-anchor="middle" x="610" y="640">Number of tool calls</text>', '<rect x="430" y="665" width="16" height="16" fill="#8fbaf5"/><text class="label" x="453" y="679">Questions</text>', '<circle cx="575" cy="673" r="6" fill="#d9485f"/><text class="label" x="590" y="679">Exact-match rate</text>']
    write_svg("pds-tool-call-distribution.svg", p)


def errors_figure(comparison: dict) -> None:
    p = svg_start(
        "Identifier-level retrieval errors",
        "False positives and false negatives across the three same-model conditions (log scale).",
    )
    conditions = comparison["conditions"]
    max_log = 4
    left, bottom, chart_h = 125, 570, 400
    for power in range(5):
        y = bottom - chart_h * power / max_log
        p += [f'<line class="grid" x1="{left}" y1="{y}" x2="1120" y2="{y}"/>', f'<text class="label" x="55" y="{y+5}">10^{power}</text>']
    import math
    for i, c in enumerate(conditions):
        center = 285 + i * 315
        for j, (key, color) in enumerate((("false_positives", "#ef8a62"), ("false_negatives", "#b2182b"))):
            value = c[key]
            h = chart_h * math.log10(max(1, value)) / max_log
            x = center - 55 + j * 75
            p += [f'<rect x="{x}" y="{bottom-h:.1f}" width="58" height="{h:.1f}" rx="4" fill="{color}"/>', f'<text class="value" text-anchor="middle" x="{x+29}" y="{bottom-h-8:.1f}">{value:,}</text>']
        p.append(f'<text class="label" text-anchor="middle" x="{center}" y="615">{c["condition"]}</text>')
    p += ['<rect x="430" y="660" width="16" height="16" fill="#ef8a62"/><text class="label" x="453" y="674">False positives</text>', '<rect x="590" y="660" width="16" height="16" fill="#b2182b"/><text class="label" x="613" y="674">False negatives</text>']
    write_svg("pds-retrieval-errors.svg", p)


def main() -> None:
    metrics = json.loads((RESULTS / "codex-live-main-300-gpt-5.6-luna-metrics.json").read_text())
    analysis = json.loads((RESULTS / "codex-live-main-300-tool-call-analysis.json").read_text())
    comparison = json.loads((RESULTS / "three-condition-comparison.json").read_text())
    difficulty_figure(metrics)
    calls_figure(analysis)
    errors_figure(comparison)


if __name__ == "__main__":
    main()
