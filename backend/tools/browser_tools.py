"""
tools/browser_tools.py
Claude tool definitions and executor for SAP Fiori browser automation.
"""

from sap_browser import sap_browser

# ── Tool definitions ───────────────────────────────────────────────────────────

BROWSER_TOOLS = [
    {
        "name": "launch_browser",
        "description": (
            "Launch the SAP browser and navigate to the SAP Fiori login page. "
            "Call this first before any other tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "take_screenshot_and_describe",
        "description": (
            "Take a screenshot of the current SAP screen and get a detailed description of "
            "everything visible including all interactive elements. Use this to understand "
            "current state before deciding next action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "click_element",
        "description": (
            "Click any element on the SAP screen by describing it in natural language. "
            "Vision AI will find and click it. Use for buttons, tiles, links, menu items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "element_description": {
                    "type": "string",
                    "description": (
                        "Natural language description of what to click. Be specific. "
                        "Example: Sign in with Microsoft SSO button, Equipment Management tile, "
                        "Search button, Edit button for EQ-12345"
                    ),
                }
            },
            "required": ["element_description"],
        },
    },
    {
        "name": "fill_field",
        "description": (
            "Type a value into any input field on the SAP screen by describing the field in "
            "natural language. Vision AI will find the field and type the value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field_description": {
                    "type": "string",
                    "description": (
                        "Natural language description of the field. "
                        "Example: Equipment Number search field, Maintenance Notes textarea"
                    ),
                },
                "value": {
                    "type": "string",
                    "description": "The value to type into the field",
                },
            },
            "required": ["field_description", "value"],
        },
    },
    {
        "name": "read_screen_data",
        "description": (
            "Extract specific information from the current SAP screen. Use this to read "
            "table data, form values, document numbers, error messages, or any other "
            "information visible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "what_to_extract": {
                    "type": "string",
                    "description": (
                        "Specific description of what to extract. "
                        "Example: All equipment records from the table, "
                        "The document number from the success page"
                    ),
                }
            },
            "required": ["what_to_extract"],
        },
    },
    {
        "name": "get_page_state",
        "description": (
            "Get a complete analysis of the current page state including what page this is, "
            "what actions are available, and what the logical next step should be. "
            "Use this when unsure what to do next."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# ── Tool executor ──────────────────────────────────────────────────────────────

async def execute_browser_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name == "launch_browser":
        return await sap_browser.launch_browser(tool_input.get("url", ""))
    elif tool_name == "take_screenshot_and_describe":
        return await sap_browser.take_screenshot_and_describe()
    elif tool_name == "click_element":
        return await sap_browser.click_element(tool_input["element_description"])
    elif tool_name == "fill_field":
        return await sap_browser.fill_field(
            tool_input["field_description"], tool_input["value"]
        )
    elif tool_name == "read_screen_data":
        return await sap_browser.read_screen_data(tool_input["what_to_extract"])
    elif tool_name == "get_page_state":
        return await sap_browser.get_page_state()
    else:
        return {
            "success": False,
            "message": f"Unknown browser tool: {tool_name}",
            "screenshot": "",
            "data": {},
        }
