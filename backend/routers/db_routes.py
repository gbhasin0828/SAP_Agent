"""
routers/db_routes.py
REST endpoints for direct database access.
All field names for equipment updates are centralised in EQUIPMENT_ALLOWED_FIELDS —
this is the single source of truth for which fields may be written.
"""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from database.crud import get_record_by_id, get_records, update_record

router = APIRouter(prefix="/db")

# ── Per-table field configuration ─────────────────────────────────────────────

EQUIPMENT_ALLOWED_FIELDS: set = {
    "description", "plant", "status", "last_service_date",
    "next_service_date", "responsible_person", "cost_center", "notes",
}

# ── Equipment endpoints ────────────────────────────────────────────────────────

@router.get("/equipment")
async def db_list_equipment(
    plant: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    eq_id: Optional[str] = Query(None),
):
    filters = {"plant": plant, "status": status, "id": eq_id}
    return get_records("equipment", filters)


@router.get("/equipment/{eq_id}")
async def db_get_equipment(eq_id: str):
    record = get_record_by_id("equipment", eq_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return record


@router.post("/equipment/{eq_id}")
async def db_update_equipment(eq_id: str, updates: Dict[str, Any] = Body(...)):
    record = update_record("equipment", eq_id, updates, EQUIPMENT_ALLOWED_FIELDS)
    if record is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return record


# ── Documents endpoint ─────────────────────────────────────────────────────────

@router.get("/documents")
async def db_list_documents(equipment_id: Optional[str] = Query(None)):
    filters = {"equipment_id": equipment_id}
    return get_records("posted_documents", filters)
