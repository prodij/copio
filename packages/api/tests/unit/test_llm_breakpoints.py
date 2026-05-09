"""Cache-breakpoint placement test.

The 4-breakpoint architecture is silent until you check token usage. This
test verifies the *structure* of the request (4 cache_control markers in
the right places) so a refactor that moves them silently fails CI.
"""
from copio_api.agent.llm import LLMClient, _cached_tools
from copio_api.agent.prompts import HONEST_VOICE_SYSTEM_PROMPT, VOICE_DOC


def test_build_system_has_three_cache_breakpoints() -> None:
    client = LLMClient()
    blocks = client.build_system(
        voice_doc=VOICE_DOC,
        system_prompt=HONEST_VOICE_SYSTEM_PROMPT,
        memory_snapshot="MEMORY: (test)",
    )
    assert len(blocks) == 3
    for block in blocks:
        assert block["type"] == "text"
        assert block["cache_control"] == {"type": "ephemeral"}

    # Ordering matters for cache hit rate (most-stable first, most-variable last).
    assert blocks[0]["text"] == VOICE_DOC
    assert blocks[1]["text"] == HONEST_VOICE_SYSTEM_PROMPT
    assert blocks[2]["text"].startswith("MEMORY:")


def test_cached_tools_marks_only_the_last_tool() -> None:
    fake_tools = [
        {"name": "a", "description": "x", "input_schema": {}},
        {"name": "b", "description": "x", "input_schema": {}},
        {"name": "c", "description": "x", "input_schema": {}},
    ]
    out = _cached_tools(fake_tools)
    assert len(out) == 3
    assert "cache_control" not in out[0]
    assert "cache_control" not in out[1]
    assert out[2]["cache_control"] == {"type": "ephemeral"}


def test_cached_tools_handles_empty() -> None:
    assert _cached_tools([]) == []


def test_total_breakpoints_at_or_below_anthropic_limit() -> None:
    """Anthropic API allows max 4 cache_control markers per request.
    3 in system + 1 in tools = 4. If this ever exceeds 4 the API rejects.
    """
    client = LLMClient()
    blocks = client.build_system(
        voice_doc=VOICE_DOC,
        system_prompt=HONEST_VOICE_SYSTEM_PROMPT,
        memory_snapshot="MEMORY: (test)",
    )
    fake_tools = [{"name": "t", "description": "x", "input_schema": {}}]
    cached = _cached_tools(fake_tools)
    total = sum(1 for b in blocks if "cache_control" in b)
    total += sum(1 for t in cached if "cache_control" in t)
    assert total == 4, f"expected exactly 4 cache breakpoints, got {total}"
