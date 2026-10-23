"""Playwright browser automation tool with resilient HTTP fallback."""
import time
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx
from backend.config import settings
from backend.core.exceptions import ToolExecutionError, PolicyViolationError
from backend.core.logging_config import logger
from backend.core.security import validate_safe_url

def _clean_html_to_text(html_content: str, max_length: int = 12000) -> str:
    """Extracts readable textual content from raw HTML, removing scripts and styles."""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    return cleaned[:max_length]

def extract_page_via_httpx(url: str, timeout_seconds: float = 12.0) -> Dict[str, Any]:
    """Fallback fetcher using httpx and BeautifulSoup for high resilience."""
    # Enforce SSRF validation
    safe_url = validate_safe_url(url, allow_simulated=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    start_time = time.time()
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            duration_ms = int((time.time() - start_time) * 1000)
            if resp.status_code >= 400:
                raise ToolExecutionError(
                    f"HTTP Error {resp.status_code} accessing {url}",
                    tool_name="browser_page_extractor",
                    recoverable=(resp.status_code in (408, 429, 500, 502, 503, 504))
                )
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else urlparse(url).netloc
            cleaned_text = _clean_html_to_text(resp.text)
            return {
                "title": title,
                "final_url": str(resp.url),
                "domain": urlparse(str(resp.url)).netloc,
                "status_code": resp.status_code,
                "content": cleaned_text,
                "extracted_chars": len(cleaned_text),
                "duration_ms": duration_ms,
                "extractor": "httpx_resilient",
            }
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to access URL {url}: {str(exc)}",
            tool_name="browser_page_extractor",
            recoverable=True
        )

def extract_page(
    url: str,
    timeout_ms: Optional[int] = None,
    simulate_failure: bool = False,
    demo_mode: bool = False,
) -> Dict[str, Any]:
    """Extracts public webpage content using Playwright, with resilient HTTP fallback.
    
    Args:
        url: Public HTTP/HTTPS URL.
        timeout_ms: Max navigation timeout.
        simulate_failure: If True, raises a controlled recoverable error to test recovery loop.
        demo_mode: If True, loads vetted demonstration content without live network calls.
    """
    logger.info(f"Extracting webpage: url='{url}', demo={demo_mode}, sim_fail={simulate_failure}")

    # Enforce SSRF validation
    safe_url = validate_safe_url(url, allow_simulated=True)

    # Controlled failure test hook
    if simulate_failure or "simulate-fail" in url or "httpstat.us/503" in url:
        logger.warning(f"Simulating controlled recoverable failure for test scenario on {url}")
        raise ToolExecutionError(
            f"HTTP 503 Service Unavailable: Remote source endpoint {url} failed to respond",
            tool_name="browser_page_extractor",
            recoverable=True,
        )

    # Demo Mode Fixture Return
    if demo_mode:
        from backend.tools.search_tool import KNOWN_DOMAIN_SOURCES
        domain = urlparse(url).netloc
        title = f"[Demo Fixture] Content from {domain}"
        fixture_body = (
            f"Official Demonstration Extract for {domain}.\n"
            "Key Topic: Autonomous AI Agents in Enterprise Environments.\n"
            "Capabilities: AI agents leverage LLMs for reasoning, dynamic planning, tool selection, and state persistence.\n"
            "Reliability & Risks: High risk of hallucination, execution drift, unexpected tool parameterization, and compounding errors.\n"
            "Human Oversight: Essential requirement for human-in-the-loop approval on sensitive, irreversible, or high-stakes actions.\n"
            "Governance: Recommended alignment with NIST AI Risk Management Framework (AI RMF 1.0) and auditable execution logging."
        )
        return {
            "title": title,
            "final_url": url,
            "domain": domain,
            "status_code": 200,
            "content": fixture_body,
            "extracted_chars": len(fixture_body),
            "duration_ms": 120,
            "extractor": "offline_demo_fixture",
        }

    # Primary: Attempt Playwright headless browser
    timeout = timeout_ms or settings.BROWSER_TIMEOUT_MS
    start_time = time.time()
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            status_code = response.status if response else 200
            
            if status_code >= 400:
                browser.close()
                raise ToolExecutionError(
                    f"HTTP Error {status_code} when navigating to {url}",
                    tool_name="browser_page_extractor",
                    recoverable=(status_code in (408, 429, 500, 502, 503, 504)),
                )
            
            title = page.title() or urlparse(url).netloc
            html = page.content()
            final_url = page.url
            browser.close()

            cleaned_text = _clean_html_to_text(html)
            duration_ms = int((time.time() - start_time) * 1000)
            
            return {
                "title": title,
                "final_url": final_url,
                "domain": urlparse(final_url).netloc,
                "status_code": status_code,
                "content": cleaned_text,
                "extracted_chars": len(cleaned_text),
                "duration_ms": duration_ms,
                "extractor": "playwright_chromium",
            }
    except ToolExecutionError:
        raise
    except Exception as exc:
        logger.warning(f"Playwright browser execution encountered issue ({exc}). Activating resilient HTTP fallback...")
        return extract_page_via_httpx(url, timeout_seconds=timeout / 1000.0)
