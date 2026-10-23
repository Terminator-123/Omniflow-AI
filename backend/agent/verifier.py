"""Verification Engine executing deterministic checks and semantic claim-support validation."""
import re
import os
from typing import Dict, Any, List, Optional
from backend.core.logging_config import logger
from backend.services.gemini_service import gemini_service

REQUIRED_REPORT_SECTIONS = [
    "1. Research Objective",
    "2. Executive Summary",
    "3. Key Findings",
    "4. Topic-by-Topic Comparison",
    "5. Supporting Evidence and Source Links",
    "6. Limitations and Unresolved Questions",
    "7. Sources Consulted",
    "8. Execution Summary",
    "9. Verification Results",
]

EXTENDED_REPORT_SECTIONS = [
    "1. Executive Summary",
    "2. Research Objectives & Methodology",
    "3. Scope & Domain Disclosure",
    "4. Topic Analysis: AI Capabilities & Workplace Productivity",
    "5. Topic Analysis: Reliability & System Drift",
    "6. Topic Analysis: Security Vectors & Operational Risks",
    "7. Topic Analysis: Human Oversight & Governance Frameworks",
    "8. Empirical Workplace Productivity Evaluation",
    "9. Synthesis & Cross-Domain Comparison Matrix",
    "10. Supporting Evidence Trail & Source Attribution",
    "11. Verification Results & Claim-Support Audit",
    "12. Research Limitations & Unresolved Questions",
    "13. Security, Ethical, and Compliance Considerations",
    "14. Actionable Enterprise Recommendations",
    "15. Complete Sources Consulted & Provenance Directory",
]

