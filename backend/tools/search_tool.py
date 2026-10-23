"""Search tool for discovery of authoritative research URLs with honest attribution and bounded retries."""
import time
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from backend.core.logging_config import logger
from backend.core.security import validate_safe_url
from backend.agent.scope_manager import parse_requested_domains, is_domain_permitted

KNOWN_DOMAIN_SOURCES = {
    "ibm": [
        {
            "title": "IBM - What are AI Agents?",
            "url": "https://www.ibm.com/think/topics/ai-agents",
            "domain": "ibm.com",
            "snippet": "AI agents are autonomous software entities powered by foundational models that perceive their environment, reason, plan multi-step workflows, and take actions using tools.",
            "provenance": "demo_fixture",
        },
        {
            "title": "IBM - Artificial Intelligence Governance and Human Oversight",
            "url": "https://www.ibm.com/topics/ai-governance",
            "domain": "ibm.com",
            "snippet": "AI governance requires guardrails, auditability, accountability frameworks, and human-in-the-loop oversight to mitigate hallucinations, drift, and bias.",
            "provenance": "demo_fixture",
        }
    ],
    "google": [
        {
            "title": "Google Cloud - What are AI Agents?",
            "url": "https://cloud.google.com/discover/what-are-ai-agents",
            "domain": "cloud.google.com",
            "snippet": "Google Cloud defines AI agents as autonomous systems combining large language models with external tools, reasoning engines, and runtime memory to execute complex business tasks.",
            "provenance": "demo_fixture",
        },
        {
            "title": "Google Cloud - Vertex AI Agent Builder & Enterprise Grounding",
            "url": "https://cloud.google.com/products/agent-builder",
            "domain": "cloud.google.com",
            "snippet": "Enterprise agents require grounding against verifiable databases, explicit tool permissions, and deterministic state transitions to ensure enterprise reliability.",
            "provenance": "demo_fixture",
        }
    ],
    "nist": [
        {
            "title": "NIST - Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
            "url": "https://www.nist.gov/itl/ai-risk-management-framework",
            "domain": "nist.gov",
            "snippet": "The NIST AI RMF offers voluntary guidance to improve the ability to incorporate trustworthiness considerations into the design, development, use, and evaluation of AI products.",
            "provenance": "demo_fixture",
        },
        {
            "title": "NIST - AI Resource Center: Measuring AI Risks and Human Oversight",
            "url": "https://airc.nist.gov/",
            "domain": "airc.nist.gov",
            "snippet": "Key AI risk dimensions include validity and reliability, safety, security and resilience, explainability and interpretability, privacy enhancement, and fair treatment.",
            "provenance": "demo_fixture",
        }
    ]
}

def _extract_actual_url(raw_href: str) -> str:
    """Extracts the canonical target URL from search engine redirect links (e.g., DuckDuckGo uddg)."""
    if not raw_href:
        return ""
    if "uddg=" in raw_href:
        parsed = urllib.parse.urlparse(raw_href)
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return params["uddg"][0]
    if raw_href.startswith("//"):
        return f"https:{raw_href}"
    return raw_href

