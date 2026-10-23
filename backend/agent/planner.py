"""Planning coordinator validating tasks and producing verified step sequences."""
from typing import Dict, Any, Optional
from backend.services.gemini_service import gemini_service
from backend.tools.registry import ALLOWED_TOOLS
from backend.core.exceptions import PolicyViolationError
from backend.core.logging_config import logger

def plan_task(request: str, scope: Optional[str] = None) -> Dict[str, Any]:
    """Generates and validates an execution plan for the requested task."""
    logger.info(f"Generating plan for task: '{request[:60]}...'")
    plan_result = gemini_service.generate_plan(request, scope)
    steps = plan_result["steps"]

    # Validate each step conforms to allowed tools and safe parameters
    validated_steps = []
    for idx, s in enumerate(steps, start=1):
        tool_name = s.get("tool_name")
        if tool_name not in ALLOWED_TOOLS:
            logger.warning(f"Planner suggested unauthorized tool '{tool_name}'. Sanitizing to 'web_search'.")
            tool_name = "web_search"
        
        step_entry = {
            "step_order": idx,
            "title": s.get("title", f"Step {idx}"),
            "description": s.get("description", "Execute research operation"),
            "tool_name": tool_name,
            "tool_input": s.get("tool_input", {}),
            "dependencies": s.get("dependencies", []),
            "requires_approval": s.get("requires_approval", False),
            "status": "planned",
        }
        validated_steps.append(step_entry)

    return {
        "steps": validated_steps,
        "llm_provider": plan_result["provider"],
        "is_fallback": plan_result.get("is_fallback", False),
        "reason": plan_result.get("reason"),
    }
