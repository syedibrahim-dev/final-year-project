"""
Agentic Post-Session Evaluator
===============================

Replaces the single-prompt PerformanceAgent with a tool-use loop.  The
LLM is given 8 analysis tools (transcript search, SPIN/LAER scoring,
EQ trajectory, framework citations, etc.) and gathers evidence before
producing structured feedback.

Key differences vs PerformanceAgent:
  • Can quote specific turns it found rather than what fit in its prompt
  • Can cite research frameworks by name (grounded feedback)
  • Can compare moments instead of giving generic praise
  • Loop is bounded (max 8 iterations, ~30-90s) so it won't run away

Output shape matches PerformanceAgent exactly, so the orchestrator and
frontend treat both the same. This lets us A/B-test without changing
any downstream code.

Feature-flagged OFF by default (ENABLE_AGENTIC_EVALUATOR) — on failure
the orchestrator falls back to PerformanceAgent. No behavioural change
unless explicitly enabled.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult
from roleplay.evaluator_tools import (
    ToolContext,
    TOOL_REGISTRY,
    TOOL_SCHEMAS,
    invoke_tool,
)
from roleplay.llm_client import OllamaClient
from config.settings import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

# Max tool-use iterations before we force the LLM to answer.
# 8 is enough for ~3 investigations + a final write-up.
MAX_ITERATIONS = 8

# Max generation tokens per LLM call in the loop.
ITER_MAX_TOKENS = 1500

# Max tokens for the final structured-output call.
FINAL_MAX_TOKENS = 3000


class AgenticEvaluator(BaseAgent):
    """
    Tool-using post-session evaluator.  Produces the same output shape
    as PerformanceAgent (summary / strengths / improvements / stage_performance
    / llm_category_scores / category_feedback / practice_recommendations).
    """

    @property
    def name(self) -> str:
        return "agentic_evaluator"

    def __init__(self):
        self._client = OllamaClient(
            model=getattr(settings, "EVAL_LLM_MODEL", settings.ROLEPLAY_LLM_MODEL),
            num_gpu=getattr(settings, "EVAL_NUM_GPU", 99),
        )

    # ── Prompt construction ──────────────────────────────────────────

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        """System prompt that teaches the LLM how + when to use tools."""
        persona = ctx.persona
        persona_name = getattr(persona, "name", "the customer")
        difficulty = getattr(persona, "difficulty", ctx.difficulty)
        objections = getattr(persona, "common_objections", []) or []
        num_turns = len(ctx.messages)

        system = f"""You are an expert sales-training evaluator analysing a completed roleplay session.

ROLE: You have access to 8 analysis tools. Use them to gather SPECIFIC evidence
from the transcript before producing feedback. Don't make up quotes or moments —
use the tools to find them.

SESSION METADATA:
- Customer persona: {persona_name}
- Difficulty: {difficulty}
- Customer's known objections: {', '.join(objections[:4]) if objections else 'general'}
- Total turns in conversation: {num_turns}

INVESTIGATION WORKFLOW (follow this order):
1. Call `get_eq_trajectory` to see how the trainee performed emotionally over time
2. Call `analyze_spin_questions` to check question quality (discovery)
3. Call `analyze_objection_moments` to see how objections were handled (LAER)
4. Call `find_extremum_moments` to find the best + worst moments
5. Call `compute_talk_ratio` to detect monologues
6. (Optional) Call `search_transcript` or `get_turn` to grab specific quotes
7. (Optional) Call `cite_framework` to reference research in your feedback

AFTER INVESTIGATION: produce the final evaluation as a JSON object (see
the OUTPUT SCHEMA below). Every strength / improvement / category_feedback
entry MUST reference a specific turn from the transcript — no generic praise.

