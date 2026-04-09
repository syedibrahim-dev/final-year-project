"""
Analyst Agent — combined Stage Tracker + Live Coach.

Detects the current sales stage via LLM (replacing the naive message-count
heuristic) and generates a real-time coaching hint, all in a single LLM call
to minimise latency on local Ollama.

Mitigation strategies:
  • skip-every-N  — only invokes LLM every N messages (configurable per
    difficulty); between runs returns the cached result.
  • NLP pre-filter — uses the existing SalesFlowAnalyzer heuristic to
    cheaply guess whether the stage has changed.  If it hasn't, the LLM
    call is skipped and only the coaching hint is refreshed.
  • lightweight model — defaults to a smaller model (configurable) since
    the output is structured JSON, not conversational prose.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult
from roleplay.llm_client import OllamaClient
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Stage definitions (shared vocabulary) ───────────────────────────

SALES_STAGES = [
    {"key": "opening",      "label": "Opening / Greeting"},
    {"key": "discovery",     "label": "Discovery / Needs Assessment"},
    {"key": "presentation",  "label": "Value Presentation"},
    {"key": "objection",     "label": "Objection Handling"},
    {"key": "closing",       "label": "Closing / Next Steps"},
]

STAGE_KEYS = [s["key"] for s in SALES_STAGES]

# ── Skip-every-N configuration ──────────────────────────────────────

SKIP_INTERVALS = {
    "beginner":     1,   # run every message (max coaching)
    "intermediate": 2,   # run every 2nd message
    "advanced":     3,   # run every 3rd message
}


class AnalystAgent(BaseAgent):
    """
    Detects the current sales conversation stage and provides a coaching hint
    for the trainee — all in one LLM call.  Uses skip-every-N to reduce the
    number of LLM calls on harder difficulties.
    """

    @property
    def name(self) -> str:
        return "analyst"

    def __init__(self):
        # Use a lighter model for the analyst (structured JSON output)
        model = getattr(settings, "ANALYST_LLM_MODEL", settings.LOCAL_LLM_MODEL)
        self._client = OllamaClient(model=model)

    # ── Should we invoke the LLM this turn? ──────────────────────────

    def should_run(self, ctx: AgentContext) -> bool:
        """
        Determine whether the Analyst Agent should make an LLM call this turn.
        Returns False when cached data is still valid (skip-every-N).

        Note: total_message_count includes both trainee and AI messages, but this
        method is called *after* the trainee message is added and *before* the AI
        message is added. Trainee turns therefore always produce odd counts
        (1, 3, 5, …). We convert to an exchange number (1-based) so the modulo
        check works correctly regardless of which message type was just added.
        """
        if not getattr(settings, "ENABLE_ANALYST_AGENT", True):
            return False

        interval = getattr(
            settings, "ANALYST_SKIP_INTERVAL",
            SKIP_INTERVALS.get(ctx.difficulty, 2),
        )
        # exchange_count: how many trainee-turn exchanges have happened so far
        exchange_count = ctx.total_message_count // 2 + 1

        # Always run on the first two exchanges
        if exchange_count <= 2:
            return True

        return exchange_count % interval == 0

    # ── Prompt construction ──────────────────────────────────────────

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        stage_list = "\n".join(
            f"  {i+1}. {s['key']} — {s['label']}" for i, s in enumerate(SALES_STAGES)
        )

        transcript = self._format_transcript(ctx.messages, max_turns=16)
        latest = ctx.trainee_message

        system_prompt = f"""You are a sales training analyst. Your job is to:
1. Identify which STAGE of the sales conversation is happening right now.
2. Provide a short, actionable COACHING HINT for the trainee (the salesperson).

The sales stages are (in order):
{stage_list}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "current_stage": "<one of: {', '.join(STAGE_KEYS)}>",
  "stage_confidence": <0.0-1.0>,
  "progress_pct": <0-100, how far through the overall sales flow>,
  "next_stage": "<the stage that should logically come next>",
  "coaching_hint": "<1-2 sentence actionable tip for the salesperson>",
  "missed_opportunities": ["<optional list of things the trainee missed>"]
}}"""

        user_message = f"""Conversation so far:
{transcript}

Latest trainee message: "{latest}"

Persona difficulty: {ctx.difficulty}

