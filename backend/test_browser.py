import asyncio
import base64
import os
from dotenv import load_dotenv
from sap_browser import sap_browser

load_dotenv()

SAP_URL = os.getenv("SAP_URL", "")

SCREENSHOT_PATH = "/Users/gauravbhasin/Desktop/Demo/sap-agent/data/test_screenshot.png"


async def main():
    print(f"Launching browser at: {SAP_URL}")
    result = await sap_browser.launch_browser(SAP_URL)

    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")

    if result["screenshot"]:
        length = len(result["screenshot"])
        print(f"Screenshot captured: YES ({length} chars)")

        os.makedirs(os.path.dirname(SCREENSHOT_PATH), exist_ok=True)

        with open(SCREENSHOT_PATH, "wb") as f:
            f.write(base64.b64decode(result["screenshot"]))
        print(f"Screenshot saved to: {SCREENSHOT_PATH}")
    else:
        print("Screenshot captured: NO")

    await asyncio.sleep(2)

    vision_result = await sap_browser.take_screenshot_and_describe()

    print("\n--- CLAUDE VISION SEES ---")
    if vision_result['success']:
        print(vision_result['data']['description'])
    else:
        print(f"Vision failed: {vision_result['message']}")
    print("--------------------------\n")

    click_result = await sap_browser.click_element("Sign in with Microsoft SSO button")

    print("\n--- CLICKING SSO BUTTON ---")
    print(f"Success: {click_result['success']}")
    print(f"Message: {click_result['message']}")
    print(f"After click: {click_result['data']['vision_after']}")
    print("---------------------------\n")

    if click_result["screenshot"]:
        after_click_path = "/Users/gauravbhasin/Desktop/Demo/sap-agent/data/after_click.png"
        with open(after_click_path, "wb") as f:
            f.write(base64.b64decode(click_result["screenshot"]))
        print(f"After-click screenshot saved to: {after_click_path}")

    await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
