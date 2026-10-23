"""Unit tests for Research Scope Enforcement and Domain Tracking."""
import pytest
from backend.agent.scope_manager import (
    parse_requested_domains,
    normalize_domain,
    is_domain_permitted,
    ScopeTracker,
)

def test_parse_requested_domains():
    """Verifies that requested domains are parsed from scope and request text."""
    scope = "IBM, Google Cloud, NIST"
    domains = parse_requested_domains(scope)
    assert "ibm.com" in domains
    assert "cloud.google.com" in domains
    assert "nist.gov" in domains

    # Direct domain strings
    scope2 = "anthropic.com, openai.com, arxiv.org"
    domains2 = parse_requested_domains(scope2)
    assert "anthropic.com" in domains2
    assert "openai.com" in domains2
    assert "arxiv.org" in domains2

def test_normalize_domain():
    """Verifies proper domain normalization."""
    assert normalize_domain("https://www.ibm.com/think/topics") == "ibm.com"
    assert normalize_domain("cloud.google.com:443") == "cloud.google.com"
    assert normalize_domain("WWW.NIST.GOV") == "nist.gov"

def test_is_domain_permitted():
    """Verifies subdomain matching and domain enforcement."""
    allowed = ["google.com", "ibm.com", "nist.gov"]
    assert is_domain_permitted("cloud.google.com", allowed) is True
    assert is_domain_permitted("www.ibm.com", allowed) is True
    assert is_domain_permitted("nist.gov", allowed) is True
    assert is_domain_permitted("malicious-site.com", allowed) is False
    assert is_domain_permitted("google.com.attacker.com", allowed) is False

def test_scope_tracker():
    """Verifies tracking of requested, attempted, consulted, and failed domains."""
    tracker = ScopeTracker(requested_domains=["ibm.com", "google.com", "nist.gov"])
    tracker.record_attempt("ibm.com")
    tracker.record_success("ibm.com")

    tracker.record_attempt("google.com")
    tracker.record_success("google.com")

    tracker.record_attempt("nist.gov")
    tracker.record_failure("nist.gov", "HTTP 503 endpoint timeout")

    summary = tracker.get_summary()
    assert "ibm.com" in summary["consulted_domains"]
    assert "google.com" in summary["consulted_domains"]
    assert "nist.gov" in summary["failed_domains"]
    assert summary["is_complete_coverage"] is False
    assert "nist.gov" in summary["missing_domains"]
