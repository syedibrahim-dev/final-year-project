"""
Agentic Fact-Checker — deep post-session claim auditor.

Adds a "truth integrity" layer on top of the existing per-turn
KnowledgeAccuracyAgent. The hot path keeps running unchanged; this agent
runs ONLY in post-session evaluation when the feature flag is on.

Key differences vs the hot-path KnowledgeAgent:
  • Multi-hop reasoning — can check one claim depends on another
  • Scope mismatch detection — catches "total X" vs "partial X" subtleties
  • Structured per-claim verdicts with evidence + reasoning
  • Produces a fact_check_report added to the evaluation JSON

Safety properties:
  • Feature-flagged OFF by default (ENABLE_AGENTIC_FACT_CHECK)
  • Additive only — existing per-turn accuracy_data is unchanged
  • On any failure: no fact_check_report in the response, eval otherwise fine
  • Max 8 iterations, ~30-60s latency
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult
from roleplay.fact_check_tools import (
    FactCheckToolContext,
    FACT_CHECK_TOOL_REGISTRY,
    FACT_CHECK_TOOL_SCHEMAS,
    invoke_fact_check_tool,
)
from roleplay.llm_client import OllamaClient
from config.settings import settings

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8
ITER_MAX_TOKENS = 1500
FINAL_MAX_TOKENS = 2500


class AgenticFactChecker(BaseAgent):
    """
    Tool-using post-session fact-checker. Output is a structured
    `fact_check_report` dict that the orchestrator appends to the
    evaluation response.
    """

    @property
    def name(self) -> str:
        return "agentic_fact_checker"

    def __init__(self):
        self._client = OllamaClient(
            model=getattr(settings, "EVAL_LLM_MODEL", settings.ROLEPLAY_LLM_MODEL),
            num_gpu=getattr(settings, "EVAL_NUM_GPU", 99),
        )

    # ── Build tool context with RAG injection ────────────────────────

    def _build_tool_ctx(self, ctx: AgentContext) -> FactCheckToolContext:
        """
        Build the fact-check tool context. Injects the RAG retrieval
        function lazily to avoid hard coupling at import time.
        """
        retrieve_fn = None
        try:
            from services.rag_service import retrieve_relevant_chunks
            retrieve_fn = retrieve_relevant_chunks
        except Exception as e:
            logger.warning(f"AgenticFactChecker: RAG service unavailable: {e}")

        return FactCheckToolContext(
            messages=ctx.messages,
            org_id=ctx.org_id,
            retrieve_fn=retrieve_fn,
        )

    # ── Prompt ───────────────────────────────────────────────────────

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        persona = ctx.persona
        persona_name = getattr(persona, "name", "the customer")

        has_docs = bool(ctx.document_context) or ctx.org_id is not None

        system = f"""You are a rigorous fact-checker auditing a completed sales roleplay.

YOUR JOB: Find every claim the trainee (salesperson) made and verify it against
the uploaded company documents. Output a structured report.

YOU HAVE 5 TOOLS:
1. extract_trainee_claims — get the list of claim-like sentences from the transcript
2. retrieve_evidence — RAG search the company docs for passages about a claim
3. analyze_claim_structure — break a claim into numbers + scope words
4. compare_numbers — numeric match with tolerance; flags exaggerations
5. check_scope_alignment — catches subtle mismatches like "total X" in claim vs "partial X" in docs

WORKFLOW:
1. Call extract_trainee_claims first to get ALL claims at once
2. For each claim (limit to top 5-8 most impactful):
   a. Call analyze_claim_structure(claim_text) to understand its structure
   b. Call retrieve_evidence(query=<claim summary>) to fetch RAG passages
   c. If the claim has numbers: call compare_numbers(claim_numbers, evidence_text)
   d. Always: call check_scope_alignment(claim_text, evidence_text)
   e. Reason about the combined evidence → decide verdict
3. Produce the final fact_check_report JSON

CONTEXT:
- Persona: {persona_name}
- Documents available: {"yes" if has_docs else "no (RAG will return no chunks)"}

