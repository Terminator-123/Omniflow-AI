import time
from playwright.sync_api import sync_playwright

def test_viewports():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Test various widths: 1366, 1100, 950, 800
        for w in [1366, 1100, 950, 800]:
            context = browser.new_context(viewport={"width": w, "height": 800})
            page = context.new_page()
            page.goto("http://localhost:8501")
            page.wait_for_timeout(2000)
            
            sb = page.query_selector('section[data-testid="stSidebar"]')
            visible = sb.is_visible() if sb else False
            expanded = sb.get_attribute("aria-expanded") if sb else None
            box = sb.bounding_box() if sb else None
            
            collapse_ctrl = page.query_selector('[data-testid="collapsedControl"]')
            ctrl_visible = collapse_ctrl.is_visible() if collapse_ctrl else False
            
            print(f"Width {w}px -> SB visible: {visible}, aria-expanded: {expanded}, box: {box}, collapseCtrl visible: {ctrl_visible}")
            page.screenshot(path=f"screen_w_{w}.png")
            context.close()
        browser.close()

if __name__ == "__main__":
    test_viewports()
