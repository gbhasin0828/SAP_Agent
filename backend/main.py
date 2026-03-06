"""
main.py
Application entry point. Creates the FastAPI app, registers routers, and runs uvicorn.
No tool definitions, no prompts, no agent logic, no database calls.
"""

import asyncio
import sys

# Windows-specific asyncio policy — must be FIRST before any other imports
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.chat import router as chat_router
from routers.approvals import router as approvals_router
from routers.db_routes import router as db_router
from routers.api_routes import router as api_router

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(chat_router)
app.include_router(approvals_router)
app.include_router(db_router)       # prefix="/db" defined on the router itself
app.include_router(api_router)

# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "SAP Agent"}

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)