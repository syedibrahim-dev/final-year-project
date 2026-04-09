"""
Performance Analytics Agent — enhanced post-session evaluator.

Runs once when a session ends.  Generates richer qualitative feedback than
the previous ConversationEvaluator by analysing per-stage performance,
missed opportunities, sentiment trajectory, and actionable improvement plans.

The NLP scoring (Tier 1 + Tier 2) still runs separately and is combined
with this agent's output by the orchestrator.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult
from roleplay.llm_client import OllamaClient
from config.settings import settings

logger = logging.getLogger(__name__)


class PerformanceAgent(BaseAgent):
    """Deep post-session evaluation via LLM."""

    @property
    def name(self) -> str:
        return "performance"

    def __init__(self):
        self._client = OllamaClient(
            model=getattr(settings, "EVAL_LLM_MODEL", settings.ROLEPLAY_LLM_MODEL),
            num_gpu=getattr(settings, "EVAL_NUM_GPU", 99),
        )

    # ── Prompt construction ──────────────────────────────────────────

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        transcript = self._format_transcript(ctx.messages, max_turns=30)
        persona = ctx.persona

        persona_name = getattr(persona, "name", "the customer")
        difficulty = getattr(persona, "difficulty", ctx.difficulty)
        objections = getattr(persona, "common_objections", []) or []

        # Retrieve document context summary for product accuracy checking
        doc_section = ""
        if ctx.document_context:
            doc_section = f"""
