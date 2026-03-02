"""
database/models.py
Table creation and initial seed data.
"""

from datetime import datetime

from database.connection import get_connection


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


# Initialise on import
init_db()
