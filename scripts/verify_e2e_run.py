"""End-to-end verification script for OmniFlow AI autonomous research workflow."""
import sys
import os
import time

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.connection import SessionLocal, init_db
from backend.database.repository import TaskRepository
from backend.services.research_service import research_service
from backend.services.gemini_service import gemini_service
from backend.agent.planner import plan_task

def test_full_autonomous_workflow(mode: str = "demo"):
    print(f"\n=======================================================")
    print(f"Starting E2E Verification in Mode: '{mode.upper()}'")
    print(f"=======================================================")

    db = SessionLocal()
    repo = TaskRepository(db)

    prompt = (
        "Research the benefits and limitations of AI agents. Compare their capabilities, "
        "reliability, risks, and need for human oversight. Use IBM, Google Cloud, and NIST "
        "as sources and generate a concise report with source links."
    )
    scope = "ibm.com, cloud.google.com, nist.gov"

    # Step 1: Create task
    task = repo.create_task(
        title="AI Agent Benefits & Limitations Research",
        original_request=prompt,
        scope=scope,
        execution_mode=mode,
        llm_provider=gemini_service.provider_name,
    )
    task_id = task.id
    print(f"[OK] Created Task ID: {task_id}")
    print(f"     Provider: {task.llm_provider}")
    print(f"     Mode: {task.execution_mode}")

    # Step 2: Generate plan
    plan_data = plan_task(prompt, scope)
    plan_steps = plan_data["steps"]
    is_fallback = plan_data.get("is_fallback", False)
    print(f"[OK] Generated Plan with {len(plan_steps)} steps (Fallback plan: {is_fallback})")
    for s in plan_steps:
        print(f"     Step {s['step_order']}: {s['title']} [{s['tool_name']}]")
    
    repo.add_plan_steps(task_id=task_id, steps=plan_steps)

    # Step 3: Approve plan
    repo.record_approval(task_id, "approved", comments="Automated E2E verification test approval.")
    repo.update_task_status(task_id, "approved")
    print("[OK] Plan approved.")
    db.close()

    # Step 4: Start execution
    started = research_service.start_task_execution(task_id)
    assert started, "Failed to start background execution!"
    print(f"[OK] Background execution started. Polling for completion...")

    # Step 5: Wait for completion
    timeout = 30.0
    start_time = time.time()
    completed = False
    while time.time() - start_time < timeout:
        poll_db = SessionLocal()
        try:
            poll_repo = TaskRepository(poll_db)
            current_task = poll_repo.get_task(task_id)
            if current_task and current_task.status in ["completed", "failed", "cancelled"]:
                completed = True
                break
        finally:
            poll_db.close()
        time.sleep(0.5)

    assert completed, f"Execution timed out after {timeout} seconds!"
    
    db = SessionLocal()
    repo = TaskRepository(db)
    final_task = repo.get_task(task_id)
    print(f"[OK] Final task status: {final_task.status} in {time.time() - start_time:.2f}s")
    assert final_task.status == "completed", f"Task ended with status: {final_task.status}"

    # Step 6: Validate Steps
    steps = repo.get_plan_steps(task_id)
    print(f"[OK] Verifying {len(steps)} plan steps:")
    for s in steps:
        print(f"     Step {s.step_order} [{s.status}] (retries={s.retry_count}): {s.title}")
        assert s.status == "completed", f"Step {s.step_order} status is {s.status}"

    # Step 7: Validate Sources
    sources = repo.get_sources(task_id)
    print(f"[OK] Sources captured: {len(sources)}")
    for src in sources:
        print(f"     - [{src.http_status_code}] {src.domain}: {src.title[:45]} ({src.extracted_chars} chars)")
    assert len(sources) >= 3, f"Expected at least 3 sources, got {len(sources)}"

    # Step 8: Validate Evidence Trail
    evidences = repo.get_evidences(task_id)
    print(f"[OK] Evidence trail captured: {len(evidences)} records")
    for ev in evidences:
        print(f"     - {ev.stable_id}: {ev.finding[:60]}...")
    assert len(evidences) >= 3, f"Expected at least 3 evidence items, got {len(evidences)}"

    # Step 9: Validate Verification Results
    verifications = repo.get_verifications(task_id)
    print(f"[OK] Verification checks performed: {len(verifications)}")
    for vr in verifications:
        pass_str = "PASS" if vr.is_passed else "FAIL"
        print(f"     - [{pass_str}] ({vr.target_type}) {vr.check_name}: {vr.details}")
        assert vr.is_passed, f"Verification failed: {vr.check_name}"

    # Step 10: Validate Final Report
    report = repo.get_report(task_id)
    assert report is not None, "Report was not saved!"
    print(f"[OK] Report Deliverable: '{report.title}'")
    print(f"     Markdown path: {report.file_path}")
    print(f"     Sources cited: {report.sources_count}, Evidence items: {report.evidence_count}")
    print(f"     Content length: {len(report.content_markdown)} characters")

    # Check 9 sections
    from backend.agent.verifier import REQUIRED_REPORT_SECTIONS
    for sec in REQUIRED_REPORT_SECTIONS:
        assert sec in report.content_markdown, f"Report is missing required section: '{sec}'"
    print(f"[OK] All 9 required report sections confirmed present and structured.")

    if mode == "controlled_failure":
        events = repo.get_events(task_id)
        recovery_events = [e for e in events if "RECOVERY" in e.event_type or "RECOVERED" in e.event_type]
        print(f"[OK] Controlled failure recovery events logged: {len(recovery_events)}")
        assert len(recovery_events) > 0, "No recovery event logged during controlled failure mode!"
        for re in recovery_events:
            print(f"     - [{re.level}] {re.event_type}: {re.message}")

    db.close()
    print(f"\n[SUCCESS] E2E Verification for mode '{mode}' PASSED flawlessly.\n")

if __name__ == "__main__":
    init_db()
    # Run standard demo mode
    test_full_autonomous_workflow(mode="demo")
    # Run controlled failure and recovery mode
    test_full_autonomous_workflow(mode="controlled_failure")
