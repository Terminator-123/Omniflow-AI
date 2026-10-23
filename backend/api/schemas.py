import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TaskCreateRequest(BaseModel):
    original_request: str = Field(..., min_length=5, description="The natural language goal or research task.")
    scope: Optional[str] = Field(None, description="Preferred domains, sources or scope constraints.")
    execution_mode: str = Field("live", description="Execution mode: 'live', 'demo', or 'controlled_failure'.")

class PlanStepSchema(BaseModel):
    id: Optional[str] = None
    step_order: int
    title: str
    description: str
    tool_name: str
    tool_input: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[int]] = None
    requires_approval: bool = False
    status: str = "planned"
    retry_count: int = 0
    output_summary: Optional[str] = None
    error_message: Optional[str] = None

class PlanResponse(BaseModel):
    task_id: str
    steps: List[PlanStepSchema]
    llm_provider: str
    is_fallback: bool = False

class TaskResponse(BaseModel):
    id: str
    title: str
    original_request: str
    scope: Optional[str] = None
    status: str
    execution_mode: str
    llm_provider: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_summary: Optional[str] = None
    steps: List[PlanStepSchema] = []
    sources_count: int = 0
    evidence_count: int = 0

class ApprovalRequest(BaseModel):
    decision: str = Field("approved", description="'approved' to proceed or 'rejected' to cancel.")
    comments: Optional[str] = None

class EventResponse(BaseModel):
    id: str
    task_id: str
    step_id: Optional[str] = None
    event_type: str
    level: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

class SourceResponse(BaseModel):
    id: str
    title: str
    url: str
    domain: str
    access_status: str
    http_status_code: Optional[int] = None
    extracted_chars: int = 0
    accessed_at: datetime
    raw_content_preview: Optional[str] = None

class EvidenceItemResponse(BaseModel):
    id: str
    stable_id: str
    research_question: str
    excerpt: str
    finding: str
    verification_status: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    step_title: Optional[str] = None
    created_at: datetime

class VerificationResponse(BaseModel):
    id: str
    target_type: str
    check_name: str
    is_passed: bool
    deterministic: bool
    details: Optional[str] = None
    verified_at: datetime

class ReportResponse(BaseModel):
    id: str
    task_id: str
    title: str
    executive_summary: str
    content_markdown: str
    file_path: Optional[str] = None
    sources_count: int
    evidence_count: int
    verification_summary: Optional[str] = None
    created_at: datetime

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    gemini_configured: bool
    playwright_available: bool
