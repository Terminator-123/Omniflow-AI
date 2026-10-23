import time
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto("http://localhost:8501")
        page.wait_for_timeout(3000)
        
        # Check elements
        content = page.query_selector('section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]')
        print("stSidebarUserContent exists:", content is not None)
        if content:
            print("stSidebarUserContent text length:", len(content.inner_text()))
            print("stSidebarUserContent visible:", content.is_visible())
            
        # Try to find collapse button
        col_btn = page.query_selector('[data-testid="stSidebarCollapseButton"] button')
        print("Collapse button found:", col_btn is not None)
        if col_btn:
            print("Clicking collapse button...")
            col_btn.click()
            time.sleep(2)
            page.screenshot(path="after_collapse.png")
            
            sb = page.query_selector('section[data-testid="stSidebar"]')
            if sb:
                print("Sidebar visible after collapse:", sb.is_visible())
                print("Sidebar bounding box:", sb.bounding_box())
                print("Sidebar aria-expanded:", sb.get_attribute("aria-expanded"))
                
            col_ctrl = page.query_selector('[data-testid="collapsedControl"]')
            print("collapsedControl exists after collapse:", col_ctrl is not None)
            if col_ctrl:
                print("collapsedControl visible:", col_ctrl.is_visible())
                
        browser.close()

if __name__ == "__main__":
    test()
