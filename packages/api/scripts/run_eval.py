"""Phase 1.0 manual eval runner.

Loads golden_questions.json, runs each question through the agent (no
streaming — collects full answer + tool-call audit), then asks Opus 4.7
as the judge to score each answer. Writes a score sheet to
artifacts/eval-runs/<timestamp>.json.

Phase 1.0: this is run manually from the founder's laptop, not on a cron.
Phase 1.1 graduates to nightly Inngest cron with regression alerting.

Usage:
    uv run python scripts/run_eval.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `python scripts/run_eval.py` from the api/ directory.
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_API_ROOT / "src"))

from anthropic import AsyncAnthropic  # noqa: E402

from copio_api.agent.llm import LLMClient  # noqa: E402
from copio_api.agent.prompts import HONEST_VOICE_SYSTEM_PROMPT, VOICE_DOC  # noqa: E402
from copio_api.agent.tools import find_tool, tool_definitions  # noqa: E402
from copio_api.agent.tools.base import ToolContext  # noqa: E402
from copio_api.config import get_settings  # noqa: E402

GOLDEN_PATH = _API_ROOT / "tests" / "eval" / "golden_questions.json"
ARTIFACTS_DIR = _API_ROOT.parent.parent / "artifacts" / "eval-runs"

JUDGE_PROMPT = """\
You are evaluating a diagnostic agent's answer against a golden question.

Golden question:
{question}

Expected facts (each one matched gets +1 point, max {n_facts}):
{expected}

Forbidden facts (each one violated subtracts a point):
{forbidden}

Narrative properties to check:
- uncertainty_marker_required: {uncertainty}
- citation_required: {citation}
- voice: {voice}

Agent's answer:
\"\"\"
{answer}
\"\"\"

Score the answer 0-10 across these dimensions, then output JSON exactly:
{{
  "factual_correctness": <0-10>,
  "narrative_coherence": <0-10>,
  "voice_match": <0-10>,
  "uncertainty_calibration": <0-10>,
  "honesty": <0-10>,
  "citation_completeness": <0-10>,
  "overall": <0-10>,
  "violations": [<list of forbidden facts that were violated>],
  "rationale": "<2-sentence explanation>"
}}

Output JSON ONLY. No prose before or after.
"""


async def _run_one_diagnostic(
    *,
    llm: LLMClient,
    question: str,
    model: str,
) -> tuple[str, list[dict[str, Any]], int]:
    """Non-streaming agent loop. Returns (answer_text, tool_calls, cache_read_tokens)."""
    settings = get_settings()
    ctx = ToolContext(tenant_id=settings.founder_tenant_id, settings=settings, spapi_client=None)
    tools = tool_definitions()
    system_blocks = llm.build_system(
        voice_doc=VOICE_DOC,
        system_prompt=HONEST_VOICE_SYSTEM_PROMPT,
        memory_snapshot="MEMORY: (eval run — no prior context)",
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    answer_chunks: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    cache_read_tokens = 0

    for _ in range(4):
        message, stats = await llm.complete_with_tools(
            model=model,
            messages=messages,
            system=system_blocks,
            tools=tools,
            max_tokens=2048,
            temperature=0.4,
        )
        cache_read_tokens += stats.cache_read_input_tokens
        assistant_blocks: list[dict[str, Any]] = []
        tool_uses: list[dict[str, Any]] = []
        for block in message.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                answer_chunks.append(block.text)
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block_type == "tool_use":
                tool_uses.append({"id": block.id, "name": block.name, "input": block.input})
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        if not tool_uses:
            break
        messages.append({"role": "assistant", "content": assistant_blocks})
        results: list[dict[str, Any]] = []
        for use in tool_uses:
            tool = find_tool(use["name"])
            if tool is None:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": use["id"],
                        "is_error": True,
                        "content": json.dumps({"error": "unknown_tool"}),
                    }
                )
                continue
            result = await tool.handler(ctx, use["input"])
            tool_calls.append({"name": use["name"], "input": use["input"], "ok": not result.degraded})
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": use["id"],
                    "is_error": result.degraded,
                    "content": json.dumps(result.content)[:6000],
                }
            )
        messages.append({"role": "user", "content": results})

    return "".join(answer_chunks).strip(), tool_calls, cache_read_tokens


async def _judge(
    client: AsyncAnthropic, *, model: str, question: dict, answer: str
) -> dict[str, Any]:
    judge_prompt = JUDGE_PROMPT.format(
        question=question["question"],
        n_facts=len(question.get("expected_facts", [])),
        expected="\n".join(f"- {f}" for f in question.get("expected_facts", [])) or "(none)",
        forbidden="\n".join(f"- {f}" for f in question.get("forbidden_facts", [])) or "(none)",
        uncertainty=question.get("narrative_properties", {}).get(
            "uncertainty_marker_required", False
        ),
        citation=question.get("narrative_properties", {}).get("citation_required", False),
        voice=question.get("narrative_properties", {}).get("voice", "honest"),
        answer=answer,
    )
    msg = await client.messages.create(
        model=model,
        max_tokens=600,
        temperature=0.0,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"overall": 0, "violations": [], "rationale": f"judge parse error: {text[:200]}"}


def _summarize(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["judge"].get("overall", 0) for r in results]
    n = len(scores) or 1
    return {
        "n": len(scores),
        "mean_score": sum(scores) / n,
        "min_score": min(scores) if scores else 0,
        "below_threshold": sum(1 for s in scores if s < 7.5),
    }


async def main() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        sys.stderr.write("ANTHROPIC_API_KEY not set — cannot run eval.\n")
        sys.exit(2)

    payload = json.loads(GOLDEN_PATH.read_text())
    questions = payload["questions"]

    llm = LLMClient(settings)
    judge_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    judge_model = settings.anthropic_fallback_model

    results: list[dict[str, Any]] = []
    for q in questions:
        print(f"[eval] {q['id']}: {q['question'][:80]}", flush=True)
        try:
            answer, tool_calls, cache_read = await _run_one_diagnostic(
                llm=llm,
                question=q["question"],
                model=settings.anthropic_default_model,
            )
        except (ValueError, RuntimeError) as exc:
            results.append({"id": q["id"], "error": str(exc)})
            continue
        scoring = await _judge(judge_client, model=judge_model, question=q, answer=answer)
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "answer": answer,
                "tool_calls": tool_calls,
                "cache_read_input_tokens": cache_read,
                "judge": scoring,
            }
        )
        print(f"  -> overall={scoring.get('overall')}", flush=True)

    summary = _summarize(results)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / f"{datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2)
    )
    print(f"\n[eval] mean_score={summary['mean_score']:.2f}  below_threshold={summary['below_threshold']}/{summary['n']}")
    print(f"[eval] wrote {out_path}")
    if summary["below_threshold"] > 0 or summary["mean_score"] < 7.5:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