PRODUCT REFERENCE MATERIAL (use to fact-check the trainee's claims):
{ctx.document_context[:2000]}
"""

        system_prompt = f"""You are an expert sales training evaluator. Analyze the following
sales conversation between a trainee (salesperson) and {persona_name} (AI customer).

Difficulty level: {difficulty}
Customer's known objections: {', '.join(objections[:4]) if objections else 'general'}
{doc_section}

EVALUATION FRAMEWORK (based on Hattie & Timperley's feedback model):
For each category, provide:
- Feed-up: What was the goal for this stage?
- Feed-back: What specifically happened? Quote the exact exchange.
- Feed-forward: What should they do differently next time?

Evaluate the trainee's performance and respond with ONLY valid JSON:
{{
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<strength 1 — reference a specific moment>", "<strength 2>", "<strength 3>"],
  "improvements": ["<improvement 1 — reference a specific moment>", "<improvement 2>", "<improvement 3>"],
  "coaching_tip": "<single most impactful piece of advice for their next session>",
  "stage_performance": {{
    "opening": "<1-2 sentences: what happened vs what should have happened>",
    "discovery": "<1-2 sentences: what happened vs what should have happened>",
    "presentation": "<1-2 sentences: what happened vs what should have happened>",
    "objection": "<1-2 sentences: what happened vs what should have happened>",
    "closing": "<1-2 sentences: what happened vs what should have happened>"
  }},
  "missed_opportunities": ["<specific moment they could have acted differently — quote the exchange>"],
  "llm_category_scores": {{
    "rapport_building": <0-20>,
    "needs_discovery": <0-20>,
    "product_presentation": <0-20>,
    "objection_handling": <0-20>,
    "closing": <0-20>
  }},
  "category_feedback": {{
    "rapport_building": "<Feed-up: goal. Feed-back: what happened. Feed-forward: next time do X>",
    "needs_discovery": "<Feed-up: goal. Feed-back: what happened. Feed-forward: next time do X>",
    "product_presentation": "<Feed-up: goal. Feed-back: what happened. Feed-forward: next time do X>",
    "objection_handling": "<Feed-up: goal. Feed-back: what happened. Feed-forward: next time do X>",
    "closing": "<Feed-up: goal. Feed-back: what happened. Feed-forward: next time do X>"
  }},
  "practice_recommendations": {{
    "weakest_area": "<category name where they scored lowest>",
    "recommended_focus": "<specific skill to drill in next session>",
    "suggested_persona_type": "<type of persona that would target this weakness>"
  }}
}}

CRITICAL OUTPUT RULES:
- Your response must be ONLY a JSON object. No text before or after the JSON.
- Do NOT write any explanation, commentary, or markdown — ONLY the JSON object.
- Start your response with {{ and end with }}
- Every piece of feedback MUST reference a specific moment from the transcript
- Do NOT give generic feedback like "good rapport building" — say WHAT they did and WHEN
- For improvements, always suggest what they SHOULD have said instead
- The coaching_tip should be the single highest-impact change for their next session"""

        user_message = f"""CONVERSATION TRANSCRIPT:
{transcript}

Provide your detailed evaluation:"""

        return {"system": system_prompt, "user": user_message}

    # ── Execution ────────────────────────────────────────────────────

    def run(self, ctx: AgentContext) -> AgentResult:
        prompts = self.build_prompt(ctx)
        num_messages = len(ctx.messages)
        max_tokens = max(1500, min(3000, num_messages * 40))

        def _call_llm():
            return self._client.generate_response(
                system_prompt=prompts["system"],
                user_message=prompts["user"],
                max_tokens=max_tokens,
            )

        try:
            raw, latency = self._timed_run(_call_llm)
            try:
                data = self._parse_response(raw)
            except ValueError:
                # LLM returned prose instead of JSON — retry with strict nudge
                logger.warning("PerformanceAgent: first attempt returned non-JSON, retrying...")
                def _retry():
                    return self._client.generate_response(
                        system_prompt=prompts["system"],
                        user_message=(
                            prompts["user"] +
                            "\n\nYou MUST respond with ONLY a JSON object. "
                            "Start with { and end with }. No other text."
                        ),
                        max_tokens=max_tokens,
                    )
                raw2, latency2 = self._timed_run(_retry)
                latency += latency2
                data = self._parse_response(raw2)

            logger.info(f"PerformanceAgent evaluated in {latency:.0f}ms")
            return self._make_result(data=data, latency_ms=latency)

        except Exception as e:
            logger.error(f"PerformanceAgent failed: {e}")
            return self._make_result(
                data=self._fallback(),
                success=False,
                error=str(e),
            )

    # ── Response parsing ─────────────────────────────────────────────

    @staticmethod
    def _repair_json(text: str) -> str:
        """Remove trailing commas before } or ] which LLMs commonly produce."""
        return re.sub(r',\s*([\}\]])', r'\1', text)

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        text = raw.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        # Extract JSON object boundaries first
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        for attempt in (text, self._repair_json(text)):
            try:
                data = json.loads(attempt)
                break
            except json.JSONDecodeError:
                continue
        else:
            raise ValueError(f"Could not parse Performance JSON: {text[:200]}")

        # Ensure required keys
        data.setdefault("summary", "Evaluation completed.")
        data.setdefault("strengths", ["Good effort"])
        data.setdefault("improvements", ["Continue practising"])
        data.setdefault("coaching_tip", "")
        data.setdefault("stage_performance", {})
        data.setdefault("missed_opportunities", [])
        data.setdefault("llm_category_scores", {})
        data.setdefault("category_feedback", {})
        data.setdefault("practice_recommendations", {
            "weakest_area": "needs_discovery",
            "recommended_focus": "asking open-ended questions",
            "suggested_persona_type": "a persona who volunteers minimal information",
        })
        return data

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "summary": "Evaluation could not be completed by the LLM.",
            "strengths": ["Participated in the conversation"],
            "improvements": ["Try to engage more deeply with the customer"],
            "coaching_tip": "Focus on asking open-ended discovery questions.",
            "stage_performance": {},
            "missed_opportunities": [],
            "llm_category_scores": {},
            "category_feedback": {},
            "practice_recommendations": {
                "weakest_area": "general",
                "recommended_focus": "engage more deeply with the customer",
                "suggested_persona_type": "any beginner-level persona",
            },
        }
