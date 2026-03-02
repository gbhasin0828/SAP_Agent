"""
database/connection.py
SQLite connection factory and database path.
"""

import os
import sqlite3

# DB lives one level up from this package (i.e. backend/sap_equipment.db)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sap_equipment.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # safe for concurrent reads
    return conn
