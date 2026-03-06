"""
database/crud.py
Generic, table-agnostic CRUD helpers.
No references to specific table names or column names.
"""

from datetime import datetime

from database.connection import get_connection


def get_records(table: str, filters: dict = None) -> list[dict]:
    """
    SELECT all rows from *table*, optionally filtered by equality on each
    key/value pair in *filters* (None values are skipped).
    Returns a list of dicts.
    """
    query = f"SELECT * FROM {table} WHERE 1=1"
    params = []
    if filters:
        for column, value in filters.items():
            if value is not None:
                query += f" AND {column} = ?"
                params.append(value)
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_record_by_id(
    table: str,
    record_id,
    id_column: str = "id",
) -> dict | None:
    """Return a single row as a dict, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {id_column} = ?",
            (record_id,),
        ).fetchone()
    return dict(row) if row else None


def update_record(
    table: str,
    record_id,
    updates: dict,
    allowed_fields: set,
    id_column: str = "id",
) -> dict | None:
    """
    Update *allowed_fields* on the row identified by *record_id*.
    Returns the updated row dict, or None if the row does not exist.
    """
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}
    existing = get_record_by_id(table, record_id, id_column)
    if existing is None:
        return None
    if not filtered:
        return existing

    filtered["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    values = list(filtered.values()) + [record_id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?",
            values,
        )
        conn.commit()
    return get_record_by_id(table, record_id, id_column)


def insert_record(table: str, data: dict) -> dict:
    """
    Insert a row built from *data* and return the inserted row.
    For text PKs supply an "id" key; for auto-increment PKs the row is
    fetched back via the SQLite rowid.
    """
    columns = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        conn.commit()
        if "id" in data:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE id = ?", (data["id"],)
            ).fetchone()
        else:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE rowid = ?", (cursor.lastrowid,)
            ).fetchone()
    return dict(row) if row else dict(data)
