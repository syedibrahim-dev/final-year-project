"""
Adaptive Difficulty Agent — dynamic persona warmth adjustment.

Reads EQ Agent scores and Analyst stage data to decide whether the
persona should become warmer (if trainee is struggling) or cooler/more
resistant (if trainee is doing well).  Runs every 3-4 messages.

LLM calls: 0  (reads other agent results, produces a modifier string)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

# ── Temperature descriptions for PersonaAgent prompt injection ───────

TEMPERATURE_DIRECTIVES = {
    "warmer": (
        "TONE ADJUSTMENT: The customer is becoming slightly warmer and more receptive. "
        "They're willing to share more details about their needs. Show subtle openness."
    ),
    "neutral": "",  # no injection
    "cooler": (
        "TONE ADJUSTMENT: The customer is becoming more guarded and skeptical. "
        "They need more convincing evidence before they'll open up further."
    ),
    "ice_cold": (
        "TONE ADJUSTMENT: The customer is very skeptical and resistant. "
        "They're considering ending the conversation. Only specific, evidence-based "
        "responses will keep them engaged. Express impatience subtly."
    ),
}


class AdaptiveDifficultyAgent(BaseAgent):
    """Adjusts persona warmth based on trainee performance — no LLM."""

    @property
    def name(self) -> str:
        return "adaptive_difficulty"

    def __init__(self):
        self._last_run: Dict[int, int] = {}  # session_id -> last msg count

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        return {}  # No LLM

    def _should_run(self, ctx: AgentContext) -> bool:
        """Run every 3-4 messages to avoid constant shifts."""
        session_id = ctx.session_id or 0
        last = self._last_run.get(session_id, 0)
        return ctx.total_message_count - last >= 3

    def run(self, ctx: AgentContext) -> AgentResult:
        session_id = ctx.session_id or 0

        if not self._should_run(ctx):
            return self._make_result(data={
                "temperature": "neutral",
                "directive": "",
                "reason": "skipped (too soon)",
            })

        self._last_run[session_id] = ctx.total_message_count

        # Gather signals from other agents
        eq_result = ctx.previous_results.get("eq")
        analyst_cache = ctx.cached_stage_info or {}

        eq_score = 50.0  # default neutral
        eq_trend = "stable"
        if eq_result and eq_result.success:
            eq_score = eq_result.data.get("eq_score", 50.0)
            eq_trend = eq_result.data.get("eq_trend", "stable")

        stage = analyst_cache.get("current_stage", "discovery")
        stage_confidence = analyst_cache.get("stage_confidence", 0.5)

        # ── Decision logic ──

        temperature = "neutral"
        reason = ""

        # High EQ + progressing well → challenge them
        if eq_score >= 65 and eq_trend in ("improving", "stable"):
            if stage in ("presentation", "objection", "closing"):
                temperature = "cooler"
                reason = f"Trainee EQ high ({eq_score:.0f}), progressing well — increasing challenge"
            elif stage == "discovery":
                temperature = "neutral"
                reason = "Still in discovery, keeping neutral"

        # Very high EQ + advanced stage → ice cold challenge
        if eq_score >= 80 and stage in ("objection", "closing") and ctx.difficulty == "advanced":
            temperature = "ice_cold"
            reason = f"Expert trainee ({eq_score:.0f} EQ) in {stage} — maximum challenge"

        # Low EQ or declining → ease up
        if eq_score < 35 or eq_trend == "declining":
            temperature = "warmer"
            reason = f"Trainee struggling (EQ={eq_score:.0f}, trend={eq_trend}) — easing persona"

        # Very early in conversation — always neutral
        if ctx.total_message_count <= 4:
            temperature = "neutral"
            reason = "Early conversation — staying neutral"

        directive = TEMPERATURE_DIRECTIVES.get(temperature, "")

        logger.info(
            f"🌡️  AdaptiveAgent: temp={temperature} "
            f"(eq={eq_score:.0f}, trend={eq_trend}, stage={stage})"
        )

        return self._make_result(data={
            "temperature": temperature,
            "directive": directive,
            "reason": reason,
        })

    def clear_session(self, session_id: int):
        self._last_run.pop(session_id, None)
