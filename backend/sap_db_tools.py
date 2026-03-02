"""
sap_db_tools.py
Claude tool definitions and executor for direct SQLite database access.
"""

from sap_database import (
    get_all_equipment,
    get_equipment_by_id,
    update_equipment,
    get_posted_documents,
)

# ── Tool definitions ───────────────────────────────────────────────────────────

DB_TOOLS = [
    {
        "name": "query_equipment",
        "description": (
            "Query equipment records directly from the database. "
            "Use this for any request that asks to list, search, or filter equipment. "
            "Much faster than browser navigation for read-only data queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plant": {
                    "type": "string",
                    "description": "Filter by plant name, e.g. PLANT-001",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status, e.g. Active, Inactive, Under Maintenance",
                },
                "eq_id": {
                    "type": "string",
                    "description": "Filter by equipment ID (partial match), e.g. EQ-12345",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_equipment_detail",
        "description": (
            "Retrieve full details for a single equipment record by its exact ID. "
            "Use this when the user asks about a specific piece of equipment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "eq_id": {
                    "type": "string",
                    "description": "The exact equipment ID, e.g. EQ-12345",
                }
            },
            "required": ["eq_id"],
        },
    },
    {
        "name": "update_equipment_db",
        "description": (
            "Update fields on an equipment record directly in the database. "
            "Use this when the user wants to change equipment data without a browser posting workflow."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "eq_id": {
                    "type": "string",
                    "description": "The exact equipment ID to update, e.g. EQ-12345",
                },
                "updates": {
                    "type": "object",
                    "description": (
                        "Key-value pairs of fields to update. "
                        "Allowed fields: description, plant, status, last_service_date, "
                        "next_service_date, responsible_person, cost_center, notes"
                    ),
                },
            },
            "required": ["eq_id", "updates"],
        },
    },
    {
        "name": "query_posted_documents",
        "description": (
            "Query posted document records from the database. "
            "Use this to list posting history, optionally filtered by equipment ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "Filter documents by equipment ID, e.g. EQ-12345",
                }
            },
            "required": [],
        },
    },
]

# ── Tool executor ──────────────────────────────────────────────────────────────

async def execute_db_tool(tool_name: str, tool_input: dict) -> dict:
    try:
        if tool_name == "query_equipment":
            data = get_all_equipment(
                plant=tool_input.get("plant"),
                status=tool_input.get("status"),
                eq_id=tool_input.get("eq_id"),
            )
            return {
                "success": True,
                "message": f"Found {len(data)} equipment record(s).",
                "data": data,
                "screenshot": "",
            }

        elif tool_name == "get_equipment_detail":
            record = get_equipment_by_id(tool_input["eq_id"])
            if record is None:
                return {
                    "success": False,
                    "message": f"No equipment found with ID {tool_input['eq_id']}.",
                    "data": {},
                    "screenshot": "",
                }
            return {
                "success": True,
                "message": f"Retrieved details for {tool_input['eq_id']}.",
                "data": record,
                "screenshot": "",
            }

        elif tool_name == "update_equipment_db":
            record = update_equipment(tool_input["eq_id"], tool_input.get("updates", {}))
            if record is None:
                return {
                    "success": False,
                    "message": f"No equipment found with ID {tool_input['eq_id']}.",
                    "data": {},
                    "screenshot": "",
                }
            return {
                "success": True,
                "message": f"Updated {tool_input['eq_id']} successfully.",
                "data": record,
                "screenshot": "",
            }

        elif tool_name == "query_posted_documents":
            data = get_posted_documents(equipment_id=tool_input.get("equipment_id"))
            return {
                "success": True,
                "message": f"Found {len(data)} posted document(s).",
                "data": data,
                "screenshot": "",
            }

        else:
            return {
                "success": False,
                "message": f"Unknown DB tool: {tool_name}",
                "data": {},
                "screenshot": "",
            }

    except Exception as exc:
        return {
            "success": False,
            "message": f"DB tool error: {exc}",
            "data": {},
            "screenshot": "",
        }

# ── System prompt addon ────────────────────────────────────────────────────────

DB_SYSTEM_PROMPT_ADDON = """DATABASE TOOLS:
You also have direct database access tools: query_equipment, get_equipment_detail, update_equipment_db, query_posted_documents.

TOOL SELECTION RULES:
- Prefer DB tools for ALL read queries (listing equipment, searching by plant/status, viewing details, checking posted documents). They are instant and do not require browser navigation.
- Use browser tools (launch_browser, click_element, etc.) only for visual navigation and document posting workflows that require interacting with the SAP Fiori UI.
- Always call query_equipment or get_equipment_detail BEFORE launching the browser if the user is asking for data that can be served from the database.
- If the user asks to post or confirm a document, use the browser workflow."""
