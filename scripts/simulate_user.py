from playwright.sync_api import sync_playwright

def simulate_user():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        page.goto("http://localhost:8501")
        page.wait_for_timeout(2000)
        
        # Simulate user having collapsed sidebar
        page.evaluate("""() => {
            const sb = document.querySelector('section[data-testid="stSidebar"]');
            if (sb) {
                sb.setAttribute('aria-expanded', 'false');
                sb.style.marginLeft = '-336px';
            }
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path="simulated_user_screen.png")
        print("Simulated user screenshot captured.")
        browser.close()

if __name__ == "__main__":
    simulate_user()