VERDICT OPTIONS (use exactly these values):
- "verified"      — claim matches evidence
- "exaggerated"   — claim overstates what evidence supports (higher number, broader scope)
- "understated"   — claim is weaker than what evidence supports (rare)
- "unverified"    — no relevant evidence found in docs (can't tell)
- "contradicted"  — evidence directly contradicts the claim

OUTPUT SCHEMA (exact keys required):
{{
  "claims_analyzed": <int>,
  "verified": <int>,
  "exaggerated": <int>,
  "understated": <int>,
  "unverified": <int>,
  "contradicted": <int>,
  "details": [
    {{
      "claim_id": <int>,
      "turn_index": <int>,
      "claim": "<quoted trainee text>",
      "verdict": "<one of the 5 options above>",
      "evidence": "<quoted evidence passage or 'no relevant evidence'>",
      "reasoning": "<why this verdict, in 1-2 sentences>",
      "confidence": <0.0 to 1.0>
    }}
  ],
  "summary": "<2-3 sentence overall assessment of trainee's factual accuracy>"
}}

RULES:
- Investigate with tools first. Don't write the JSON until you've gathered evidence.
- Quote actual passages in the "evidence" field — no paraphrasing.
- If no docs were uploaded, most claims will be "unverified" — that's expected and honest.
- Final output MUST be a single valid JSON object — no markdown fences, no prose around it."""

        user = (
            "Begin by calling extract_trainee_claims. Then investigate each claim "
            "using the other tools. When done, produce the final JSON report."
        )
        return {"system": system, "user": user}

    # ── Tool-loop core ───────────────────────────────────────────────

    def _run_tool_loop(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_ctx: FactCheckToolContext,
    ) -> Dict[str, Any]:
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
                    tools=FACT_CHECK_TOOL_SCHEMAS,
                    max_tokens=ITER_MAX_TOKENS,
                )
            except Exception as e:
                logger.error(f"AgenticFactChecker: LLM call failed at iter {iteration}: {e}")
                raise

            content = assistant_msg.get("content", "")
            tool_calls = assistant_msg.get("tool_calls") or []

            if not tool_calls:
                return {
                    "final_text": content or "",
                    "iterations_used": iterations_used,
                    "tool_call_trace": trace,
                }

            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                fn_info = call.get("function", {}) or {}
                tool_name = fn_info.get("name", "")
                raw_args = fn_info.get("arguments", {})

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}

                logger.info(f"AgenticFactChecker → tool[{tool_name}]")
                result = invoke_fact_check_tool(tool_ctx, tool_name, args)

                preview = str(result)[:200]
                trace.append({"name": tool_name, "args": args, "result_preview": preview})

                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, default=str)[:4000],
                })

        # Iteration cap hit — force the final JSON
        logger.warning(
            f"AgenticFactChecker: hit max iterations ({MAX_ITERATIONS}), forcing final answer"
        )
        messages.append({
            "role": "user",
            "content": (
                "You've done enough investigation. Output the final fact_check_report "
                "JSON now per the schema — no more tool calls."
            ),
        })
        try:
            final_msg = self._client.chat_with_tools(
                messages=messages,
                tools=[],
                max_tokens=FINAL_MAX_TOKENS,
            )
            return {
                "final_text": final_msg.get("content", ""),
                "iterations_used": iterations_used + 1,
                "tool_call_trace": trace,
            }
        except Exception as e:
            logger.error(f"AgenticFactChecker: forced-final call failed: {e}")
            raise

    # ── JSON parsing (same robustness as other agentic files) ────────

    _TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        if not raw or not raw.strip():
            raise ValueError("Empty LLM response")

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"No JSON object in response: {cleaned[:200]}")
        candidate = cleaned[start : end + 1]
        repaired = self._TRAILING_COMMA_RE.sub(r"\1", candidate)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed: {e}. Raw start: {candidate[:200]}")

    def _normalise(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Guarantee schema completeness with safe defaults."""
        data.setdefault("claims_analyzed", 0)
        data.setdefault("verified", 0)
        data.setdefault("exaggerated", 0)
        data.setdefault("understated", 0)
        data.setdefault("unverified", 0)
        data.setdefault("contradicted", 0)
        data.setdefault("details", [])
        data.setdefault("summary", "")

        # Coerce counts to int
        for key in ("claims_analyzed", "verified", "exaggerated", "understated", "unverified", "contradicted"):
            try:
                data[key] = int(data[key] or 0)
            except (TypeError, ValueError):
                data[key] = 0

        # Validate detail entries
        valid_verdicts = {"verified", "exaggerated", "understated", "unverified", "contradicted"}
        cleaned_details = []
        for d in data.get("details", []):
            if not isinstance(d, dict):
                continue
            verdict = d.get("verdict", "unverified")
            if verdict not in valid_verdicts:
                verdict = "unverified"
            try:
                confidence = float(d.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                confidence = 0.5

            cleaned_details.append({
                "claim_id": int(d.get("claim_id", 0)),
                "turn_index": int(d.get("turn_index", 0)),
                "claim": str(d.get("claim", ""))[:500],
                "verdict": verdict,
                "evidence": str(d.get("evidence", ""))[:500],
                "reasoning": str(d.get("reasoning", ""))[:500],
                "confidence": round(confidence, 2),
            })
        data["details"] = cleaned_details

        return data

    # ── Entry point ──────────────────────────────────────────────────

    def run(self, ctx: AgentContext) -> AgentResult:
        t0 = time.perf_counter()

        tool_ctx = self._build_tool_ctx(ctx)

        # Fast short-circuit: if there's no RAG available and no doc context,
        # the fact-checker can't do much meaningful — return an empty report.
        if tool_ctx.retrieve_fn is None and not ctx.document_context:
            latency = (time.perf_counter() - t0) * 1000
            return self._make_result(
                data={
                    "claims_analyzed": 0,
                    "verified": 0, "exaggerated": 0, "understated": 0,
                    "unverified": 0, "contradicted": 0,
                    "details": [],
                    "summary": "No documents available to fact-check claims against.",
                    "_agentic_meta": {"short_circuited": True, "reason": "no_docs"},
                },
                latency_ms=latency,
                success=True,
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
            logger.error(f"AgenticFactChecker: tool loop crashed: {e}")
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
                f"AgenticFactChecker: JSON parse failed after {iterations} iter"
            )
            return self._make_result(
                data={"raw": final_text[:500]},
                latency_ms=latency,
                success=False,
                error=f"parse: {e}",
            )

        normalised = self._normalise(parsed)
        normalised["_agentic_meta"] = {
            "iterations_used": iterations,
            "tools_called": [t["name"] for t in trace],
            "tool_call_count": len(trace),
        }

        latency = (time.perf_counter() - t0) * 1000
        logger.info(
            f"AgenticFactChecker: done in {latency:.0f}ms, "
            f"{iterations} iter, {len(trace)} tool calls, "
            f"{normalised.get('claims_analyzed', 0)} claims"
        )
        return self._make_result(data=normalised, latency_ms=latency, success=True)
