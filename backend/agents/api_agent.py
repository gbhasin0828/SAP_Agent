"""
agents/api_agent.py
Pure-DB agentic query layer — no browser, no screenshots.
Provides both a blocking helper (execute_api_query) and a streaming
async generator (stream_api_query) that emits SSE events.
Schema is fetched fresh on every request via build_api_prompt().
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from tools.db_tools import DB_TOOLS, execute_db_tool
from prompts.api_prompt import build_api_prompt

load_dotenv()

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

# ── Streaming generator ────────────────────────────────────────────────────────

async def stream_api_query(message: str):
    """
    Async generator that yields SSE events for an agentic DB-only loop.
    Events: thinking, tool_call, tool_result, final, done.
    Never yields screenshot events.
    """
    system_prompt = build_api_prompt()

    yield _sse({"type": "thinking", "content": "Querying database..."})

    messages = [{"role": "user", "content": message}]

    for _ in range(10):
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=DB_TOOLS,
            messages=messages,
        )

        assistant_content = []
        tool_results = []

        for block in response.content:
            assistant_content.append(block)

            if block.type == "text" and block.text.strip():
                yield _sse({"type": "thinking", "content": block.text})

            elif block.type == "tool_use":
                yield _sse({
                    "type": "tool_call",
                    "content": f"Calling: {block.name}",
                    "tool": block.name,
                    "input": str(block.input),
                })

                try:
                    result = await execute_db_tool(block.name, block.input)
                except Exception as exc:
                    result = {"success": False, "message": str(exc), "data": {}, "screenshot": ""}

                yield _sse({"type": "tool_result", "content": result.get("message", "")})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps({
                        "success": result.get("success"),
                        "message": result.get("message", ""),
                        "data": result.get("data", {}),
                    }),
                })

        messages.append({"role": "assistant", "content": assistant_content})

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            final_text = " ".join(
                b.text for b in response.content if b.type == "text" and b.text.strip()
            )
            yield _sse({"type": "final", "content": final_text})
            break

        if response.stop_reason != "tool_use":
            break

    yield _sse({"type": "done"})
