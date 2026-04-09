"""
Knowledge Accuracy Agent — RAG-based fact-checker.

Cross-references the trainee's factual claims against uploaded documents
via vector similarity search.  No LLM required — uses the existing
ChromaDB retrieval pipeline.

LLM calls: 0  (RAG vector search only)
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

# ── Claim extraction patterns ────────────────────────────────────────

# Sentences likely to contain factual claims
CLAIM_INDICATORS = [
    r'\b\d+%',           # percentages
    r'\$[\d.,]+',        # dollar amounts
    r'\b\d+\s*(x|times)\b',  # multipliers
    r'\b\d+\s*(hour|day|week|month|year)s?\b',  # time-based claims
    r'\b(feature|capability|include|offer|provide|support|guarantee|deliver|achieve'
    r'|reduce|increase|improve|save|automate|streamline|enable|accelerate|integrate'
    r'|eliminate|optimize|simplify|scale)\b',
    r'\b(compared to|better than|faster than|more than|up to|at least|on average)\b',
    r'\b(industry.?leading|best.?in.?class|state.?of.?the.?art|cutting.?edge|enterprise.?grade)\b',
    r'\b(roi|cost.?sav|payback|break.?even|total.?cost)\b',  # ROI / cost claims
]


def _looks_like_claim(sentence: str) -> bool:
    """Check if a sentence likely contains a factual/product claim."""
    s = sentence.lower().strip()
    if len(s) < 15:  # too short to be a claim
        return False
    for pattern in CLAIM_INDICATORS:
        if re.search(pattern, s, re.IGNORECASE):
            return True
    return False


def _extract_claims(text: str) -> List[str]:
    """Extract sentences that look like factual claims."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    claims = [s.strip() for s in sentences if _looks_like_claim(s)]
    return claims[:3]  # cap at 3 claims per message


class KnowledgeAccuracyAgent(BaseAgent):
    """Fact-checks trainee claims against uploaded docs — no LLM."""

    @property
    def name(self) -> str:
        return "knowledge_accuracy"

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        return {}  # No LLM

    def run(self, ctx: AgentContext) -> AgentResult:
        # Skip if no org (no documents to check against)
        if not ctx.org_id:
            return self._make_result(data={
                "accuracy_flag": "no_docs",
                "claims_checked": 0,
                "flagged_claims": [],
                "supported_claims": [],
            })

        claims = _extract_claims(ctx.trainee_message)

        if not claims:
            return self._make_result(data={
                "accuracy_flag": "no_claims",
                "claims_checked": 0,
                "flagged_claims": [],
                "supported_claims": [],
            })

        # Check each claim against documents
        flagged = []
        supported = []

        try:
            from services.rag_service import retrieve_relevant_chunks
        except ImportError:
            logger.warning("Could not import retrieve_relevant_chunks")
            return self._make_result(data={
                "accuracy_flag": "unavailable",
                "claims_checked": 0,
                "flagged_claims": [],
                "supported_claims": [],
            })

        # Pre-loaded document context from orchestrator (used for quick substring check)
        preloaded_context = (ctx.document_context or "").lower()

        for claim in claims:
            try:
                # Fast check: if the claim's key terms appear in already-retrieved context,
                # do a targeted RAG lookup to get the exact score. If not even mentioned,
                # likely unverified.
                chunks = retrieve_relevant_chunks(
                    query=claim, org_id=ctx.org_id, k=3
                )

                if not chunks:
                    flagged.append({
                        "claim": claim,
                        "reason": "No matching documents found",
                        "confidence": 0.0,
                    })
                    continue

                # Retrieval score: 1 - L2_distance on normalised embeddings
                # Range roughly [-0.4, 0.55]; higher = more relevant.
                best = chunks[0]
                score = best.get("score", 0.0)

                # Quantitative claims (%, $, timeframes) need a HIGHER bar.
                # A generic positive score just means "document mentions the topic"
                # but doesn't confirm the exact figure (e.g., "60% savings" vs doc
                # that just mentions "cost savings" generically).
                has_number = bool(re.search(
                    r'\b\d+%|\$[\d.,]+|\b\d+\s*(x|times|hour|day|week|month|year)s?\b',
                    claim, re.IGNORECASE
                ))
                support_threshold = 0.15 if has_number else 0.0

                if score >= support_threshold:
                    supported.append({
                        "claim": claim,
                        "source": best.get("source", "document"),
                        "similarity": round(score, 2),
                    })
                elif score >= -0.25:
                    # Partial match — not flagged but not confirmed
                    # For quantitative claims with moderate scores, flag as unverified
                    if has_number and score < support_threshold:
                        flagged.append({
                            "claim": claim,
                            "reason": "Quantitative claim not confirmed by documents",
                            "confidence": round(score, 2),
                        })
                else:
                    flagged.append({
                        "claim": claim,
                        "reason": "Low match with uploaded documents",
                        "confidence": round(score, 2),
                    })

            except Exception as e:
                logger.warning(f"Claim check failed for '{claim[:50]}': {e}")
                continue

        # Determine overall flag
        # If ANY claims were checked but NONE were supported, that's unverified — not "no_match"
        total_checked = len(claims)
        if flagged:
            flag = "unverified"
        elif supported and not flagged:
            flag = "accurate"
        elif total_checked > 0 and not supported:
            # Claims were made but none matched documents — warn the trainee
            flag = "unverified"
        else:
            flag = "no_claims"

        data = {
            "accuracy_flag": flag,
            "claims_checked": total_checked,
            "flagged_claims": flagged,
            "supported_claims": supported,
        }

        if flagged:
            logger.info(
                f"⚠️  KnowledgeAgent: {len(flagged)} unverified claim(s) "
                f"out of {total_checked}"
            )
        else:
            logger.info(
                f"✅ KnowledgeAgent: {len(supported)}/{total_checked} "
                f"claims supported by docs"
            )

        return self._make_result(data=data)
