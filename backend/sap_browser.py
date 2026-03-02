import asyncio
import base64
import os
import anthropic
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

SAP_URL = os.getenv("SAP_URL", "")


class SAPBrowser:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    async def _take_screenshot(self) -> str:
        screenshot_bytes = await self.page.screenshot()
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    def _ask_vision(self, screenshot_b64: str, question: str) -> str:
        try:
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": screenshot_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": question,
                            },
                        ],
                    }
                ],
            )
            return response.content[0].text
        except Exception as e:
            return str(e)

    async def take_screenshot_and_describe(self) -> dict:
        screenshot = await self._take_screenshot()
        description = self._ask_vision(
            screenshot,
            "Describe exactly what you see on this screen. "
            "List ALL visible interactive elements: "
            "buttons, input fields, links, tiles, dropdowns. "
            "Include their exact label text.",
        )
        return {
            "success": True,
            "message": "Screen captured and analyzed",
            "screenshot": screenshot,
            "data": {
                "description": description,
            },
        }

    async def click_element(self, element_description: str) -> dict:
        try:
            screenshot_before = await self._take_screenshot()

            vision_question = (
                f"I need to click: {element_description}\n"
                "Look at this screen carefully.\n"
                "Respond in this exact JSON format with no other text:\n"
                "{\n"
                '  "found": true or false,\n'
                '  "method": "aria-label" or "text" or "css",\n'
                '  "value": "the selector value",\n'
                '  "confidence": "high" or "medium" or "low",\n'
                '  "reasoning": "one sentence why you chose this"\n'
                "}"
            )

            vision_response = self._ask_vision(screenshot_before, vision_question)

            selector_info = None
            try:
                import json
                import re
                # Strip markdown code fences if present
                cleaned = vision_response.strip()
                cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
                selector_info = json.loads(cleaned.strip())
            except (json.JSONDecodeError, ValueError):
                # Try to extract key fields from raw text
                import re
                method_match = re.search(r'"method"\s*:\s*"([^"]+)"', vision_response)
                value_match = re.search(r'"value"\s*:\s*"([^"]+)"', vision_response)
                found_match = re.search(r'"found"\s*:\s*(true|false)', vision_response, re.IGNORECASE)
                if method_match and value_match:
                    selector_info = {
                        "found": found_match.group(1).lower() == "true" if found_match else True,
                        "method": method_match.group(1),
                        "value": value_match.group(1),
                        "confidence": "low",
                        "reasoning": "Extracted from non-JSON response",
                    }
                else:
                    return {
                        "success": False,
                        "message": "Vision did not return a parseable response",
                        "screenshot": screenshot_before,
                        "data": {
                            "selector_used": None,
                            "vision_before": vision_response,
                            "vision_after": None,
                        },
                    }

            if not selector_info.get("found", False):
                return {
                    "success": False,
                    "message": f"Element not found on screen: {element_description}",
                    "screenshot": screenshot_before,
                    "data": {
                        "selector_used": None,
                        "vision_before": selector_info,
                        "vision_after": None,
                    },
                }

            method = selector_info.get("method", "")
            value = selector_info.get("value", "")

            if method == "aria-label":
                selector = f'[aria-label="{value}"]'
            elif method == "text":
                selector = f"text={value}"
            else:
                selector = value

            await self.page.click(selector)
            await self.page.wait_for_timeout(1500)

            screenshot_after = await self._take_screenshot()

            vision_after = self._ask_vision(
                screenshot_after,
                "What changed on screen after the click? "
                "What page or state is showing now? "
                "Was the action successful?",
            )

            return {
                "success": True,
                "message": f"Clicked element: {element_description}",
                "screenshot": screenshot_after,
                "data": {
                    "selector_used": selector,
                    "vision_before": selector_info,
                    "vision_after": vision_after,
                },
            }

        except Exception as e:
            try:
                screenshot_err = await self._take_screenshot()
            except Exception:
                screenshot_err = ""
            return {
                "success": False,
                "message": str(e),
                "screenshot": screenshot_err,
                "data": {
                    "selector_used": selector if "selector" in dir() else None,
                    "vision_before": selector_info if "selector_info" in dir() else None,
                    "vision_after": None,
                },
            }

    async def fill_field(self, field_description: str, value: str) -> dict:
        import json
        import re

        selector_info = None
        selector = None
        try:
            screenshot_before = await self._take_screenshot()

            vision_question = (
                f"I need to type into: {field_description}\n"
                "Look at this screen carefully.\n"
                "Respond in this exact JSON format with no other text:\n"
                "{\n"
                '  "found": true or false,\n'
                '  "method": "aria-label" or "css" or "placeholder",\n'
                '  "value": "the selector value",\n'
                '  "confidence": "high" or "medium" or "low",\n'
                '  "reasoning": "one sentence why"\n'
                "}"
            )

            vision_response = self._ask_vision(screenshot_before, vision_question)

            try:
                cleaned = vision_response.strip()
                cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
                selector_info = json.loads(cleaned.strip())
            except (json.JSONDecodeError, ValueError):
                method_match = re.search(r'"method"\s*:\s*"([^"]+)"', vision_response)
                value_match = re.search(r'"value"\s*:\s*"([^"]+)"', vision_response)
                found_match = re.search(r'"found"\s*:\s*(true|false)', vision_response, re.IGNORECASE)
                if method_match and value_match:
                    selector_info = {
                        "found": found_match.group(1).lower() == "true" if found_match else True,
                        "method": method_match.group(1),
                        "value": value_match.group(1),
                        "confidence": "low",
                        "reasoning": "Extracted from non-JSON response",
                    }
                else:
                    return {
                        "success": False,
                        "message": "Vision did not return a parseable response",
                        "screenshot": screenshot_before,
                        "data": {"selector_used": None, "vision_response": vision_response, "verification": None},
                    }

            if not selector_info.get("found", False):
                return {
                    "success": False,
                    "message": f"Field not found on screen: {field_description}",
                    "screenshot": screenshot_before,
                    "data": {"selector_used": None, "vision_response": selector_info, "verification": None},
                }

            method = selector_info.get("method", "")
            sel_value = selector_info.get("value", "")

            if method == "aria-label":
                selector = f'[aria-label="{sel_value}"]'
            elif method == "placeholder":
                selector = f'[placeholder="{sel_value}"]'
            else:
                selector = sel_value

            await self.page.fill(selector, value)
            await self.page.wait_for_timeout(500)

            screenshot_after = await self._take_screenshot()

            verification = self._ask_vision(
                screenshot_after,
                f'Was the value "{value}" successfully entered into the field? '
                "What does the field show now?",
            )

            return {
                "success": True,
                "message": f"Filled field '{field_description}' with '{value}'",
                "screenshot": screenshot_after,
                "data": {
                    "selector_used": selector,
                    "vision_response": selector_info,
                    "verification": verification,
                },
            }

        except Exception as e:
            try:
                screenshot_err = await self._take_screenshot()
            except Exception:
                screenshot_err = ""
            return {
                "success": False,
                "message": str(e),
                "screenshot": screenshot_err,
                "data": {
                    "selector_used": selector,
                    "vision_response": selector_info,
                    "verification": None,
                },
            }

    async def read_screen_data(self, what_to_extract: str) -> dict:
        try:
            screenshot = await self._take_screenshot()

            vision_question = (
                f"From this screen extract the following:\n{what_to_extract}\n"
                "Be specific and structured.\n"
                "If extracting table data return each row clearly.\n"
                "If extracting a single value state it clearly.\n"
                "If information is not visible say so."
            )

            extracted = self._ask_vision(screenshot, vision_question)

            return {
                "success": True,
                "message": "Data extracted from screen",
                "screenshot": screenshot,
                "data": {"extracted": extracted},
            }

        except Exception as e:
            try:
                screenshot_err = await self._take_screenshot()
            except Exception:
                screenshot_err = ""
            return {
                "success": False,
                "message": str(e),
                "screenshot": screenshot_err,
                "data": {"extracted": None},
            }

    async def get_page_state(self) -> dict:
        try:
            screenshot = await self._take_screenshot()

            vision_question = (
                "Analyze this screen completely:\n"
                "1. What page or state is this?\n"
                "2. What is the main content shown?\n"
                "3. What actions are available to the user?\n"
                "4. Is there anything requiring attention like errors, warnings, or confirmations?\n"
                "5. What would be the logical next step?"
            )

            state = self._ask_vision(screenshot, vision_question)

            return {
                "success": True,
                "message": "Page state analyzed",
                "screenshot": screenshot,
                "data": {"state": state},
            }

        except Exception as e:
            try:
                screenshot_err = await self._take_screenshot()
            except Exception:
                screenshot_err = ""
            return {
                "success": False,
                "message": str(e),
                "screenshot": screenshot_err,
                "data": {"state": None},
            }

    async def launch_browser(self, url: str = SAP_URL) -> dict:
        try:
            if self.playwright is None:
                self.playwright = await async_playwright().start()
            if self.browser is None or not self.browser.is_connected():
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
            self.page = await self.browser.new_page(viewport={"width": 1280, "height": 800})
            await self.page.goto(url)
            await self.page.wait_for_load_state("load")
            screenshot = await self._take_screenshot()
            return {
                "success": True,
                "message": "Browser launched successfully",
                "screenshot": screenshot,
            }
        except Exception as e:
            self.playwright = None
            self.browser = None
            self.page = None
            return {
                "success": False,
                "message": str(e),
                "screenshot": "",
            }


sap_browser = SAPBrowser()
