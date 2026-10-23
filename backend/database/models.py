import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_id() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_id)
    title = Column(String(255), nullable=False)
    original_request = Column(Text, nullable=False)
    scope = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending_plan")
    execution_mode = Column(String(50), nullable=False, default="live")
    llm_provider = Column(String(50), nullable=False, default="gemini")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_summary = Column(Text, nullable=True)

    # Relationships
    steps = relationship("PlanStepModel", back_populates="task", cascade="all, delete-orphan", order_by="PlanStepModel.step_order")
    sources = relationship("SourceModel", back_populates="task", cascade="all, delete-orphan")
    evidences = relationship("EvidenceModel", back_populates="task", cascade="all, delete-orphan")
    events = relationship("ExecutionEventModel", back_populates="task", cascade="all, delete-orphan", order_by="ExecutionEventModel.timestamp")
    verifications = relationship("VerificationResultModel", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("ApprovalDecisionModel", back_populates="task", cascade="all, delete-orphan")
    report = relationship("ReportModel", back_populates="task", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_created_at", "created_at"),
    )

class PlanStepModel(Base):
    __tablename__ = "plan_steps"

    id = Column(String(36), primary_key=True, default=generate_id)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    tool_name = Column(String(100), nullable=False)
    tool_input_json = Column(Text, nullable=True)
    dependencies_json = Column(Text, nullable=True)
    requires_approval = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False, default="planned")
    retry_count = Column(Integer, default=0, nullable=False)
    output_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("TaskModel", back_populates="steps")
    sources = relationship("SourceModel", back_populates="step")
    evidences = relationship("EvidenceModel", back_populates="step")

    __table_args__ = (
        Index("idx_steps_task_order", "task_id", "step_order"),
    )

class SourceModel(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True, default=generate_id)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(String(36), ForeignKey("plan_steps.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    domain = Column(String(255), nullable=False)
    access_status = Column(String(50), nullable=False, default="success")
    http_status_code = Column(Integer, nullable=True)
    extracted_chars = Column(Integer, default=0, nullable=False)
    accessed_at = Column(DateTime, default=utc_now, nullable=False)
    raw_content_preview = Column(Text, nullable=True)

    task = relationship("TaskModel", back_populates="sources")
    step = relationship("PlanStepModel", back_populates="sources")
    evidences = relationship("EvidenceModel", back_populates="source")

    __table_args__ = (
        Index("idx_sources_task_url", "task_id", "url"),
    )

class EvidenceModel(Base):
    __tablename__ = "evidences"

    id = Column(String(36), primary_key=True, default=generate_id)
    stable_id = Column(String(36), nullable=False)  # e.g., "EVID-001"
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(String(36), ForeignKey("plan_steps.id", ondelete="SET NULL"), nullable=True)
    source_id = Column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    research_question = Column(Text, nullable=False)
    excerpt = Column(Text, nullable=False)
    finding = Column(Text, nullable=False)
    verification_status = Column(String(50), nullable=False, default="captured")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    task = relationship("TaskModel", back_populates="evidences")
    step = relationship("PlanStepModel", back_populates="evidences")
    source = relationship("SourceModel", back_populates="evidences")

    __table_args__ = (
        Index("idx_evidence_task_stable_id", "task_id", "stable_id"),
    )

class ExecutionEventModel(Base):
    __tablename__ = "execution_events"

    id = Column(String(36), primary_key=True, default=generate_id)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(String(36), nullable=True)
    event_type = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False, default="INFO")
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)

    task = relationship("TaskModel", back_populates="events")

    __table_args__ = (
        Index("idx_events_task_time", "task_id", "timestamp"),
    )

class VerificationResultModel(Base):
    __tablename__ = "verification_results"

    id = Column(String(36), primary_key=True, default=generate_id)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(String(36), nullable=True)
    target_type = Column(String(50), nullable=False)  # "step", "report", "evidence"
    check_name = Column(String(100), nullable=False)
    is_passed = Column(Boolean, nullable=False)
    deterministic = Column(Boolean, default=True, nullable=False)
    details = Column(Text, nullable=True)
    verified_at = Column(DateTime, default=utc_now, nullable=False)

    task = relationship("TaskModel", back_populates="verifications")

class ApprovalDecisionModel(Base):
    __tablename__ = "approval_decisions"

    id = Column(String(36), primary_key=True, default=generate_id)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(String(36), nullable=True)
    decision = Column(String(50), nullable=False)  # "approved", "rejected"
    comments = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=utc_now, nullable=False)

    task = relationship("TaskModel", back_populates="approvals")

class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_id)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=False)
    content_markdown = Column(Text, nullable=False)
    file_path = Column(String(1024), nullable=True)
    sources_count = Column(Integer, default=0, nullable=False)
    evidence_count = Column(Integer, default=0, nullable=False)
    verification_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    task = relationship("TaskModel", back_populates="report")
