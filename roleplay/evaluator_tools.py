"""
Evaluator Tools — pure functions for the agentic post-session evaluator.

These are invoked by the LLM via tool-calling (Ollama function-call API)
to gather evidence from a completed roleplay session before producing
feedback. Keeping them pure (no LLM deps, no DB writes) makes them:

  - Fast (all work on in-memory transcript + rolling scores)
  - Deterministic (same call → same output, great for debugging)
  - Individually testable (unit tests don't need Ollama running)

Each tool takes a ToolContext (transcript + session metadata) and returns
a JSON-serialisable dict that the LLM can reason about.

Tool inventory (must match the registry at the bottom of the file):
  1. search_transcript          — keyword search with context windows
  2. get_turn                   — fetch one turn + surrounding context
  3. analyze_spin_questions     — classify trainee questions (Rackham 1988)
  4. analyze_objection_moments  — LAER breakdown of each objection exchange
  5. get_eq_trajectory          — rolling EQ scores + trend
  6. find_extremum_moments      — best/worst moments by EQ swing
  7. cite_framework             — research framework descriptions
  8. compute_talk_ratio         — trainee vs customer word share
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ══════════════════════════════════════════════════════════════════
#  TOOL CONTEXT — what every tool has access to
# ══════════════════════════════════════════════════════════════════

@dataclass
class ToolContext:
    """
    Lightweight wrapper around the data an agentic evaluator needs.
    Built once by the orchestrator before starting the tool loop.
    """
    messages: List[Any]                     # list of RoleplayMessage or dicts
    eq_scores: List[float] = field(default_factory=list)
    persona_name: str = "the customer"
    persona_difficulty: str = "intermediate"
    persona_objections: List[str] = field(default_factory=list)
    document_context: str = ""

    def _turn(self, idx: int) -> Optional[Dict[str, Any]]:
        """Return a normalised turn dict for the given index, or None."""
        if idx < 0 or idx >= len(self.messages):
            return None
        m = self.messages[idx]
        sender = getattr(m, "sender", None) or (m.get("sender") if isinstance(m, dict) else "unknown")
        text = getattr(m, "message_text", None) or (m.get("text") if isinstance(m, dict) else "")
        return {
            "turn_index": idx,
            "sender": sender,
            "text": text or "",
        }

    def _all_turns(self) -> List[Dict[str, Any]]:
        return [self._turn(i) for i in range(len(self.messages))]


# ══════════════════════════════════════════════════════════════════
#  TOOL 1 — search_transcript
# ══════════════════════════════════════════════════════════════════

def search_transcript(ctx: ToolContext, keyword: str, max_hits: int = 5) -> Dict[str, Any]:
    """
    Case-insensitive keyword search. Returns matching turns with a small
    context window (previous + next turn). Good for locating specific
    moments before quoting them in feedback.
    """
    if not keyword or not keyword.strip():
        return {"keyword": keyword, "hits": [], "message": "Empty keyword"}

    needle = keyword.lower().strip()
    hits: List[Dict[str, Any]] = []

    for i, msg in enumerate(ctx.messages):
        turn = ctx._turn(i)
        if not turn or not turn["text"]:
            continue
        if needle in turn["text"].lower():
            prev_turn = ctx._turn(i - 1)
            next_turn = ctx._turn(i + 1)
            hits.append({
                "turn_index": i,
                "sender": turn["sender"],
                "text": turn["text"][:300],
                "previous": (prev_turn["text"][:200] if prev_turn else None),
                "next": (next_turn["text"][:200] if next_turn else None),
            })
            if len(hits) >= max_hits:
                break

    return {
        "keyword": keyword,
        "total_matches": len(hits),
        "hits": hits,
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 2 — get_turn
# ══════════════════════════════════════════════════════════════════

def get_turn(ctx: ToolContext, turn_index: int, window: int = 2) -> Dict[str, Any]:
    """
    Fetch a specific turn with context_window turns before and after.
    Useful when the LLM already knows which moment it wants to quote.
    """
    total = len(ctx.messages)
    if turn_index < 0 or turn_index >= total:
        return {"error": f"turn_index out of range (0..{total - 1})"}

    window = max(0, min(window, 5))
    start = max(0, turn_index - window)
    end = min(total, turn_index + window + 1)

    return {
        "requested_turn": turn_index,
        "window": window,
        "total_turns": total,
        "context": [ctx._turn(i) for i in range(start, end)],
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 3 — analyze_spin_questions
# ══════════════════════════════════════════════════════════════════

# Rackham (1988) SPIN classification via surface-level keyword heuristics.
# Agents can use these counts + per-question examples to reason about
# discovery quality.
_SPIN_KEYWORDS = {
    "situation":   ["what is your", "who handles", "how do you currently", "what does your", "what tools", "how many"],
    "problem":     ["challenge", "problem", "issue", "pain", "struggle", "difficult", "trouble", "frustrat"],
    "implication": ["impact", "effect", "consequence", "cost", "lose", "risk", "result in", "lead to"],
    "need_payoff": ["would it help", "would you benefit", "how would it", "value", "important if", "save you"],
}


def analyze_spin_questions(ctx: ToolContext) -> Dict[str, Any]:
    """
    Classify trainee questions via SPIN heuristics.
    Returns per-type counts + example turns.
    """
    counts = {k: 0 for k in _SPIN_KEYWORDS}
    examples: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _SPIN_KEYWORDS}
    trainee_question_count = 0

    for i, msg in enumerate(ctx.messages):
        turn = ctx._turn(i)
        if not turn or turn["sender"] != "trainee":
            continue
        if "?" not in turn["text"]:
            continue

        trainee_question_count += 1
        lower = turn["text"].lower()

        for spin_type, keywords in _SPIN_KEYWORDS.items():
            if any(k in lower for k in keywords):
                counts[spin_type] += 1
                if len(examples[spin_type]) < 2:
                    examples[spin_type].append({
                        "turn_index": i,
                        "text": turn["text"][:200],
                    })
                break   # count each question once — priority: problem > implication > situation

    return {
        "total_trainee_questions": trainee_question_count,
        "counts_by_type": counts,
        "examples_by_type": examples,
        "reference": "Rackham (1988) SPIN Selling — 35,000 call study",
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 4 — analyze_objection_moments
# ══════════════════════════════════════════════════════════════════

_OBJECTION_KEYWORDS = [
    "expensive", "too much", "can't afford", "budget", "not sure",
    "concerned", "worried", "competitor", "not ready", "think about",
    "need to discuss", "maybe later", "not convinced", "prove", "doubt",
]

_LAER_PATTERNS = {
    "listen":     ["i hear", "i understand", "i can see", "that makes sense", "i appreciate"],
    "acknowledge":["valid", "good point", "fair concern", "understandable", "you're right"],
    "explore":    ["can you tell me more", "what exactly", "help me understand", "why is that", "could you elaborate"],
    "respond":    ["let me explain", "here's how", "what we've found", "based on", "in your case"],
}


def analyze_objection_moments(ctx: ToolContext) -> Dict[str, Any]:
    """
    Identify objection exchanges and score trainee's handling via LAER
    heuristics (Listen / Acknowledge / Explore / Respond).
    """
    moments = []

    turns = ctx._all_turns()
    for i, t in enumerate(turns):
        if not t or t["sender"] != "ai_customer":
            continue
        text_lower = t["text"].lower()
        if not any(kw in text_lower for kw in _OBJECTION_KEYWORDS):
            continue

        # Next trainee turn is the response
        response_idx = None
        for j in range(i + 1, min(i + 3, len(turns))):
            tt = turns[j]
            if tt and tt["sender"] == "trainee":
                response_idx = j
                break

        laer_detected = {k: False for k in _LAER_PATTERNS}
        response_text = ""
        if response_idx is not None:
            response_text = turns[response_idx]["text"]
            response_lower = response_text.lower()
            for step, patterns in _LAER_PATTERNS.items():
                if any(p in response_lower for p in patterns):
                    laer_detected[step] = True

        moments.append({
            "objection_turn": i,
            "objection_text": t["text"][:250],
            "response_turn": response_idx,
            "response_text": response_text[:250] if response_text else None,
            "laer_steps_detected": [k for k, v in laer_detected.items() if v],
            "laer_steps_missed": [k for k, v in laer_detected.items() if not v],
            "laer_score": round(sum(laer_detected.values()) / 4, 2),
        })

    return {
        "total_objection_moments": len(moments),
        "moments": moments,
        "reference": "Carew International LAER framework — improves close rates 30-40%",
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 5 — get_eq_trajectory
# ══════════════════════════════════════════════════════════════════

def get_eq_trajectory(ctx: ToolContext) -> Dict[str, Any]:
    """Return the rolling EQ scores collected during the session + trend."""
    if not ctx.eq_scores:
        return {"available": False, "message": "No EQ scores recorded for this session"}

    scores = list(ctx.eq_scores)
    first = scores[0]
    last = scores[-1]
    avg = round(sum(scores) / len(scores), 1)
    peak = max(scores)
    trough = min(scores)

    if len(scores) >= 3:
        trend = (
            "improving" if last > first + 5 else
            "declining" if last < first - 5 else
            "stable"
        )
    else:
        trend = "insufficient_data"

    return {
        "available": True,
        "count": len(scores),
        "first": round(first, 1),
        "last": round(last, 1),
        "average": avg,
        "peak": round(peak, 1),
        "trough": round(trough, 1),
        "trend": trend,
        "raw_scores": [round(s, 1) for s in scores],
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 6 — find_extremum_moments
# ══════════════════════════════════════════════════════════════════

def find_extremum_moments(ctx: ToolContext) -> Dict[str, Any]:
    """
    Find the two biggest EQ swings (up and down) and return the
    turn-indices + text of the trainee messages that likely caused them.
    """
    if not ctx.eq_scores or len(ctx.eq_scores) < 3:
        return {"available": False, "message": "Need at least 3 EQ scores to detect swings"}

    scores = ctx.eq_scores
    deltas = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
    if not deltas:
        return {"available": False, "message": "No deltas computable"}

    best_delta = max(deltas)
    worst_delta = min(deltas)
    best_i = deltas.index(best_delta) + 1
    worst_i = deltas.index(worst_delta) + 1

    # Map EQ score index → trainee message (EQ is updated per trainee turn)
    trainee_turns = [
        i for i, m in enumerate(ctx.messages)
        if getattr(m, "sender", None) == "trainee" or
        (isinstance(m, dict) and m.get("sender") == "trainee")
    ]

    def _map(eq_idx: int) -> Optional[Dict[str, Any]]:
        if eq_idx >= len(trainee_turns):
            return None
        turn_idx = trainee_turns[eq_idx]
        return ctx._turn(turn_idx)

    return {
        "available": True,
        "best_moment": {
            "eq_delta": round(best_delta, 1),
            "eq_score_after": round(scores[best_i], 1),
            "turn": _map(best_i),
        },
        "worst_moment": {
            "eq_delta": round(worst_delta, 1),
            "eq_score_after": round(scores[worst_i], 1),
            "turn": _map(worst_i),
        },
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 7 — cite_framework
# ══════════════════════════════════════════════════════════════════

_FRAMEWORKS = {
    "SPIN": {
        "full_name": "SPIN Selling",
        "author": "Neil Rackham",
        "year": 1988,
        "summary": (
            "Question-based selling methodology based on a 35,000-call study. "
            "Four question types: Situation (context), Problem (pain), "
            "Implication (consequences), Need-payoff (benefits). "
            "Implication questions are the strongest predictor of complex B2B "
            "sales success."
        ),
        "use_for": "discovery, needs assessment",
    },
    "LAER": {
        "full_name": "Listen-Acknowledge-Explore-Respond framework",
        "author": "Carew International",
        "year": None,
        "summary": (
            "4-step objection handling: Listen (full attention, no interruption), "
            "Acknowledge (validate the concern), Explore (probe for root cause), "
            "Respond (evidence-based rebuttal). Training data shows 30-40% "
            "improvement in close rates."
        ),
        "use_for": "objection handling",
    },
    "WLEIS": {
        "full_name": "Wong and Law Emotional Intelligence Scale",
        "author": "Wong & Law",
        "year": 2002,
        "summary": (
            "Four EI dimensions: Self-Emotion Appraisal (SEA), "
            "Others-Emotion Appraisal (OEA), Use of Emotion (UOE), "
            "Regulation of Emotion (ROE). Strong predictor of sales performance."
        ),
        "use_for": "emotional intelligence scoring",
    },
    "Hattie": {
        "full_name": "Hattie & Timperley Feedback Model",
        "author": "Hattie & Timperley",
        "year": 2007,
        "summary": (
            "Three-layer feedback: Feed-up (what is the goal?), "
            "Feed-back (what has been done?), Feed-forward (what's next?). "
            "Effect size 0.79 in meta-analysis of 196,000 studies — one of "
            "the strongest education interventions ever measured."
        ),
        "use_for": "structuring coaching feedback",
    },
}


def cite_framework(ctx: ToolContext, name: str) -> Dict[str, Any]:
    """
    Return the canonical citation + one-paragraph description of a
    sales/training framework so the evaluator can ground its feedback.
    """
    key = (name or "").strip()
    # Case-insensitive lookup
    for k, v in _FRAMEWORKS.items():
        if k.lower() == key.lower():
            return {"name": k, **v}

    return {
        "name": name,
        "error": f"Framework '{name}' not in catalogue",
        "available": list(_FRAMEWORKS.keys()),
    }


# ══════════════════════════════════════════════════════════════════
#  TOOL 8 — compute_talk_ratio
# ══════════════════════════════════════════════════════════════════

def compute_talk_ratio(ctx: ToolContext) -> Dict[str, Any]:
    """
    Return word-count share between trainee and customer.
    Gong-style monologue detection: any single turn > 120 words is flagged.
    """
    trainee_words = 0
    customer_words = 0
    longest_trainee_turn = {"turn_index": None, "word_count": 0, "text_preview": ""}

    for i, msg in enumerate(ctx.messages):
        turn = ctx._turn(i)
        if not turn:
            continue
        wc = len((turn["text"] or "").split())

        if turn["sender"] == "trainee":
            trainee_words += wc
            if wc > longest_trainee_turn["word_count"]:
                longest_trainee_turn = {
                    "turn_index": i,
                    "word_count": wc,
                    "text_preview": turn["text"][:160],
                }
        elif turn["sender"] == "ai_customer":
            customer_words += wc

    total = trainee_words + customer_words
    trainee_pct = round(trainee_words / total * 100, 1) if total else 0.0
    customer_pct = round(customer_words / total * 100, 1) if total else 0.0

    verdict = "balanced"
    if trainee_pct >= 65:
        verdict = "trainee_dominated"
    elif trainee_pct <= 35:
        verdict = "customer_dominated"

    return {
        "trainee_word_share_pct": trainee_pct,
        "customer_word_share_pct": customer_pct,
        "total_words": total,
        "verdict": verdict,
        "longest_trainee_turn": longest_trainee_turn,
        "is_monologue": longest_trainee_turn["word_count"] > 120,
        "reference": "Gong Labs analysis of 519K sales calls — optimal trainee share 40-50%",
    }


# ══════════════════════════════════════════════════════════════════
#  REGISTRY — name → (function, JSON schema for tool-calling)
# ══════════════════════════════════════════════════════════════════

# Schemas follow the OpenAI-compatible function-calling format that
# Ollama's /api/chat expects when `tools` is provided.

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_transcript",
            "description": "Search the conversation transcript for a keyword (case-insensitive). Returns matching turns with previous/next context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Word or phrase to search for"},
                    "max_hits": {"type": "integer", "description": "Max matches to return (default 5)"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_turn",
            "description": "Fetch a specific turn by index with context (window turns before and after).",
            "parameters": {
                "type": "object",
                "properties": {
                    "turn_index": {"type": "integer", "description": "0-based turn index"},
                    "window": {"type": "integer", "description": "Context window size (0-5)"},
                },
                "required": ["turn_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_spin_questions",
            "description": "Classify trainee questions by SPIN type (Situation/Problem/Implication/Need-payoff). Returns counts + examples per type.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_objection_moments",
            "description": "Identify each customer objection in the transcript and score the trainee's LAER response (Listen/Acknowledge/Explore/Respond).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_eq_trajectory",
            "description": "Return the rolling EQ scores + trend (improving/declining/stable).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_extremum_moments",
            "description": "Return the single best and worst EQ moments in the session with the trainee turns that caused them.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cite_framework",
            "description": "Return canonical citation + one-paragraph description of a sales/training framework. Valid names: SPIN, LAER, WLEIS, Hattie.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Framework name: SPIN, LAER, WLEIS, or Hattie"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_talk_ratio",
            "description": "Return word-count share between trainee and customer + longest trainee turn (monologue detection).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# Name → callable registry (all functions take ctx + kwargs from the LLM)
TOOL_REGISTRY: Dict[str, Any] = {
    "search_transcript": search_transcript,
    "get_turn": get_turn,
    "analyze_spin_questions": analyze_spin_questions,
    "analyze_objection_moments": analyze_objection_moments,
    "get_eq_trajectory": get_eq_trajectory,
    "find_extremum_moments": find_extremum_moments,
    "cite_framework": cite_framework,
    "compute_talk_ratio": compute_talk_ratio,
}


def invoke_tool(ctx: ToolContext, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch a tool call. Returns the tool's result dict, or an error
    payload if the tool name is unknown or execution fails.
    """
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}", "available_tools": list(TOOL_REGISTRY.keys())}

    try:
        # Never trust LLM-provided args blindly — filter to the ones the fn expects
        import inspect
        sig = inspect.signature(fn)
        accepted = {k for k in sig.parameters.keys() if k != "ctx"}
        clean_args = {k: v for k, v in (arguments or {}).items() if k in accepted}
        return fn(ctx, **clean_args)
    except Exception as e:
        return {"error": f"Tool '{name}' raised: {type(e).__name__}: {e}"}
