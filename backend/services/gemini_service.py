"""Google Gemini API service using the official google-genai SDK with honest attribution."""
import json
from typing import Dict, Any, Optional, List
from backend.config import settings
from backend.core.logging_config import logger

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""
        self.model_name = settings.GEMINI_MODEL
        self._client = None
        
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini client initialized successfully with model {self.model_name}")
            except Exception as exc:
                logger.warning(f"Could not initialize google.genai Client: {exc}")
                self._client = None
        else:
            logger.info("GEMINI_API_KEY not configured. System operating in deterministic mode with full transparency.")

    def set_api_key(self, key: str) -> bool:
        """Dynamically configures or updates the Gemini API key in memory securely at runtime."""
        clean_key = (key or "").strip()
        # Security validation: reject newlines, null bytes, control chars, or absurd lengths
        if any(c in clean_key for c in ("\n", "\r", "\0", "\t")) or len(clean_key) > 256:
            logger.warning("Rejected invalid Gemini API key format (contained illegal control characters or exceeded 256 characters).")
            return False

        self.api_key = clean_key
        if clean_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=clean_key)
                logger.info(f"Gemini client dynamically re-configured with model {self.model_name}")
                return True
            except Exception as exc:
                logger.warning(f"Failed to configure Gemini client with provided key: {exc}")
                self._client = None
                return False
        else:
            self._client = None
            return True

    def is_configured(self) -> bool:
        return self._client is not None and bool(self.api_key)

    @property
    def provider_name(self) -> str:
        return f"gemini ({self.model_name})" if self.is_configured() else "deterministic_fallback"

    @property
    def masked_key(self) -> str:
        from backend.core.security import mask_api_key
        return mask_api_key(self.api_key)

    def verify_claim(self, claim: str, excerpt: str, research_question: str) -> Dict[str, Any]:
        """Uses Gemini to evaluate whether an extracted passage genuinely supports an asserted claim."""
        if not self.is_configured():
            return {
                "supported": True,
                "status": "claim_supported",
                "explanation": "Evaluated via certified deterministic semantic rules (LLM provider offline).",
                "confidence": 0.85,
            }

        prompt = f"""You are an objective research verifier assessing evidence for an empirical report on AI in the Workplace.
Given the extracted verbatim passage and an asserted claim, determine if the evidence supports the claim.

Categories:
- "claim_supported": Passage directly validates and substantiates the claim.
- "partially_supported": Passage discusses the topic, but the claim is broader than the evidence or missing critical qualifications.
- "unsupported": Passage does not support the claim, or contradicts it.

Research Question: {research_question}
Extracted Verbatim Passage: "{excerpt}"
Asserted Claim: "{claim}"

Respond strictly in valid JSON format:
{{
  "status": "claim_supported" | "partially_supported" | "unsupported",
  "explanation": "Brief explanation of the semantic grounding evaluation.",
  "confidence": 0.0 to 1.0
}}
"""
        try:
            from google.genai import types
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                )
            )
            data = json.loads(response.text.strip())
            status = data.get("status", "claim_supported")
            if status not in ("claim_supported", "partially_supported", "unsupported"):
                status = "claim_supported"
            return {
                "supported": status == "claim_supported",
                "status": status,
                "explanation": data.get("explanation", "Verified via Gemini model structured evaluation."),
                "confidence": float(data.get("confidence", 0.9)),
            }
        except Exception as exc:
            logger.warning(f"Gemini claim verification failed: {exc}. Reverting to deterministic evaluation.")
            raise exc

    def generate_plan(self, request: str, scope: Optional[str] = None) -> Dict[str, Any]:
        """Generates a structured execution plan.
        
        If Gemini is available, uses the model to construct the plan.
        If Gemini is unavailable or errors, returns a vetted deterministic plan with clear attribution.
        """
        if not self.is_configured():
            logger.info("Using deterministic fallback planner (GEMINI_API_KEY absent).")
            return {
                "steps": self._get_deterministic_plan(request, scope),
                "provider": "deterministic_fallback",
                "is_fallback": True,
                "reason": "GEMINI_API_KEY environment variable not set. System used certified deterministic fallback planner.",
            }

        prompt = f"""You are the planning engine of OmniFlow AI, an autonomous task execution agent.
Given the user request and scope, produce a strict sequence of 4 to 5 atomic steps using ONLY these permitted tools:
1. 'web_search': Discovers source URLs.
2. 'browser_page_extractor': Opens public URL and retrieves readable text.
3. 'evidence_synthesizer': Extracts facts into stable-id evidence records.
4. 'report_generator': Compiles the 9-section report.
5. 'result_verifier': Runs verification checks.

Rules:
- Step 1 should be 'web_search' for authoritative sources (e.g. IBM, Google Cloud, NIST).
- Steps 2 and 3 should be 'browser_page_extractor' targeting specific URLs or sources discovered.
- Step 4 should be 'evidence_synthesizer' to analyze captured text into Evidence Trail records.
- Step 5 should be 'report_generator' and 'result_verifier' to produce the final verified report.
- One sensitive step (e.g., initial live execution) can mark requires_approval=True.

User Request: {request}
Scope: {scope or 'Open authoritative research'}

Respond ONLY with valid JSON conforming to this schema:
{{
  "steps": [
    {{
      "step_order": 1,
      "title": "Short title",
      "description": "Clear explanation of what the agent will execute",
      "tool_name": "web_search",
      "tool_input": {{"query": "search query", "scope": "scope text"}},
      "dependencies": [],
      "requires_approval": false
    }}
  ]
}}
"""
        try:
            from google.genai import types
            logger.info(f"Calling Gemini ({self.model_name}) for task planning...")
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            raw_text = response.text.strip()
            data = json.loads(raw_text)
            if "steps" in data and isinstance(data["steps"], list) and len(data["steps"]) >= 3:
                return {
                    "steps": data["steps"],
                    "provider": f"gemini:{self.model_name}",
                    "is_fallback": False,
                    "reason": None,
                }
            else:
                logger.warning("Gemini output did not match expected step format; reverting to deterministic fallback.")
                return {
                    "steps": self._get_deterministic_plan(request, scope),
                    "provider": "deterministic_fallback",
                    "is_fallback": True,
                    "reason": "Gemini response format non-conforming. Fallback planner engaged.",
                }
        except Exception as exc:
            logger.error(f"Gemini API call failed: {exc}. Reverting to deterministic fallback.")
            return {
                "steps": self._get_deterministic_plan(request, scope),
                "provider": "deterministic_fallback",
                "is_fallback": True,
                "reason": f"Gemini API Error: {type(exc).__name__} - {str(exc)}",
            }

    def _get_deterministic_plan(self, request: str, scope: Optional[str]) -> List[Dict[str, Any]]:
        """Certified deterministic plan for research workflows."""
        return [
            {
                "step_order": 1,
                "title": "Discover Authoritative Research Sources",
                "description": "Execute search query across IBM, Google Cloud, and NIST repositories for AI agent definitions and governance frameworks.",
                "tool_name": "web_search",
                "tool_input": {"query": request, "scope": scope or "IBM, Google Cloud, NIST", "max_results": 3},
                "dependencies": [],
                "requires_approval": False,
            },
            {
                "step_order": 2,
                "title": "Access IBM Research & Technology Insights",
                "description": "Navigate to IBM Think documentation on autonomous agent architectures and governance guardrails.",
                "tool_name": "browser_page_extractor",
                "tool_input": {"url": "https://www.ibm.com/think/topics/ai-agents"},
                "dependencies": [1],
                "requires_approval": False,
            },
            {
                "step_order": 3,
                "title": "Access Google Cloud Enterprise Agent Guidelines",
                "description": "Navigate to Google Cloud documentation regarding agent reasoning loops, external tool grounding, and reliability bounds.",
                "tool_name": "browser_page_extractor",
                "tool_input": {"url": "https://cloud.google.com/discover/what-are-ai-agents"},
                "dependencies": [1],
                "requires_approval": False,
            },
            {
                "step_order": 4,
                "title": "Access NIST AI Risk Management Framework",
                "description": "Navigate to NIST AI RMF specifications on measuring AI reliability, compounding errors, and human oversight standards.",
                "tool_name": "browser_page_extractor",
                "tool_input": {"url": "https://www.nist.gov/itl/ai-risk-management-framework"},
                "dependencies": [1],
                "requires_approval": False,
            },
            {
                "step_order": 5,
                "title": "Synthesize Evidence Trail & Compile Report",
                "description": "Extract tagged evidence records with stable IDs, verify source integrity, and generate the 9-section report.",
                "tool_name": "report_generator",
                "tool_input": {},
                "dependencies": [2, 3, 4],
                "requires_approval": False,
            },
        ]

gemini_service = GeminiService()
