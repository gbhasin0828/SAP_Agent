"""
tools/db_tools.py
Claude tool definitions and executor for direct SQLite database access.
Generic — no hardcoded table names, column names, or domain concepts.
"""

from database.audit import execute_natural_query, execute_write_query

# ── Tool definitions ───────────────────────────────────────────────────────────

DB_TOOLS = [
    {
        "name": "execute_sql_query",
        "description": (
            "Execute a SELECT-only SQL query directly against the database. "
            "Use this to read, search, filter, aggregate, or join any data. "
            "Always inspect the schema before writing SQL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": (
                        "A SELECT-only SQL query to run against the database. "
                        "Only SELECT statements are permitted."
                    ),
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "execute_db_write",
        "description": (
            "Update an existing record in any database table. "
            "Only fields that already exist on the record may be changed; "
            "system fields (id, created_at, updated_at) are always protected. "
            "Use execute_sql_query first to confirm the record exists and note its exact field names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "The table to update, e.g. equipment or posted_documents.",
                },
                "record_id": {
                    "type": "string",
                    "description": "The primary-key value of the record to update.",
                },
                "updates": {
                    "type": "object",
                    "description": (
                        "Key-value pairs of fields to update. "
                        "Keys must match existing column names on the record."
                    ),
                },
            },
            "required": ["table", "record_id", "updates"],
        },
    },
]

# ── Tool executor ──────────────────────────────────────────────────────────────

async def execute_db_tool(tool_name: str, tool_input: dict) -> dict:
    try:
        if tool_name == "execute_sql_query":
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
                "message": f"Query returned {len(result)} row(s).",
                "data": result,
                "screenshot": "",
            }

        elif tool_name == "execute_db_write":
            result = execute_write_query(
                tool_input["table"],
                tool_input["record_id"],
                tool_input.get("updates", {}),
            )
            if isinstance(result, dict) and "error" in result:
                return {
                    "success": False,
                    "message": result["error"],
                    "data": {},
                    "screenshot": "",
                }
            return {
                "success": True,
                "message": f"Record {tool_input['record_id']} in {tool_input['table']} updated successfully.",
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
You also have direct database access tools: execute_sql_query, execute_db_write.

TOOL SELECTION RULES:
- Use execute_sql_query for ALL read queries — listing, searching, filtering, or aggregating any data. It is instant and does not require browser navigation.
- Use execute_db_write to update an existing record in any table. Always run execute_sql_query first to confirm the record exists and to get exact field names before writing.
- Use browser tools (launch_browser, click_element, etc.) only for visual navigation and document posting workflows that require interacting with the SAP Fiori UI.
- If the user asks to post or confirm a document, use the browser workflow."""
