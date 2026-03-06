"""
agents/browser_agent.py
Async generator for the SAP Fiori browser automation + DB agentic loop.
"""

import asyncio
import json
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

from tools.browser_tools import BROWSER_TOOLS, execute_browser_tool
from tools.db_tools import DB_TOOLS, execute_db_tool
from prompts.browser_prompt import SYSTEM_PROMPT, DB_SYSTEM_PROMPT_ADDON

load_dotenv()

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_SAP_URL = os.getenv("SAP_URL", "")
_BROWSER_TOOL_NAMES = {t["name"] for t in BROWSER_TOOLS}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _extract_eq_id(text: str) -> str | None:
    """Return the first EQ-##### token found in text, or None."""
    m = re.search(r'\bEQ-\d+\b', text or "")
    return m.group(0) if m else None


async def _execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Dispatch to browser or DB executor. Injects SAP_URL for launch_browser."""
    if tool_name == "launch_browser":
        return await execute_browser_tool("launch_browser", {"url": _SAP_URL})
    elif tool_name in _BROWSER_TOOL_NAMES:
        return await execute_browser_tool(tool_name, tool_input)
    else:
        return await execute_db_tool(tool_name, tool_input)


async def run_browser_agent(message: str):
    """
    Async generator that runs the full SAP browser + DB agentic loop.
    Yields SSE-formatted strings exactly as the /sap-chat endpoint did.
    Events: thinking, tool_call, screenshot, tool_result, sap_approval,
            sap_update_approval, final, done.
    """
    yield _sse({"type": "thinking", "content": "Analyzing your request..."})
    await asyncio.sleep(0)

    messages = [{"role": "user", "content": message}]
    pending_approval = False
    pending_update_approval = False

    for _ in range(20):
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT + "\n\n" + DB_SYSTEM_PROMPT_ADDON,
            tools=BROWSER_TOOLS + DB_TOOLS,
            messages=messages,
        )

        assistant_content = []
        tool_results = []

        for block in response.content:
            assistant_content.append(block)

            if block.type == "text" and block.text.strip():
                yield _sse({"type": "thinking", "content": block.text})
                await asyncio.sleep(0)

            elif block.type == "tool_use":
                print(f"[TOOL CALL] {block.name} | input: {block.input}")

                yield _sse({
                    "type": "tool_call",
                    "content": f"Calling: {block.name}",
                    "tool": block.name,
                    "input": str(block.input),
                })
                await asyncio.sleep(0)

                try:
                    result = await _execute_tool(block.name, block.input)
                except Exception as e:
                    print(f"[ERROR] _execute_tool({block.name}) raised: {e}")
                    result = {"success": False, "message": str(e), "screenshot": "", "data": {}}

                screenshot = result.get("screenshot", "")
                print(f"[SCREENSHOT] {block.name} returned screenshot length: {len(screenshot)}")

                # Stream screenshot BEFORE tool_result
                if screenshot:
                    yield _sse({
                        "type": "screenshot",
                        "content": f"Screen after {block.name}",
                        "screenshot": screenshot,
                    })
                    await asyncio.sleep(0)

                # Stream descriptive tool result
                if block.name in ("click_element", "get_page_state"):
                    vision_text = (
                        result.get("data", {}).get("vision_after")
                        or result.get("data", {}).get("state")
                        or result.get("message", "")
                    )
                    yield _sse({"type": "tool_result", "content": vision_text})
                else:
                    yield _sse({"type": "tool_result", "content": result.get("message", "")})
                await asyncio.sleep(0)

                # Check if this is a posting action that needs HITL approval
                if block.name == "click_element" and "post" in block.input.get(
                    "element_description", ""
                ).lower():
                    data = result.get("data", {})
                    eq_id_hint = (
                        _extract_eq_id(data.get("vision_after", ""))
                        or _extract_eq_id(data.get("state", ""))
                        or _extract_eq_id(data.get("extracted", ""))
                        or _extract_eq_id(result.get("message", ""))
                    )
                    yield _sse({
                        "type": "sap_approval",
                        "content": "Document ready to post",
                        "summary": data,
                        "equipment_id": eq_id_hint,
                    })
                    await asyncio.sleep(0)
                    pending_approval = True

                elif block.name == "update_equipment_db":
                    eq_id = block.input.get("eq_id", "")
                    updates = block.input.get("updates", {})
                    fields_changed = list(updates.keys())
                    summary = f"Proposed update to {eq_id}: " + ", ".join(
                        f"{k} = {v}" for k, v in updates.items()
                    )
                    yield _sse({
                        "type": "sap_update_approval",
                        "content": summary,
                        "equipment_id": eq_id,
                        "updates": updates,
                        "changed_fields": fields_changed,
                        "summary": summary,
                    })
                    await asyncio.sleep(0)
                    pending_update_approval = True

                # Build tool result for message history
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

        if pending_approval:
            break

        if pending_update_approval:
            break

        if response.stop_reason == "end_turn":
            final_text = " ".join(
                b.text for b in response.content if b.type == "text" and b.text.strip()
            )
            yield _sse({"type": "final", "content": final_text})
            await asyncio.sleep(0)
            break

        if response.stop_reason != "tool_use":
            break

    yield _sse({"type": "done"})
    await asyncio.sleep(0)
