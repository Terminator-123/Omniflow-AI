"""FastAPI endpoints for OmniFlow AI task lifecycle and artifact retrieval."""
import os
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Header
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.repository import TaskRepository
from backend.agent.planner import plan_task
from backend.services.research_service import research_service
from backend.services.gemini_service import gemini_service
from backend.api.schemas import (
    TaskCreateRequest,
    TaskResponse,
    PlanResponse,
    PlanStepSchema,
    ApprovalRequest,
    EventResponse,
    EvidenceItemResponse,
    SourceResponse,
    ReportResponse,
    HealthResponse,
)
from backend.config import settings
from backend.core.logging_config import logger

router = APIRouter(prefix="/api", tags=["OmniFlow Agent"])

def _model_to_task_response(task, repo: TaskRepository) -> TaskResponse:
    from backend.database.models import PlanStepModel, SourceModel, EvidenceModel
    steps_models = repo.db.query(PlanStepModel).filter(PlanStepModel.task_id == task.id).order_by(PlanStepModel.step_order.asc()).all()
    sources_cnt = repo.db.query(SourceModel).filter(SourceModel.task_id == task.id).count()
    evidences_cnt = repo.db.query(EvidenceModel).filter(EvidenceModel.task_id == task.id).count()

    steps = [
        PlanStepSchema(
            id=s.id,
            step_order=s.step_order,
            title=s.title,
            description=s.description,
            tool_name=s.tool_name,
            tool_input=json.loads(s.tool_input_json) if s.tool_input_json else {},
            dependencies=json.loads(s.dependencies_json) if s.dependencies_json else [],
            requires_approval=s.requires_approval,
            status=s.status,
            retry_count=s.retry_count,
            output_summary=s.output_summary,
            error_message=s.error_message,
        )
        for s in steps_models
    ]
    return TaskResponse(
        id=task.id,
        title=task.title,
        original_request=task.original_request,
        scope=task.scope,
        status=task.status,
        execution_mode=task.execution_mode,
        llm_provider=task.llm_provider,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        error_summary=task.error_summary,
        steps=steps,
        sources_count=sources_cnt,
        evidence_count=evidences_cnt,
    )

@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Health check verifying database connectivity, Gemini status, and browser tool readiness."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        database="sqlite_active",
        gemini_configured=gemini_service.is_configured(),
        playwright_available=True,
    )

@router.post("/config/gemini_key")
def configure_gemini_key(payload: dict, x_admin_key: Optional[str] = Header(None)):
    """Dynamically sets or updates the Gemini API key in-memory with authorization checks."""
    admin_secret = os.getenv("OMNIFLOW_ADMIN_KEY", "").strip()
    if admin_secret and x_admin_key != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: invalid or missing admin credentials (X-Admin-Key)."
        )

    key = payload.get("api_key", "").strip()
    success = gemini_service.set_api_key(key)
    return {
        "status": "success" if success else "failed",
        "gemini_configured": gemini_service.is_configured(),
        "provider": gemini_service.provider_name,
        "masked_key": gemini_service.masked_key,
    }

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(req: TaskCreateRequest, db: Session = Depends(get_db)):
    """Submits a new task, generates the plan, and initializes task state in SQLite."""
    from backend.database.models import TaskModel, PlanStepModel, ExecutionEventModel
    logger.info(f"POST /api/tasks: Creating task for '{req.original_request[:50]}...'")
    repo = TaskRepository(db)

    # 1. Generate execution plan
    plan_out = plan_task(req.original_request, req.scope)

    # 2. Persist task, steps, and event in a single atomic transaction
    task_title = req.original_request.split(".")[0][:60]
    task = TaskModel(
        title=task_title,
        original_request=req.original_request,
        scope=req.scope,
        execution_mode=req.execution_mode,
        llm_provider=plan_out["llm_provider"],
        status="awaiting_approval",
    )
    db.add(task)
    db.flush()

    for s in plan_out["steps"]:
        step = PlanStepModel(
            task_id=task.id,
            step_order=s["step_order"],
            title=s["title"],
            description=s["description"],
            tool_name=s["tool_name"],
            tool_input_json=json.dumps(s.get("tool_input", {})),
            dependencies_json=json.dumps(s.get("dependencies", [])),
            requires_approval=s.get("requires_approval", False),
            status="planned",
        )
        db.add(step)

    event = ExecutionEventModel(
        task_id=task.id,
        event_type="TASK_CREATED",
        level="INFO",
        message=f"Task initialized. Plan generated ({len(plan_out['steps'])} steps) via {plan_out['llm_provider']}.",
        details_json=json.dumps({"is_fallback": plan_out.get("is_fallback", False), "reason": plan_out.get("reason")}),
    )
    db.add(event)
    db.commit()

    return _model_to_task_response(task, repo)