def _execute_live_search(
    query: str,
    max_results: int = 4,
    max_retries: int = 2,
    timeout_sec: float = 6.0,
) -> List[Dict[str, Any]]:
    """Performs live web search using public endpoints with bounded retries and exponential backoff."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    encoded_q = urllib.parse.quote_plus(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
                resp = client.get(search_url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = soup.find_all("a", class_="result__url")
                    snippets = soup.find_all("a", class_="result__snippet")
                    titles = soup.find_all("a", class_="result__title")

                    items: List[Dict[str, Any]] = []
                    for idx, link in enumerate(links[:max_results]):
                        raw_href = link.get("href", "").strip()
                        actual_url = _extract_actual_url(raw_href)
                        if actual_url and actual_url.startswith("http"):
                            try:
                                # Validate against SSRF before returning
                                safe_url = validate_safe_url(actual_url, allow_simulated=True)
                                parsed_dom = urllib.parse.urlparse(safe_url).netloc
                                title_text = titles[idx].get_text(strip=True) if idx < len(titles) else link.get_text(strip=True)
                                snippet_text = snippets[idx].get_text(strip=True) if idx < len(snippets) else f"Search result for {query}"
                                
                                items.append({
                                    "title": title_text or f"Discovered source for {query}",
                                    "url": safe_url,
                                    "domain": parsed_dom,
                                    "snippet": snippet_text,
                                    "provenance": "live_search",
                                    "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                                })
                            except Exception as ssrf_err:
                                logger.warning(f"Skipping discovered URL {actual_url} due to security validation: {ssrf_err}")
                    
                    if items:
                        return items
        except Exception as exc:
            last_error = exc
            logger.warning(f"Live search attempt {attempt + 1}/{max_retries + 1} failed: {exc}")
            if attempt < max_retries:
                time.sleep(0.4 * (attempt + 1))

    logger.warning(f"Live search exhausted retries ({max_retries + 1}) for query '{query}': {last_error}")
    return []

def search_web(
    query: str,
    scope: str = "",
    max_results: int = 3,
    mode: str = "live",
) -> List[Dict[str, Any]]:
    """Discovers authoritative public research URLs based on query and target scope constraints.
    
    States:
    - 'live': Real network calls executed. Results tagged provenance='live_search'.
    - 'demo': Explicitly requested demo fixtures returned, tagged provenance='demo_fixture'.
    - 'partial': Live search was requested but failed; fallback fixtures clearly tagged provenance='predefined_catalog'.
    """
    logger.info(f"Executing web_search for query='{query}', scope='{scope}', mode='{mode}'")
    requested_domains = parse_requested_domains(scope, query)
    now_ts = datetime.now(timezone.utc).isoformat()

    # 1. Explicit Demonstration Mode
    if mode == "demo":
        logger.info("Demo mode: Returning certified demonstration fixtures with explicit demo provenance.")
        demo_results = []
        for key in ["ibm", "google", "nist"]:
            for entry in KNOWN_DOMAIN_SOURCES[key][:max_results]:
                res = dict(entry)
                res["title"] = f"[Demo Fixture] {res['title']}"
                res["provenance"] = "demo_fixture"
                res["execution_state"] = "demo"
                res["retrieval_timestamp"] = now_ts
                demo_results.append(res)
        return demo_results[:max_results * 2]

    # 2. Live Search Execution
    live_results: List[Dict[str, Any]] = []

    # If explicit domains were requested, search specifically with domain constraint
    if requested_domains:
        for domain in requested_domains[:3]:
            scoped_query = f"{query} site:{domain}"
            discovered = _execute_live_search(scoped_query, max_results=2)
            for item in discovered:
                if is_domain_permitted(item["domain"], requested_domains):
                    item["execution_state"] = "live"
                    live_results.append(item)

    # General search if no domain restrictions or if scoped queries returned few results
    if len(live_results) < max_results:
        general_discovered = _execute_live_search(query, max_results=max_results)
        for item in general_discovered:
            # Enforce domain restrictions if specified
            if not requested_domains or is_domain_permitted(item["domain"], requested_domains):
                item["execution_state"] = "live"
                if not any(r["url"] == item["url"] for r in live_results):
                    live_results.append(item)

    if live_results:
        logger.info(f"Live search successful. Discovered {len(live_results)} genuine live URLs.")
        return live_results[:max_results * 2]

    # 3. Transparent Fallback (Partial Execution State)
    # When live search fails, NEVER mislabel catalog entries as live search!
    logger.warning("Live search yielded no reachable results. Engaging transparent fallback catalog.")
    fallback_results: List[Dict[str, Any]] = []
    
    # Match against requested domains in catalog if available
    lower_scope = (scope or "").lower()
    lower_query = query.lower()
    matched_keys = []
    if "ibm" in lower_scope or "ibm" in lower_query:
        matched_keys.append("ibm")
    if "google" in lower_scope or "google" in lower_query or "vertex" in lower_query:
        matched_keys.append("google")
    if "nist" in lower_scope or "nist" in lower_query:
        matched_keys.append("nist")

    if not matched_keys:
        matched_keys = ["ibm", "google", "nist"]

    for k in matched_keys:
        if k in KNOWN_DOMAIN_SOURCES:
            for entry in KNOWN_DOMAIN_SOURCES[k][:max_results]:
                res = dict(entry)
                res["title"] = f"[Predefined Catalog] {res['title']}"
                res["provenance"] = "predefined_catalog"
                res["execution_state"] = "partial"
                res["retrieval_timestamp"] = now_ts
                fallback_results.append(res)

    return fallback_results[:max_results * 2]
