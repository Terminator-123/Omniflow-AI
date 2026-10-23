import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database.models import (
    TaskModel,
    PlanStepModel,
    SourceModel,
    EvidenceModel,
    ExecutionEventModel,
    VerificationResultModel,
    ApprovalDecisionModel,
    ReportModel,
)

class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_task(
        self,
        title: str,
        original_request: str,
        scope: Optional[str] = None,
        execution_mode: str = "live",
        llm_provider: str = "gemini",
    ) -> TaskModel:
        task = TaskModel(
            title=title,
            original_request=original_request,
            scope=scope,
            execution_mode=execution_mode,
            llm_provider=llm_provider,
            status="pending_plan",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(self, task_id: str) -> Optional[TaskModel]:
        return self.db.query(TaskModel).filter(TaskModel.id == task_id).first()

    def list_tasks(self, limit: int = 50, offset: int = 0) -> List[TaskModel]:
        return (
            self.db.query(TaskModel)
            .order_by(TaskModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_task_status(
        self,
        task_id: str,
        status: str,
        error_summary: Optional[str] = None,
        completed: bool = False,
    ) -> Optional[TaskModel]:
        task = self.get_task(task_id)
        if not task:
            return None
        task.status = status
        if error_summary is not None:
            task.error_summary = error_summary
        if completed:
            task.completed_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(task)
        return task

    def add_plan_steps(self, task_id: str, steps: List[Dict[str, Any]]) -> List[PlanStepModel]:
        created_steps = []
        for step_data in steps:
            step = PlanStepModel(
                task_id=task_id,
                step_order=step_data["step_order"],
                title=step_data["title"],
                description=step_data["description"],
                tool_name=step_data["tool_name"],
                tool_input_json=json.dumps(step_data.get("tool_input", {})),
                dependencies_json=json.dumps(step_data.get("dependencies", [])),
                requires_approval=step_data.get("requires_approval", False),
                status=step_data.get("status", "planned"),
            )
            self.db.add(step)
            created_steps.append(step)
        self.db.commit()
        return created_steps

    def update_step(
        self,
        step_id: str,
        status: Optional[str] = None,
        retry_count: Optional[int] = None,
        output_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        started: bool = False,
        completed: bool = False,
    ) -> Optional[PlanStepModel]:
        step = self.db.query(PlanStepModel).filter(PlanStepModel.id == step_id).first()
        if not step:
            return None
        if status:
            step.status = status
        if retry_count is not None:
            step.retry_count = retry_count
        if output_summary is not None:
            step.output_summary = output_summary
        if error_message is not None:
            step.error_message = error_message
        if started and not step.started_at:
            step.started_at = datetime.utcnow()
        if completed:
            step.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(step)
        return step

    def add_source(
        self,
        task_id: str,
        title: str,
        url: str,
        domain: str,
        step_id: Optional[str] = None,
        access_status: str = "success",
        http_status_code: Optional[int] = 200,
        extracted_chars: int = 0,
        raw_content_preview: Optional[str] = None,
    ) -> SourceModel:
        # Check if source URL already recorded for this task
        existing = (
            self.db.query(SourceModel)
            .filter(SourceModel.task_id == task_id, SourceModel.url == url)
            .first()
        )
        if existing:
            existing.access_status = access_status
            existing.http_status_code = http_status_code
            existing.extracted_chars = max(existing.extracted_chars, extracted_chars)
            if raw_content_preview:
                existing.raw_content_preview = raw_content_preview
            self.db.commit()
            self.db.refresh(existing)
            return existing

        source = SourceModel(
            task_id=task_id,
            step_id=step_id,
            title=title,
            url=url,
            domain=domain,
            access_status=access_status,
            http_status_code=http_status_code,
            extracted_chars=extracted_chars,
            raw_content_preview=raw_content_preview,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def add_evidence(
        self,
        task_id: str,
        stable_id: str,
        research_question: str,
        excerpt: str,
        finding: str,
        step_id: Optional[str] = None,
        source_id: Optional[str] = None,
        verification_status: str = "captured",
    ) -> EvidenceModel:
        existing = (
            self.db.query(EvidenceModel)
            .filter(EvidenceModel.task_id == task_id, EvidenceModel.stable_id == stable_id)
            .first()
        )
        if existing:
            existing.research_question = research_question
            existing.excerpt = excerpt
            existing.finding = finding
            existing.verification_status = verification_status
            if source_id:
                existing.source_id = source_id
            if step_id:
                existing.step_id = step_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        evidence = EvidenceModel(
            task_id=task_id,
            step_id=step_id,
            source_id=source_id,
            stable_id=stable_id,
            research_question=research_question,
            excerpt=excerpt,
            finding=finding,
            verification_status=verification_status,
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def add_event(
        self,
        task_id: str,
        event_type: str,
        message: str,
        step_id: Optional[str] = None,
        level: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
    ) -> ExecutionEventModel:
        event = ExecutionEventModel(
            task_id=task_id,
            step_id=step_id,
            event_type=event_type,
            level=level,
            message=message,
            details_json=json.dumps(details) if details else None,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events(self, task_id: str, limit: int = 100) -> List[ExecutionEventModel]:
        return (
            self.db.query(ExecutionEventModel)
            .filter(ExecutionEventModel.task_id == task_id)
            .order_by(ExecutionEventModel.timestamp.asc())
            .limit(limit)
            .all()
        )

    def add_verification(
        self,
        task_id: str,
        target_type: str,
        check_name: str,
        is_passed: bool,
        deterministic: bool = True,
        step_id: Optional[str] = None,
        details: Optional[str] = None,
    ) -> VerificationResultModel:
        existing = (
            self.db.query(VerificationResultModel)
            .filter(
                VerificationResultModel.task_id == task_id,
                VerificationResultModel.target_type == target_type,
                VerificationResultModel.check_name == check_name,
            )
            .first()
        )
        if existing:
            existing.is_passed = is_passed
            existing.deterministic = deterministic
            existing.details = details
            if step_id:
                existing.step_id = step_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        vr = VerificationResultModel(
            task_id=task_id,
            step_id=step_id,
            target_type=target_type,
            check_name=check_name,
            is_passed=is_passed,
            deterministic=deterministic,
            details=details,
        )
        self.db.add(vr)
        self.db.commit()
        self.db.refresh(vr)
        return vr

    def record_approval(
        self,
        task_id: str,
        decision: str,
        step_id: Optional[str] = None,
        comments: Optional[str] = None,
    ) -> ApprovalDecisionModel:
        approval = ApprovalDecisionModel(
            task_id=task_id,
            step_id=step_id,
            decision=decision,
            comments=comments,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def save_report(
        self,
        task_id: str,
        title: str,
        executive_summary: str,
        content_markdown: str,
        file_path: Optional[str] = None,
        sources_count: int = 0,
        evidence_count: int = 0,
        verification_summary: Optional[str] = None,
    ) -> ReportModel:
        report = self.db.query(ReportModel).filter(ReportModel.task_id == task_id).first()
        if report:
            report.title = title
            report.executive_summary = executive_summary
            report.content_markdown = content_markdown
            report.file_path = file_path
            report.sources_count = sources_count
            report.evidence_count = evidence_count
            report.verification_summary = verification_summary
            report.created_at = datetime.utcnow()
        else:
            report = ReportModel(
                task_id=task_id,
                title=title,
                executive_summary=executive_summary,
                content_markdown=content_markdown,
                file_path=file_path,
                sources_count=sources_count,
                evidence_count=evidence_count,
                verification_summary=verification_summary,
            )
            self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_report(self, task_id: str) -> Optional[ReportModel]:
        return self.db.query(ReportModel).filter(ReportModel.task_id == task_id).first()

    def get_evidences(self, task_id: str) -> List[EvidenceModel]:
        return (
            self.db.query(EvidenceModel)
            .filter(EvidenceModel.task_id == task_id)
            .order_by(EvidenceModel.created_at.asc())
            .all()
        )

    def get_sources(self, task_id: str) -> List[SourceModel]:
        return (
            self.db.query(SourceModel)
            .filter(SourceModel.task_id == task_id)
            .order_by(SourceModel.accessed_at.asc())
            .all()
        )

    def get_plan_steps(self, task_id: str) -> List[PlanStepModel]:
        return (
            self.db.query(PlanStepModel)
            .filter(PlanStepModel.task_id == task_id)
            .order_by(PlanStepModel.step_order.asc())
            .all()
        )

    def get_verifications(self, task_id: str) -> List[VerificationResultModel]:
        return (
            self.db.query(VerificationResultModel)
            .filter(VerificationResultModel.task_id == task_id)
            .order_by(VerificationResultModel.verified_at.asc())
            .all()
        )
