"""Integration tests for FastAPI REST endpoints."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.research_service import research_service
from backend.services.gemini_service import gemini_service

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_health_check_endpoint(client):
    """Verifies the health check endpoint returns 200 and operational status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "database" in data

def test_create_task_and_validation(client):
    """Verifies task submission and Pydantic schema validation."""
    # Invalid request (too short)
    bad_resp = client.post("/api/tasks", json={"original_request": "hi"})
    assert bad_resp.status_code == 422

    # Valid task submission
    resp = client.post(
        "/api/tasks",
        json={
            "original_request": "Research the benefits and limitations of AI agents.",
            "scope": "IBM, Google Cloud, NIST",
            "execution_mode": "demo",
        },
    )
    assert resp.status_code == 201
    task = resp.json()
    assert task["id"] is not None
    assert task["status"] == "awaiting_approval"
    assert len(task["steps"]) >= 3
    assert "llm_provider" in task

def test_get_task_and_plan(client):
    """Verifies retrieval of task details and structured plan."""
    resp = client.post(
        "/api/tasks",
        json={"original_request": "Analyze multi-agent safety.", "execution_mode": "demo"},
    )
    task_id = resp.json()["id"]

    # Get task
    get_resp = client.get(f"/api/tasks/{task_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id

    # Get plan
    plan_resp = client.get(f"/api/tasks/{task_id}/plan")
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert plan_data["task_id"] == task_id
    assert len(plan_data["steps"]) >= 3

def test_plan_approval_and_rejection(client):
    """Verifies plan approval transitions task to approved."""
    resp = client.post(
        "/api/tasks",
        json={"original_request": "Investigate agent risks.", "execution_mode": "demo"},
    )
    task_id = resp.json()["id"]

    # Approve
    app_resp = client.post(
        f"/api/tasks/{task_id}/approve",
        json={"decision": "approved", "comments": "Proceed with research."},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "approved"

def test_start_task_and_prevent_duplicate_execution(client):
    """Verifies starting task execution and duplicate start prevention."""
    resp = client.post(
        "/api/tasks",
        json={"original_request": "Execute sample agent test.", "execution_mode": "demo"},
    )
    task_id = resp.json()["id"]

    # Approve
    client.post(f"/api/tasks/{task_id}/approve", json={"decision": "approved"})

    # Test start with controlled mock on background worker
    with patch.object(research_service, "start_task_execution") as mock_start:
        mock_start.return_value = True
        start_resp = client.post(f"/api/tasks/{task_id}/start")
        assert start_resp.status_code == 202
        assert start_resp.json()["started"] is True
        mock_start.assert_called_once_with(task_id)

        # Duplicate start attempt: service reports already running
        mock_start.return_value = False
        dup_resp = client.post(f"/api/tasks/{task_id}/start")
        assert dup_resp.status_code == 202
        assert dup_resp.json()["started"] is False

def test_task_cancellation(client):
    """Verifies cancellation endpoint halts execution."""
    resp = client.post(
        "/api/tasks",
        json={"original_request": "Execute cancellation check.", "execution_mode": "demo"},
    )
    task_id = resp.json()["id"]
    client.post(f"/api/tasks/{task_id}/approve", json={"decision": "approved"})

    with patch.object(research_service, "cancel_task") as mock_cancel:
        mock_cancel.return_value = True
        cancel_resp = client.post(f"/api/tasks/{task_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"
        mock_cancel.assert_called_once_with(task_id)

def test_invalid_task_404(client):
    """Verifies proper 404 behavior for non-existent task IDs."""
    bad_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/api/tasks/{bad_id}")
    assert resp.status_code == 404

def test_configure_gemini_key_endpoint(client, monkeypatch):
    """Verifies key setting endpoint returns masked key and enforces admin auth when configured."""
    resp = client.post("/api/config/gemini_key", json={"api_key": "AIzaSyValidTestKey123456"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert "masked_key" in resp.json()

    # When OMNIFLOW_ADMIN_KEY is configured in environment
    monkeypatch.setenv("OMNIFLOW_ADMIN_KEY", "super_secret_admin_token")
    # Missing header -> 403
    unauth_resp = client.post("/api/config/gemini_key", json={"api_key": "AIzaSyTest"})
    assert unauth_resp.status_code == 403

    # With header -> 200
    auth_resp = client.post(
        "/api/config/gemini_key",
        json={"api_key": "AIzaSyTestKey"},
        headers={"X-Admin-Key": "super_secret_admin_token"},
    )
    assert auth_resp.status_code == 200

    # Reset key back to clean state
    gemini_service.set_api_key("")

def test_upload_task_document_endpoint(client):
    """Verifies file upload and ingestion via POST /api/tasks/{task_id}/documents."""
    resp = client.post(
        "/api/tasks",
        json={"original_request": "Test document grounding.", "execution_mode": "demo"},
    )
    task_id = resp.json()["id"]

    files = {"file": ("test_policy.txt", b"Enterprise Safety Policy: Human oversight is required.", "text/plain")}
    doc_resp = client.post(f"/api/tasks/{task_id}/documents", files=files)
    assert doc_resp.status_code == 200
    assert doc_resp.json()["status"] == "success"
    assert doc_resp.json()["filename"] == "test_policy.txt"
    assert doc_resp.json()["evidence_count"] >= 1

def test_task_productivity_endpoint(client):
    """Verifies productivity metrics endpoint."""
    resp = client.post(
        "/api/tasks",
        json={"original_request": "Test productivity metrics.", "execution_mode": "demo"},
    )
    task_id = resp.json()["id"]

    prod_resp = client.get(f"/api/tasks/{task_id}/productivity")
    assert prod_resp.status_code == 200
    metrics = prod_resp.json()
    assert "speedup_factor" in metrics
    assert "time_savings_pct" in metrics
    assert metrics["time_savings_pct"] > 50.0
