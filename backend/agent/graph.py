"""LangGraph workflow definition for OmniFlow AI's stateful execution machine."""
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from backend.agent.state import AgentState
from backend.agent.planner import plan_task
from backend.agent.executor import execute_step
from backend.agent.verifier import verifier
from backend.tools.report_tool import generate_markdown_report
from backend.core.logging_config import logger

def validate_task_node(state: AgentState) -> Dict[str, Any]:
    """Node: Validates the incoming task request and scope constraints."""
    req = state.get("original_request", "").strip()
    logger.info(f"LangGraph node: validate_task_node for task {state.get('task_id')}")
    if len(req) < 5:
        return {"status": "failed", "error_details": "Task request is too short (min 5 characters)."}
    return {
        "status": "pending_plan",
        "current_step_idx": 0,
        "step_statuses": {},
        "retry_counts": {},
        "collected_sources": [],
        "evidence_records": [],
        "execution_events": [
            {
                "event_type": "TASK_VALIDATED",
                "level": "INFO",
                "message": f"Task validated: '{req[:50]}...'",
            }
        ],
        "recovered_steps": 0,
    }

def generate_plan_node(state: AgentState) -> Dict[str, Any]:
    """Node: Generates the structured multi-step execution plan."""
    logger.info(f"LangGraph node: generate_plan_node for task {state.get('task_id')}")
    plan_out = plan_task(state["original_request"], state.get("scope"))
    steps = plan_out["steps"]
    
    events = list(state.get("execution_events", []))
    events.append({
        "event_type": "PLAN_GENERATED",
        "level": "INFO",
        "message": f"Generated {len(steps)} plan steps via {plan_out['llm_provider']}.",
        "details": {"step_count": len(steps), "provider": plan_out["llm_provider"]},
    })

    return {
        "plan": steps,
        "llm_provider": plan_out["llm_provider"],
        "is_fallback_plan": plan_out.get("is_fallback", False),
        "status": "awaiting_approval",
        "execution_events": events,
    }

def await_approval_node(state: AgentState) -> Dict[str, Any]:
    """Node: Checks or yields for user plan approval."""
    logger.info(f"LangGraph node: await_approval_node (approval_state={state.get('approval_state')})")
    # If user has approved, transition to running
    if state.get("approval_state") == "approved":
        events = list(state.get("execution_events", []))
        events.append({
            "event_type": "APPROVAL_GRANTED",
            "level": "SUCCESS",
            "message": "User approved the proposed execution plan. Beginning execution.",
        })
        return {"status": "running", "execution_events": events}
    
    return {"status": "awaiting_approval"}

def execute_step_node(state: AgentState) -> Dict[str, Any]:
    """Node: Selects and invokes the tool for the active step."""
    plan = state.get("plan", [])
    idx = state.get("current_step_idx", 0)
    
    if idx >= len(plan):
        return {}

    step = plan[idx]
    order = step["step_order"]
    retry_count = state.get("retry_counts", {}).get(order, 0)
    
    logger.info(f"LangGraph node: execute_step_node for step #{order}: {step['title']}")
    
    # Mark step running in events
    events = list(state.get("execution_events", []))
    events.append({
        "event_type": "STEP_STARTED",
        "step_id": str(order),
        "level": "INFO",
        "message": f"Starting step #{order}: {step['title']} [{step['tool_name']}]",
    })

    exec_result = execute_step(
        step=step,
        execution_mode=state.get("execution_mode", "live"),
        collected_sources=state.get("collected_sources", []),
        evidence_records=state.get("evidence_records", []),
        current_retry_count=retry_count,
    )

    tool_results = dict(state.get("tool_results", {}))
    tool_results[order] = exec_result

    # Append any newly discovered sources and evidence
    sources = list(state.get("collected_sources", []))
    sources.extend(exec_result.get("new_sources", []))

    evidences = list(state.get("evidence_records", []))
    evidences.extend(exec_result.get("new_evidence", []))

    return {
        "tool_results": tool_results,
        "collected_sources": sources,
        "evidence_records": evidences,
        "execution_events": events,
    }

