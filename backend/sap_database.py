"""
sap_database.py
SQLite database layer for the SAP Fake Equipment Management system.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "sap_equipment.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # safe for concurrent reads
    return conn


def init_db():
    """Create tables and seed initial data if the DB is empty."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id                TEXT PRIMARY KEY,
                description       TEXT NOT NULL,
                plant             TEXT NOT NULL,
                status            TEXT NOT NULL,
                last_service_date TEXT,
                next_service_date TEXT,
                responsible_person TEXT,
                cost_center       TEXT,
                notes             TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_documents (
                doc_number   TEXT PRIMARY KEY,
                equipment_id TEXT NOT NULL,
                plant        TEXT,
                status       TEXT,
                notes        TEXT,
                posted_by    TEXT,
                posted_at    TEXT NOT NULL,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                action         TEXT NOT NULL,
                equipment_id   TEXT NOT NULL,
                changed_fields TEXT,
                old_values     TEXT,
                new_values     TEXT,
                performed_by   TEXT,
                performed_at   TEXT NOT NULL
            )
        """)

        # Seed only if empty
        count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
        if count == 0:
            now = datetime.utcnow().isoformat()
            seed_data = [
                (
                    "EQ-12345", "Industrial Pump Unit", "PLANT-001", "Active",
                    "2025-11-15", "2026-05-15", "John Martinez", "CC-4521",
                    "Last inspection: Nov 2025. All systems operational.", now, now
                ),
                (
                    "EQ-12346", "Conveyor Belt System", "PLANT-002", "Active",
                    "2025-10-20", "2026-04-20", "Maria Chen", "CC-4522",
                    "Routine maintenance completed Oct 2025.", now, now
                ),
                (
                    "EQ-12347", "Pressure Valve Assembly", "PLANT-001", "Inactive",
                    "2025-08-05", "2026-02-05", "Robert Kim", "CC-4523",
                    "Decommissioned pending review. Awaiting reactivation approval.", now, now
                ),
                (
                    "EQ-12348", "Heat Exchanger Unit", "PLANT-003", "Under Maintenance",
                    "2025-09-12", "2026-03-12", "Sarah Johnson", "CC-4524",
                    "Scheduled overhaul in progress.", now, now
                ),
                (
                    "EQ-12349", "Centrifuge Assembly", "PLANT-002", "Active",
                    "2025-12-01", "2026-06-01", "David Lee", "CC-4525",
                    "New unit installed Dec 2025. All checks passed.", now, now
                ),
            ]
            conn.executemany("""
                INSERT INTO equipment
                  (id, description, plant, status, last_service_date, next_service_date,
                   responsible_person, cost_center, notes, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, seed_data)
            conn.commit()
            print(f"[DB] Seeded {len(seed_data)} equipment records.")
        else:
            print(f"[DB] Database already has {count} equipment records.")


# ── CRUD helpers ───────────────────────────────────────────────────────────────

def get_all_equipment(plant: str = None, status: str = None, eq_id: str = None) -> list[dict]:
    query = "SELECT * FROM equipment WHERE 1=1"
    params = []
    if plant:
        query += " AND plant = ?"
        params.append(plant)
    if status:
        query += " AND LOWER(status) = LOWER(?)"
        params.append(status)
    if eq_id:
        query += " AND id LIKE ?"
        params.append(f"%{eq_id}%")
    query += " ORDER BY id"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_equipment_by_id(eq_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM equipment WHERE id = ?", (eq_id,)).fetchone()
    return dict(row) if row else None


def update_equipment(eq_id: str, updates: dict) -> dict | None:
    """Update allowed fields on an equipment record. Returns updated record."""
    allowed = {
        "description", "plant", "status", "last_service_date",
        "next_service_date", "responsible_person", "cost_center", "notes"
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}

    # Fetch existing record BEFORE updating so old values can be captured
    old_record = get_equipment_by_id(eq_id)
    if old_record is None:
        return None

    if not filtered:
        return old_record

    filtered["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    values = list(filtered.values()) + [eq_id]

    with get_connection() as conn:
        conn.execute(f"UPDATE equipment SET {set_clause} WHERE id = ?", values)
        conn.commit()
    return get_equipment_by_id(eq_id)


def post_document(equipment_id: str, posted_by: str = "Demo User") -> dict:
    """Create a posted document record and return it."""
    import random
    doc_number = f"DOC-2026-{random.randint(1000, 9999)}"
    now = datetime.utcnow().isoformat()
    eq = get_equipment_by_id(equipment_id)

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO posted_documents
              (doc_number, equipment_id, plant, status, notes, posted_by, posted_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            doc_number, equipment_id,
            eq["plant"] if eq else None,
            eq["status"] if eq else None,
            eq["notes"] if eq else None,
            posted_by, now
        ))
        conn.commit()

    return {
        "doc_number": doc_number,
        "equipment_id": equipment_id,
        "posted_by": posted_by,
        "posted_at": now,
    }


def log_audit_entry(
    action: str,
    equipment_id: str,
    changed_fields: list,
    old_values: dict,
    new_values: dict,
    performed_by: str = "SAP Agent",
) -> dict:
    """Write an audit record to audit_log. Returns the created record metadata."""
    import json as _json
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO audit_log
              (action, equipment_id, changed_fields, old_values, new_values, performed_by, performed_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            action,
            equipment_id,
            _json.dumps(changed_fields),
            _json.dumps(old_values),
            _json.dumps(new_values),
            performed_by,
            now,
        ))
        conn.commit()
    return {
        "id": cursor.lastrowid,
        "action": action,
        "equipment_id": equipment_id,
        "performed_by": performed_by,
        "performed_at": now,
    }


def get_posted_documents(equipment_id: str = None) -> list[dict]:
    query = "SELECT * FROM posted_documents"
    params = []
    if equipment_id:
        query += " WHERE equipment_id = ?"
        params.append(equipment_id)
    query += " ORDER BY posted_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Natural-language / ad-hoc query helpers ────────────────────────────────────

def get_schema_info() -> dict:
    """Return column names and declared types for all application tables."""
    tables = ["equipment", "posted_documents"]
    schema = {}
    with get_connection() as conn:
        for table in tables:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            schema[table] = [
                {"column": r["name"], "type": r["type"]}
                for r in rows
            ]
    return schema


def execute_natural_query(sql: str, params: list = None) -> list[dict] | dict:
    """
    Execute an arbitrary SELECT query and return results as a list of dicts.

    Only SELECT statements are permitted.  Any other statement (INSERT, UPDATE,
    DELETE, DROP, …) is rejected immediately without touching the database.

    Returns:
        list[dict]  – one dict per row on success
        dict        – {"error": "…"} on validation failure or runtime error
    """
    stripped = sql.strip()

    # Safety: only allow SELECT
    if not stripped.upper().startswith("SELECT"):
        return {"error": "Only SELECT queries are permitted."}

    # Block obvious multi-statement injection ( ; followed by anything )
    if ";" in stripped[:-1]:          # allow a trailing semicolon but not mid-query
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


# Initialise on import
init_db()