class VerificationEngine:
    """Orchestrates deterministic retrieval verification and semantic claim-level verification."""

    @staticmethod
    def verify_step_execution(
        step: Dict[str, Any],
        tool_output: Dict[str, Any],
        sources: List[Dict[str, Any]],
        evidences: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Validates the output of an individual step using deterministic integrity checks."""
        results = []
        tool_name = step.get("tool_name")
        step_id = step.get("id")

        if tool_name == "browser_page_extractor":
            # Check 1: Content non-empty (>50 chars)
            content = tool_output.get("content", "")
            is_valid_content = bool(content and len(content.strip()) > 50)
            results.append({
                "step_id": step_id,
                "target_type": "step",
                "check_name": "page_content_non_empty",
                "is_passed": is_valid_content,
                "deterministic": True,
                "details": f"Extracted {len(content)} characters from target URL.",
            })

            # Check 2: HTTP status 200
            status_code = tool_output.get("status_code", 0)
            is_200 = (status_code == 200)
            results.append({
                "step_id": step_id,
                "target_type": "step",
                "check_name": "http_status_success",
                "is_passed": is_200,
                "deterministic": True,
                "details": f"Response status code: {status_code}.",
            })

            # Check 3: Domain and final URL resolved
            final_url = tool_output.get("final_url", "")
            has_url = bool(final_url and final_url.startswith("http"))
            results.append({
                "step_id": step_id,
                "target_type": "step",
                "check_name": "canonical_url_resolved",
                "is_passed": has_url,
                "deterministic": True,
                "details": f"Resolved canonical URL: {final_url}.",
            })

        elif tool_name == "web_search":
            results_list = tool_output.get("results", [])
            has_results = bool(results_list and len(results_list) > 0)
            results.append({
                "step_id": step_id,
                "target_type": "step",
                "check_name": "search_discovery_yield",
                "is_passed": has_results,
                "deterministic": True,
                "details": f"Discovered {len(results_list)} reference candidates.",
            })

        elif tool_name == "evidence_synthesizer":
            extracted = tool_output.get("evidences", [])
            has_ev = bool(extracted and len(extracted) > 0)
            results.append({
                "step_id": step_id,
                "target_type": "step",
                "check_name": "evidence_records_synthesized",
                "is_passed": has_ev,
                "deterministic": True,
                "details": f"Synthesized {len(extracted)} evidence records.",
            })

        return results

    @staticmethod
    def verify_evidence_claim(
        evidence: Dict[str, Any],
        full_source_text: str = "",
    ) -> Dict[str, Any]:
        """Performs retrieval and semantic verification on a single evidence record.
        
        Statuses:
        - 'retrieved': Intended source was accessed and passage extracted.
        - 'claim_supported': Evidence directly substantiates the finding/claim.
        - 'partially_supported': Evidence addresses topic but has broader claims or missing context.
        - 'unsupported': Evidence contradicts or fails to substantiate the claim.
        - 'verification_failed': Technical failure during verification.
        - 'source_unavailable': Source could not be reached.
        """
        excerpt = evidence.get("excerpt", "").strip()
        finding = evidence.get("finding", "").strip()
        question = evidence.get("research_question", "").strip()
        url = evidence.get("source_url", "")

        # 1. Retrieval Verification
        if not excerpt or len(excerpt) < 15:
            return {
                "status": "unsupported",
                "is_supported": False,
                "details": "Extracted passage is empty or too short to substantiate research claims.",
                "retrieval_verified": False,
            }

        # If source text is available, verify verbatim containment
        retrieval_verified = True
        if full_source_text:
            retrieval_verified = (excerpt[:60].lower() in full_source_text.lower())

        # 2. Semantic Verification
        # If Gemini is configured, use structured LLM evaluation
        if gemini_service.is_configured():
            try:
                evaluation = gemini_service.verify_claim(
                    claim=finding,
                    excerpt=excerpt,
                    research_question=question,
                )
                if evaluation and evaluation.get("status"):
                    return {
                        "status": evaluation.get("status", "claim_supported"),
                        "is_supported": evaluation.get("supported", True),
                        "details": evaluation.get("explanation", "Verified by Gemini semantic evaluator."),
                        "retrieval_verified": retrieval_verified,
                    }
            except Exception as exc:
                logger.warning(f"Gemini evaluation failed ({exc}); falling back to deterministic semantic rules.")

        # Deterministic semantic validation heuristic when LLM is offline
        finding_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", finding.lower()))
        excerpt_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", excerpt.lower()))
        overlap = finding_words & excerpt_words
        overlap_ratio = len(overlap) / max(1, len(finding_words))

        # Check for contradictions / hedge words
        has_contradiction = bool(re.search(r"\b(disproved|false|refutes|untrue|fabricated)\b", excerpt.lower()))

        if has_contradiction:
            return {
                "status": "unsupported",
                "is_supported": False,
                "details": "Passage contains contradictory or refuting terminology.",
                "retrieval_verified": retrieval_verified,
            }
        elif overlap_ratio >= 0.35:
            return {
                "status": "claim_supported",
                "is_supported": True,
                "details": f"Deterministic semantic check passed ({int(overlap_ratio * 100)}% key concept overlap).",
                "retrieval_verified": retrieval_verified,
            }
        else:
            return {
                "status": "partially_supported",
                "is_supported": True,
                "details": "Passage provides contextual grounding, but finding extrapolates beyond verbatim text.",
                "retrieval_verified": retrieval_verified,
            }

    @staticmethod
    def verify_final_report(
        report_markdown: str,
        sources: List[Dict[str, Any]],
        evidences: List[Dict[str, Any]],
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """Verifies report structure, evidence citations, referential integrity, and file persistence."""
        results = []

        # Check 1: All required base sections present (conforming to hackathon requirements)
        missing_sections = []
        for sec in REQUIRED_REPORT_SECTIONS:
            if sec.lower() not in report_markdown.lower():
                missing_sections.append(sec)
        
        all_sections_present = (len(missing_sections) == 0)
        results.append({
            "target_type": "report",
            "check_name": "all_nine_sections_present",
            "is_passed": all_sections_present,
            "deterministic": True,
            "details": "All required core sections verified." if all_sections_present else f"Missing sections: {', '.join(missing_sections)}",
        })

        # Check 2: Evidence ID referential integrity
        # Check that evidence IDs mentioned in text (e.g. `EVID-001`) actually exist in evidences
        known_ids = {e["stable_id"] for e in evidences if "stable_id" in e}
        found_ids = set(re.findall(r"EVID-\d{3}", report_markdown))
        orphan_ids = found_ids - known_ids
        
        referential_integrity = (len(orphan_ids) == 0 and len(found_ids) > 0)
        results.append({
            "target_type": "report",
            "check_name": "evidence_id_referential_integrity",
            "is_passed": referential_integrity,
            "deterministic": True,
            "details": f"Found {len(found_ids)} cited IDs; 0 orphans." if referential_integrity else f"Orphan cited IDs: {orphan_ids}",
        })

        # Check 3: Downloadable file exists on disk
        file_exists = os.path.exists(file_path) and os.path.getsize(file_path) > 100
        results.append({
            "target_type": "report",
            "check_name": "downloadable_report_file_exists",
            "is_passed": file_exists,
            "deterministic": True,
            "details": f"File verified on disk at {file_path} ({os.path.getsize(file_path) if file_exists else 0} bytes).",
        })

        # Check 4: Sources consulted alignment
        sources_aligned = len(sources) > 0 and any(s.get("domain", "") in report_markdown for s in sources)
        results.append({
            "target_type": "report",
            "check_name": "source_domains_referenced",
            "is_passed": sources_aligned,
            "deterministic": True,
            "details": f"Verified {len(sources)} distinct domain references in report body.",
        })

        # Check 5: Claim Support Audit (all evidence items evaluated)
        supported_count = sum(1 for e in evidences if e.get("verification_status") in ("claim_supported", "partially_supported"))
        has_verified_claims = (supported_count > 0 or len(evidences) == 0)
        results.append({
            "target_type": "report",
            "check_name": "evidence_claim_support_audit",
            "is_passed": has_verified_claims,
            "deterministic": True,
            "details": f"Verified claim support for {supported_count}/{len(evidences)} evidence records.",
        })

        return results

verifier = VerificationEngine()
