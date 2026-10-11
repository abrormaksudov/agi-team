"""One user turn: the model calls catalog tools until it can answer; everything streams out as panel events."""

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import anthropic
import httpx

from .om_mcp import McpError, OmMcp, Unauthorized
from .proposals import Proposals
from .tools import clip_result, is_withheld, preview, slim_details, status_label

SYSTEM = (Path(__file__).parent / "prompts" / "system.md").read_text()
MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("AGENT_EFFORT", "low")  # thinking depth; low measured as fast and as correct (eval/)
MAX_LLM_CALLS = 10
# $ per million tokens: input, output. Cache writes cost 1.25x input, cache reads 0.1x.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}


def cost_usd(model: str, u: dict) -> float:
    p_in, p_out = PRICES.get(model, (0.0, 0.0))
    return (u["input"] * p_in + u["cache_write"] * p_in * 1.25 + u["cache_read"] * p_in * 0.1
            + u["output"] * p_out) / 1e6


async def run_turn(client: anthropic.AsyncAnthropic, mcp: OmMcp, tools: list[dict], history: list,
                   proposals: Proposals, owner: tuple[str, str]) -> AsyncIterator[dict]:
    """history ends with the new user message; assistant turns and tool results are appended in place."""
    started = time.monotonic()
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    calls: list[dict] = []
    llm_calls = 0
    stop = "end_turn"

    for llm_calls in range(1, MAX_LLM_CALLS + 1):
        async with client.messages.stream(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=tools, messages=history,
            cache_control={"type": "ephemeral"}, output_config={"effort": EFFORT},
        ) as stream:
            async for event in stream:
                if event.type == "text":
                    yield {"type": "text", "text": event.text}
            msg = await stream.get_final_message()
        u = msg.usage
        usage["input"] += u.input_tokens
        usage["output"] += u.output_tokens
        usage["cache_read"] += u.cache_read_input_tokens or 0
        usage["cache_write"] += u.cache_creation_input_tokens or 0
        history.append({"role": "assistant", "content": msg.content})
        stop = msg.stop_reason or "end_turn"

        if stop == "refusal":
            yield {"type": "error", "message": "The model declined this request."}
            break
        tool_uses = [b for b in msg.content if b.type == "tool_use"]
        if stop != "tool_use" or not tool_uses:
            break

        for b in tool_uses:
            yield {"type": "tool", "name": b.name, "label": status_label(b.name, b.input)}
        results = await asyncio.gather(*(_run_tool(mcp, proposals, owner, b) for b in tool_uses))
        for b, (text, is_error, seconds, extra) in zip(tool_uses, results):
            calls.append({"tool": b.name, "args": preview(b.input), "chars": len(text), "error": is_error,
                          "seconds": round(seconds, 2)})
            if extra:
                yield extra
        history.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": is_error}
            for b, (text, is_error, _, _) in zip(tool_uses, results)]})
    else:
        stop = "step_limit"
        note = f"\n\n_Stopped after {MAX_LLM_CALLS} steps; ask a narrower question to go on._"
        yield {"type": "text", "text": note}
        history.append({"role": "assistant", "content": note.strip()})

    yield {"type": "done", "model": MODEL, "effort": EFFORT, "stop": stop, "llm_calls": llm_calls, "tool_calls": calls,
           "usage": usage, "cost_usd": round(cost_usd(MODEL, usage), 5),
           "seconds": round(time.monotonic() - started, 2)}


async def _run_tool(mcp: OmMcp, proposals: Proposals, owner: tuple[str, str], block) -> tuple[str, bool, float, dict | None]:
    t = time.monotonic()
    if block.name == "propose_change":
        p = proposals.add(owner, block.input)
        text = (f"Proposal {p['id']} is shown to the user as a card with Apply / Discard. Nothing is written until "
                "they click Apply.")
        return text, False, time.monotonic() - t, {"type": "proposal", **proposals.public(p)}
    try:
        text, is_error = await mcp.call_tool(block.name, block.input)
        if block.name == "get_entity_details" and not is_error:
            text = await _details(mcp, block.input, text)
    except Unauthorized:
        raise
    except (McpError, httpx.HTTPError) as e:
        text, is_error = f"Tool failed: {e!r}", True
    return clip_result(text), is_error, time.monotonic() - t, None


async def _details(mcp: OmMcp, args: dict, text: str) -> str:
    """Slim entity JSON; a batch OM withheld as too big is read again one entity at a time, in parallel."""
    entities = args.get("entities") or []
    if is_withheld(text) and len(entities) > 1:
        rest = {k: v for k, v in args.items() if k != "entities"}
        parts = await asyncio.gather(*(mcp.call_tool("get_entity_details", {**rest, "entities": [e]})
                                       for e in entities))
        merged = []
        for (part, part_error), name in zip(parts, entities):
            try:
                merged.extend(json.loads(part).get("entities") or [] if not part_error else [])
            except ValueError:
                part_error = True
            if part_error or is_withheld(part):
                merged.append({"entity": name, "error": "too large or unavailable; read it on its own"})
        text = json.dumps({"entities": merged}, ensure_ascii=False)
    return slim_details(text)
