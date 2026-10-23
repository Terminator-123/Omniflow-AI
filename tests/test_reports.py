"""Unit tests for Report Generation tool and file exports."""
import os
import pytest
from backend.tools.report_tool import generate_markdown_report
from backend.config import settings

def test_report_generation_all_nine_sections():
    """Verifies that generated markdown report includes all 9 required sections."""
    task_id = "test-report-task-001"
    sources = [
        {
            "domain": "ibm.com",
            "title": "IBM - AI Agents",
            "url": "https://www.ibm.com/think/topics/ai-agents",
            "access_status": "success",
            "extracted_chars": 3500,
        },
        {
            "domain": "cloud.google.com",
            "title": "Google Cloud - Vertex AI Agents",
            "url": "https://cloud.google.com/discover/what-are-ai-agents",
            "access_status": "success",
            "extracted_chars": 4200,
        },
        {
            "domain": "nist.gov",
            "title": "NIST AI Risk Management Framework",
            "url": "https://www.nist.gov/itl/ai-risk-management-framework",
            "access_status": "recovered",
            "extracted_chars": 2800,
        },
    ]

    evidences = [
        {
            "stable_id": "EVID-001",
            "research_question": "What core capabilities do autonomous AI agents possess?",
            "topic": "capabilities",
            "excerpt": "AI agents perceive their environment, reason, plan multi-step workflows, and take actions using tools.",
            "finding": "[IBM.COM] Confirms capabilities: multi-step planning and tool usage.",
            "source_url": "https://www.ibm.com/think/topics/ai-agents",
            "domain": "ibm.com",
            "verification_status": "claim_supported",
        },
        {
            "stable_id": "EVID-002",
            "research_question": "Why is human oversight necessary for agents?",
            "topic": "human_oversight",
            "excerpt": "Human-in-the-loop oversight is essential to prevent unintended tool authorization and execution drift.",
            "finding": "[NIST.GOV] Confirms governance requirement for human oversight.",
            "source_url": "https://www.nist.gov/itl/ai-risk-management-framework",
            "domain": "nist.gov",
            "verification_status": "claim_supported",
        },
    ]

    events = [
        {"event_type": "TASK_CREATED", "timestamp": "2026-10-21 12:00:00 UTC"},
        {"event_type": "TASK_COMPLETED", "timestamp": "2026-10-21 12:00:15 UTC"},
    ]

    report_result = generate_markdown_report(
        task_id=task_id,
        original_request="Research benefits and limitations of AI agents.",
        scope="IBM, Google Cloud, NIST",
        execution_mode="live",
        llm_provider="gemini-2.5-flash",
        sources=sources,
        evidences=evidences,
        verifications=[],
        events=events,
        recovered_steps=1,
    )

    md = report_result["content_markdown"]
    
    # Verify all 9 sections
    assert "## 1. Research Objective" in md
    assert "## 2. Executive Summary" in md
    assert "## 3. Key Findings" in md
    assert "## 4. Topic-by-Topic Comparison" in md
    assert "## 5. Supporting Evidence and Source Links" in md
    assert "## 6. Limitations and Unresolved Questions" in md
    assert "## 7. Sources Consulted" in md
    assert "## 8. Execution Summary" in md
    assert "## 9. Verification Results" in md

    # Verify Evidence Trail citations
    assert "`EVID-001`" in md
    assert "`EVID-002`" in md

    # Verify physical file paths exist on disk
    file_path = report_result["file_path"]
    html_path = report_result["html_file_path"]
    assert os.path.exists(file_path)
    assert os.path.exists(html_path)
    assert os.path.getsize(file_path) > 500
    assert os.path.getsize(html_path) > 500

    # Clean up test artifacts
    if os.path.exists(file_path):
        os.remove(file_path)
    if os.path.exists(html_path):
        os.remove(html_path)
