import json
from playwright.sync_api import sync_playwright

def inspect_collapsed():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto("http://localhost:8501")
        page.wait_for_timeout(3000)
        
        # Manually trigger collapse by calling Streamlit React or by evaluating JS:
        # Let's find what happens if aria-expanded="false" is on stSidebar
        info = page.evaluate("""() => {
            const sb = document.querySelector('section[data-testid="stSidebar"]');
            if (!sb) return 'NO SB';
            
            // Look at computed styles of stSidebar
            const cs = window.getComputedStyle(sb);
            return {
                display: cs.display,
                visibility: cs.visibility,
                transform: cs.transform,
                marginLeft: cs.marginLeft,
                left: cs.left,
                position: cs.position,
                width: cs.width,
                box: sb.getBoundingClientRect(),
                parentClasses: sb.parentElement ? sb.parentElement.className : null
            };
        }""")
        print("Sidebar styles currently:", json.dumps(info, indent=2))
        browser.close()

if __name__ == "__main__":
    inspect_collapsed()
