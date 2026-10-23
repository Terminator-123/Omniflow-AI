"""Unit tests for SQLite database models and repository layer."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base
from backend.database.repository import TaskRepository

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_database_initialization(test_db):
    """Verifies SQLite tables initialize correctly."""
    repo = TaskRepository(test_db)
    tasks = repo.list_tasks()
    assert tasks == []

def test_task_creation_and_status_update(test_db):
    """Verifies task creation and state transitions."""
    repo = TaskRepository(test_db)
    task = repo.create_task(
        title="Research AI Agents",
        original_request="Investigate AI agent safety and capabilities.",
        scope="IBM, Google Cloud, NIST",
        execution_mode="live",
        llm_provider="gemini",
    )
    assert task.id is not None
    assert task.status == "pending_plan"
    assert task.title == "Research AI Agents"

    # Update to running
    updated = repo.update_task_status(task.id, "running")
    assert updated.status == "running"

    # Complete task
    completed = repo.update_task_status(task.id, "completed", completed=True)
    assert completed.status == "completed"
    assert completed.completed_at is not None

def test_plan_steps_persistence(test_db):
    """Verifies plan steps persistence and status updates."""
    repo = TaskRepository(test_db)
    task = repo.create_task("Test Task", "Original request")
    steps_data = [
        {
            "step_order": 1,
            "title": "Search Sources",
            "description": "Discover URLs",
            "tool_name": "web_search",
            "tool_input": {"query": "AI agents"},
            "dependencies": [],
            "requires_approval": False,
        },
        {
            "step_order": 2,
            "title": "Extract Page",
            "description": "Read content",
            "tool_name": "browser_page_extractor",
            "tool_input": {"url": "https://example.com"},
            "dependencies": [1],
            "requires_approval": True,
        },
    ]
    created = repo.add_plan_steps(task.id, steps_data)
    assert len(created) == 2
    assert created[0].step_order == 1
    assert created[1].requires_approval is True

    # Update step 1 status
    step_up = repo.update_step(created[0].id, status="completed", output_summary="Done")
    assert step_up.status == "completed"
    assert step_up.output_summary == "Done"

def test_source_and_evidence_persistence(test_db):
    """Verifies source recording and Evidence Trail persistence with stable IDs."""
    repo = TaskRepository(test_db)
    task = repo.create_task("Test Task", "Request")
    
    # Add source
    source = repo.add_source(
        task_id=task.id,
        title="IBM AI Agents",
        url="https://www.ibm.com/think/topics/ai-agents",
        domain="ibm.com",
        access_status="success",
        http_status_code=200,
        extracted_chars=4500,
    )
    assert source.id is not None
    assert source.domain == "ibm.com"

    # Add evidence record
    evidence = repo.add_evidence(
        task_id=task.id,
        source_id=source.id,
        stable_id="EVID-001",
        research_question="What are agent capabilities?",
        excerpt="AI agents perceive their environment and execute multi-step plans.",
        finding="Confirms autonomous reasoning and tool use.",
        verification_status="claim_supported",
    )
    assert evidence.stable_id == "EVID-001"
    assert evidence.verification_status == "claim_supported"

    evidences = repo.get_evidences(task.id)
    assert len(evidences) == 1
    assert evidences[0].stable_id == "EVID-001"

def test_execution_events_and_verifications(test_db):
    """Verifies event logging and verification persistence."""
    repo = TaskRepository(test_db)
    task = repo.create_task("Test Task", "Request")

    event = repo.add_event(
        task_id=task.id,
        event_type="STEP_STARTED",
        message="Starting step 1",
        details={"step": 1},
    )
    assert event.id is not None
    assert event.event_type == "STEP_STARTED"

    events = repo.get_events(task.id)
    assert len(events) == 1

    # Verification
    vr = repo.add_verification(
        task_id=task.id,
        target_type="step",
        check_name="content_non_empty",
        is_passed=True,
        deterministic=True,
    )
    assert vr.is_passed is True

def test_report_save_and_fetch(test_db):
    """Verifies report model persistence and retrieval."""
    repo = TaskRepository(test_db)
    task = repo.create_task("Report Task", "Request")

    report = repo.save_report(
        task_id=task.id,
        title="Autonomous Research Report",
        executive_summary="Summary text",
        content_markdown="# Report\nContent",
        file_path="/path/to/report.md",
        sources_count=3,
        evidence_count=4,
    )
    assert report.id is not None
    assert report.sources_count == 3

    fetched = repo.get_report(task.id)
    assert fetched is not None
    assert fetched.title == "Autonomous Research Report"
