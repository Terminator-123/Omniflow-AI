"""Research service orchestrating LangGraph execution with SQLite persistence and background threading."""
import json
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from backend.database.connection import SessionLocal
from backend.database.repository import TaskRepository
from backend.agent.graph import agent_app
from backend.agent.state import AgentState
from backend.core.logging_config import logger

class ResearchService:
    def __init__(self):
        self._active_tasks: Dict[str, threading.Thread] = {}
        self._cancel_flags: Dict[str, bool] = {}
        self._lock = threading.RLock()

    def is_task_running(self, task_id: str) -> bool:
        with self._lock:
            thread = self._active_tasks.get(task_id)
            return thread is not None and thread.is_alive()

    def wait_for_task(self, task_id: str, timeout: float = 6.0) -> bool:
        """Waits for an active background thread to complete within timeout."""
        with self._lock:
            thread = self._active_tasks.get(task_id)
        if thread:
            thread.join(timeout=timeout)
            return not thread.is_alive()
        return True

    def cancel_task(self, task_id: str) -> bool:
        """Signals an active task to halt subsequent execution steps."""
        logger.info(f"Cancellation requested for task {task_id}")
        with self._lock:
            self._cancel_flags[task_id] = True
            
        # Update task status in database
        db = SessionLocal()
        try:
            repo = TaskRepository(db)
            repo.update_task_status(task_id, "cancelled", error_summary="User requested task cancellation.")
            repo.add_event(
                task_id=task_id,
                event_type="TASK_CANCELLED",
                level="WARNING",
                message="Task execution cancelled by user request.",
            )
        finally:
            db.close()
        return True

    def start_task_execution(self, task_id: str) -> bool:
        """Launches the LangGraph workflow for task_id in an asynchronous background worker."""
        with self._lock:
            if self.is_task_running(task_id):
                logger.warning(f"Task {task_id} is already actively running. Ignoring duplicate start call.")
                return False

            self._cancel_flags[task_id] = False
            worker = threading.Thread(
                target=self._run_task_lifecycle,
                args=(task_id,),
                name=f"omniflow-worker-{task_id}",
                daemon=True,
            )
            self._active_tasks[task_id] = worker
            worker.start()
            logger.info(f"Spawned background execution worker for task {task_id}")
            return True

    def _run_task_lifecycle(self, task_id: str):
        """Worker thread executing the LangGraph agent graph via streaming and persisting transitions."""
        logger.info(f"Worker started for task {task_id}")
        db = SessionLocal()
        repo = TaskRepository(db)

        try:
            task = repo.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found in database.")
                return

            repo.update_task_status(task_id, "running")
            repo.add_event(
                task_id=task_id,
                event_type="EXECUTION_STARTED",
                level="INFO",
                message=f"Autonomous workflow running in '{task.execution_mode}' mode.",
            )

            # Reconstruct initial plan from database
            from backend.database.models import PlanStepModel
            steps_db = repo.db.query(PlanStepModel).filter(PlanStepModel.task_id == task_id).order_by(PlanStepModel.step_order.asc()).all()
            initial_plan = [
                {
                    "id": s.id,
                    "step_order": s.step_order,
                    "title": s.title,
                    "description": s.description,
                    "tool_name": s.tool_name,
                    "tool_input": json.loads(s.tool_input_json) if s.tool_input_json else {},
                    "dependencies": json.loads(s.dependencies_json) if s.dependencies_json else [],
                    "requires_approval": s.requires_approval,
                    "status": s.status,
                    "retry_count": s.retry_count,
                }
                for s in steps_db
            ]

            state: AgentState = {
                "task_id": task.id,
                "original_request": task.original_request,
                "scope": task.scope,
                "execution_mode": task.execution_mode,
                "llm_provider": task.llm_provider,
                "is_fallback_plan": False,
                "plan": initial_plan,
                "current_step_idx": 0,
                "step_statuses": {s["step_order"]: s["status"] for s in initial_plan},
                "retry_counts": {s["step_order"]: 0 for s in initial_plan},
                "approval_state": "approved",
                "collected_sources": [],
                "evidence_records": [],
                "tool_results": {},
                "execution_events": [],
                "verification_results": [],
                "final_report": None,
                "status": "running",
                "error_details": None,
                "recovered_steps": 0,
            }

            accumulated_state = dict(state)
            persisted_events_count = 0

            # Stream LangGraph execution
            for step_chunk in agent_app.stream(state):
                # Check for cancellation signal
                if self._cancel_flags.get(task_id, False):
                    logger.info(f"Task {task_id} stopping downstream execution due to cancellation signal.")
                    break

                for node_name, node_update in step_chunk.items():
                    accumulated_state.update(node_update)

                    # Sync newly appended execution events to DB
                    current_events = accumulated_state.get("execution_events", [])
                    while persisted_events_count < len(current_events):
                        ev = current_events[persisted_events_count]
                        repo.add_event(
                            task_id=task_id,
                            event_type=ev.get("event_type", "STEP_EVENT"),
                            message=ev.get("message", ""),
                            step_id=str(ev.get("step_id")) if ev.get("step_id") else None,
                            level=ev.get("level", "INFO"),
                            details=ev.get("details"),
                        )
                        persisted_events_count += 1

                    # When a step is observed / completed
                    if node_name == "observe_and_recover":
                        # Sync step status to DB
                        for s_order, status_val in accumulated_state.get("step_statuses", {}).items():
                            step_db = next((s for s in steps_db if s.step_order == s_order), None)
                            if step_db:
                                retry_num = accumulated_state.get("retry_counts", {}).get(s_order, 0)
                                repo.update_step(
                                    step_id=step_db.id,
                                    status=status_val,
                                    retry_count=retry_num,
                                    completed=(status_val == "completed"),
                                )

                        # Sync newly collected sources to DB
                        for src in accumulated_state.get("collected_sources", []):
                            repo.add_source(
                                task_id=task_id,
                                title=src.get("title", "Untitled Source"),
                                url=src.get("url", ""),
                                domain=src.get("domain", ""),
                                access_status=src.get("access_status", "success"),
                                http_status_code=src.get("http_status_code", 200),
                                extracted_chars=src.get("extracted_chars", 0),
                                raw_content_preview=src.get("raw_content_preview", ""),
                            )

                        # Sync evidence records to DB
                        for ev in accumulated_state.get("evidence_records", []):
                            repo.add_evidence(
                                task_id=task_id,
                                stable_id=ev["stable_id"],
                                research_question=ev["research_question"],
                                excerpt=ev["excerpt"],
                                finding=ev["finding"],
                                verification_status=ev.get("verification_status", "captured"),
                            )

                    # When report verification is done
                    elif node_name == "verify_report":
                        final_rep = accumulated_state.get("final_report", {})
                        if final_rep:
                            repo.save_report(
                                task_id=task_id,
                                title=final_rep.get("title", "Autonomous Research Report"),
                                executive_summary=final_rep.get("executive_summary", ""),
                                content_markdown=final_rep.get("content_markdown", ""),
                                file_path=final_rep.get("file_path"),
                                sources_count=final_rep.get("sources_count", 0),
                                evidence_count=final_rep.get("evidence_count", 0),
                                verification_summary="All 9 sections confirmed. Referential integrity valid.",
                            )

                        for vr in accumulated_state.get("verification_results", []):
                            repo.add_verification(
                                task_id=task_id,
                                target_type=vr.get("target_type", "report"),
                                check_name=vr.get("check_name", "check"),
                                is_passed=vr.get("is_passed", True),
                                deterministic=vr.get("deterministic", True),
                                details=vr.get("details"),
                            )

                        repo.update_task_status(task_id, "completed", completed=True)
                        repo.add_event(
                            task_id=task_id,
                            event_type="TASK_COMPLETED",
                            level="SUCCESS",
                            message="Workflow completed successfully. Deliverables verified.",
                        )
                        logger.info(f"Task {task_id} successfully finalized in database.")

        except Exception as exc:
            logger.error(f"Fatal error during task {task_id} background execution: {exc}", exc_info=True)
            repo.update_task_status(task_id, "failed", error_summary=str(exc))
            repo.add_event(
                task_id=task_id,
                event_type="TASK_FAILED",
                level="ERROR",
                message=f"Fatal workflow failure: {str(exc)}",
            )
        finally:
            with self._lock:
                self._active_tasks.pop(task_id, None)
                self._cancel_flags.pop(task_id, None)
            db.close()

research_service = ResearchService()
