"""Step executor executing allowed tools and handling observation & persistence."""
from typing import Dict, Any, List
from backend.tools.registry import validate_tool_call
from backend.tools.search_tool import search_web
from backend.tools.browser_tool import extract_page
from backend.tools.source_extractor import extract_evidence_from_content
from backend.tools.report_tool import generate_markdown_report
from backend.agent.verifier import verifier
from backend.agent.recovery import decide_recovery, RecoveryDecision
from backend.core.exceptions import ToolExecutionError, PolicyViolationError
from backend.core.logging_config import logger

def execute_step(
    step: Dict[str, Any],
    execution_mode: str,
    collected_sources: List[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
    current_retry_count: int = 0,
) -> Dict[str, Any]:
    """Executes a single workflow step using allowed tools, returning the structured output."""
    tool_name = step["tool_name"]
    tool_input = dict(step.get("tool_input", {}))
    step_order = step["step_order"]
    
    logger.info(f"Executing step #{step_order} [{tool_name}]: {step['title']}")
    validate_tool_call(tool_name, tool_input)

    # Check for controlled failure trigger in Step 3 if mode == "controlled_failure"
    is_controlled_failure_step = (
        execution_mode == "controlled_failure"
        and step_order == 3
        and current_retry_count == 0
    )

    try:
        if tool_name == "web_search":
            query = tool_input.get("query", "AI agents capabilities and governance")
            scope = tool_input.get("scope", "")
            results = search_web(
                query=query,
                scope=scope,
                max_results=tool_input.get("max_results", 3),
                mode=execution_mode,
            )
            return {
                "success": True,
                "tool_name": tool_name,
                "results": results,
                "summary": f"Discovered {len(results)} authoritative reference candidates.",
                "new_sources": [
                    {
                        "title": r["title"],
                        "url": r["url"],
                        "domain": r["domain"],
                        "access_status": "discovered",
                        "extracted_chars": 0,
                        "raw_content_preview": r.get("snippet", "")
                    }
                    for r in results
                ],
                "new_evidence": [],
            }

        elif tool_name == "browser_page_extractor":
            url = tool_input.get("url", "")
            demo = (execution_mode == "demo")
            sim_fail = is_controlled_failure_step

            page_result = extract_page(
                url=url,
                simulate_failure=sim_fail,
                demo_mode=demo,
            )

            # Auto-extract evidence records from the retrieved page content
            start_idx = len(evidence_records) + 1
            extracted_evs = extract_evidence_from_content(
                content=page_result["content"],
                source_url=page_result["final_url"],
                source_title=page_result["title"],
                domain=page_result["domain"],
                start_index=start_idx,
            )

            source_record = {
                "title": page_result["title"],
                "url": page_result["final_url"],
                "domain": page_result["domain"],
                "access_status": "success",
                "http_status_code": page_result["status_code"],
                "extracted_chars": page_result["extracted_chars"],
                "raw_content_preview": page_result["content"][:300],
            }

            return {
                "success": True,
                "tool_name": tool_name,
                "content": page_result["content"],
                "status_code": page_result["status_code"],
                "final_url": page_result["final_url"],
                "summary": f"Accessed {page_result['domain']} ({page_result['extracted_chars']:,} chars). Captured {len(extracted_evs)} evidence records.",
                "new_sources": [source_record],
                "new_evidence": extracted_evs,
            }

        elif tool_name == "evidence_synthesizer":
            # Execute genuine semantic verification on all captured evidence records
            supported_count = 0
            for ev in evidence_records:
                eval_out = verifier.verify_evidence_claim(ev)
                ev["verification_status"] = eval_out["status"]
                ev["verification_explanation"] = eval_out["details"]
                if eval_out["is_supported"]:
                    supported_count += 1

            return {
                "success": True,
                "tool_name": tool_name,
                "summary": f"Completed claim verification on {len(evidence_records)} evidence records ({supported_count} supported).",
                "new_sources": [],
                "new_evidence": [],
            }

        elif tool_name == "report_generator":
            return {
                "success": True,
                "tool_name": tool_name,
                "summary": "Report synthesis scheduled for workflow finalization.",
                "new_sources": [],
                "new_evidence": [],
            }

        else:
            raise PolicyViolationError(f"Tool {tool_name} is not handled by executor.")

    except Exception as exc:
        logger.error(f"Step execution failure on #{step_order} [{tool_name}]: {str(exc)}")
        # Delegate to recovery decision logic
        recovery = decide_recovery(
            error_message=str(exc),
            tool_name=tool_name,
            tool_input=tool_input,
            current_retry_count=current_retry_count,
        )
        return {
            "success": False,
            "tool_name": tool_name,
            "error_message": str(exc),
            "recovery_decision": recovery.model_dump(),
            "summary": f"Execution failed: {str(exc)}",
            "new_sources": [],
            "new_evidence": [],
        }
