import time
from playwright.sync_api import sync_playwright

def test_done():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto("http://localhost:8501")
        time.sleep(3)
        page.screenshot(path="final_flow_live.png")
        print("Captured final_flow_live.png")
        
        # Click Final Report on sidebar
        rep_btn = page.query_selector("button:has-text('Final Report')")
        if rep_btn:
            rep_btn.click()
            time.sleep(3)
            page.screenshot(path="final_flow_report.png")
            print("Captured final_flow_report.png")
            
        browser.close()

if __name__ == "__main__":
    test_done()
