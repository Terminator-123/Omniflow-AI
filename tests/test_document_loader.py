"""Unit tests for Document Ingestion and Parser."""
import pytest
from backend.tools.document_loader import ingest_document
from backend.core.exceptions import ToolExecutionError

def test_ingest_text_document():
    """Verifies that a plain text file is parsed and yields structured evidence."""
    sample_content = (
        "Internal Technical Report on Autonomous AI Agents.\n"
        "Core Capabilities: AI agents leverage foundational models to plan multi-step workflows, "
        "perceive environmental state, and invoke external tool integrations.\n"
        "Reliability & Governance: Compounding errors across multi-turn trajectories require continuous "
        "human-in-the-loop oversight and verification guardrails."
    ).encode("utf-8")

    result = ingest_document(
        filename="ai_report.txt",
        file_bytes=sample_content,
        task_id="task-doc-001",
        start_evidence_index=1,
    )
    assert result["filename"] == "ai_report.txt"
    assert result["extracted_chars"] > 100
    assert result["source"]["domain"] == "user_upload"
    assert len(result["evidences"]) >= 1
    assert result["evidences"][0]["provenance"] == "user_upload"

def test_ingest_rejects_unsupported_format():
    """Verifies that unsupported or executable extensions are rejected."""
    with pytest.raises(ToolExecutionError, match="Unsupported document format"):
        ingest_document(
            filename="malicious.exe",
            file_bytes=b"MZ123456",
            task_id="task-doc-002",
        )

def test_ingest_rejects_oversized_file():
    """Verifies that files exceeding 10MB are rejected."""
    oversized = b"A" * (11 * 1024 * 1024)
    with pytest.raises(ToolExecutionError, match="exceeds the maximum limit"):
        ingest_document(
            filename="big.txt",
            file_bytes=oversized,
            task_id="task-doc-003",
        )
