"""
routers/chat.py
/sap-chat endpoint — delegates entirely to the browser agent.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.browser_agent import run_browser_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/sap-chat")
async def sap_chat(request: ChatRequest):
    return StreamingResponse(
        run_browser_agent(request.message),
        media_type="text/event-stream",
    )
