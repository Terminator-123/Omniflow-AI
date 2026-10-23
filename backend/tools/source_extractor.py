"""Evidence extraction and synthesis tool that creates stable-id evidence records with deduplication."""
import re
import hashlib
from typing import List, Dict, Any, Set, Optional
from backend.core.logging_config import logger

RESEARCH_TOPICS = [
    {
        "topic": "capabilities",
        "question": "What core capabilities do autonomous AI agents possess?",
        "keywords": ["capability", "capabilities", "reasoning", "planning", "tool", "actions", "autonomous", "workflow", "perceive"],
    },
    {
        "topic": "reliability",
        "question": "What are the primary reliability challenges and failure modes of AI agents?",
        "keywords": ["reliability", "drift", "hallucination", "failure", "compounding", "deterministic", "accuracy", "error"],
    },
    {
        "topic": "risks",
        "question": "What security, operational, and organizational risks do AI agents introduce?",
        "keywords": ["risk", "risks", "security", "vulnerability", "bias", "injection", "privacy", "safety", "unauthorized"],
    },
    {
        "topic": "human_oversight",
        "question": "Why is human oversight and human-in-the-loop governance necessary for agents?",
        "keywords": ["oversight", "human", "governance", "approval", "supervision", "control", "accountability", "guardrail"],
    },
]

def extract_evidence_from_content(
    content: str,
    source_url: str,
    source_title: str,
    domain: str,
    start_index: int = 1,
    existing_hashes: Optional[Set[str]] = None,
    provenance: str = "web_retrieval",
) -> List[Dict[str, Any]]:
    """Analyzes raw extracted webpage text and generates structured Evidence Trail records with stable IDs.
    
    Initial verification status is strictly set to 'retrieved'. Claim support is evaluated
    in the semantic verification stage, never automatically assumed from successful HTTP fetch.
    """
    logger.info(f"Extracting evidence records from {source_url} ({len(content)} chars)")
    
    if existing_hashes is None:
        existing_hashes = set()

    # Split content into sentences/paragraphs
    paragraphs = [p.strip() for p in content.split("\n") if len(p.strip()) > 40]
    evidences: List[Dict[str, Any]] = []
    current_index = start_index

    # Find the best paragraph/sentence for each key topic
    for topic_info in RESEARCH_TOPICS:
        topic_name = topic_info["topic"]
        question = topic_info["question"]
        keywords = topic_info["keywords"]

        best_excerpt = None
        best_score = 0

        for para in paragraphs:
            para_lower = para.lower()
            # Count keyword hits
            hits = sum(1 for kw in keywords if kw in para_lower)
            if hits > best_score:
                best_score = hits
                # Trim excerpt to a clean citation length (approx 150-300 chars)
                sentences = re.split(r"(?<=[.!?])\s+", para)
                relevant_sentences = [s for s in sentences if any(kw in s.lower() for kw in keywords)]
                if relevant_sentences:
                    best_excerpt = " ".join(relevant_sentences[:2]).strip()
                else:
                    best_excerpt = para[:300].strip()

        if best_excerpt and best_score >= 1:
            content_hash = hashlib.sha256(best_excerpt.encode("utf-8")).hexdigest()[:12]
            # Deduplication: Avoid duplicate passages across or within documents
            if content_hash in existing_hashes:
                logger.info(f"Skipping duplicate evidence passage (hash {content_hash})")
                continue

            existing_hashes.add(content_hash)
            stable_id = f"EVID-{current_index:03d}"
            current_index += 1
            
            # Formulate synthesized finding based on evidence excerpt and topic
            finding = f"[{domain.upper()}] Confirms {topic_name.replace('_', ' ')}: {best_excerpt[:180]}..."
            
            evidences.append({
                "stable_id": stable_id,
                "research_question": question,
                "topic": topic_name,
                "excerpt": best_excerpt,
                "finding": finding,
                "source_url": source_url,
                "source_title": source_title,
                "domain": domain,
                "provenance": provenance,
                "verification_status": "retrieved",  # Initial status must be 'retrieved', NOT 'claim_supported'
                "verification_explanation": "Retrieved passage extracted and preserved from source text.",
                "content_hash": content_hash,
            })

    # If no topic matched (very short page), provide general capture
    if not evidences and content.strip():
        sample = content[:250].strip()
        content_hash = hashlib.sha256(sample.encode("utf-8")).hexdigest()[:12]
        if content_hash not in existing_hashes:
            existing_hashes.add(content_hash)
            stable_id = f"EVID-{current_index:03d}"
            evidences.append({
                "stable_id": stable_id,
                "research_question": "General source evidence on autonomous systems",
                "topic": "general",
                "excerpt": sample,
                "finding": f"Baseline evidence captured from {domain}.",
                "source_url": source_url,
                "source_title": source_title,
                "domain": domain,
                "provenance": provenance,
                "verification_status": "retrieved",
                "verification_explanation": "General content excerpt captured and preserved.",
                "content_hash": content_hash,
            })

    logger.info(f"Generated {len(evidences)} evidence items for {domain} (initial status: 'retrieved')")
    return evidences
