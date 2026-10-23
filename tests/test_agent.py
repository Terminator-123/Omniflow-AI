"""Unit and integration tests for LangGraph agent workflow, tools, and recovery."""
import pytest
from backend.agent.graph import agent_app
from backend.agent.planner import plan_task
from backend.agent.executor import execute_step
from backend.agent.recovery import classify_error, decide_recovery
from backend.tools.registry import validate_tool_call
from backend.core.exceptions import PolicyViolationError, ToolExecutionError

def test_planner_generates_valid_sequence():
    """Verifies that plan_task returns a compliant step sequence."""
    plan_out = plan_task("Research AI agent reliability and risks", scope="IBM, Google Cloud, NIST")
    assert "steps" in plan_out
    assert len(plan_out["steps"]) >= 4
    for s in plan_out["steps"]:
        assert s["step_order"] >= 1
        assert s["tool_name"] in {"web_search", "browser_page_extractor", "evidence_synthesizer", "report_generator", "result_verifier"}

def test_tool_allowlist_security():
    """Verifies that unauthorized tools or dangerous commands are strictly blocked."""
    # Disallowed tools
    with pytest.raises(PolicyViolationError):
        validate_tool_call("bash_shell", {"command": "rm -rf /"})

    with pytest.raises(PolicyViolationError):
        validate_tool_call("python_eval", {"code": "import os; os.system('echo')"})

    # Disallowed URL schemes
    with pytest.raises(PolicyViolationError):
        validate_tool_call("browser_page_extractor", {"url": "file:///etc/passwd"})

    with pytest.raises(PolicyViolationError):
        validate_tool_call("browser_page_extractor", {"url": "http://127.0.0.1:8000/secret"})

    # Allowed tool call
    validate_tool_call("browser_page_extractor", {"url": "https://www.ibm.com/think/topics/ai-agents"})

def test_error_classification():
    """Verifies error classification for different failure modes."""
    assert classify_error("HTTP 503: Service Unavailable") == "HTTP_503_SERVICE_UNAVAILABLE"
    assert classify_error("Navigation timed out after 15000ms") == "TRANSIENT_NETWORK_TIMEOUT"
    assert classify_error("HTTP 404: Page Not Found") == "HTTP_404_NOT_FOUND"
    assert classify_error("Policy violation: Disallowed tool") == "POLICY_VIOLATION_BLOCKED"

def test_recovery_decision_bounded_retries():
    """Verifies recovery engine caps retries at max limit."""
    # Attempt 0 -> retry
    dec0 = decide_recovery("Connection timed out", "browser_page_extractor", {"url": "https://example.com"}, current_retry_count=0, max_retries=2)
    assert dec0.action in ("retry", "retry_with_alternative")

    # Attempt 2 (at limit) -> fail_step
    dec2 = decide_recovery("Connection timed out", "browser_page_extractor", {"url": "https://example.com"}, current_retry_count=2, max_retries=2)
    assert dec2.action == "fail_step"

def test_controlled_failure_and_autonomous_recovery():
    """Verifies that a simulated Step 3 failure triggers alternate mirror recovery."""
    step = {
        "step_order": 3,
        "title": "Access NIST AI RMF",
        "tool_name": "browser_page_extractor",
        "tool_input": {"url": "https://www.nist.gov/itl/ai-risk-management-framework"},
    }

    # Execute in controlled_failure mode (attempt 0 triggers simulated 503)
    result = execute_step(
        step=step,
        execution_mode="controlled_failure",
        collected_sources=[],
        evidence_records=[],
        current_retry_count=0,
    )

    assert result["success"] is False
    assert "recovery_decision" in result
    rec = result["recovery_decision"]
    assert rec["action"] == "retry_with_alternative"
    assert "airc.nist.gov" in rec["updated_tool_input"]["url"]

    # Now execute retry with the updated alternative input
    step_recovered = dict(step)
    step_recovered["tool_input"] = rec["updated_tool_input"]
    recovered_result = execute_step(
        step=step_recovered,
        execution_mode="controlled_failure",
        collected_sources=[],
        evidence_records=[],
        current_retry_count=1,
    )
    assert recovered_result["success"] is True

def test_full_langgraph_workflow_demo_execution():
    """Executes the entire LangGraph workflow from START to END in demo mode."""
    initial_state = {
        "task_id": "test-langgraph-run-123",
        "original_request": "Research benefits and limitations of AI agents.",
        "scope": "IBM, Google Cloud, NIST",
        "execution_mode": "demo",
        "llm_provider": "deterministic_fallback",
        "is_fallback_plan": True,
        "plan": [],
        "current_step_idx": 0,
        "step_statuses": {},
        "retry_counts": {},
        "approval_state": "approved",
        "collected_sources": [],
        "evidence_records": [],
        "tool_results": {},
        "execution_events": [],
        "verification_results": [],
        "final_report": None,
        "status": "pending_plan",
        "error_details": None,
        "recovered_steps": 0,
    }

    final_state = agent_app.invoke(initial_state)
    assert final_state["status"] == "completed"
    assert final_state["final_report"] is not None
    assert final_state["final_report"]["sources_count"] >= 1
    assert final_state["final_report"]["evidence_count"] >= 1
    assert len(final_state["verification_results"]) >= 3
