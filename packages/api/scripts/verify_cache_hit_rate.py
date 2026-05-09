"""Verify that the 4 explicit prompt-cache breakpoints actually cache.

Phase 1.0 ship gate: cache_hit_rate must be >= 0.80 on the second call
of an identical prompt prefix. Misplaced breakpoints silently degrade
to full-price calls — this script catches that.

Usage:
    uv run python scripts/verify_cache_hit_rate.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_API_ROOT / "src"))

from copio_api.agent.llm import LLMClient  # noqa: E402
from copio_api.agent.prompts import HONEST_VOICE_SYSTEM_PROMPT, VOICE_DOC  # noqa: E402
from copio_api.agent.tools import tool_definitions  # noqa: E402
from copio_api.config import get_settings  # noqa: E402

QUESTION = "What's a high-level summary of how you would diagnose a conversion drop?"
MEMORY_SNAPSHOT = "MEMORY: (cache verification run)"


async def main() -> int:
    settings = get_settings()
    if not settings.anthropic_api_key:
        sys.stderr.write("ANTHROPIC_API_KEY not set.\n")
        return 2

    llm = LLMClient(settings)
    system = llm.build_system(
        voice_doc=VOICE_DOC,
        system_prompt=HONEST_VOICE_SYSTEM_PROMPT,
        memory_snapshot=MEMORY_SNAPSHOT,
    )
    tools = tool_definitions()
    messages = [{"role": "user", "content": QUESTION}]

    print("[cache] cold call (writes the cache)...")
    _, cold = await llm.complete_with_tools(
        model=settings.anthropic_default_model,
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=200,
    )
    print(
        f"  cold: cache_creation={cold.cache_creation_input_tokens} "
        f"cache_read={cold.cache_read_input_tokens}"
    )

    print("[cache] warm call (should hit cache)...")
    _, warm = await llm.complete_with_tools(
        model=settings.anthropic_default_model,
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=200,
    )
    print(
        f"  warm: cache_creation={warm.cache_creation_input_tokens} "
        f"cache_read={warm.cache_read_input_tokens} "
        f"hit_rate={warm.hit_rate:.2f}"
    )

    target = settings.cache_hit_rate_target
    if warm.hit_rate < target:
        print(f"\n[cache] FAIL: hit_rate {warm.hit_rate:.2f} < target {target:.2f}")
        print("        Check breakpoint placement in agent/llm.py:build_system + _cached_tools.")
        return 1
    print(f"\n[cache] PASS: hit_rate {warm.hit_rate:.2f} >= {target:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
