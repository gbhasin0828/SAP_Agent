"""
database/audit.py
Audit logging, schema inspection, and ad-hoc SELECT query helpers.
"""

import json
import sqlite3
from datetime import datetime

from database.connection import get_connection
from database.crud import get_record_by_id, update_record


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
            """
            PRAGMA table_info` is a SQLite special command that returns metadata about a table's columns — name, type, whether it's nullable etc. Result for `equipment` looks like:
            [{"name": "id", "type": "TEXT"}, {"name": "description", "type": "TEXT"}, ...]
            """
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            schema[table] = [
                {"column": c["name"], "type": c["type"]}
                for c in cols
            ]
    return schema


_SYSTEM_FIELDS = {"id", "created_at", "updated_at", "rowid"}


def execute_write_query(
    table: str,
    record_id,
    updates: dict,
    id_column: str = "id",
) -> dict:
    """
    Update a record using only the fields that already exist on it,
    excluding system-managed columns (id, created_at, updated_at, rowid).

    Returns the updated record dict, or {"error": "..."} on failure.
    """
    existing = get_record_by_id(table, record_id, id_column)
    if existing is None:
        return {"error": "Record not found"}

    allowed_fields = set(existing.keys()) - _SYSTEM_FIELDS

    try:
        result = update_record(table, record_id, updates, allowed_fields, id_column)
        if result is None:
            return {"error": "Record not found"}
        return result
    except Exception as exc:
        return {"error": str(exc)}


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
