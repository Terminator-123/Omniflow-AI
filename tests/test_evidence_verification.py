"""Unit tests for Genuine Claim-Level Evidence Verification and Deduplication."""
import pytest
from backend.agent.verifier import verifier
from backend.tools.source_extractor import extract_evidence_from_content

def test_initial_extraction_status_is_retrieved():
    """Verifies that newly extracted evidence begins as 'retrieved', not automatically claim_supported."""
    sample_text = (
        "AI agents are autonomous software entities that perceive their environment, "
        "reason about complex multi-step workflows, and take actions using external tools. "
        "Human-in-the-loop oversight is an essential operational requirement to prevent compounding errors."
    )
    evidences = extract_evidence_from_content(
        content=sample_text,
        source_url="https://cloud.google.com/discover/what-are-ai-agents",
        source_title="Google Cloud - AI Agents",
        domain="cloud.google.com",
    )
    assert len(evidences) >= 1
    # Check that initial status is strictly 'retrieved'
    assert all(e["verification_status"] == "retrieved" for e in evidences)

def test_evidence_deduplication():
    """Verifies that identical extracted passages across runs are deduplicated via hash."""
    sample_text = (
        "Human-in-the-loop oversight is an essential operational requirement to prevent compounding errors."
    )
    hashes = set()
    ev1 = extract_evidence_from_content(
        content=sample_text,
        source_url="https://nist.gov/ai-rmf",
        source_title="NIST",
        domain="nist.gov",
        existing_hashes=hashes,
    )
    assert len(ev1) == 1
    assert len(hashes) == 1

    # Second run with same text and same hash tracker
    ev2 = extract_evidence_from_content(
        content=sample_text,
        source_url="https://nist.gov/ai-rmf-copy",
        source_title="NIST Duplicate",
        domain="nist.gov",
        existing_hashes=hashes,
    )
    # Should be deduplicated
    assert len(ev2) == 0

def test_semantic_claim_verification():
    """Verifies deterministic semantic evaluation of claim support."""
    supported_ev = {
        "stable_id": "EVID-001",
        "research_question": "What core capabilities do autonomous AI agents possess?",
        "finding": "[IBM.COM] Confirms capabilities: multi-step planning and tool usage.",
        "excerpt": "AI agents perceive their environment, reason, plan multi-step workflows, and take actions using tools.",
        "source_url": "https://www.ibm.com/think/topics/ai-agents",
    }
    res = verifier.verify_evidence_claim(supported_ev)
    assert res["status"] in ("claim_supported", "partially_supported")
    assert res["is_supported"] is True

    # Contradicting passage
    contradicting_ev = {
        "stable_id": "EVID-002",
        "research_question": "Are AI agents reliable without human oversight?",
        "finding": "Agents are fully reliable without oversight.",
        "excerpt": "It is completely false and disproved that agents can operate reliably without continuous human oversight.",
        "source_url": "https://nist.gov/ai-rmf",
    }
    res_bad = verifier.verify_evidence_claim(contradicting_ev)
    assert res_bad["status"] == "unsupported"
    assert res_bad["is_supported"] is False
