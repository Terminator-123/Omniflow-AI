import json
from playwright.sync_api import sync_playwright

def check():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto("http://localhost:8501")
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        
        info = page.evaluate("""() => {
            const header = document.querySelector('header[data-testid="stHeader"]');
            const collapseInHeader = header ? header.querySelector('[data-testid="collapsedControl"]') : null;
            const allCollapse = document.querySelectorAll('[data-testid="collapsedControl"]');
            const sb = document.querySelector('section[data-testid="stSidebar"]');
            
            // Check localStorage
            const storage = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                storage[k] = localStorage.getItem(k);
            }
            
            return {
                headerFound: !!header,
                headerDisplay: header ? window.getComputedStyle(header).display : null,
                collapseInHeader: !!collapseInHeader,
                totalCollapseFound: allCollapse.length,
                sidebarExpanded: sb ? sb.getAttribute('aria-expanded') : null,
                sidebarDisplay: sb ? window.getComputedStyle(sb).display : null,
                sidebarWidth: sb ? window.getComputedStyle(sb).width : null,
                sidebarTransform: sb ? window.getComputedStyle(sb).transform : null,
                sidebarMarginLeft: sb ? window.getComputedStyle(sb).marginLeft : null,
                storage: storage
            };
        }""")
        print(json.dumps(info, indent=2))
        browser.close()

if __name__ == "__main__":
    check()
