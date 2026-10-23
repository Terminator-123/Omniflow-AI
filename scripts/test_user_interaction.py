import time
from playwright.sync_api import sync_playwright

def test_full_interaction():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto("http://localhost:8501")
        page.wait_for_selector(".stTextArea textarea", timeout=25000)
        time.sleep(2)
        
        print("[1] On Workspace. Taking screenshot...")
        page.screenshot(path="test_step1_workspace.png")
        
        # Click Run agent -> button
        run_btn = page.query_selector("button:has-text('Run agent')")
        assert run_btn is not None, "Run agent button not found!"
        print("[2] Clicking 'Run agent  ->' button...")
        run_btn.click()
        
        # Wait for either error or transition
        time.sleep(4)
        page.screenshot(path="test_step2_after_run.png")
        
        # Check if error is present
        error_el = page.query_selector("[data-testid='stAlert'], [data-testid='stNotification']")
        if error_el:
            print("ALERT FOUND:", error_el.inner_text())
        else:
            print("No error alert found!")
            
        # Check if Execution Plan heading is visible
        h1 = page.query_selector("h1")
        if h1:
            print("Current H1 text:", h1.inner_text())
            
        # Click Run task -> button on Execution Plan
        run_task_btn = page.query_selector("button:has-text('Run task')")
        if run_task_btn:
            print("[3] Clicking 'Run task ->' to approve and launch execution...")
            run_task_btn.click()
            time.sleep(5)
            page.screenshot(path="test_step3_execution.png")
            h1_exec = page.query_selector("h1")
            if h1_exec:
                print("After Run task, H1 text:", h1_exec.inner_text())
                
        browser.close()

if __name__ == "__main__":
    test_full_interaction()