Analyze the stage and provide a coaching hint:"""

        return {"system": system_prompt, "user": user_message}

    # ── NLP fallback for stage detection ─────────────────────────────

    def _nlp_stage_guess(self, ctx: AgentContext) -> str:
        """
        Fast, rule-based stage guess using the existing SalesFlowAnalyzer
        heuristic.  Used as a fallback when the LLM call is skipped.
        """
        try:
            from roleplay.prompts import detect_conversation_phase
            return detect_conversation_phase(ctx.messages, ctx.difficulty)
        except Exception:
            # Absolute fallback: estimate from message count
            n = ctx.total_message_count
            if n <= 3:
                return "opening"
            elif n <= 8:
                return "discovery"
            elif n <= 14:
                return "presentation"
            elif n <= 20:
                return "objection"
            return "closing"

    # ── Execution ────────────────────────────────────────────────────

    def run(self, ctx: AgentContext) -> AgentResult:
        """
        If should_run() is True  → invoke LLM for stage + coaching hint.
        If should_run() is False → return cached data (with NLP stage update).
        """
        if not self.should_run(ctx):
            # Return FULL cached data unchanged to prevent stage flickering.
            # Only fall back to NLP if there is no cache at all (first message).
            cached = ctx.cached_stage_info or {}
            if cached:
                logger.info(
                    f"⏭️  AnalystAgent skipped LLM (msg #{ctx.total_message_count}), "
                    f"using cached stage={cached.get('current_stage')}"
                )
                return self._make_result(data={**cached, "from_cache": True})
            
            # No cache yet — use NLP fallback
            stage = self._nlp_stage_guess(ctx)
            logger.info(
                f"⏭️  AnalystAgent skipped LLM (msg #{ctx.total_message_count}), "
                f"NLP fallback stage={stage}"
            )
            return self._make_result(data={
                "current_stage":  stage,
                "stage_confidence": 0.5,
                "progress_pct":   self._stage_to_pct(stage),
                "next_stage":     self._next_stage(stage),
                "coaching_hint":  "",
                "missed_opportunities": [],
                "from_cache": True,
            })

        # Full LLM call
        prompts = self.build_prompt(ctx)

        def _call_llm():
            return self._client.generate_response(
                system_prompt=prompts["system"],
                user_message=prompts["user"],
                max_tokens=200,
            )

        try:
            raw, latency = self._timed_run(_call_llm)
            data = self._parse_response(raw)
            data["from_cache"] = False
            logger.info(
                f"📊 AnalystAgent: stage={data.get('current_stage')} "
                f"hint={data.get('coaching_hint', '')[:60]}… ({latency:.0f}ms)"
            )
            return self._make_result(data=data, latency_ms=latency)

        except Exception as e:
            logger.error(f"AnalystAgent LLM failed: {e}")
            stage = self._nlp_stage_guess(ctx)
            return self._make_result(
                data={
                    "current_stage": stage,
                    "stage_confidence": 0.4,
                    "progress_pct": self._stage_to_pct(stage),
                    "next_stage": self._next_stage(stage),
                    "coaching_hint": "",
                    "missed_opportunities": [],
                    "from_cache": False,
                },
                success=False,
                error=str(e),
            )

    # ── Response parsing ─────────────────────────────────────────────

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """Parse the LLM's JSON response, tolerating markdown fences."""
        text = raw.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from surrounding text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                raise ValueError(f"Could not parse Analyst JSON: {text[:200]}")

        # Validate & normalise
        stage = data.get("current_stage", "discovery")
        if stage not in STAGE_KEYS:
            stage = "discovery"
        data["current_stage"] = stage
        data.setdefault("stage_confidence", 0.7)
        data.setdefault("progress_pct", self._stage_to_pct(stage))
        data.setdefault("next_stage", self._next_stage(stage))
        data.setdefault("coaching_hint", "")
        data.setdefault("missed_opportunities", [])
        return data

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _stage_to_pct(stage: str) -> int:
        mapping = {
            "opening": 10, "discovery": 30, "presentation": 55,
            "objection": 75, "closing": 90,
        }
        return mapping.get(stage, 50)

    @staticmethod
    def _next_stage(stage: str) -> str:
        order = STAGE_KEYS
        try:
            idx = order.index(stage)
            return order[min(idx + 1, len(order) - 1)]
        except ValueError:
            return "discovery"
