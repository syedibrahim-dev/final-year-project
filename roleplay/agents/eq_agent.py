"""
EQ (Emotional Intelligence) Agent — Transformer-powered analysis.

Uses two parallel transformer engines:
  Engine A (DeBERTa NLI):    intent + semantic analysis
  Engine B (Emotion-RoBERTa): emotion + tone classification

Combines their outputs into a unified EQ score with granular breakdown.

LLM calls: 0  (transformer classifiers only — ~20-40ms total on CPU)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)


class EQAgent(BaseAgent):
    """
    Tracks emotional intelligence using transformer classifiers.
    
    Replaces the previous VADER + keyword approach with:
      - DeBERTa NLI for objection handling & active listening
      - Emotion-RoBERTa for empathy detection & pressure level
    """

    @property
    def name(self) -> str:
        return "eq"

    def __init__(self):
        self._engines_loaded = False

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        # Not used — this agent doesn't call an LLM
        return {}

    # ── Helper: get last AI message from conversation ────────────────

    @staticmethod
    def _get_last_ai_message(messages: list) -> str:
        """Extract the most recent AI/customer message from history."""
        for m in reversed(messages):
            sender = m.sender if hasattr(m, "sender") else (
                m.get("sender", "") if isinstance(m, dict) else ""
            )
            text = m.message_text if hasattr(m, "message_text") else (
                m.get("text", "") if isinstance(m, dict) else ""
            )
            if sender in ("ai", "ai_customer"):
                return text
        return ""

    # ── Core analysis ────────────────────────────────────────────────

    def run(self, ctx: AgentContext) -> AgentResult:
        import time
        t0 = time.perf_counter()

        trainee_text = ctx.trainee_message.strip()
        prospect_text = self._get_last_ai_message(ctx.messages)

        # Default fallback data
        intent_data = {
            "is_objection": False,
            "objection_confidence": 0.0,
            "objection_handling": None,
            "handling_confidence": None,
            "active_listening_score": 0.0,
        }
        emotion_data = {
            "empathy": {
                "prospect_emotion": "neutral",
                "empathy_score": 0.5,
                "rep_showed_empathy": False,
            },
            "pressure": {
                "pressure_level": "consultative",
                "pressure_score": 0.0,
            },
        }

        # ── Engine A: Intent & Semantics (DeBERTa NLI) ──
        try:
            from roleplay.engines.intent_engine import run_intent_analysis
            if prospect_text:
                intent_data = run_intent_analysis(
                    prospect_message=prospect_text,
                    rep_message=trainee_text,
                )
        except Exception as e:
            logger.warning(f"Engine A (Intent) failed: {e}")

        # ── Engine B: Emotion & Tone (Emotion-RoBERTa) ──
        try:
            from roleplay.engines.emotion_engine import run_emotion_analysis
            if prospect_text:
                emotion_data = run_emotion_analysis(
                    prospect_message=prospect_text,
                    rep_message=trainee_text,
                )
        except Exception as e:
            logger.warning(f"Engine B (Emotion) failed: {e}")

        # ── Extract key metrics as local variables (used in score + WLEIS) ──
        empathy_score = emotion_data.get("empathy", {}).get("empathy_score", 0.5)
        listening = intent_data.get("active_listening_score", 0.0)
        pressure = emotion_data.get("pressure", {}).get("pressure_score", 0.0)

        # ── Aggregate into EQ Score ──
        eq_score = self._compute_eq_score(intent_data, emotion_data, trainee_text)

        # Rolling trend from previous EQ scores
        prev_scores = list(ctx.eq_scores) if ctx.eq_scores else []
        prev_scores.append(eq_score)
        trend = self._compute_trend(prev_scores)

        latency = (time.perf_counter() - t0) * 1000

        # ── Build result ──
        data = {
            # Aggregated scores
            "eq_score": round(eq_score, 1),
            "eq_trend": trend,
            "rolling_scores": prev_scores[-10:],

            # Engine A outputs
            "is_objection": intent_data.get("is_objection", False),
            "objection_confidence": intent_data.get("objection_confidence", 0.0),
            "objection_handling": intent_data.get("objection_handling"),
            "handling_confidence": intent_data.get("handling_confidence"),
            "active_listening_score": intent_data.get("active_listening_score", 0.0),

            # Engine B outputs
            "prospect_emotion": emotion_data.get("empathy", {}).get("prospect_emotion", "neutral"),
            "rep_dominant_emotion": emotion_data.get("empathy", {}).get("rep_dominant_emotion", "neutral"),
            "empathy_score": emotion_data.get("empathy", {}).get("empathy_score", 0.5),
            "prospect_needs_empathy": emotion_data.get("empathy", {}).get("prospect_needs_empathy", False),
            "rep_showed_empathy": emotion_data.get("empathy", {}).get("rep_showed_empathy", False),
            "pressure_level": emotion_data.get("pressure", {}).get("pressure_level", "consultative"),
            "pressure_score": emotion_data.get("pressure", {}).get("pressure_score", 0.0),

            # Metadata
            "engine": "transformer",
            "latency_ms": round(latency, 1),
        }

        # WLEIS dimension mapping (validated EQ framework)
        laer_result = self._assess_laer(intent_data, trainee_text)
        data["laer_assessment"] = laer_result
        data["wleis_dimensions"] = {
            "others_emotion_appraisal": round(empathy_score * 100),  # OEA — reading prospect emotions
            "regulation_of_emotion": round((1.0 - pressure) * 100),  # ROE — managing own pressure/tone
            "use_of_emotion": round(listening * 100),  # UOE — channeling into active listening
            "self_emotion_appraisal": round(eq_score, 1),  # SEA — overall self-awareness proxy
        }

        logger.info(
            f"💚 EQAgent: score={eq_score:.0f} "
            f"empathy={data['empathy_score']:.2f} "
            f"pressure={data['pressure_level']} "
            f"objection={'YES→'+str(data['objection_handling']) if data['is_objection'] else 'no'} "
            f"listening={data['active_listening_score']:.2f} "
            f"trend={trend} ({latency:.0f}ms)"
        )
        return self._make_result(data=data, latency_ms=latency)

    # ── LAER Objection Handling Assessment ───────────────────────────

    @staticmethod
    def _assess_laer(intent_data: Dict, trainee_text: str) -> Dict[str, Any]:
        """Assess objection handling against LAER framework (Listen, Acknowledge, Explore, Respond)."""
        if not intent_data.get("is_objection"):
            return {"applicable": False, "score": 0.6, "steps_detected": []}

        steps = []
        score = 0.0
        text_lower = trainee_text.lower()

        # Listen — did they show they heard the concern? (active listening score as proxy)
        # Threshold 0.40: even partial paraphrasing ("I understand your concern")
        # demonstrates listening — full semantic echo (>0.6) is rare in natural speech.
        listening = intent_data.get("active_listening_score", 0.0)
        if listening >= 0.40:
            steps.append("listen")
            score += 0.25

        # Acknowledge — did they validate the concern?
        ack_patterns = [
            r'\b(i understand|i hear you|that makes sense|valid|fair point|good point|'
            r'appreciate|i get that|you.re right|that.s a real concern|absolutely)\b'
        ]
        if any(re.search(p, text_lower) for p in ack_patterns):
            steps.append("acknowledge")
            score += 0.25

        # Explore — did they ask a follow-up question about the concern?
        if '?' in trainee_text and listening >= 0.3:
            steps.append("explore")
            score += 0.25

        # Respond — did they provide a tailored solution? (resolved = good response)
        handling = intent_data.get("objection_handling", "deflected")
        if handling == "resolved":
            steps.append("respond")
            score += 0.25
        elif handling == "deflected":
            score += 0.10

        return {
            "applicable": True,
            "score": score,
            "steps_detected": steps,
            "steps_missed": [s for s in ["listen", "acknowledge", "explore", "respond"] if s not in steps],
        }

    # ── EQ Score Aggregation ─────────────────────────────────────────

    @staticmethod
    def _compute_eq_score(intent_data: Dict, emotion_data: Dict, trainee_text: str) -> float:
        """
        Combine Engine A + B outputs into a single EQ score (0-100).

        Weighted components:
          - Empathy response:     30 points
          - Active listening:     25 points
          - Pressure (inverse):   25 points
          - Objection handling:   20 points  (LAER framework)
        """
        score = 0.0

        # 1. Empathy (30 pts)
        empathy_score = emotion_data.get("empathy", {}).get("empathy_score", 0.5)
        score += empathy_score * 30

        # 2. Active listening (25 pts)
        listening = intent_data.get("active_listening_score", 0.0)
        score += listening * 25

        # 3. Pressure level (25 pts — lower pressure = higher score)
        pressure = emotion_data.get("pressure", {}).get("pressure_score", 0.0)
        score += (1.0 - pressure) * 25

        # 4. Objection handling (20 pts) — LAER framework
        laer = EQAgent._assess_laer(intent_data, trainee_text)
        if laer["applicable"]:
            score += laer["score"] * 20
        else:
            score += 0.6 * 20  # neutral credit when no objection

        return max(0.0, min(100.0, score))

    # ── Trend calculation ────────────────────────────────────────────

    @staticmethod
    def _compute_trend(scores: List[float]) -> str:
        if len(scores) < 3:
            return "stable"
        recent = scores[-3:]
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(scores[:-3]) / max(len(scores[:-3]), 1) if len(scores) > 3 else avg_recent
        diff = avg_recent - avg_older
        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        return "stable"
