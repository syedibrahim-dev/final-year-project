"""
Agent Orchestrator — coordinates multi-agent execution for roleplay.

Responsibilities:
  1. Build a shared AgentContext for each turn.
  2. Execute agents in priority order.
  3. Manage per-session caching.
  4. Provide a clean interface for the service layer.

Agent execution order (per message):
  Pre-Persona (no LLM — transformer classifiers):
    1. Guardrail Agent    → input validation
    2. EQ Agent           → Engine A (DeBERTa NLI) + Engine B (Emotion-RoBERTa)
    3. Knowledge Agent    → fact-check trainee claims
    4. Objection Agent    → may set objection directive
    5. Adaptive Agent     → may set difficulty modifier

  Core (LLM):
    6. Persona Agent      → generates customer reply (reads directives)
    7. Analyst Agent      → LLM stage tracking + coaching hints (skip-every-N)

  Post-Persona (async via subprocess — Ollama swaps GPU models):
    8. SalesRLAgent       → real-time conversion probability (deepmost PPO)

Post-session:
    9. Performance Agent  → deep evaluation (1 LLM)
   10. Replay Agent       → annotated transcript (1 LLM)
   11. SalesRLAgent       → full conversion trajectory (deepmost subprocess)

LLM call budget per message:
  • Always:     1 Ollama call  (Persona)
  • Periodic:   1 Ollama call  (Analyst — skip-every-N based on difficulty)
  • Optional:   1 Ollama swap  (SalesRL Qwen3-4B, async — never blocks)
  • Post-session: 2 Ollama calls (Performance + Replay)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from roleplay.agents.base import AgentContext, AgentResult
from roleplay.agents.persona_agent import PersonaAgent
from roleplay.agents.analyst_agent import AnalystAgent
from roleplay.agents.performance_agent import PerformanceAgent
from roleplay.agents.eq_agent import EQAgent
from roleplay.agents.knowledge_agent import KnowledgeAccuracyAgent
from roleplay.agents.objection_agent import ObjectionInjectionAgent
from roleplay.agents.adaptive_agent import AdaptiveDifficultyAgent
from roleplay.agents.replay_agent import ReplayAgent
from roleplay.agents.guardrail_agent import GuardrailAgent
from roleplay.prompts import retrieve_document_context
from services.conversion_service import get_conversion_service
from training.lstm_inference import encode_turn, predict_conversation_risk
from config.settings import settings

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Singleton-style orchestrator that holds agent instances and
    per-session caches.
    """

    def __init__(self):
        # Core agents
        self.persona_agent = PersonaAgent()
        self.analyst_agent = AnalystAgent()
        self.performance_agent = PerformanceAgent()

        # Lazy: only instantiated when ENABLE_AGENTIC_EVALUATOR flag is on.
        # Keeps import-time side effects to zero for the default code path.
        self._agentic_evaluator = None

        # Lazy: only instantiated when ENABLE_AGENTIC_FACT_CHECK flag is on.
        self._agentic_fact_checker = None

        # Guardrail (input validation — runs first)
        self.guardrail_agent = GuardrailAgent()

        # New agents
        self.eq_agent = EQAgent()
        self.knowledge_agent = KnowledgeAccuracyAgent()
        self.objection_agent = ObjectionInjectionAgent()
        self.adaptive_agent = AdaptiveDifficultyAgent()
        self.replay_agent = ReplayAgent()

        # SalesRLAgent conversion predictor (persistent subprocess, Ollama-routed)
        self.conversion_service = get_conversion_service()

        # Per-session caches
        self._analyst_cache: Dict[int, Dict[str, Any]] = {}
        self._eq_scores: Dict[int, List[float]] = {}
        self._lstm_features: Dict[int, List[List[float]]] = {}  # LSTM turn sequences

    # ── Main entry point: process a single message ───────────────────

    def process_message(
        self,
        persona: Any,
        messages: list,
        trainee_message: str,
        session_id: int,
        org_id: Optional[int] = None,
        total_message_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Run the multi-agent pipeline for one trainee message.

        Returns:
            {
                "response":        str,           # AI customer reply
                "stage_info":      dict | None,   # stage + progress data
                "coaching_hint":   str | None,    # actionable tip
                "eq_data":         dict | None,   # EQ scores
                "accuracy_data":   dict | None,   # fact-check results
            }
        """
        difficulty = getattr(persona, "difficulty", "intermediate")

        # ── Step 1: RAG retrieval (conversation-aware, no LLM) ──
        document_context = ""
        if org_id:
            document_context = retrieve_document_context(
                query=trainee_message, org_id=org_id, k=4,
                conversation_history=messages,
            )

        # ── Build shared context ──
        cached = self._analyst_cache.get(session_id)
        eq_history = self._eq_scores.get(session_id, [])

        ctx = AgentContext(
            persona=persona,
            messages=messages,
            trainee_message=trainee_message,
            org_id=org_id,
            document_context=document_context,
            session_id=session_id,
            total_message_count=total_message_count,
            difficulty=difficulty,
            cached_stage_info=cached,
            eq_scores=eq_history,
        )

        # ── Step 1: Guardrail Agent (no LLM) ──
        guardrail_info: Dict[str, Any] = {"action": "allow", "reason": None}
        try:
            guardrail_result = self.guardrail_agent.run(ctx)
            action = guardrail_result.data.get("action", "allow")
            guardrail_info = {
                "action": action,
                "reason": guardrail_result.data.get("reason"),
            }

            if action == "block":
                logger.info(
                    f"GuardrailAgent blocked message: "
                    f"{guardrail_result.data.get('reason')}"
                )
                return {
                    "response": guardrail_result.data.get(
                        "canned_response",
                        "Sorry, I didn't quite catch that. Could you say that again?"
                    ),
                    "stage_info": None,
                    "coaching_hint": None,
                    "eq_data": None,
                    "accuracy_data": None,
                    "conversion_data": None,
                    "guardrail": guardrail_result.data,
                    "agent_diagnostics": {
                        "guardrail_action": "block",
                        "guardrail_reason": guardrail_result.data.get("reason"),
                        "objection_injected": False,
                        "objection_directive": None,
                        "adaptive_directive": None,
                        "guardrail_redirect": None,
                    },
                }

            if action == "redirect":
                ctx.guardrail_redirect = guardrail_result.data.get(
                    "redirect_hint", ""
                )
        except Exception as e:
            logger.warning(f"GuardrailAgent failed (non-fatal): {e}")

        # ── Step 2: EQ Agent (no LLM) ──
        eq_data = None
        try:
            eq_result = self.eq_agent.run(ctx)
            ctx.previous_results["eq"] = eq_result
            eq_data = eq_result.data

            # Update rolling scores
            if eq_result.success and "eq_score" in eq_result.data:
                eq_history.append(eq_result.data["eq_score"])
                self._eq_scores[session_id] = eq_history[-10:]
        except Exception as e:
            logger.warning(f"EQAgent failed (non-fatal): {e}")

        # ── Step 3: Knowledge Accuracy Agent (no LLM) ──
        accuracy_data = None
        try:
            accuracy_result = self.knowledge_agent.run(ctx)
            ctx.previous_results["knowledge_accuracy"] = accuracy_result
            accuracy_data = accuracy_result.data
        except Exception as e:
            logger.warning(f"KnowledgeAgent failed (non-fatal): {e}")

        # ── Step 4: Objection Injection Agent (no LLM) ──
        try:
            objection_result = self.objection_agent.run(ctx)
            if objection_result.data.get("should_inject"):
                ctx.objection_directive = objection_result.data["directive"]
        except Exception as e:
            logger.warning(f"ObjectionAgent failed (non-fatal): {e}")

        # ── Step 5: Adaptive Difficulty Agent (no LLM) ──
        try:
            adaptive_result = self.adaptive_agent.run(ctx)
            ctx.previous_results["adaptive_difficulty"] = adaptive_result
            directive = adaptive_result.data.get("directive", "")
            if directive:
                ctx.difficulty_modifier = directive
        except Exception as e:
            logger.warning(f"AdaptiveAgent failed (non-fatal): {e}")

        # ── Step 6: Persona Agent (LLM #1 — always runs) ──
        persona_result = self.persona_agent.run(ctx)
        if not persona_result.success:
            raise Exception(
                f"PersonaAgent failed: {persona_result.error}"
            )

        # ── Step 7: Stage Tracking via Analyst Agent (LLM reasoning) ──
        # Uses LLM to reason about conversation stage with skip-every-N
        # optimization (skip interval depends on difficulty level).
        # Falls back to NLP heuristic if LLM call is skipped or fails.
        stage_info = None
        coaching_hint = None

        if getattr(settings, "ENABLE_ANALYST_AGENT", True):
            try:
                analyst_result = self.analyst_agent.run(ctx)
                if analyst_result.success:
                    stage_info = analyst_result.data
                    coaching_hint = analyst_result.data.get("coaching_hint", None)
                    # Cache for next turn
                    self._analyst_cache[session_id] = analyst_result.data
                else:
                    # LLM failed — use NLP fallback
                    stage = self.analyst_agent._nlp_stage_guess(ctx)
                    stage_info = {
                        "current_stage": stage,
                        "stage_confidence": 0.4,
                        "progress_pct": self.analyst_agent._stage_to_pct(stage),
                        "next_stage": self.analyst_agent._next_stage(stage),
                        "from_cache": False,
                    }
            except Exception as e:
                logger.warning(f"AnalystAgent failed (non-fatal): {e}")
                stage = self.analyst_agent._nlp_stage_guess(ctx)
                stage_info = {
                    "current_stage": stage,
                    "stage_confidence": 0.4,
                    "progress_pct": self.analyst_agent._stage_to_pct(stage),
                    "next_stage": self.analyst_agent._next_stage(stage),
                    "from_cache": False,
                }

        # ── Step 8: SalesRLAgent Conversion Prediction (async) ──
        # Fires prediction in background thread — never blocks the response.
        # Returns the most recent available result (may be from previous turn).
        conversion_data = None
        if getattr(settings, "ENABLE_SALESRL_AGENT", False):
            interval = getattr(settings, "SALESRL_PREDICT_INTERVAL", 2)
            exchange_count = total_message_count // 2 + 1

            # Fire async prediction every N exchanges
            if exchange_count >= 2 and exchange_count % interval == 0:
                try:
                    conv_messages = []
                    for m in messages:
                        sender = m.sender if hasattr(m, "sender") else (
                            m.get("sender", "") if isinstance(m, dict) else ""
                        )
                        text = m.message_text if hasattr(m, "message_text") else (
                            m.get("text", "") if isinstance(m, dict) else ""
                        )
                        if sender and text:
                            conv_messages.append({"sender": sender, "text": text})
                    conv_messages.append({"sender": "trainee", "text": trainee_message})

                    self.conversion_service.predict_async(
                        session_id=session_id,
                        messages=conv_messages,
                    )
                except Exception as e:
                    logger.warning(f"SalesRLAgent fire failed (non-fatal): {e}")

            # Always return the latest available result (non-blocking)
            conversion_data = self.conversion_service.get_latest(session_id)

        # ── Step 9: Trained Model Predictions (no LLM — DistilBERT, <50ms each) ──
        trained_models_data = {}
        try:
            from training.inference import predict_outcome, predict_sales_state, predict_willingness

            # Build conversation text for models
            recent = messages[-6:] if len(messages) > 6 else messages
            conv_text = " ".join([
                f"{(m.sender if hasattr(m, 'sender') else m.get('sender', ''))}: "
                f"{(m.message_text if hasattr(m, 'message_text') else m.get('text', ''))}"
                for m in recent
            ])
            conv_text += f" trainee: {trainee_message}"

            # Conversation window (last 3 turns) for state/willingness
            window = messages[-3:] if len(messages) > 3 else messages
            window_text = " ".join([
                f"{(m.sender if hasattr(m, 'sender') else m.get('sender', ''))}: "
                f"{(m.message_text if hasattr(m, 'message_text') else m.get('text', ''))}"
                for m in window
            ])

            # Outcome Predictor — conversion probability
            # Dampen early predictions toward 0.5 (not enough data to predict confidently)
            outcome = predict_outcome(conv_text[:512])
            if total_message_count <= 2:
                # Very early — blend heavily toward neutral
                outcome["probability"] = round(0.5 * 0.7 + outcome["probability"] * 0.3, 4)
                outcome["label"] = "converted" if outcome["probability"] >= 0.5 else "failed"
            elif total_message_count <= 4:
                # Early — moderate dampening
                outcome["probability"] = round(0.5 * 0.4 + outcome["probability"] * 0.6, 4)
                outcome["label"] = "converted" if outcome["probability"] >= 0.5 else "failed"
            trained_models_data["outcome_prediction"] = outcome

            # Sales State Model — buyer state
            # Apply position-aware override: early turns can't be decision/drop_off
            state = predict_sales_state(window_text[:512])
            if total_message_count <= 4 and state["state"] in ("decision", "drop_off_risk"):
                # Too early for these states — fall back to second-best prediction
                alternatives = state.get("all_states", [])
                for alt_state, alt_conf in alternatives:
                    if alt_state not in ("decision", "drop_off_risk"):
                        state["state"] = alt_state
                        state["confidence"] = alt_conf
                        break
                else:
                    state["state"] = "interest"
                    state["confidence"] = 0.5
            trained_models_data["sales_state"] = state

            # Willingness Predictor — engagement level
            # Dampen early predictions toward neutral (too little signal to judge)
            willingness = predict_willingness(window_text[:512])
            if total_message_count <= 2:
                willingness["confidence"] = round(willingness["confidence"] * 0.3, 4)
                willingness["willingness"] = "neutral"
            elif total_message_count <= 4:
                willingness["confidence"] = round(willingness["confidence"] * 0.6, 4)
            trained_models_data["willingness"] = willingness

        except Exception as e:
            logger.debug(f"Trained model predictions failed (non-fatal): {e}")

        # ── Step 10: LSTM Conversation Risk Model (sequence prediction) ──
        # Uses per-turn classifier outputs as features, predicts deal failure risk.
        lstm_risk = None
        try:
            # Extract classifier labels for this turn
            state_label = trained_models_data.get("sales_state", {}).get("state", "interest")
            will_label = trained_models_data.get("willingness", {}).get("willingness", "neutral")

            # Get objection type from EQ agent's intent engine output
            obj_label = "not_objection"
            if eq_data and eq_data.get("is_objection"):
                obj_label = eq_data.get("objection_handling", "not_objection")
                # Map handling labels to objection type if needed
                if obj_label in ("resolved", "deflected", "escalated"):
                    obj_label = "not_objection"  # fall back — use classifier directly
            # Try the DistilBERT objection classifier for accurate type
            try:
                from training.inference import predict_objection
                obj_result = predict_objection(trainee_message[:512])
                obj_label = obj_result.get("label", "not_objection")
            except Exception:
                pass

            # Get emotion from EQ agent
            emotion_label = "neutral"
            if eq_data:
                emotion_label = eq_data.get("prospect_emotion", "neutral")

            # Normalized position (0-1, capped at 30 turns)
            position = min(total_message_count / 30.0, 1.0)

            # Object resolved? Check if handling quality indicates resolution
            obj_resolved = False
            if eq_data and eq_data.get("objection_handling") == "resolved":
                obj_resolved = True

            # Encode this turn's features
            turn_vec = encode_turn(
                state=state_label,
                willingness=will_label,
                objection=obj_label,
                emotion=emotion_label,
                position=position,
                obj_resolved=obj_resolved,
                is_customer=False,  # trainee is the sales rep
            )

            # Accumulate sequence for this session
            session_features = self._lstm_features.get(session_id, [])
            session_features.append(turn_vec)
            self._lstm_features[session_id] = session_features

            # Predict risk from full conversation sequence so far
            lstm_risk = predict_conversation_risk(session_features)

            # Dampen early-turn LSTM predictions (sequence too short to be reliable)
            if total_message_count <= 2:
                raw = lstm_risk["risk_score"]
                lstm_risk["risk_score"] = round(0.3 * 0.7 + raw * 0.3, 4)
                lstm_risk["trend"] = "stable"
            elif total_message_count <= 4:
                raw = lstm_risk["risk_score"]
                lstm_risk["risk_score"] = round(0.3 * 0.4 + raw * 0.6, 4)
            # Re-derive label from dampened score
            s = lstm_risk["risk_score"]
            lstm_risk["risk_label"] = "low" if s < 0.4 else ("medium" if s < 0.7 else "high")

            logger.debug(
                f"LSTM risk: score={lstm_risk['risk_score']}, "
                f"label={lstm_risk['risk_label']}, trend={lstm_risk['trend']}"
            )
        except Exception as e:
            logger.warning(f"LSTM risk prediction failed (non-fatal): {e}")

        # ── Build Deal Intelligence (complementary prediction signals) ──
        deal_intelligence = {}

        # Signal 1: Deal Confidence (DistilBERT — pattern-based)
        # Trained on 30K+ historical sales conversations.
        # Measures: "Does this conversation PATTERN match deals that closed?"
        # Strength: Catches red-flag patterns (e.g. repeated price pushback).
        # Limitation: Tends pessimistic when prospect is engaged but challenging.
        if trained_models_data.get("outcome_prediction"):
            op = trained_models_data["outcome_prediction"]
            deal_intelligence["deal_confidence"] = {
                "probability": op.get("probability", 0.5),
                "label": op.get("label", "unknown"),
                "source": "DistilBERT (30K conversations)",
                "measures": "Historical pattern matching — does this look like deals that closed?",
            }

        # Signal 2: Conversation Momentum (SalesRLAgent — dynamics-based)
        # Uses reinforcement learning on real-time conversation dynamics.
        # Measures: "Is the prospect moving TOWARD a decision?"
        # Strength: Tracks engagement trajectory, not just keywords.
        # Note: Engaged negotiation (price questions) = positive momentum.
        if conversion_data and not conversion_data.get("model_not_loaded"):
            deal_intelligence["conversation_momentum"] = {
                "probability": conversion_data.get("probability", 0.5),
                "trend": conversion_data.get("trend", "stable"),
                "source": "SalesRLAgent (reinforcement learning)",
                "measures": "Real-time engagement trajectory — is the prospect moving toward a decision?",
            }

        # Signal 3: Buyer Psychology (Sales State + Willingness models)
        if trained_models_data.get("sales_state"):
            deal_intelligence["buyer_state"] = trained_models_data["sales_state"]
        if trained_models_data.get("willingness"):
            deal_intelligence["buyer_willingness"] = trained_models_data["willingness"]

        # Signal 4: LSTM Conversation Risk (sequence-based trajectory prediction)
        if lstm_risk and lstm_risk.get("source") != "unavailable":
            deal_intelligence["conversation_risk"] = {
                "risk_score": lstm_risk["risk_score"],
                "risk_label": lstm_risk["risk_label"],
                "trend": lstm_risk["trend"],
                "source": "LSTM (2-layer, trained on 1K SaaS conversations)",
                "measures": "Sequence trajectory — is the conversation heading toward deal failure?",
            }

        # Expose hidden agent outputs for demo / debug consumers (non-functional)
        agent_diagnostics = {
            "guardrail_action": guardrail_info.get("action", "allow"),
            "guardrail_reason": guardrail_info.get("reason"),
            "objection_injected": bool(ctx.objection_directive),
            "objection_directive": ctx.objection_directive,
            "adaptive_directive": ctx.difficulty_modifier,
            "guardrail_redirect": ctx.guardrail_redirect,
        }

        return {
            "response": persona_result.data["response"],
            "stage_info": stage_info,
            "coaching_hint": coaching_hint,
            "eq_data": eq_data,
            "accuracy_data": accuracy_data,
            "lstm_risk": lstm_risk,                     # LSTM risk prediction
            "conversion_data": conversion_data,       # raw SalesRL (backward compat)
            "trained_models": trained_models_data,     # raw models (backward compat)
            "deal_intelligence": deal_intelligence,    # unified, labelled view
            "agent_diagnostics": agent_diagnostics,   # hidden agent outputs (for demo)
        }

    # ── Post-session evaluation ──────────────────────────────────────

    def process_evaluation(
        self,
        persona: Any,
        messages: list,
        org_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run the Performance Agent + Replay Agent for post-session evaluation.
        Called once when the session ends.
        """
        # Retrieve doc context for product accuracy checking (conversation-aware)
        document_context = ""
        if org_id:
            trainee_texts = []
            for m in messages:
                sender = m.sender if hasattr(m, "sender") else (m.get("sender", "") if isinstance(m, dict) else "")
                text = m.message_text if hasattr(m, "message_text") else (m.get("text", "") if isinstance(m, dict) else "")
                if sender == "trainee":
                    trainee_texts.append(text)
            query = " ".join(trainee_texts[-3:]) if trainee_texts else ""
            if query:
                document_context = retrieve_document_context(
                    query=query, org_id=org_id, k=4,
                    conversation_history=messages,
                )

        ctx = AgentContext(
            persona=persona,
            messages=messages,
            trainee_message="",
            org_id=org_id,
            document_context=document_context,
            session_id=session_id,
            total_message_count=len(messages),
            difficulty=getattr(persona, "difficulty", "intermediate"),
            eq_scores=self._eq_scores.get(session_id, []),
        )

        # ── Run evaluator ──
        # Agentic evaluator (tool-use loop) is preferred when the feature flag
        # is on. Falls back to the classic single-prompt PerformanceAgent on:
        #   • flag OFF
        #   • agentic evaluator raises (Ollama down, tool loop crash, parse fail)
        #   • agentic evaluator returns empty data (no-op safety)
        # Fallback is silent to the user — the /evaluate response shape is
        # identical either way. Logs tell us which path ran.
        data: Dict[str, Any] = {}
        evaluator_used = "performance"   # default label for logging

        if getattr(settings, "ENABLE_AGENTIC_EVALUATOR", False):
            try:
                # Lazy-import + lazy-instantiate so a misconfiguration here
                # never affects the hot path or module import.
                if self._agentic_evaluator is None:
                    from roleplay.agents.agentic_evaluator import AgenticEvaluator
                    self._agentic_evaluator = AgenticEvaluator()

                agentic_result = self._agentic_evaluator.run(ctx)
                if agentic_result.success and agentic_result.data:
                    data = agentic_result.data
                    evaluator_used = "agentic"
                    logger.info(
                        f"AgenticEvaluator succeeded in {agentic_result.latency_ms:.0f}ms"
                    )
                else:
                    logger.warning(
                        f"AgenticEvaluator returned empty/failed — falling back. "
                        f"Error: {agentic_result.error}"
                    )
            except Exception as _ae_err:
                logger.warning(
                    f"AgenticEvaluator raised — falling back to PerformanceAgent. "
                    f"Error: {_ae_err}"
                )

        if not data:
            # Fallback (or default) path — classic PerformanceAgent
            perf_result = self.performance_agent.run(ctx)
            data = perf_result.data
            evaluator_used = "performance"

        # Attach transparency marker so downstream logs / responses know which path ran
        data["_evaluator_used"] = evaluator_used

        # ── Optional deep fact-check (additive, never breaks eval) ──
        # Appends `fact_check_report` to the evaluation output. If the flag is
        # off or the agent fails for any reason, the key is simply absent —
        # frontend / DB storage keep working exactly as before.
        if getattr(settings, "ENABLE_AGENTIC_FACT_CHECK", False):
            try:
                if self._agentic_fact_checker is None:
                    from roleplay.agents.agentic_fact_checker import AgenticFactChecker
                    self._agentic_fact_checker = AgenticFactChecker()

                fc_result = self._agentic_fact_checker.run(ctx)
                if fc_result.success and fc_result.data:
                    data["fact_check_report"] = fc_result.data
                    logger.info(
                        f"AgenticFactChecker: {fc_result.data.get('claims_analyzed', 0)} "
                        f"claims analysed in {fc_result.latency_ms:.0f}ms"
                    )
                else:
                    logger.warning(
                        f"AgenticFactChecker returned empty/failed — skipping report. "
                        f"Error: {fc_result.error}"
                    )
            except Exception as _fc_err:
                logger.warning(
                    f"AgenticFactChecker raised — skipping report. Error: {_fc_err}"
                )

        # Inject session-level EQ summary into performance data
        eq_history = self._eq_scores.get(session_id, [])
        if eq_history:
            data["eq_summary"] = {
                "average_score": round(sum(eq_history) / len(eq_history), 1),
                "final_score": round(eq_history[-1], 1),
                "trend": "improving" if len(eq_history) > 2 and eq_history[-1] > eq_history[0] else (
                    "declining" if len(eq_history) > 2 and eq_history[-1] < eq_history[0] else "stable"
                ),
                "total_messages_scored": len(eq_history),
            }

        # Run Replay Agent
        try:
            replay_result = self.replay_agent.run(ctx)
            data["replay"] = replay_result.data
        except Exception as e:
            logger.error(f"ReplayAgent failed: {e}")
            data["replay"] = {
                "annotations": [],
                "key_moments": [],
                "alternative_responses": [],
            }

        # Run SalesRLAgent full post-session conversion analysis
        if getattr(settings, "ENABLE_SALESRL_AGENT", False):
            try:
                conv_messages = []
                for m in messages:
                    sender = m.sender if hasattr(m, "sender") else (
                        m.get("sender", "") if isinstance(m, dict) else ""
                    )
                    text = m.message_text if hasattr(m, "message_text") else (
                        m.get("text", "") if isinstance(m, dict) else ""
                    )
                    if sender and text:
                        conv_messages.append({"sender": sender, "text": text})

                conversion_analysis = self.conversion_service.analyze_full_session(
                    session_id=session_id or 0,
                    messages=conv_messages,
                )
                if conversion_analysis:
                    data["conversion_trajectory"] = conversion_analysis
                    logger.info(
                        f"SalesRL post-session: final_prob="
                        f"{conversion_analysis.get('final_probability', '?')}, "
                        f"{len(conversion_analysis.get('turn_predictions', []))} turns"
                    )
            except Exception as e:
                logger.warning(f"SalesRL post-session analysis failed (non-fatal): {e}")

        return data

    # ── Session cleanup ──────────────────────────────────────────────

    def clear_session_cache(self, session_id: int):
        """Remove all cached data when a session ends."""
        self._analyst_cache.pop(session_id, None)
        self._eq_scores.pop(session_id, None)
        self._lstm_features.pop(session_id, None)
        self.objection_agent.clear_session(session_id)
        self.conversion_service.clear_session(session_id)
        self.adaptive_agent.clear_session(session_id)


# ── Module-level singleton ───────────────────────────────────────────

_orchestrator_instance: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AgentOrchestrator()
        logger.info("🤖 Multi-agent orchestrator initialised (8 agents)")
    return _orchestrator_instance