@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Retrieves SQLite-backed task history."""
    repo = TaskRepository(db)
    tasks = repo.list_tasks(limit=limit, offset=offset)
    return [_model_to_task_response(t, repo) for t in tasks]

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Retrieves current state and steps of a specific task."""
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return _model_to_task_response(task, repo)

@router.get("/tasks/{task_id}/plan", response_model=PlanResponse)
def get_task_plan(task_id: str, db: Session = Depends(get_db)):
    """Retrieves the structured plan steps for review."""
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    steps = [
        PlanStepSchema(
            id=s.id,
            step_order=s.step_order,
            title=s.title,
            description=s.description,
            tool_name=s.tool_name,
            tool_input=json.loads(s.tool_input_json) if s.tool_input_json else {},
            dependencies=json.loads(s.dependencies_json) if s.dependencies_json else [],
            requires_approval=s.requires_approval,
            status=s.status,
            retry_count=s.retry_count,
            output_summary=s.output_summary,
            error_message=s.error_message,
        )
        for s in task.steps
    ]
    return PlanResponse(
        task_id=task.id,
        steps=steps,
        llm_provider=task.llm_provider,
        is_fallback=("fallback" in task.llm_provider),
    )

@router.post("/tasks/{task_id}/approve", response_model=TaskResponse)
def approve_plan(task_id: str, req: ApprovalRequest, db: Session = Depends(get_db)):
    """Records the user's plan approval decision."""
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    decision = req.decision.lower()
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'.")

    from backend.database.models import ExecutionEventModel
    repo.record_approval(task_id, decision, comments=req.comments)
    if decision == "approved":
        task.status = "approved"
        event = ExecutionEventModel(
            task_id=task_id,
            event_type="PLAN_APPROVED",
            level="SUCCESS",
            message="Plan approved by user. Ready for agent execution.",
        )
    else:
        task.status = "rejected"
        task.error_summary = "Plan rejected by user."
        event = ExecutionEventModel(
            task_id=task_id,
            event_type="PLAN_REJECTED",
            level="WARNING",
            message=f"Plan rejected by user: {req.comments or 'No reason provided.'}",
        )

    db.add(event)
    db.commit()
    return _model_to_task_response(task, repo)

@router.post("/tasks/{task_id}/start", status_code=status.HTTP_202_ACCEPTED)
def start_task(task_id: str, db: Session = Depends(get_db)):
    """Triggers background execution of an approved task."""
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    if task.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot start task in '{task.status}' state.")

    db.close()
    started = research_service.start_task_execution(task_id)
    return {
        "task_id": task_id,
        "started": started,
        "message": "Background execution started." if started else "Task is already executing.",
    }

@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """Signals an active task to stop subsequent step execution."""
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    cancelled = research_service.cancel_task(task_id)
    if not cancelled:
        # If not actively in thread, mark cancelled in DB
        repo.update_task_status(task_id, "cancelled", error_summary="Task cancelled by user.")

    return {"task_id": task_id, "status": "cancelled"}

@router.get("/tasks/{task_id}/events", response_model=List[EventResponse])
def get_task_events(task_id: str, limit: int = 100, db: Session = Depends(get_db)):
    """Returns stored SQLite execution log events."""
    repo = TaskRepository(db)
    events = repo.get_events(task_id, limit=limit)
    return [
        EventResponse(
            id=e.id,
            task_id=e.task_id,
            step_id=e.step_id,
            event_type=e.event_type,
            level=e.level,
            message=e.message,
            details=json.loads(e.details_json) if e.details_json else None,
            timestamp=e.timestamp,
        )
        for e in events
    ]

@router.get("/tasks/{task_id}/evidence", response_model=List[EvidenceItemResponse])
def get_task_evidence(task_id: str, db: Session = Depends(get_db)):
    """Returns the Evidence Trail for a given task."""
    repo = TaskRepository(db)
    evidences = repo.get_evidences(task_id)
    return [
        EvidenceItemResponse(
            id=ev.id,
            stable_id=ev.stable_id,
            research_question=ev.research_question,
            excerpt=ev.excerpt,
            finding=ev.finding,
            verification_status=ev.verification_status,
            source_url=ev.source.url if ev.source else None,
            source_title=ev.source.title if ev.source else None,
            step_title=ev.step.title if ev.step else None,
            created_at=ev.created_at,
        )
        for ev in evidences
    ]

@router.get("/tasks/{task_id}/sources", response_model=List[SourceResponse])
def get_task_sources(task_id: str, db: Session = Depends(get_db)):
    """Returns the consulted sources for a given task."""
    repo = TaskRepository(db)
    sources = repo.get_sources(task_id)
    return [
        SourceResponse(
            id=s.id,
            title=s.title,
            url=s.url,
            domain=s.domain,
            access_status=s.access_status,
            http_status_code=s.http_status_code,
            extracted_chars=s.extracted_chars,
            accessed_at=s.accessed_at,
            raw_content_preview=s.raw_content_preview,
        )
        for s in sources
    ]

