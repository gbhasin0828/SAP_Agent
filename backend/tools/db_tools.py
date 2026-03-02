"""
tools/db_tools.py
Claude tool definitions and executor for direct SQLite database access.
"""

from database.crud import get_record_by_id, update_record
from database.audit import execute_natural_query

# ── Allowed update fields ──────────────────────────────────────────────────────

_EQUIPMENT_ALLOWED_FIELDS = {
    "description", "plant", "status", "last_service_date",
    "next_service_date", "responsible_person", "cost_center", "notes",
}

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
        "name": "execute_sql_query",
        "description": (
            "Execute a SELECT-only SQL query directly against the database. "
            "Use this for complex filtering, aggregation, or joins not covered by other tools. "
            "Always check the schema before writing SQL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SELECT-only SQL query to run against the database. Only SELECT statements are permitted.",
                }
            },
            "required": ["sql"],
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
            conditions = ["1=1"]
            params = []
            if plant := tool_input.get("plant"):
                conditions.append("plant = ?")
                params.append(plant)
            if status := tool_input.get("status"):
                conditions.append("LOWER(status) = LOWER(?)")
                params.append(status)
            if eq_id := tool_input.get("eq_id"):
                conditions.append("id LIKE ?")
                params.append(f"%{eq_id}%")
            sql = f"SELECT * FROM equipment WHERE {' AND '.join(conditions)} ORDER BY id"
            result = execute_natural_query(sql, params)
            if isinstance(result, dict) and "error" in result:
                return {"success": False, "message": result["error"], "data": {}, "screenshot": ""}
            return {
                "success": True,
                "message": f"Found {len(result)} equipment record(s).",
                "data": result,
                "screenshot": "",
            }

        elif tool_name == "get_equipment_detail":
            record = get_record_by_id("equipment", tool_input["eq_id"])
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
            record = update_record(
                "equipment",
                tool_input["eq_id"],
                tool_input.get("updates", {}),
                _EQUIPMENT_ALLOWED_FIELDS,
            )
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

        elif tool_name == "execute_sql_query":
            result = execute_natural_query(tool_input["sql"])
            if isinstance(result, dict) and "error" in result:
                return {
                    "success": False,
                    "message": result["error"],
                    "data": {},
                    "screenshot": "",
                }
            return {
                "success": True,
                "message": f"Query returned {len(result)} rows.",
                "data": result,
                "screenshot": "",
            }

        elif tool_name == "query_posted_documents":
            equipment_id = tool_input.get("equipment_id")
            if equipment_id:
                sql = (
                    "SELECT * FROM posted_documents WHERE equipment_id = ? "
                    "ORDER BY posted_at DESC"
                )
                result = execute_natural_query(sql, [equipment_id])
            else:
                result = execute_natural_query(
                    "SELECT * FROM posted_documents ORDER BY posted_at DESC"
                )
            if isinstance(result, dict) and "error" in result:
                # No results is not a failure for this tool
                if "no results" in result["error"].lower():
                    return {"success": True, "message": "Found 0 posted document(s).", "data": [], "screenshot": ""}
                return {"success": False, "message": result["error"], "data": [], "screenshot": ""}
            return {
                "success": True,
                "message": f"Found {len(result)} posted document(s).",
                "data": result,
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
You also have direct database access tools: query_equipment, get_equipment_detail, update_equipment_db, query_posted_documents, execute_sql_query.

TOOL SELECTION RULES:
- Prefer DB tools for ALL read queries (listing equipment, searching by plant/status, viewing details, checking posted documents). They are instant and do not require browser navigation.
- Use browser tools (launch_browser, click_element, etc.) only for visual navigation and document posting workflows that require interacting with the SAP Fiori UI.
- Always call query_equipment or get_equipment_detail BEFORE launching the browser if the user is asking for data that can be served from the database.
- If the user asks to post or confirm a document, use the browser workflow."""
