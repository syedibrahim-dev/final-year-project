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
#
# The agent must distinguish two very different things:
#
#   (a) HARD claims — carry concrete, checkable facts: numbers, prices,
#       timeframes, percentages, multipliers, ROI figures, named
#       superlatives ("industry-leading"). These MUST be fact-checked.
#
#   (b) SOFT filler — conversational verbs in generic sentences like
#       "the goal is to reduce your workload", "we can help you save
#       time". Sending these to RAG produces noisy low similarity
#       scores and creates false-positive "unverified" flags.
#
# Old logic treated (b) as a claim whenever any of {reduce, offer,
# save, improve, scale, ...} appeared. New logic requires a sentence
# to contain at least one HARD marker before it's forwarded to RAG.

# Hard markers — any one of these anchors the sentence to a concrete claim
HARD_CLAIM_PATTERNS = [
    r'\b\d+\s*%',                                              # percentages (also "60 %")
    r'\$\s*[\d][\d.,]*',                                       # dollar amounts
    r'\b(?:usd|eur|gbp|inr|cad|aud)\s*[\d][\d.,]*',            # other currencies
    r'\b[\d][\d.,]*\s*(?:dollars?|euros?|pounds?|rupees?)\b',  # spelled-out currency
    r'\b\d+\s*(?:x|times)\b',                                  # multipliers ("3x faster")
    r'\b\d+\s*(?:hours?|days?|weeks?|months?|years?|minutes?)\b',  # timeframes
    r'\b(?:industry.?leading|best.?in.?class|state.?of.?the.?art|cutting.?edge|enterprise.?grade)\b',
    r'\b(?:roi|payback|break.?even|total.?cost|cost.?sav\w*)\b',
]
_HARD_CLAIM_RE = re.compile("|".join(HARD_CLAIM_PATTERNS), re.IGNORECASE)

_NUMBER_RE = re.compile(
    r'\$\s*\d[\d,]*(?:\.\d+)?'    # $15,000 / $ 15000.50
    r'|\d[\d,]*(?:\.\d+)?\s*%'    # 60% / 12.5 %
    r'|\b\d[\d,]*(?:\.\d+)?',     # bare numbers (also catches '3' in '3x')
    re.IGNORECASE,
)


def _looks_like_claim(sentence: str) -> bool:
    """A sentence is worth fact-checking only if it carries a HARD marker."""
    s = sentence.strip()
    if len(s) < 15:
        return False
    return bool(_HARD_CLAIM_RE.search(s))


def _extract_claims(text: str) -> List[str]:
    """Extract sentences that look like hard factual claims."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    claims = [s.strip() for s in sentences if _looks_like_claim(s)]
    return claims[:3]  # cap at 3 claims per message


def _normalize_number(raw: str) -> str:
    """Strip formatting so '$15,000' and '15000' compare equal."""
    return re.sub(r'[^0-9.]', '', raw)


def _extract_numbers(text: str) -> List[str]:
    """Return normalized numeric tokens present in the text."""
    out: List[str] = []
    for m in _NUMBER_RE.finditer(text):
        n = _normalize_number(m.group(0))
        # drop trailing '.' if pattern caught something like "3."
        n = n.rstrip('.')
        if n and n != '.':
            out.append(n)
    return out


def _numbers_supported(claim_numbers: List[str], chunks: List[dict]) -> List[str]:
    """
    Return the subset of claim_numbers that actually appear in ANY chunk.
    Uses normalized comparison so formatting doesn't matter.
    """
    if not claim_numbers:
        return []
    chunk_numbers: set[str] = set()
    for ch in chunks:
        text = ch.get("chunk") or ""
        for m in _NUMBER_RE.finditer(text):
            chunk_numbers.add(_normalize_number(m.group(0)).rstrip('.'))
    return [n for n in claim_numbers if n in chunk_numbers]


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

        for claim in claims:
            try:
                chunks = retrieve_relevant_chunks(
                    query=claim, org_id=ctx.org_id, k=5
                )

                if not chunks:
                    flagged.append({
                        "claim": claim,
                        "reason": "No matching documents found",
                        "confidence": 0.0,
                    })
                    continue

                best = chunks[0]
                score = float(best.get("score", 0.0))
                best_source = (best.get("metadata") or {}).get("source", "document")

                # Step 1: if the claim has numeric values, they MUST appear
                # in the retrieved chunks. Topical similarity alone is not
                # enough — a doc mentioning "pricing" does not support a
                # hallucinated "$15,000" figure.
                claim_numbers = _extract_numbers(claim)
                if claim_numbers:
                    found = _numbers_supported(claim_numbers, chunks)
                    missing = [n for n in claim_numbers if n not in found]

                    if missing:
                        flagged.append({
                            "claim": claim,
                            "reason": (
                                f"Numeric value(s) {missing} not found in any "
                                f"uploaded document"
                            ),
                            "confidence": round(score, 2),
                        })
                        continue

                    # Numbers check out AND topical similarity is reasonable
                    supported.append({
                        "claim": claim,
                        "source": best_source,
                        "similarity": round(score, 2),
                        "numbers_verified": found,
                    })
                    continue

                # Step 2: non-numeric hard claims (superlatives, ROI words).
                # Require a positive cross-encoder score. Raise the bar a
                # little so weakly-related topics aren't auto-approved.
                if score >= 0.08:
                    supported.append({
                        "claim": claim,
                        "source": best_source,
                        "similarity": round(score, 2),
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

        # Determine overall flag.
        # Priority: any flagged claim → "unverified". Otherwise, if at
        # least one claim was supported → "accurate". If zero claims
        # were extracted (filler-only trainee message) → "no_claims".
        total_checked = len(claims)
        if flagged:
            flag = "unverified"
        elif supported:
            flag = "accurate"
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