OUTPUT SCHEMA (exact keys required):
{{
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<strength with specific moment reference>", ...],
  "improvements": ["<improvement with specific moment + suggested rephrase>", ...],
  "coaching_tip": "<single most impactful piece of advice>",
  "stage_performance": {{
    "opening": "<what happened vs what should have>",
    "discovery": "...",
    "presentation": "...",
    "objection": "...",
    "closing": "..."
  }},
  "missed_opportunities": ["<specific moment they could have acted differently>", ...],
  "llm_category_scores": {{
    "rapport_building": <0-20 integer>,
    "needs_discovery": <0-20 integer>,
    "product_presentation": <0-20 integer>,
    "objection_handling": <0-20 integer>,
    "closing": <0-20 integer>
  }},
  "category_feedback": {{
    "rapport_building": "<Feed-up: goal. Feed-back: what happened. Feed-forward: next time do X>",
    "needs_discovery": "...",
    "product_presentation": "...",
    "objection_handling": "...",
    "closing": "..."
  }},
  "practice_recommendations": {{
    "weakest_area": "<category name>",
    "recommended_focus": "<specific skill>",
    "suggested_persona_type": "<persona style to drill>"
  }}
}}

RULES:
- Investigate first, write last. Don't output the JSON until you've called at least 3 tools.
- Quote actual transcript text — use search_transcript or get_turn to get it.
- Feedback grounded in Hattie & Timperley: Feed-up / Feed-back / Feed-forward.
- Final output MUST be a single valid JSON object — no markdown fences, no prose around it."""

        user = (
            "Begin your investigation now. Start with get_eq_trajectory, "
            "then analyze_spin_questions, then analyze_objection_moments. "
            "After you've gathered evidence, produce the final JSON evaluation."
        )
        return {"system": system, "user": user}

    # ── Tool-loop core ───────────────────────────────────────────────

    def _run_tool_loop(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_ctx: ToolContext,
    ) -> Dict[str, Any]:
        """
        Drive the tool-use loop. Returns:
          {
            "final_text": str (last assistant message),
            "iterations_used": int,
            "tool_call_trace": [ {name, args, result_preview}, ... ],
          }
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        trace: List[Dict[str, Any]] = []
        iterations_used = 0

        for iteration in range(MAX_ITERATIONS):
            iterations_used = iteration + 1
            try:
                assistant_msg = self._client.chat_with_tools(
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    max_tokens=ITER_MAX_TOKENS,
                )
            except Exception as e:
                logger.error(f"AgenticEvaluator: LLM call failed at iteration {iteration}: {e}")
                raise

            content = assistant_msg.get("content", "")
            tool_calls = assistant_msg.get("tool_calls") or []

            # If no tool calls, we're done
            if not tool_calls:
                return {
                    "final_text": content or "",
                    "iterations_used": iterations_used,
                    "tool_call_trace": trace,
                }

            # Otherwise, execute each tool call and append results
            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                fn_info = call.get("function", {}) or {}
                tool_name = fn_info.get("name", "")
                raw_args = fn_info.get("arguments", {})

                # Ollama sometimes returns arguments as a JSON string, sometimes a dict
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}

                logger.info(f"AgenticEvaluator → tool[{tool_name}]({args})")
                result = invoke_tool(tool_ctx, tool_name, args)

                # Trim result preview for trace logging
                preview = str(result)[:200]
                trace.append({"name": tool_name, "args": args, "result_preview": preview})

                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, default=str)[:4000],  # cap size
                })

        # Exceeded iteration cap — force a final answer
        logger.warning(
            f"AgenticEvaluator: hit max iterations ({MAX_ITERATIONS}), forcing final answer"
        )
        messages.append({
            "role": "user",
            "content": (
                "You've done enough investigation. Now output the final JSON "
                "evaluation object per the schema in your system prompt. "
                "No more tool calls — produce the JSON now."
            ),
        })

        try:
            final_msg = self._client.chat_with_tools(
                messages=messages,
                tools=[],   # no tools on the final call — force text output
                max_tokens=FINAL_MAX_TOKENS,
            )
            return {
                "final_text": final_msg.get("content", ""),
                "iterations_used": iterations_used + 1,
                "tool_call_trace": trace,
            }
        except Exception as e:
            logger.error(f"AgenticEvaluator: forced-final call failed: {e}")
            raise

    # ── JSON parsing (same robustness as PerformanceAgent) ───────────

    _TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """Extract and parse the JSON object from the LLM's final text."""
        if not raw or not raw.strip():
            raise ValueError("Empty LLM response")

        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

        # Find the outermost JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"No JSON object in response: {cleaned[:200]}")
        candidate = cleaned[start : end + 1]

        # Repair trailing commas
        repaired = self._TRAILING_COMMA_RE.sub(r"\1", candidate)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed: {e}. Raw start: {candidate[:200]}")

    # ── Normaliser: ensure the output has every key PerformanceAgent produces ─

    def _normalise(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guarantee that every key downstream code expects is present,
        with empty defaults if the LLM omitted them.
        """
        data.setdefault("summary", "")
        data.setdefault("strengths", [])
        data.setdefault("improvements", [])
        data.setdefault("coaching_tip", "")
        data.setdefault("missed_opportunities", [])

        stage_default = {
            "opening": "", "discovery": "", "presentation": "",
            "objection": "", "closing": "",
        }
        stage_performance = data.get("stage_performance") or {}
        for k, v in stage_default.items():
            stage_performance.setdefault(k, v)
        data["stage_performance"] = stage_performance

        score_default = {
            "rapport_building": 10, "needs_discovery": 10,
            "product_presentation": 10, "objection_handling": 10, "closing": 10,
        }
        scores = data.get("llm_category_scores") or {}
        for k, v in score_default.items():
            try:
                scores[k] = int(scores.get(k, v))
            except (TypeError, ValueError):
                scores[k] = v
            # Clamp 0-20
            scores[k] = max(0, min(20, scores[k]))
        data["llm_category_scores"] = scores

        fb_default = {
            "rapport_building": "", "needs_discovery": "",
            "product_presentation": "", "objection_handling": "", "closing": "",
        }
        fb = data.get("category_feedback") or {}
        for k, v in fb_default.items():
            fb.setdefault(k, v)
        data["category_feedback"] = fb

        pr = data.get("practice_recommendations") or {}
        pr.setdefault("weakest_area", "")
        pr.setdefault("recommended_focus", "")
        pr.setdefault("suggested_persona_type", "")
        data["practice_recommendations"] = pr

        return data

    # ── Entry point ──────────────────────────────────────────────────

    def run(self, ctx: AgentContext) -> AgentResult:
        """Run the full agentic evaluation. Matches BaseAgent contract."""
        t0 = time.perf_counter()

        # Build tool context from AgentContext
        tool_ctx = ToolContext(
            messages=ctx.messages,
            eq_scores=list(ctx.eq_scores or []),
            persona_name=getattr(ctx.persona, "name", "the customer"),
            persona_difficulty=getattr(ctx.persona, "difficulty", ctx.difficulty),
            persona_objections=list(getattr(ctx.persona, "common_objections", []) or []),
            document_context=ctx.document_context or "",
        )

        prompts = self.build_prompt(ctx)

        try:
            loop_result = self._run_tool_loop(
                system_prompt=prompts["system"],
                user_prompt=prompts["user"],
                tool_ctx=tool_ctx,
            )
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            logger.error(f"AgenticEvaluator: tool loop crashed: {e}")
            return self._make_result(
                data={}, latency_ms=latency, success=False, error=str(e),
            )

        final_text = loop_result["final_text"]
        iterations = loop_result["iterations_used"]
        trace = loop_result["tool_call_trace"]

        try:
            parsed = self._parse_response(final_text)
        except ValueError as e:
            latency = (time.perf_counter() - t0) * 1000
            logger.warning(
                f"AgenticEvaluator: JSON parse failed after {iterations} iter — "
                f"tools called: {[t['name'] for t in trace]}"
            )
            return self._make_result(
                data={"raw": final_text[:500]},
                latency_ms=latency,
                success=False,
                error=f"parse: {e}",
            )

        normalised = self._normalise(parsed)
        # Attach meta for transparency (consumed by the /evaluate response optionally)
        normalised["_agentic_meta"] = {
            "iterations_used": iterations,
            "tools_called": [t["name"] for t in trace],
            "tool_call_count": len(trace),
        }

        latency = (time.perf_counter() - t0) * 1000
        logger.info(
            f"AgenticEvaluator: done in {latency:.0f}ms, "
            f"{iterations} iter, {len(trace)} tool calls"
        )
        return self._make_result(data=normalised, latency_ms=latency, success=True)