def observe_and_recover_node(state: AgentState) -> Dict[str, Any]:
    """Node: Evaluates tool outcome, performs verification, and manages bounded retries/recoveries."""
    plan = state.get("plan", [])
    idx = state.get("current_step_idx", 0)
    step = plan[idx]
    order = step["step_order"]
    
    result = state.get("tool_results", {}).get(order, {})
    success = result.get("success", False)
    
    events = list(state.get("execution_events", []))
    step_statuses = dict(state.get("step_statuses", {}))
    retry_counts = dict(state.get("retry_counts", {}))
    recovered_count = state.get("recovered_steps", 0)
    verifs = list(state.get("verification_results", []))

    if success:
        # Step succeeded
        step_statuses[order] = "completed"
        step["output_summary"] = result.get("summary", "Step executed successfully.")
        
        events.append({
            "event_type": "STEP_COMPLETED",
            "step_id": str(order),
            "level": "SUCCESS",
            "message": f"Step #{order} completed: {result.get('summary')}",
        })

        # Run deterministic verification on step output
        step_verifs = verifier.verify_step_execution(
            step=step,
            tool_output=result,
            sources=state.get("collected_sources", []),
            evidences=state.get("evidence_records", []),
        )
        verifs.extend(step_verifs)

        # Advance to next step
        return {
            "current_step_idx": idx + 1,
            "step_statuses": step_statuses,
            "execution_events": events,
            "verification_results": verifs,
        }

    else:
        # Tool failed; evaluate recovery decision
        rec_decision = result.get("recovery_decision", {})
        action = rec_decision.get("action", "fail_step")
        current_retries = retry_counts.get(order, 0)

        events.append({
            "event_type": "ERROR_DETECTED",
            "step_id": str(order),
            "level": "WARNING",
            "message": f"Step #{order} failed attempt: {result.get('error_message')}",
            "details": rec_decision,
        })

        if action in ("retry", "retry_with_alternative"):
            retry_counts[order] = current_retries + 1
            step_statuses[order] = "retrying"
            recovered_count += 1
            
            # If alternative parameters were supplied, update step tool_input
            if rec_decision.get("updated_tool_input"):
                step["tool_input"] = rec_decision["updated_tool_input"]

            events.append({
                "event_type": "RECOVERY_ATTEMPTED",
                "step_id": str(order),
                "level": "INFO",
                "message": f"Recovery triggered on step #{order}: {rec_decision.get('reason')}",
                "details": rec_decision,
            })

            # Do not increment current_step_idx, so loop retries this step
            return {
                "step_statuses": step_statuses,
                "retry_counts": retry_counts,
                "recovered_steps": recovered_count,
                "execution_events": events,
            }
        else:
            # Fatal step failure
            step_statuses[order] = "failed"
            step["output_summary"] = f"Failed permanently: {result.get('error_message')}"
            events.append({
                "event_type": "STEP_FAILED",
                "step_id": str(order),
                "level": "ERROR",
                "message": f"Step #{order} could not be recovered: {rec_decision.get('reason')}",
            })
            # Advance to next step anyway so independent steps can continue
            return {
                "current_step_idx": idx + 1,
                "step_statuses": step_statuses,
                "execution_events": events,
            }

def generate_report_node(state: AgentState) -> Dict[str, Any]:
    """Node: Synthesizes final report across all 9 required sections."""
    logger.info(f"LangGraph node: generate_report_node for task {state.get('task_id')}")
    events = list(state.get("execution_events", []))
    events.append({
        "event_type": "REPORT_SYNTHESIS_STARTED",
        "level": "INFO",
        "message": "Synthesizing evidence and formatting 9-section report...",
    })

    report_data = generate_markdown_report(
        task_id=state["task_id"],
        original_request=state["original_request"],
        scope=state.get("scope"),
        execution_mode=state.get("execution_mode", "live"),
        llm_provider=state.get("llm_provider", "gemini"),
        sources=state.get("collected_sources", []),
        evidences=state.get("evidence_records", []),
        verifications=state.get("verification_results", []),
        events=events,
        recovered_steps=state.get("recovered_steps", 0),
    )

    events.append({
        "event_type": "REPORT_GENERATED",
        "level": "SUCCESS",
        "message": f"Report compiled: {report_data['sources_count']} sources, {report_data['evidence_count']} evidence items.",
    })

    return {
        "final_report": report_data,
        "execution_events": events,
    }

def verify_report_node(state: AgentState) -> Dict[str, Any]:
    """Node: Runs comprehensive verification on the final report."""
    logger.info(f"LangGraph node: verify_report_node for task {state.get('task_id')}")
    report_data = state.get("final_report", {})
    markdown = report_data.get("content_markdown", "")
    file_path = report_data.get("file_path", "")

    verifs = list(state.get("verification_results", []))
    rep_verifs = verifier.verify_final_report(
        report_markdown=markdown,
        sources=state.get("collected_sources", []),
        evidences=state.get("evidence_records", []),
        file_path=file_path,
    )
    verifs.extend(rep_verifs)

    events = list(state.get("execution_events", []))
    all_passed = all(v["is_passed"] for v in rep_verifs)
    events.append({
        "event_type": "VERIFICATION_COMPLETED",
        "level": "SUCCESS" if all_passed else "WARNING",
        "message": f"Verification completed: {'All checks passed' if all_passed else 'Partial checks passed'}.",
    })

    return {
        "status": "completed",
        "verification_results": verifs,
        "execution_events": events,
    }

# Conditional Routing Functions
def check_approval_or_continue(state: AgentState) -> Literal["await_approval", "execute_step"]:
    if state.get("approval_state") == "approved":
        return "execute_step"
    return "await_approval"

def check_more_steps_or_report(state: AgentState) -> Literal["execute_step", "generate_report"]:
    idx = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    if idx < len(plan):
        return "execute_step"
    return "generate_report"

# Assemble LangGraph
workflow = StateGraph(AgentState)

workflow.add_node("validate_task", validate_task_node)
workflow.add_node("generate_plan", generate_plan_node)
workflow.add_node("await_approval", await_approval_node)
workflow.add_node("execute_step", execute_step_node)
workflow.add_node("observe_and_recover", observe_and_recover_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("verify_report", verify_report_node)

# Connect Edges
workflow.add_edge(START, "validate_task")
workflow.add_edge("validate_task", "generate_plan")
workflow.add_conditional_edges("generate_plan", check_approval_or_continue)
workflow.add_edge("await_approval", "execute_step")
workflow.add_edge("execute_step", "observe_and_recover")
workflow.add_conditional_edges("observe_and_recover", check_more_steps_or_report)
workflow.add_edge("generate_report", "verify_report")
workflow.add_edge("verify_report", END)

# Compile Graph
agent_app = workflow.compile()
