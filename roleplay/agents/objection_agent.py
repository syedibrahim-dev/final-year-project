"""
Objection Injection Agent — rule-based objection planner.

Decides when and what kind of objection the PersonaAgent should raise,
based on conversation stage, difficulty, and which objections have
already been used.  Sets an `objection_directive` on the AgentContext
that the PersonaAgent reads and weaves into its response.

LLM calls: 0  (pure rule-based logic)
"""
from __future__ import annotations

import random
import logging
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

# ── Objection templates (fallbacks when persona has none) ────────────

DEFAULT_OBJECTIONS = {
    # ~50% of real B2B objections are dismissive brush-offs (HubSpot research)
    "dismissive": [
        "Can you just send me an email with the details?",
        "We're not really looking at this right now.",
        "I'm not the right person for this — you'd need to talk to someone else.",
        "I think we're good, but thanks for reaching out.",
        "We've already got something that works for us.",
    ],
    "mild": [
        "I'm not sure this is the right time for us to make a change.",
        "We're currently happy with our existing solution.",
        "I'd need to see more details before considering this.",
    ],
    "medium": [
        "The pricing seems high compared to what we're paying now.",
        "How does this compare to [competitor]? They offered us something similar.",
        "We've had bad experiences with vendor switches in the past.",
        "Our team would need significant training to adopt this.",
    ],
    "strong": [
        "I've already spoken with your competitor and their offer is more competitive.",
        "Our budget for this quarter is already committed elsewhere.",
        "I'd need to get buy-in from our entire leadership team, and they're skeptical.",
        "Honestly, I'm not convinced this would deliver enough ROI to justify the switch.",
    ],
}

# ── Stage-based objection probability ────────────────────────────────

TRIGGER_CONFIG = {
    # stage: (probability, severity)
    "opening":      (0.0,  "mild"),    # never during opening
    "discovery":    (0.25, "mild"),
    "presentation": (0.45, "medium"),
    "objection":    (0.60, "strong"),
    "closing":      (0.65, "strong"),
}

DIFFICULTY_MULTIPLIER = {
    "beginner":     0.6,   # fewer objections
    "intermediate": 1.0,
    "advanced":     1.4,   # more + harder objections
}


class ObjectionInjectionAgent(BaseAgent):
    """Plans when objections should be injected — no LLM."""

    @property
    def name(self) -> str:
        return "objection_injection"

    def __init__(self):
        # Track which objections were already used per session
        self._used_objections: Dict[int, set] = {}

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        return {}  # No LLM

    def run(self, ctx: AgentContext) -> AgentResult:
        session_id = ctx.session_id or 0

        # Never inject on first 3 messages (let rapport build)
        if ctx.total_message_count < 4:
            return self._make_result(data={
                "should_inject": False,
                "directive": None,
                "severity": None,
            })

        # Get current stage from AnalystAgent cache or guess
        stage = "discovery"
        if ctx.cached_stage_info:
            stage = ctx.cached_stage_info.get("current_stage", "discovery")

        # Determine probability and severity
        base_prob, base_severity = TRIGGER_CONFIG.get(stage, (0.3, "medium"))
        difficulty = ctx.difficulty
        multiplier = DIFFICULTY_MULTIPLIER.get(difficulty, 1.0)
        final_prob = min(base_prob * multiplier, 0.85)

        # ~50% chance of dismissive brush-off (matches real B2B distribution)
        if random.random() < 0.45 and base_severity in ("mild", "medium"):
            severity = "dismissive"
        else:
            severity = base_severity

        # Roll the dice
        if random.random() > final_prob:
            return self._make_result(data={
                "should_inject": False,
                "directive": None,
                "severity": None,
            })

        # Pick an objection
        persona = ctx.persona
        persona_objections = getattr(persona, "common_objections", None) or []

        used = self._used_objections.get(session_id, set())

        # Prefer persona-specific objections, then defaults
        candidates = [o for o in persona_objections if o not in used]
        if not candidates:
            candidates = [o for o in DEFAULT_OBJECTIONS.get(severity, DEFAULT_OBJECTIONS["medium"]) if o not in used]
        if not candidates:
            # All used — recycle
            candidates = persona_objections or DEFAULT_OBJECTIONS.get(severity, DEFAULT_OBJECTIONS["medium"])

        objection = random.choice(candidates) if candidates else None

        if not objection:
            return self._make_result(data={
                "should_inject": False,
                "directive": None,
                "severity": None,
            })

        # Mark as used
        used.add(objection)
        self._used_objections[session_id] = used

        # Build the directive for the PersonaAgent
        directive = (
            f"IMPORTANT: In your next response, naturally raise this concern/objection: "
            f'"{objection}" — weave it into your reply as a real customer would. '
            f"Don't just copy it verbatim; express the underlying concern naturally."
        )

        logger.info(
            f"🎯 ObjectionAgent: injecting {severity} objection "
            f"(stage={stage}, prob={final_prob:.0%})"
        )

        return self._make_result(data={
            "should_inject": True,
            "directive": directive,
            "severity": severity,
            "objection_text": objection,
        })

    def clear_session(self, session_id: int):
        """Clear used objections for a session."""
        self._used_objections.pop(session_id, None)
