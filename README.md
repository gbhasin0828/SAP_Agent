# Generic Intelligent SAP Agent

> AI-powered SAP automation agent built with Claude AI, Playwright browser automation, and Claude Vision. Enables natural language interaction with SAP Fiori — no manual clicking required.

---

## Overview

The Generic Intelligent SAP Agent is a prototype demonstration of how AI agents can automate SAP S/4HANA workflows through intelligent browser automation. A user types a natural language instruction, and the agent autonomously navigates SAP Fiori, reads screens using Claude Vision, interacts with forms, and streams live progress back to the user — including screenshots of every step.

All document posting actions require explicit human approval before execution, implementing the Human-in-the-Loop (HITL) safety pattern required for enterprise AI.

---

## What It Demonstrates

- Natural language instructions driving SAP automation
- Claude Vision reading and understanding SAP Fiori screens dynamically
- No hardcoded selectors — the agent finds elements intelligently
- Live screenshot streaming showing the agent working in real time
- Human-in-the-Loop approval before any document is posted
- Professional Generic branded UI
- Foundation for production SAP API integration via MCP

################################################################################################################
What you can demonstrate:

Demo 1 — Data Discovery:
"Login to SAP and show me all equipment"
→ Agent reads and summarizes entire table

Demo 2 — Intelligent Analysis:
"Find EQ-12347 and tell me why it is inactive"
→ Agent finds inconsistencies humans might miss

Demo 3 — Data Entry (try this next):
"Update the maintenance notes for EQ-12347
 to say: Status reviewed February 2026.
 Equipment cleared for reactivation."
→ Agent fills the field and saves

Demo 4 — HITL Posting (the safety demo):
"Update EQ-12347 status to Active
 and post the document"
→ Agent prepares everything
→ STOPS for human approval
→ You approve
→ Document posted

###########################################################################################################################

---

## Architecture

```
User Chat UI (sap_agent.html)
        ↓
FastAPI Backend (sap_main.py)
        ↓
Claude Agent Brain (claude-sonnet-4-6)
        ↓
Browser Tools (sap_browser.py)
        ↓
Playwright → Chrome Browser → SAP Fiori UI
```

### Key Components

| File | Purpose |
|---|---|
| `frontend/sap_agent.html` | Split-screen chat UI with live SAP screen view |
| `frontend/fake_sap.html` | Simulated SAP Fiori UI for demo purposes |
| `backend/sap_main.py` | FastAPI backend with Claude agent loop and SSE streaming |
| `backend/sap_browser.py` | Generic browser controller using Playwright and Claude Vision |
| `backend/setup_database.py` | Creates SQLite sample database |
| `backend/setup_excel.py` | Creates sample Excel device inventory |

---

## Prerequisites

- Python 3.13+
- Node.js (optional, for frontend development)
- Anthropic API key
- macOS, Windows, or Linux

---

## Installation

### 1. Set up Python virtual environment

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install fastapi uvicorn anthropic python-dotenv
pip install playwright pillow python-multipart
playwright install chromium
```

### 3. Configure environment variables

Create a `.env` file in the `backend` folder:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
SAP_URL=http://localhost:8001/fake_sap.html
SAP_USERNAME=demo
SAP_PASSWORD=demo123
```

---

## Running the Demo

You need **two terminal windows** running simultaneously.

### Terminal 1 — Frontend Server

```bash
cd /path/to/sap-agent
source backend/venv/bin/activate  # Mac
venv\Scripts\activate         # Windows
python -m http.server 8001 --directory frontend
or 
python -m http.server 8001    # if running inside frontend

```

Expected output:
```
Serving HTTP on :: port 8001 (http://[::]:8001/) ...
```

### Terminal 2 — Backend Server

```bash
cd /path/to/sap-agent/backend
source venv/bin/activate
venv\Scripts\activate         # Windows
uvicorn sap_main:app --reload --port 8000
```

Expected output:
```
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Application startup complete.
```

### Open the UI

```
http://localhost:8001/sap_agent.html
```

### Verify backend is running

```
http://localhost:8000/health
```

Should return: `{"status": "ok", "service": "SAP Agent"}`

---

## Sample Instructions to Try

Type these in the agent chat input:

```
Login to SAP and show me all equipment
```

```
Find equipment EQ-12347 and tell me why it is inactive
```

```
Open EQ-12345 and update the maintenance notes
to say: Inspection completed February 2026,
all systems operational
```

```
Show me all equipment in PLANT-001
and identify any that need attention
```

```
Find EQ-12347, update notes, and post the service document
```

---

## How It Works

### Agent Loop

```
1. User types natural language instruction
2. FastAPI receives instruction via POST /sap-chat
3. Claude agent receives instruction with 6 tools available
4. Claude decides which tool to call based on instruction
5. Tool executes via Playwright browser
6. Result including screenshot streams back via SSE
7. UI updates left panel (activity) and right panel (SAP screen)
8. Loop continues until task complete
9. HITL approval required before any document posting
```

### Available Agent Tools

