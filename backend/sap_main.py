
from dotenv import load_dotenv
import os

load_dotenv()  # Make sure this is called BEFORE creating the client
print("API KEY LOADED:", os.getenv("ANTHROPIC_API_KEY"))


import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from anthropic import Anthropic
import asyncio
import json
import os
import re
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from sap_browser import sap_browser
from sap_db_tools import DB_TOOLS, execute_db_tool, DB_SYSTEM_PROMPT_ADDON
from sap_database import (
    get_all_equipment, get_equipment_by_id,
    update_equipment, get_posted_documents,
    post_document,
)

load_dotenv()

SAP_URL = os.getenv("SAP_URL", "")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class ChatRequest(BaseModel):
    message: str


class ApproveRequest(BaseModel):
    equipment_id: Optional[str] = None


def _extract_eq_id(text: str) -> Optional[str]:
    """Return the first EQ-##### token found in text, or None."""
    m = re.search(r'\bEQ-\d+\b', text or "")
    return m.group(0) if m else None


# ── Tool definitions ───────────────────────────────────────────────────────────

SAP_TOOLS = [
    {
        "name": "launch_browser",
        "description": (
            "Launch the SAP browser and navigate to the SAP Fiori login page. "
            "Call this first before any other tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "take_screenshot_and_describe",
        "description": (
            "Take a screenshot of the current SAP screen and get a detailed description of "
            "everything visible including all interactive elements. Use this to understand "
            "current state before deciding next action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "click_element",
        "description": (
            "Click any element on the SAP screen by describing it in natural language. "
            "Vision AI will find and click it. Use for buttons, tiles, links, menu items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "element_description": {
                    "type": "string",
                    "description": (
                        "Natural language description of what to click. Be specific. "
                        "Example: Sign in with Microsoft SSO button, Equipment Management tile, "
                        "Search button, Edit button for EQ-12345"
                    ),
                }
            },
            "required": ["element_description"],
        },
    },
    {
        "name": "fill_field",
        "description": (
            "Type a value into any input field on the SAP screen by describing the field in "
            "natural language. Vision AI will find the field and type the value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field_description": {
                    "type": "string",
                    "description": (
                        "Natural language description of the field. "
                        "Example: Equipment Number search field, Maintenance Notes textarea"
                    ),
                },
                "value": {
                    "type": "string",
                    "description": "The value to type into the field",
                },
            },
            "required": ["field_description", "value"],
        },
    },
    {
        "name": "read_screen_data",
        "description": (
            "Extract specific information from the current SAP screen. Use this to read "
            "table data, form values, document numbers, error messages, or any other "
            "information visible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "what_to_extract": {
                    "type": "string",
                    "description": (
                        "Specific description of what to extract. "
                        "Example: All equipment records from the table, "
                        "The document number from the success page"
                    ),
                }
            },
            "required": ["what_to_extract"],
        },
    },
    {
        "name": "get_page_state",
        "description": (
            "Get a complete analysis of the current page state including what page this is, "
            "what actions are available, and what the logical next step should be. "
            "Use this when unsure what to do next."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent SAP automation agent for Eli Lilly & Company. \
You control a SAP Fiori web application through browser automation.

You have these tools available:
- launch_browser: always call this first
- take_screenshot_and_describe: see current screen
- click_element: click anything on screen
- fill_field: type into any field
- read_screen_data: extract data from screen
- get_page_state: understand current state

IMPORTANT RULES:
1. Always launch_browser first if the browser is not already open
2. After every click wait and check page state
3. Before filling fields always verify you are on the right page
4. NEVER post or confirm documents without emitting a sap_approval event first
5. When ready to post a document STOP and emit sap_approval event with full summary
6. Be methodical - one step at a time
7. If something fails try to understand why by reading the screen before retrying
8. Always report what you see and what you are about to do before doing it

SAP LOGIN:
The SAP Fiori login page has a single button called 'Sign in with Microsoft SSO'
There is NO username or password field
Just click the SSO button and the system will automatically log you in
After clicking SSO button wait 2 seconds for the launchpad to load

STREAMING:
Stream your progress at every step so the user can see what you are doing in real time"""

# ── Tool executor ──────────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name == "launch_browser":
        return await sap_browser.launch_browser(SAP_URL)
    elif tool_name == "take_screenshot_and_describe":
        return await sap_browser.take_screenshot_and_describe()
    elif tool_name == "click_element":
        return await sap_browser.click_element(tool_input["element_description"])
    elif tool_name == "fill_field":
        return await sap_browser.fill_field(
            tool_input["field_description"], tool_input["value"]
        )
    elif tool_name == "read_screen_data":
        return await sap_browser.read_screen_data(tool_input["what_to_extract"])
    elif tool_name == "get_page_state":
        return await sap_browser.get_page_state()
    else:
        return await execute_db_tool(tool_name, tool_input)

# ── SSE helper ─────────────────────────────────────────────────────────────────

def format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

# ── /sap-chat endpoint ─────────────────────────────────────────────────────────

@app.post("/sap-chat")
async def sap_chat(request: ChatRequest):
    async def generate():
        yield format_sse({"type": "thinking", "content": "Analyzing your request..."})
        await asyncio.sleep(0)

        messages = [{"role": "user", "content": request.message}]
        pending_approval = False

        for _ in range(20):
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT + "\n\n" + DB_SYSTEM_PROMPT_ADDON,
                tools=SAP_TOOLS + DB_TOOLS,
                messages=messages,
            )

            # Collect tool use blocks to build the assistant message
            assistant_content = []
            tool_results = []

            for block in response.content:
                assistant_content.append(block)

                if block.type == "text" and block.text.strip():
                    yield format_sse({"type": "thinking", "content": block.text})
                    await asyncio.sleep(0)

                elif block.type == "tool_use":
                    print(f"[TOOL CALL] {block.name} | input: {block.input}")

                    yield format_sse(
                        {
                            "type": "tool_call",
                            "content": f"Calling: {block.name}",
                            "tool": block.name,
                            "input": str(block.input),
                        }
                    )
                    await asyncio.sleep(0)

                    try:
                        result = await execute_tool(block.name, block.input)
                    except Exception as e:
                        print(f"[ERROR] execute_tool({block.name}) raised: {e}")
                        result = {"success": False, "message": str(e), "screenshot": "", "data": {}}

                    screenshot = result.get("screenshot", "")
                    print(f"[SCREENSHOT] {block.name} returned screenshot length: {len(screenshot)}")

                    # Stream screenshot BEFORE tool_result
                    if screenshot:
                        yield format_sse(
                            {
                                "type": "screenshot",
                                "content": f"Screen after {block.name}",
                                "screenshot": screenshot,
                            }
                        )
                        await asyncio.sleep(0)

                    # Stream descriptive tool result
                    if block.name in ("click_element", "get_page_state"):
                        vision_text = (
                            result.get("data", {}).get("vision_after")
                            or result.get("data", {}).get("state")
                            or result.get("message", "")
                        )
                        yield format_sse({"type": "tool_result", "content": vision_text})
                    else:
                        yield format_sse(
                            {"type": "tool_result", "content": result.get("message", "")}
                        )
                    await asyncio.sleep(0)

                    # Check if this is a posting action that needs approval
                    if block.name == "click_element" and "post" in block.input.get(
                        "element_description", ""
                    ).lower():
                        # Try to surface the equipment ID so the frontend can pass it back
                        data = result.get("data", {})
                        eq_id_hint = (
                            _extract_eq_id(data.get("vision_after", ""))
                            or _extract_eq_id(data.get("state", ""))
                            or _extract_eq_id(data.get("extracted", ""))
                            or _extract_eq_id(result.get("message", ""))
                        )
                        yield format_sse(
                            {
                                "type": "sap_approval",
                                "content": "Document ready to post",
                                "summary": data,
                                "equipment_id": eq_id_hint,
                            }
                        )
                        await asyncio.sleep(0)
                        pending_approval = True

                    # Build tool result for message history
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(
                                {
                                    "success": result.get("success"),
                                    "message": result.get("message", ""),
                                    "data": result.get("data", {}),
                                }
                            ),
                        }
                    )

            # Append assistant turn
            messages.append({"role": "assistant", "content": assistant_content})

            # Append tool results as user turn if any tools were called
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            if pending_approval:
                break

            if response.stop_reason == "end_turn":
                final_text = " ".join(
                    b.text for b in response.content if b.type == "text" and b.text.strip()
                )
                yield format_sse({"type": "final", "content": final_text})
                await asyncio.sleep(0)
                break

            # If stop_reason is tool_use, continue the loop
            if response.stop_reason != "tool_use":
                break

        yield format_sse({"type": "done"})
        await asyncio.sleep(0)

    return StreamingResponse(generate(), media_type="text/event-stream")

# ── /approve-sap-post endpoint ─────────────────────────────────────────────────

@app.post("/approve-sap-post")
async def approve_sap_post(request: ApproveRequest = Body(default=ApproveRequest())):
    async def generate():
        equipment_id = request.equipment_id

        yield format_sse({"type": "thinking", "content": "Processing approval..."})
        await asyncio.sleep(0)

        click_result = await sap_browser.click_element("Confirm Post button")
        print(f"[APPROVE] click_element result: {click_result.get('success')} | screenshot length: {len(click_result.get('screenshot', ''))}")

        if click_result.get("screenshot"):
            yield format_sse(
                {
                    "type": "screenshot",
                    "content": "Screen after posting",
                    "screenshot": click_result["screenshot"],
                }
            )
            await asyncio.sleep(0)

        read_result = await sap_browser.read_screen_data(
            "equipment ID, document number and posting confirmation details"
        )

        # Fallback: try to extract equipment_id from the screen if not passed by the caller
        if not equipment_id:
            data = read_result.get("data", {})
            equipment_id = (
                _extract_eq_id(data.get("extracted", ""))
                or _extract_eq_id(data.get("state", ""))
                or _extract_eq_id(read_result.get("message", ""))
            )
            if not equipment_id:
                print("[APPROVE] Warning: could not extract equipment ID from screen data — skipping DB record")

        # Persist the posted document in the database
        doc_number = None
        if equipment_id:
            try:
                db_doc = post_document(equipment_id, posted_by="SAP Agent")
                doc_number = db_doc.get("doc_number")
                print(f"[APPROVE] DB record created: {doc_number} for {equipment_id}")
            except Exception as exc:
                print(f"[APPROVE] Warning: failed to create DB record: {exc}")

        confirmation = read_result.get("data", {}).get("extracted") or read_result.get(
            "message", "Document posted."
        )
        db_note = f"\n\n**DB Document Number:** {doc_number}" if doc_number else ""

        yield format_sse(
            {
                "type": "final",
                "content": f"Document posted successfully.\n\n{confirmation}{db_note}",
            }
        )
        await asyncio.sleep(0)

        if read_result.get("screenshot"):
            yield format_sse(
                {
                    "type": "screenshot",
                    "content": "Confirmation screen",
                    "screenshot": read_result["screenshot"],
                }
            )
            await asyncio.sleep(0)

        # Let the frontend know the DB doc number so it can display it
        if doc_number:
            yield format_sse(
                {
                    "type": "doc_posted",
                    "doc_number": doc_number,
                    "equipment_id": equipment_id,
                }
            )
            await asyncio.sleep(0)

        yield format_sse({"type": "done"})
        await asyncio.sleep(0)

    return StreamingResponse(generate(), media_type="text/event-stream")

# ── /db endpoints ──────────────────────────────────────────────────────────────

@app.get("/db/equipment")
async def db_list_equipment(
    plant: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    eq_id: Optional[str] = Query(None),
):
    return get_all_equipment(plant=plant, status=status, eq_id=eq_id)


@app.get("/db/equipment/{eq_id}")
async def db_get_equipment(eq_id: str):
    record = get_equipment_by_id(eq_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return record


@app.post("/db/equipment/{eq_id}")
async def db_update_equipment(eq_id: str, updates: Dict[str, Any] = Body(...)):
    record = update_equipment(eq_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return record


@app.get("/db/documents")
async def db_list_documents(equipment_id: Optional[str] = Query(None)):
    return get_posted_documents(equipment_id=equipment_id)


# ── /health endpoint ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "SAP Agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("sap_main:app", host="127.0.0.1", port=8000)