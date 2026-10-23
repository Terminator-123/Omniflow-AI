import time
from playwright.sync_api import sync_playwright

def test_screens():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto("http://localhost:8501")
        page.wait_for_selector(".stTextArea textarea", timeout=25000)
        time.sleep(2)
        
        pages = [
            ("Execution Plan", "nav_plan", "screen_plan.png"),
            ("Live Execution", "nav_execution", "screen_execution.png"),
            ("Evidence Explorer", "nav_evidence", "screen_evidence.png"),
            ("Final Report", "nav_results", "screen_report.png"),
            ("Task History", "nav_history", "screen_history.png"),
        ]
        
        for name, key, filename in pages:
            btn = page.query_selector(f"[data-testid='baseButton-secondary'][kind='secondary']:has-text('{name}'), button:has-text('{name}')")
            if btn:
                btn.click()
                time.sleep(2)
                page.screenshot(path=filename)
                print(f"Captured {filename} for {name}")
            else:
                print(f"Could not find button for {name}")
                
        browser.close()

if __name__ == "__main__":
    test_screens()
