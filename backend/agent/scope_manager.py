"""Research Scope Manager enforcing explicit domain constraints and honest scope tracking."""
import re
from urllib.parse import urlparse
from typing import List, Set, Dict, Any, Optional
from backend.core.logging_config import logger

KNOWN_NAME_TO_DOMAIN = {
    "ibm": "ibm.com",
    "google": "cloud.google.com",
    "google cloud": "cloud.google.com",
    "vertex": "cloud.google.com",
    "nist": "nist.gov",
    "anthropic": "anthropic.com",
    "openai": "openai.com",
    "arxiv": "arxiv.org",
    "microsoft": "microsoft.com",
    "azure": "microsoft.com",
    "iso": "iso.org",
    "langchain": "langchain.com",
    "aws": "aws.amazon.com",
    "amazon": "aws.amazon.com",
}

def normalize_domain(domain: str) -> str:
    """Normalizes domain strings by stripping protocol, paths, and 'www.'."""
    if not domain:
        return ""
    d = domain.strip().lower()
    if d.startswith("http://") or d.startswith("https://"):
        d = urlparse(d).netloc
    if d.startswith("www."):
        d = d[4:]
    # Remove port if present
    d = d.split(":")[0]
    return d

def parse_requested_domains(scope_text: str = "", request_text: str = "") -> List[str]:
    """Extracts explicit target domains from scope constraints and task description."""
    domains: Set[str] = set()
    combined = f"{scope_text or ''} {request_text or ''}".lower()

    # 1. Direct domain regex matching (e.g. ibm.com, cloud.google.com, nist.gov)
    raw_domains = re.findall(r"\b([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b", combined)
    for rd in raw_domains:
        norm = normalize_domain(rd)
        if norm and "." in norm and not norm.endswith(".py") and not norm.endswith(".txt") and not norm.endswith(".md"):
            domains.add(norm)

    # 2. Match known organization names
    for name, dom in KNOWN_NAME_TO_DOMAIN.items():
        # Match whole word
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, combined):
            domains.add(dom)

    return sorted(list(domains))

def is_domain_permitted(target_domain: str, requested_domains: List[str]) -> bool:
    """Verifies whether a target domain matches or is a subdomain of any requested domain."""
    if not requested_domains:
        return True  # Open scope if no restrictions specified

    norm_target = normalize_domain(target_domain)
    for req in requested_domains:
        norm_req = normalize_domain(req)
        if norm_target == norm_req:
            return True
        # Allow subdomains (e.g., cloud.google.com permitted for google.com, or vice versa)
        if norm_target.endswith("." + norm_req) or norm_req.endswith("." + norm_target):
            return True

    return False

class ScopeTracker:
    """Tracks requested, attempted, successfully consulted, and failed research domains."""

    def __init__(self, requested_domains: Optional[List[str]] = None):
        self.requested_domains: List[str] = [normalize_domain(d) for d in (requested_domains or []) if d]
        self.attempted_domains: Set[str] = set()
        self.consulted_domains: Set[str] = set()
        self.failed_domains: Dict[str, str] = {}  # domain -> reason
        self.unresolved_questions: List[str] = []

    def record_attempt(self, domain: str):
        norm = normalize_domain(domain)
        if norm:
            self.attempted_domains.add(norm)

    def record_success(self, domain: str):
        norm = normalize_domain(domain)
        if norm:
            self.attempted_domains.add(norm)
            self.consulted_domains.add(norm)

    def record_failure(self, domain: str, reason: str = "Endpoint unavailable"):
        norm = normalize_domain(domain)
        if norm:
            self.attempted_domains.add(norm)
            self.failed_domains[norm] = reason

    def add_unresolved_question(self, question: str):
        if question and question not in self.unresolved_questions:
            self.unresolved_questions.append(question)

    def get_summary(self) -> Dict[str, Any]:
        """Produces a structured scope audit."""
        requested_set = set(self.requested_domains)
        missing = requested_set - self.consulted_domains
        is_complete = len(requested_set) > 0 and len(missing) == 0

        return {
            "requested_domains": sorted(list(self.requested_domains)),
            "attempted_domains": sorted(list(self.attempted_domains)),
            "consulted_domains": sorted(list(self.consulted_domains)),
            "failed_domains": self.failed_domains,
            "missing_domains": sorted(list(missing)),
            "is_complete_coverage": is_complete if requested_set else True,
            "unresolved_questions": self.unresolved_questions,
        }
