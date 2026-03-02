"""
database/audit.py
Audit logging, schema inspection, and ad-hoc SELECT query helpers.
"""

import json
import sqlite3
from datetime import datetime

from database.connection import get_connection


def log_audit_entry(
    action: str,
    equipment_id: str,
    changed_fields: list,
    old_values: dict,
    new_values: dict,
    performed_by: str = "SAP Agent",
) -> dict:
    """Write an audit record to audit_log. Returns the created record metadata."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO audit_log
              (action, equipment_id, changed_fields, old_values, new_values, performed_by, performed_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                action,
                equipment_id,
                json.dumps(changed_fields),
                json.dumps(old_values),
                json.dumps(new_values),
                performed_by,
                now,
            ),
        )
        conn.commit()
    return {
        "id": cursor.lastrowid,
        "action": action,
        "equipment_id": equipment_id,
        "performed_by": performed_by,
        "performed_at": now,
    }


def get_schema_info() -> dict:
    """
    Return column names and declared types for every table in the database.
    Table names are read dynamically — nothing is hardcoded.
    """
    schema = {}
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for row in tables:
            table = row["name"]
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            schema[table] = [
                {"column": c["name"], "type": c["type"]}
                for c in cols
            ]
    return schema


def execute_natural_query(sql: str, params: list = None) -> list[dict] | dict:
    """
    Execute an arbitrary SELECT query and return results as a list of dicts.

    Only SELECT statements are permitted. Any other statement (INSERT, UPDATE,
    DELETE, DROP, …) is rejected immediately without touching the database.

    Returns:
        list[dict]  – one dict per row on success
        dict        – {"error": "…"} on validation failure or runtime error
    """
    stripped = sql.strip()

    # Safety: only allow SELECT
    if not stripped.upper().startswith("SELECT"):
        return {"error": "Only SELECT queries are permitted."}

    # Block obvious multi-statement injection (; followed by anything)
    if ";" in stripped[:-1]:  # allow a trailing semicolon but not mid-query
        return {"error": "Multi-statement queries are not allowed."}

    try:
        with get_connection() as conn:
            rows = conn.execute(stripped, params or []).fetchall()
        if not rows:
            return {"error": "Query executed successfully but returned no results."}
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as exc:
        return {"error": f"SQL error: {exc}"}
    except Exception as exc:
        return {"error": f"Unexpected error: {exc}"}
