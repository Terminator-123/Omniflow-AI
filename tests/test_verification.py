"""Unit tests for the Verification Engine."""
import os
import pytest
from backend.agent.verifier import verifier

def test_step_verification_success():
    """Verifies deterministic checks pass for a successful page extraction."""
    step = {"id": "step-1", "tool_name": "browser_page_extractor"}
    tool_output = {
        "status_code": 200,
        "content": "A" * 200,
        "final_url": "https://www.ibm.com/think/topics/ai-agents",
    }
    results = verifier.verify_step_execution(step, tool_output, sources=[], evidences=[])
    assert len(results) == 3
    assert all(r["is_passed"] for r in results)

def test_step_verification_failure():
    """Verifies deterministic checks accurately flag empty content and non-200 status."""
    step = {"id": "step-2", "tool_name": "browser_page_extractor"}
    bad_output = {
        "status_code": 503,
        "content": "",
        "final_url": "https://example.com/failed",
    }
    results = verifier.verify_step_execution(step, bad_output, sources=[], evidences=[])
    passed_map = {r["check_name"]: r["is_passed"] for r in results}
    assert passed_map["page_content_non_empty"] is False
    assert passed_map["http_status_success"] is False

def test_report_verification_all_sections():
    """Verifies report check detects presence and absence of required sections."""
    # Complete markdown with all 9 sections
    complete_report = """
    # Report Title
    ## 1. Research Objective
    Obj
    ## 2. Executive Summary
    Exec
    ## 3. Key Findings
    Keys with `EVID-001`
    ## 4. Topic-by-Topic Comparison
    Comp
    ## 5. Supporting Evidence and Source Links
    Evs
    ## 6. Limitations and Unresolved Questions
    Limits
    ## 7. Sources Consulted
    Sources
    ## 8. Execution Summary
    Exec sum
    ## 9. Verification Results
    Verifs
    """
    evidences = [{"stable_id": "EVID-001"}]
    sources = [{"domain": "ibm.com"}]

    # Create dummy file to pass file exists check
    dummy_file = "dummy_test_report.md"
    with open(dummy_file, "w") as f:
        f.write(complete_report)

    try:
        results = verifier.verify_final_report(complete_report, sources, evidences, dummy_file)
        passed_map = {r["check_name"]: r["is_passed"] for r in results}
        assert passed_map["all_nine_sections_present"] is True
        assert passed_map["evidence_id_referential_integrity"] is True
        assert passed_map["downloadable_report_file_exists"] is True

        # Incomplete report (missing section 4 and 6)
        broken_report = "# Broken Report\n## 1. Research Objective\n## 2. Executive Summary"
        broken_results = verifier.verify_final_report(broken_report, sources, evidences, dummy_file)
        broken_map = {r["check_name"]: r["is_passed"] for r in broken_results}
        assert broken_map["all_nine_sections_present"] is False

    finally:
        if os.path.exists(dummy_file):
            os.remove(dummy_file)

def test_evidence_orphan_detection():
    """Verifies that referencing an uncaptured evidence ID fails referential integrity."""
    report_with_orphan = """
    ## 1. Research Objective
    ## 2. Executive Summary
    ## 3. Key Findings
    Claim citing `EVID-999` which was never captured!
    ## 4. Topic-by-Topic Comparison
    ## 5. Supporting Evidence and Source Links
    ## 6. Limitations and Unresolved Questions
    ## 7. Sources Consulted
    ## 8. Execution Summary
    ## 9. Verification Results
    """
    known_evidences = [{"stable_id": "EVID-001"}]
    results = verifier.verify_final_report(report_with_orphan, sources=[], evidences=known_evidences, file_path="nonexistent")
    ref_check = next(r for r in results if r["check_name"] == "evidence_id_referential_integrity")
    assert ref_check["is_passed"] is False
