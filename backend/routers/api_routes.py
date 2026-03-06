"""

routers/api_routes.py
/api/query endpoint — delegates entirely to the API agent.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.api_agent import stream_api_query

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/api/query")
async def api_query(request: ChatRequest):
    return StreamingResponse(
        stream_api_query(request.message),
        media_type="text/event-stream",
    )
