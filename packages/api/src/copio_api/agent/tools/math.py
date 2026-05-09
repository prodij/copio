from __future__ import annotations

import math
import statistics
from typing import Any

from copio_api.agent.tools.base import Tool, ToolContext, ToolResult


async def _summary_stats_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    raw = args.get("values") or []
    values: list[float] = [float(v) for v in raw if isinstance(v, (int, float))]
    if not values:
        return ToolResult(content={"error": "no_values"})
    n = len(values)
    mean = sum(values) / n
    median = statistics.median(values)
    stdev = statistics.pstdev(values) if n > 1 else 0.0
    return ToolResult(
        content={
            "n": n,
            "mean": mean,
            "median": median,
            "stdev": stdev,
            "min": min(values),
            "max": max(values),
        }
    )


async def _pct_change_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    a = args.get("baseline")
    b = args.get("current")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return ToolResult(content={"error": "invalid_inputs"})
    if a == 0:
        return ToolResult(content={"error": "baseline_zero"})
    pct = (b - a) / a * 100.0
    return ToolResult(
        content={
            "baseline": a,
            "current": b,
            "abs_delta": b - a,
            "pct_change": round(pct, 2),
        }
    )


async def _z_score_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    raw = args.get("baseline_values") or []
    point = args.get("point")
    values: list[float] = [float(v) for v in raw if isinstance(v, (int, float))]
    if not values or not isinstance(point, (int, float)):
        return ToolResult(content={"error": "invalid_inputs"})
    mean = sum(values) / len(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return ToolResult(content={"error": "zero_stdev"})
    z = (float(point) - mean) / stdev
    return ToolResult(
        content={
            "z": round(z, 3),
            "mean": mean,
            "stdev": stdev,
            "anomaly": abs(z) >= 2.0,
        }
    )


MATH_TOOLS: list[Tool] = [
    Tool(
        name="summary_stats",
        description=(
            "Summary statistics over a numeric array (n, mean, median, stdev, min, max). "
            "Use when you need to describe the shape of a series before reasoning about it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Numeric values to summarize.",
                },
            },
            "required": ["values"],
        },
        handler=_summary_stats_handler,
        label="Summary statistics",
    ),
    Tool(
        name="pct_change",
        description=(
            "Compute percent change between a baseline and a current value. "
            "Use for week-over-week, month-over-month deltas."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "baseline": {"type": "number"},
                "current": {"type": "number"},
            },
            "required": ["baseline", "current"],
        },
        handler=_pct_change_handler,
        label="Percent change",
    ),
    Tool(
        name="z_score",
        description=(
            "Compute z-score of a point against a baseline distribution. Use to detect "
            "whether a recent metric is a real anomaly or noise. Anomaly threshold: |z|>=2."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "baseline_values": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "point": {"type": "number"},
            },
            "required": ["baseline_values", "point"],
        },
        handler=_z_score_handler,
        label="Z-score",
    ),
]
