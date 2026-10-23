"""Typed state schema for the LangGraph agent workflow."""
from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    task_id: str
    original_request: str
    scope: Optional[str]
    execution_mode: str  # "live", "demo", "controlled_failure"
    llm_provider: str
    is_fallback_plan: bool
    
    # Workflow Execution
    plan: List[Dict[str, Any]]
    current_step_idx: int
    step_statuses: Dict[int, str]  # step_order -> status
    retry_counts: Dict[int, int]
    approval_state: str  # "pending", "approved", "rejected"
    
    # Data artifacts
    collected_sources: List[Dict[str, Any]]
    evidence_records: List[Dict[str, Any]]
    tool_results: Dict[str, Any]
    execution_events: List[Dict[str, Any]]
    verification_results: List[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    
    # Lifecycle
    status: str  # "pending_plan", "awaiting_approval", "running", "completed", "failed", "cancelled"
    error_details: Optional[str]
    recovered_steps: int
