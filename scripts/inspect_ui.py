import time
from playwright.sync_api import sync_playwright

def inspect():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto("http://localhost:8501")
        # Wait for the main text area to be mounted
        page.wait_for_selector(".stTextArea textarea", timeout=25000)
        time.sleep(2)
        page.screenshot(path="current_screen.png")
        print("Screenshot successfully captured!")
        browser.close()

if __name__ == "__main__":
    inspect()