@router.get("/tasks/{task_id}/report", response_model=ReportResponse)
def get_task_report(task_id: str, db: Session = Depends(get_db)):
    """Retrieves the generated final report for a task."""
    repo = TaskRepository(db)
    report = repo.get_report(task_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated for this task.")

    return ReportResponse(
        id=report.id,
        task_id=report.task_id,
        title=report.title,
        executive_summary=report.executive_summary,
        content_markdown=report.content_markdown,
        file_path=report.file_path,
        sources_count=report.sources_count,
        evidence_count=report.evidence_count,
        verification_summary=report.verification_summary,
        created_at=report.created_at,
    )

@router.get("/tasks/{task_id}/download")
def download_task_report(
    task_id: str,
    format: str = Query("markdown", description="'markdown' or 'html'"),
    db: Session = Depends(get_db),
):
    """Downloads the generated report file directly."""
    repo = TaskRepository(db)
    report = repo.get_report(task_id)
    if not report or not report.file_path:
        raise HTTPException(status_code=404, detail="Report file not found.")

    if format == "html":
        html_path = report.file_path.replace(".md", ".html")
        if os.path.exists(html_path):
            return FileResponse(
                path=html_path,
                filename=f"omniflow_report_{task_id}.html",
                media_type="text/html",
            )

    if os.path.exists(report.file_path):
        return FileResponse(
            path=report.file_path,
            filename=f"omniflow_report_{task_id}.md",
            media_type="text/markdown",
        )

    # Fallback to streaming content directly if file was moved
    return PlainTextResponse(
        content=report.content_markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=omniflow_report_{task_id}.md"},
    )

@router.post("/tasks/{task_id}/documents")
async def upload_task_document(
    task_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Uploads, validates, and ingests a user reference document (PDF, TXT, MD, DOCX) into the research grounding pipeline."""
    from backend.tools.document_loader import ingest_document
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    try:
        content_bytes = await file.read()
        existing_evidences = repo.get_evidences(task_id)
        start_idx = len(existing_evidences) + 1

        doc_result = ingest_document(
            filename=file.filename or "uploaded_document.txt",
            file_bytes=content_bytes,
            task_id=task_id,
            start_evidence_index=start_idx,
        )

        # Persist source record
        src_data = doc_result["source"]
        src = repo.add_source(
            task_id=task_id,
            title=src_data["title"],
            url=src_data["url"],
            domain=src_data["domain"],
            access_status=src_data["access_status"],
            http_status_code=src_data["http_status_code"],
            extracted_chars=src_data["extracted_chars"],
            raw_content_preview=src_data["raw_content_preview"],
        )

        # Persist extracted evidence records
        for ev in doc_result["evidences"]:
            repo.add_evidence(
                task_id=task_id,
                stable_id=ev["stable_id"],
                research_question=ev["research_question"],
                excerpt=ev["excerpt"],
                finding=ev["finding"],
                source_id=src.id,
                verification_status=ev.get("verification_status", "retrieved"),
            )

        repo.add_event(
            task_id=task_id,
            event_type="DOCUMENT_INGESTED",
            level="SUCCESS",
            message=f"Ingested '{doc_result['filename']}' ({doc_result['extracted_chars']:,} chars, {len(doc_result['evidences'])} evidence records).",
        )

        return {
            "status": "success",
            "filename": doc_result["filename"],
            "extracted_chars": doc_result["extracted_chars"],
            "evidence_count": len(doc_result["evidences"]),
            "summary": doc_result["summary"],
        }
    except Exception as exc:
        logger.error(f"Failed to ingest document for task {task_id}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/productivity/metrics")
def get_productivity_benchmarks():
    """Returns baseline workplace productivity benchmark data and aggregate metrics."""
    from backend.services.productivity_service import productivity_service
    return productivity_service.get_benchmarks_summary()

@router.get("/tasks/{task_id}/productivity")
def get_task_productivity(task_id: str, db: Session = Depends(get_db)):
    """Computes empirical workplace productivity and time savings metrics for a task."""
    from backend.services.productivity_service import productivity_service
    repo = TaskRepository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    sources_cnt = len(repo.get_sources(task_id))
    evidences_cnt = len(repo.get_evidences(task_id))

    metrics = productivity_service.evaluate_task_productivity(
        task_id=task_id,
        start_time_iso=task.created_at.isoformat() if task.created_at else None,
        end_time_iso=task.completed_at.isoformat() if task.completed_at else None,
        sources_count=sources_cnt,
        evidence_count=evidences_cnt,
    )
    return metrics
