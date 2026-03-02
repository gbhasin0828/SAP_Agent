"""
routers/approvals.py
HITL approval endpoints — document posting and equipment update confirmation.
No agentic logic; pure endpoint handlers.
"""

import asyncio
import json
import random
import re
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.crud import get_record_by_id, insert_record, update_record
from database.audit import log_audit_entry
from routers.db_routes import EQUIPMENT_ALLOWED_FIELDS
from sap_browser import sap_browser

router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    equipment_id: Optional[str] = None


class UpdateApproveRequest(BaseModel):
    equipment_id: str
    updates: Dict[str, Any]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _extract_eq_id(text: str) -> str | None:
    """Return the first EQ-##### token found in text, or None."""
    m = re.search(r'\bEQ-\d+\b', text or "")
    return m.group(0) if m else None


def _post_document(equipment_id: str, posted_by: str = "SAP Agent") -> dict:
    """Create a posted document record using generic crud functions."""
    doc_number = f"DOC-2026-{random.randint(1000, 9999)}"
    now = datetime.utcnow().isoformat()
    eq = get_record_by_id("equipment", equipment_id)
    return insert_record("posted_documents", {
        "doc_number": doc_number,
        "equipment_id": equipment_id,
        "plant": eq["plant"] if eq else None,
        "status": eq["status"] if eq else None,
        "notes": eq["notes"] if eq else None,
        "posted_by": posted_by,
        "posted_at": now,
    })


# ── /approve-sap-post ──────────────────────────────────────────────────────────

@router.post("/approve-sap-post")
async def approve_sap_post(request: ApproveRequest = Body(default=ApproveRequest())):
    async def generate():
        equipment_id = request.equipment_id

        yield _sse({"type": "thinking", "content": "Processing approval..."})
        await asyncio.sleep(0)

        click_result = await sap_browser.click_element("Confirm Post button")
        print(
            f"[APPROVE] click_element result: {click_result.get('success')} | "
            f"screenshot length: {len(click_result.get('screenshot', ''))}"
        )

        if click_result.get("screenshot"):
            yield _sse({
                "type": "screenshot",
                "content": "Screen after posting",
                "screenshot": click_result["screenshot"],
            })
            await asyncio.sleep(0)

        read_result = await sap_browser.read_screen_data(
            "equipment ID, document number and posting confirmation details"
        )

        # Fallback: extract equipment_id from screen if not supplied by caller
        if not equipment_id:
            data = read_result.get("data", {})
            equipment_id = (
                _extract_eq_id(data.get("extracted", ""))
                or _extract_eq_id(data.get("state", ""))
                or _extract_eq_id(read_result.get("message", ""))
            )
            if not equipment_id:
                print("[APPROVE] Warning: could not extract equipment ID — skipping DB record")

        # Persist the posted document
        doc_number = None
        if equipment_id:
            try:
                db_doc = _post_document(equipment_id, posted_by="SAP Agent")
                doc_number = db_doc.get("doc_number")
                print(f"[APPROVE] DB record created: {doc_number} for {equipment_id}")
            except Exception as exc:
                print(f"[APPROVE] Warning: failed to create DB record: {exc}")

        confirmation = read_result.get("data", {}).get("extracted") or read_result.get(
            "message", "Document posted."
        )
        db_note = f"\n\n**DB Document Number:** {doc_number}" if doc_number else ""

        yield _sse({
            "type": "final",
            "content": f"Document posted successfully.\n\n{confirmation}{db_note}",
        })
        await asyncio.sleep(0)

        if read_result.get("screenshot"):
            yield _sse({
                "type": "screenshot",
                "content": "Confirmation screen",
                "screenshot": read_result["screenshot"],
            })
            await asyncio.sleep(0)

        if doc_number:
            yield _sse({
                "type": "doc_posted",
                "doc_number": doc_number,
                "equipment_id": equipment_id,
            })
            await asyncio.sleep(0)

        yield _sse({"type": "done"})
        await asyncio.sleep(0)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── /approve-sap-update ────────────────────────────────────────────────────────

@router.post("/approve-sap-update")
async def approve_sap_update(request: UpdateApproveRequest):
    async def generate():
        equipment_id = request.equipment_id
        updates = request.updates

        yield _sse({"type": "thinking", "content": "Processing update approval..."})
        await asyncio.sleep(0)

        old_record = get_record_by_id("equipment", equipment_id)
        if old_record is None:
            yield _sse({"type": "error", "content": f"Equipment {equipment_id} not found."})
            yield _sse({"type": "done"})
            await asyncio.sleep(0)
            return

        new_record = update_record("equipment", equipment_id, updates, EQUIPMENT_ALLOWED_FIELDS)

        changed_fields = [k for k in updates if k in EQUIPMENT_ALLOWED_FIELDS]
        old_values = {k: old_record.get(k) for k in changed_fields}
        new_values = {k: new_record.get(k) for k in changed_fields}

        try:
            log_audit_entry(
                action="update",
                equipment_id=equipment_id,
                changed_fields=changed_fields,
                old_values=old_values,
                new_values=new_values,
                performed_by="SAP Agent",
            )
        except Exception as exc:
            print(f"[AUDIT] Warning: failed to write audit log: {exc}")

        changes_text = "\n".join(
            f"- **{k}**: {old_values.get(k)} → {new_values.get(k)}"
            for k in changed_fields
        )
        confirmation = f"Equipment **{equipment_id}** updated successfully.\n\n{changes_text}"

        yield _sse({"type": "final", "content": confirmation})
        await asyncio.sleep(0)
        yield _sse({"type": "done"})
        await asyncio.sleep(0)

    return StreamingResponse(generate(), media_type="text/event-stream")
