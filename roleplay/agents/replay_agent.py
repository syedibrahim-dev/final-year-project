"""
Session Replay & Annotation Agent — post-session annotated transcript.

Runs once when the session ends alongside the PerformanceAgent.
Produces an annotated transcript highlighting turning points,
missed buying signals, strong moments, and alternative responses.

LLM calls: 1  (post-session only, batched with PerformanceAgent)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult
from roleplay.llm_client import OllamaClient
from config.settings import settings

logger = logging.getLogger(__name__)


class ReplayAgent(BaseAgent):
    """Post-session: generates annotated transcript with alternative suggestions."""

    @property
    def name(self) -> str:
        return "replay"

    def __init__(self):
        self._client = OllamaClient(
            model=getattr(settings, "EVAL_LLM_MODEL", settings.ROLEPLAY_LLM_MODEL),
            num_gpu=getattr(settings, "EVAL_NUM_GPU", 99),
        )

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        transcript = self._format_transcript(ctx.messages, max_turns=30)
        persona_name = getattr(ctx.persona, "name", "the customer")

        system_prompt = f"""You are a sales training replay analyst. Review the conversation
between a trainee (salesperson) and {persona_name} (customer).

Identify the most important moments and annotate them.

Respond with ONLY valid JSON:
{{
  "annotations": [
    {{
      "message_index": <1-based index of the message>,
      "speaker": "trainee" or "customer",
      "type": "<turning_point | missed_signal | strong_moment | weak_moment>",
      "comment": "<1-sentence explanation of why this moment matters>"
    }}
  ],
  "key_moments": [
    "<1-sentence description of the top 3 most impactful moments>"
  ],
  "alternative_responses": [
    {{
      "message_index": <index of a weak trainee message>,
      "original": "<what they said>",
      "suggested": "<what they could have said instead>",
      "reasoning": "<why the alternative is better>"
    }}
  ]
}}

CRITICAL OUTPUT RULES:
- Your response must be ONLY a JSON object. No text before or after the JSON.
- Do NOT write any explanation, commentary, or markdown — ONLY the JSON object.
- Start your response with {{ and end with }}
- Provide 4-8 annotations covering different types
- Provide exactly 3 key moments
- Provide 2 alternative responses for the weakest trainee messages
- Be specific and actionable, not generic"""

        user_message = f"""CONVERSATION TRANSCRIPT:
{transcript}

Total messages: {ctx.total_message_count}
Difficulty: {ctx.difficulty}

Provide your replay annotations:"""

        return {"system": system_prompt, "user": user_message}

    def run(self, ctx: AgentContext) -> AgentResult:
        # Only run if there are enough messages
        if ctx.total_message_count < 6:
            return self._make_result(data={
                "annotations": [],
                "key_moments": ["Conversation too short for detailed replay."],
                "alternative_responses": [],
            })

        prompts = self.build_prompt(ctx)

        def _call_llm():
            return self._client.generate_response(
                system_prompt=prompts["system"],
                user_message=prompts["user"],
                max_tokens=2500,
            )

        try:
            raw, latency = self._timed_run(_call_llm)
            try:
                data = self._parse_response(raw)
            except ValueError:
                logger.warning("ReplayAgent: first attempt returned non-JSON, retrying...")
                def _retry():
                    return self._client.generate_response(
                        system_prompt=prompts["system"],
                        user_message=(
                            prompts["user"] +
                            "\n\nYou MUST respond with ONLY a JSON object. "
                            "Start with { and end with }. No other text."
                        ),
                        max_tokens=2500,
                    )
                raw2, latency2 = self._timed_run(_retry)
                latency += latency2
                data = self._parse_response(raw2)

            logger.info(
                f"ReplayAgent: {len(data.get('annotations', []))} annotations, "
                f"{len(data.get('alternative_responses', []))} alternatives ({latency:.0f}ms)"
            )
            return self._make_result(data=data, latency_ms=latency)

        except Exception as e:
            logger.error(f"ReplayAgent failed: {e}")
            return self._make_result(
                data=self._fallback(),
                success=False,
                error=str(e),
            )

    @staticmethod
    def _repair_json(text: str) -> str:
        """Remove trailing commas before } or ] which LLMs commonly produce."""
        return re.sub(r',\s*([\}\]])', r'\1', text)

    @staticmethod
    def _recover_truncated_json(text: str) -> str:
        """
        Salvage truncated JSON by rewinding to the last complete item
        and closing all open structures.
        """
        depth: list = []
        in_string = False
        last_safe = 0
        i = 0
        while i < len(text):
            ch = text[i]
            if in_string:
                if ch == '\\':
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch in ('{', '['):
                    depth.append(ch)
                elif ch in ('}', ']'):
                    if depth:
                        depth.pop()
                    if len(depth) <= 2:
                        last_safe = i + 1
            i += 1

        if not depth:
            return text  # already balanced
        if last_safe == 0:
            return text  # can't recover

        truncated = text[:last_safe].rstrip().rstrip(',')
        for opener in reversed(depth):
            truncated += ']' if opener == '[' else '}'
        return truncated

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        text = raw.strip()
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

        recovered = self._recover_truncated_json(text)
        for attempt in (text, self._repair_json(text), recovered, self._repair_json(recovered)):
            try:
                data = json.loads(attempt)
                break
            except json.JSONDecodeError:
                continue
        else:
            raise ValueError(f"Could not parse Replay JSON: {text[:200]}")

        data.setdefault("annotations", [])
        data.setdefault("key_moments", [])
        data.setdefault("alternative_responses", [])
        return data

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "annotations": [],
            "key_moments": ["Replay analysis could not be completed."],
            "alternative_responses": [],
        }