| Tool | What It Does |
|---|---|
| `launch_browser` | Opens Chrome and navigates to SAP Fiori |
| `take_screenshot_and_describe` | Takes screenshot and asks Claude Vision to describe everything visible |
| `click_element` | Clicks any element described in natural language |
| `fill_field` | Types into any field described in natural language |
| `read_screen_data` | Extracts specific data from current screen |
| `get_page_state` | Gets full analysis of current page state |

### Human-in-the-Loop (HITL) Pattern

The agent **never posts documents autonomously**. When ready to post:

1. Agent prepares all details
2. Streams a special approval card to the UI
3. User reviews: Equipment, Document Type, Notes, Attachments
4. User clicks **Approve & Post** or **Cancel**
5. Only on approval does the agent execute the post

---

## UI Layout

```
┌─────────────────────────────────────────────────────┐
│  🤖 Generic Intelligent SAP Agent   [Tabs]         │
├──────────────────────┬──────────────────────────────┤
│   AGENT ACTIVITY     │   SAP SCREEN VIEW            │
│                      │                              │
│  Streaming steps     │  Live screenshots            │
│  appear here as      │  from the agent's            │
│  agent works:        │  browser appear here         │
│                      │  and update after            │
│  🤔 Thinking...      │  every action                │
│  🔧 Tool called      │                              │
│  ✅ Result           │  Status bar below:           │
│  📸 Screenshot       │  Current step | Status       │
│  📋 HITL card        │                              │
├──────────────────────┴──────────────────────────────┤
│  Type your SAP instruction here...         [Send]    │
│  Generic Automation Platform | Powered by Claude   │
└─────────────────────────────────────────────────────┘
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Verify backend is running |
| POST | `/sap-chat` | Send instruction to SAP agent |
| POST | `/approve-sap-post` | Approve pending document posting |

```
## SAP Fiori Demo Pages

The fake SAP Fiori (`fake_sap.html`) simulates these pages:

| Page | Description |
|---|---|
| Login | SSO login with Microsoft Azure AD button |
| Launchpad | 6 application tiles including Equipment Management |
| Equipment List | Searchable table with 3 sample equipment records |
| Equipment Detail | Full edit form with notes, attachments, status |
| Post Confirmation | Summary modal with warning before posting |
| Success | Document number and posting confirmation |

### Sample Equipment Data

| Equipment | Description | Plant | Status |
|---|---|---|---|
| EQ-12345 | Industrial Pump Unit | PLANT-001 | Active |
| EQ-12346 | Conveyor Belt System | PLANT-002 | Active |
| EQ-12347 | Pressure Valve Assembly | PLANT-001 | Inactive |

---

## Production Roadmap

### Phase 1 — Current (Browser Automation)
- Playwright controls Chrome browser
- Claude Vision reads screens dynamically
- Works without SAP API access
- Ideal for demos and stakeholder buy-in

### Phase 2 — SAP Sandbox Access
- Point agent at real SAP Fiori URL
- Update SAP_URL in .env file
- Tune selectors for real SAP HTML structure
- Test each tool against real SAP
- Estimated effort: 1-2 days

### Phase 3 — Production via MCP + SAP OData APIs
- Build MCP server wrapping SAP OData REST APIs
- Replace browser tools with API tools for supported actions
- Keep browser automation as fallback for unsupported actions
- Add Azure Key Vault for credential management
- Add audit logging and monitoring

### MCP Production Architecture

```
Claude Agent
        ↓
MCP Server (sap-connector)
        ↓
SAP OData REST APIs
https://company.s4hana.cloud.sap/sap/opu/odata/

Tools exposed via MCP:
@mcp.tool() get_equipment(equipment_id)
@mcp.tool() update_equipment_notes(id, notes)
@mcp.tool() search_equipment(plant, status)
@mcp.tool() post_service_document(id, details)
```

---

## Scheduled Automation

To run the agent automatically without human prompting:

```python
import schedule
import httpx
import asyncio

async def run_scheduled_report():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/sap-chat",
            json={
                "message": """
                Login to SAP and generate weekly report:
                1. Get all equipment status
                2. Identify inactive equipment
                3. Check overdue service items
                4. Report only - do not post anything
                """
            },
            timeout=300
        )

# Run every Monday at 9am
schedule.every().monday.at("09:00").do(
    lambda: asyncio.run(run_scheduled_report())
)
```

For enterprise scheduling at Generic: use **Azure Functions** with timer triggers.

## Technology Stack

| Component | Technology |
|---|---|
| Agent Brain | Claude claude-sonnet-4-6 (Anthropic) |
| Vision AI | Claude Vision API |
| Backend | FastAPI + Python |
| Browser Automation | Playwright |
| Streaming | Server-Sent Events (SSE) |
| Frontend | Vanilla HTML/CSS/JavaScript |
| Database (IT Demo) | SQLite |
| Environment | Python venv |

**Connection refused error:**
Make sure both servers are running on ports 8000 and 8001.

**API key error:**
Check your `.env` file has the correct `ANTHROPIC_API_KEY`.

**Agent goes in circles:**
Check terminal logs for missing method errors in `sap_browser.py`.
All 6 methods must be implemented: `launch_browser`, `take_screenshot_and_describe`,
`click_element`, `fill_field`, `read_screen_data`, `get_page_state`.

**Screenshot not showing in right panel:**
Open browser console (F12) and check for JavaScript errors.
