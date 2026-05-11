"""
Fact-Check Tools — pure-function helpers for the agentic fact-checker.

These let an LLM reason about trainee claims with structured evidence
gathering, rather than relying on the hot-path KnowledgeAgent's
regex + vector + numeric heuristic.

Tool inventory:
  1. extract_trainee_claims      — scan transcript for claim-worthy sentences
  2. retrieve_evidence           — RAG search (uses existing retrieve_relevant_chunks)
  3. analyze_claim_structure     — extract numbers, scope modifiers, subject hints
  4. compare_numbers             — numeric match with tolerance + exaggeration detection
  5. check_scope_alignment       — flag "total X" vs "partial X" style mismatches

Design note: tools are additive to the existing KnowledgeAgent. The hot
path (per-turn regex + vector + numeric match) still runs as always.
These tools only power the optional post-session deep fact-check.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  TOOL CONTEXT
# ══════════════════════════════════════════════════════════════════

@dataclass
class FactCheckToolContext:
    """
    What every fact-check tool has access to. Built once by the
    AgenticFactChecker before starting its tool loop.
    """
    messages: List[Any]
    org_id: Optional[int] = None
    # Callable injected at run time — wraps services.rag_service.retrieve_relevant_chunks
    # Signature: retrieve_fn(query: str, org_id: int, k: int) -> list[dict]
    retrieve_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None

    def _turn(self, idx: int) -> Optional[Dict[str, Any]]:
        if idx < 0 or idx >= len(self.messages):
            return None
        m = self.messages[idx]
        sender = getattr(m, "sender", None) or (m.get("sender") if isinstance(m, dict) else "unknown")
        text = getattr(m, "message_text", None) or (m.get("text") if isinstance(m, dict) else "")
        return {"turn_index": idx, "sender": sender, "text": text or ""}


# ══════════════════════════════════════════════════════════════════
#  CLAIM DETECTION SIGNALS (shared patterns)
# ══════════════════════════════════════════════════════════════════

# Numeric claims: 60%, $1.5M, 3x, 99.7, etc.
_NUMBER_RE = re.compile(
    r"\b("
    r"\d+(?:\.\d+)?\s*%|"                          # 60%, 99.7%
    r"\$\s*\d+(?:,\d{3})*(?:\.\d+)?\s*[MBKmbk]?|"  # $1.5M, $500K, $1,000
    r"\d+(?:\.\d+)?\s*[MBKmbk]\b|"                 # 1.5M, 500K
    r"\d+(?:\.\d+)?\s*x\b|"                        # 3x, 10x
    r"\d+(?:\.\d+)?\s+(?:days|weeks|months|years|hours|minutes)"  # 3 weeks
    r")"
)

# Superlative / guarantee markers — "industry-leading", "always", "100%", etc.
_SUPERLATIVE_SIGNALS = [
    "industry-leading", "industry leading", "best-in-class", "best in class",
    "number one", "#1", "no. 1", "top-rated", "award-winning",
    "guaranteed", "guarantee", "zero downtime", "100%", "always",
    "every time", "never", "fastest", "cheapest", "most reliable",
    "proven", "proof", "certified",
]

# Scope modifiers — "total", "complete", "all", etc.
_SCOPE_MODIFIERS = [
    "total", "complete", "entire", "full", "all", "every", "any",
    "always", "never", "guaranteed", "every single", "100%", "zero",
    "unlimited", "whole",
]

# Hedging / partial language in evidence — opposite of absolute claims
_HEDGING_WORDS = [
    "typically", "usually", "often", "some", "most", "many",
    "up to", "as much as", "can be", "may be", "sometimes",
    "average", "on average", "approximately", "roughly", "around",
]


# ══════════════════════════════════════════════════════════════════
#  TOOL 1 — extract_trainee_claims
# ══════════════════════════════════════════════════════════════════

def extract_trainee_claims(
    ctx: FactCheckToolContext,
    min_length: int = 25,
    max_claims: int = 20,
) -> Dict[str, Any]:
    """
    Scan trainee messages for sentences likely to contain verifiable claims.
    A sentence qualifies if it has numeric markers OR superlative markers
    AND is longer than `min_length` characters.
    """
    claims: List[Dict[str, Any]] = []

    for i, m in enumerate(ctx.messages):
        turn = ctx._turn(i)
        if not turn or turn["sender"] != "trainee":
            continue
        text = (turn["text"] or "").strip()
        if len(text) < min_length:
            continue

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            s = s.strip()
            if len(s) < min_length:
                continue

            lower = s.lower()
            has_number = bool(_NUMBER_RE.search(s))
            has_superlative = any(marker in lower for marker in _SUPERLATIVE_SIGNALS)

            if not (has_number or has_superlative):
                continue

            claims.append({
                "claim_id": len(claims),
                "turn_index": i,
                "claim_text": s[:400],
                "has_numbers": has_number,
                "has_superlatives": has_superlative,
            })

            if len(claims) >= max_claims:
                break
        if len(claims) >= max_claims:
            break

    return {
        "total_claims_found": len(claims),
        "max_claims_cap": max_claims,
        "claims": claims,
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 2 — retrieve_evidence
# ══════════════════════════════════════════════════════════════════

def retrieve_evidence(
    ctx: FactCheckToolContext,
    query: str,
    k: int = 5,
) -> Dict[str, Any]:
    """
    Search the org's knowledge base for passages supporting or contradicting
    a claim. Uses the existing RAG pipeline, so no new embedding model is
    needed.
    """
    if not query or not query.strip():
        return {"available": False, "message": "Empty query", "chunks": []}

    if ctx.org_id is None or ctx.retrieve_fn is None:
        return {
            "available": False,
            "message": "No document index available for this org",
            "chunks": [],
        }

    try:
        raw_chunks = ctx.retrieve_fn(query=query.strip(), org_id=ctx.org_id, k=k)
    except Exception as e:
        logger.warning(f"retrieve_evidence: RAG call failed: {e}")
        return {"available": False, "message": f"RAG error: {e}", "chunks": []}

    chunks: List[Dict[str, Any]] = []
    for c in (raw_chunks or []):
        # raw_chunks format: {"chunk": "...", "score": 0.87, maybe "source": "..."}
        text = c.get("chunk", "") if isinstance(c, dict) else ""
        score = c.get("score", 0.0) if isinstance(c, dict) else 0.0
        source = c.get("source", None) if isinstance(c, dict) else None
        if text:
            chunks.append({
                "text": text[:500],
                "score": round(float(score), 3),
                "source": source,
            })

    return {
        "available": True,
        "query": query,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 3 — analyze_claim_structure
# ══════════════════════════════════════════════════════════════════

def _extract_numbers(text: str) -> List[Dict[str, Any]]:
    """Find numeric tokens with surrounding context."""
    numbers = []
    for m in _NUMBER_RE.finditer(text):
        raw = m.group(0).strip()
        # Try to parse the value as a float (strip non-numeric parts)
        numeric_part = re.search(r"\d+(?:\.\d+)?", raw)
        if not numeric_part:
            continue
        value = float(numeric_part.group(0))

        # Unit detection — check most specific patterns first
        unit = None
        raw_lower = raw.lower()
        if "%" in raw:
            unit = "percent"
        elif "$" in raw:
            unit = "usd"
        elif any(u in raw_lower for u in ["day", "week", "month", "year", "hour", "minute"]):
            unit = "time"   # must check time FIRST so "week" isn't matched as "k"
        # Bare trailing-letter multipliers — require whitespace or end-of-string boundary
        elif re.search(r"\d\s*[Mm]\b", raw):
            unit = "million"
        elif re.search(r"\d\s*[Kk]\b", raw):
            unit = "thousand"
        elif re.search(r"\d\s*x\b", raw_lower):
            unit = "multiplier"

        # Context: 30 chars before + 30 after
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        context = text[start:end].strip()

        numbers.append({
            "raw": raw,
            "value": value,
            "unit": unit,
            "context": context,
        })
    return numbers


def analyze_claim_structure(ctx: FactCheckToolContext, claim_text: str) -> Dict[str, Any]:
    """
    Break down a claim into structured components the LLM can reason about:
      - numbers (with units and context)
      - scope modifiers (absolute vs hedged language)
      - superlative signals
    """
    if not claim_text or not claim_text.strip():
        return {"error": "Empty claim"}

    text = claim_text.strip()
    lower = text.lower()

    numbers = _extract_numbers(text)
    scope_hits = [w for w in _SCOPE_MODIFIERS if w in lower]
    superlative_hits = [w for w in _SUPERLATIVE_SIGNALS if w in lower]

    return {
        "claim_text": text,
        "numbers": numbers,
        "has_scope_modifiers": bool(scope_hits),
        "scope_modifiers_found": scope_hits,
        "has_superlatives": bool(superlative_hits),
        "superlatives_found": superlative_hits,
        "word_count": len(text.split()),
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 4 — compare_numbers
# ══════════════════════════════════════════════════════════════════

def compare_numbers(
    ctx: FactCheckToolContext,
    claim_numbers: List[Dict[str, Any]],
    evidence_text: str,
    tolerance_pct: float = 5.0,
) -> Dict[str, Any]:
    """
    Given claim numbers (from analyze_claim_structure) and a raw evidence
    passage, extract evidence numbers and compute match / exaggeration /
    understatement per claim number.
    """
    if not claim_numbers:
        return {"comparisons": [], "message": "No claim numbers to compare"}

    evidence_numbers = _extract_numbers(evidence_text or "")

    comparisons = []
    for claim_num in claim_numbers:
        claim_val = claim_num.get("value")
        claim_unit = claim_num.get("unit")
        claim_raw = claim_num.get("raw", "?")

        # Find the closest-unit evidence number
        candidates = [e for e in evidence_numbers if e.get("unit") == claim_unit]
        if not candidates:
            comparisons.append({
                "claim_number": claim_raw,
                "verdict": "not_in_evidence",
                "reason": f"No {claim_unit}-unit number found in evidence",
            })
            continue

        # Pick the candidate closest to the claim value
        best = min(candidates, key=lambda e: abs(e["value"] - claim_val))
        diff = best["value"] - claim_val
        pct_diff = (abs(diff) / max(claim_val, 0.001)) * 100

        if pct_diff <= tolerance_pct:
            verdict = "match"
            reason = f"Evidence has {best['raw']} vs claim {claim_raw} ({pct_diff:.1f}% diff, within {tolerance_pct}% tolerance)"
        elif claim_val > best["value"]:
            verdict = "exaggerated"
            reason = f"Claim says {claim_raw} but evidence shows {best['raw']} (claim is {pct_diff:.1f}% higher)"
        else:
            verdict = "understated"
            reason = f"Claim says {claim_raw} but evidence shows {best['raw']} (claim is {pct_diff:.1f}% lower)"

        comparisons.append({
            "claim_number": claim_raw,
            "claim_value": claim_val,
            "evidence_number": best["raw"],
            "evidence_value": best["value"],
            "evidence_context": best["context"],
            "verdict": verdict,
            "reason": reason,
        })

    return {
        "comparisons": comparisons,
        "tolerance_pct": tolerance_pct,
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 5 — check_scope_alignment
# ══════════════════════════════════════════════════════════════════

def check_scope_alignment(
    ctx: FactCheckToolContext,
    claim_text: str,
    evidence_text: str,
) -> Dict[str, Any]:
    """
    Detect scope/qualifier mismatches between claim and evidence. This is
    the "total costs" vs "ops costs" case — subtle lies the hot-path
    regex misses because the words look similar.

    Heuristics:
      - If claim uses absolute scope words (total/all/every) AND evidence
        uses hedging (typically/up to/some) → possible overreach
      - Capture adjacent nouns for side-by-side comparison
    """
    if not claim_text or not evidence_text:
        return {"aligned": True, "message": "Empty input"}

    claim_lower = claim_text.lower()
    evidence_lower = evidence_text.lower()

    claim_scope = [w for w in _SCOPE_MODIFIERS if w in claim_lower]
    evidence_hedging = [w for w in _HEDGING_WORDS if w in evidence_lower]

    # Extract noun phrases adjacent to scope words in the claim
    # e.g. "total security costs" — the 2 words after "total"
    claim_scope_phrases = []
    for w in claim_scope:
        # find the word and capture up to 3 words following it
        m = re.search(rf"\b{re.escape(w)}\s+(\w+(?:\s+\w+){{0,3}})", claim_lower)
        if m:
            claim_scope_phrases.append(f"{w} {m.group(1)}")

    # Look for the same nouns in evidence but without the absolute modifier
    scope_mismatches = []
    for phrase in claim_scope_phrases:
        scope_word, *noun_parts = phrase.split()
        noun = " ".join(noun_parts)
        if not noun:
            continue
        if noun in evidence_lower and phrase not in evidence_lower:
            scope_mismatches.append({
                "claim_phrase": phrase,
                "evidence_has_noun": True,
                "evidence_has_same_scope": False,
                "flag": (
                    f"Claim says '{phrase}' — evidence mentions '{noun}' but "
                    f"without the '{scope_word}' modifier. Possible scope overreach."
                ),
            })

    # Cross-check: claim is absolute, evidence is hedged
    cross_flag = None
    if claim_scope and evidence_hedging:
        cross_flag = (
            f"Claim uses absolute language ({claim_scope[:3]}) while evidence "
            f"uses hedging ({evidence_hedging[:3]}) — possible overreach."
        )

    return {
        "claim_scope_words": claim_scope,
        "evidence_hedging_words": evidence_hedging,
        "scope_mismatches": scope_mismatches,
        "absolute_vs_hedged_flag": cross_flag,
        "aligned": not scope_mismatches and cross_flag is None,
    }


# ══════════════════════════════════════════════════════════════════
#  REGISTRY for tool-calling
# ══════════════════════════════════════════════════════════════════

FACT_CHECK_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_trainee_claims",
            "description": "Scan the transcript for trainee sentences containing numbers or superlatives (likely claims). Returns a list of claim_id, turn_index, claim_text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_length": {"type": "integer", "description": "Minimum sentence length (default 25)"},
                    "max_claims": {"type": "integer", "description": "Max claims to return (default 20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_evidence",
            "description": "Search the organisation's uploaded documents (RAG) for passages supporting or contradicting a claim. Returns top-k chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The claim or key phrase to search for"},
                    "k": {"type": "integer", "description": "Top-k chunks to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_claim_structure",
            "description": "Extract structured components (numbers, scope modifiers, superlatives) from a claim sentence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string", "description": "The claim sentence"},
                },
                "required": ["claim_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_numbers",
            "description": "Given claim numbers (from analyze_claim_structure) and evidence passage text, return per-number verdicts: match / exaggerated / understated / not_in_evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_numbers": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of number objects from analyze_claim_structure",
                    },
                    "evidence_text": {"type": "string", "description": "Raw passage text to compare against"},
                    "tolerance_pct": {"type": "number", "description": "Percentage tolerance for 'match' (default 5)"},
                },
                "required": ["claim_numbers", "evidence_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_scope_alignment",
            "description": "Detect scope mismatches like 'total security costs' (claim) vs 'security ops costs' (evidence) — subtle lies the regex misses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "evidence_text": {"type": "string"},
                },
                "required": ["claim_text", "evidence_text"],
            },
        },
    },
]


FACT_CHECK_TOOL_REGISTRY: Dict[str, Callable] = {
    "extract_trainee_claims": extract_trainee_claims,
    "retrieve_evidence": retrieve_evidence,
    "analyze_claim_structure": analyze_claim_structure,
    "compare_numbers": compare_numbers,
    "check_scope_alignment": check_scope_alignment,
}


def invoke_fact_check_tool(
    ctx: FactCheckToolContext,
    name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Dispatch a fact-check tool call. Returns its result or an error payload."""
    fn = FACT_CHECK_TOOL_REGISTRY.get(name)
    if fn is None:
        return {
            "error": f"Unknown tool: {name}",
            "available": list(FACT_CHECK_TOOL_REGISTRY.keys()),
        }
    try:
        import inspect
        sig = inspect.signature(fn)
        accepted = {k for k in sig.parameters.keys() if k != "ctx"}
        clean_args = {k: v for k, v in (arguments or {}).items() if k in accepted}
        return fn(ctx, **clean_args)
    except Exception as e:
        return {"error": f"Tool '{name}' raised: {type(e).__name__}: {e}"}
