"""
Guardrail Agent — validates trainee input before it reaches the Persona Agent.

Zero LLM calls. Uses regex and keyword matching to detect:
  - Empty / too-short / too-long messages
  - Prompt injection attempts
  - Inappropriate content
  - Off-topic nonsense
  - Character-breaking attempts (trying to make the AI reveal it's an AI)

Actions:
  "allow"    — normal flow, no changes
  "redirect" — PersonaAgent gets a hint to steer conversation back on topic
  "block"    — short-circuits the pipeline, returns a canned in-character response
"""
from __future__ import annotations

import re
import logging
from typing import Dict

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

# ── Detection patterns ────────────────────────────────────────────

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(your|previous|all|above)\s+(instructions|rules|prompt|system)",
    r"you\s+are\s+(now|actually)\s+(a|an)\b",
    r"(system\s*prompt\b(?!ed|s|ing)|new\s*instructions|override\s*instructions)",
    r"pretend\s+you\s+are",
    r"respond\s+as\s+(chatgpt|an?\s*ai|a?\s*helpful|gpt)",
    r"forget\s+(everything|your\s*character|your\s*role|all\s*previous)",
    r"disregard\s+(everything|all|your)",
    r"jailbreak",
    r"DAN\s*mode",
]

CHARACTER_BREAKING_PATTERNS = [
    r"what\s+(model|llm|ai|language\s*model)\s+(are\s+you|is\s+this)",
    r"are\s+you\s+(an?\s*ai|chatgpt|a?\s*bot|a?\s*language\s*model|claude|gemini|gpt)",
    r"(break|drop|stop)\s+(character|the\s*roleplay|acting|pretending)",
    r"what\s+are\s+your\s+(instructions|rules|system\s*prompt)",
    r"show\s+me\s+your\s+(prompt|instructions|system)",
    r"reveal\s+your\s+(true|real)\s+(identity|nature)",
]

INAPPROPRIATE_WORDS = [
    # Keep this small and targeted — just the most obvious cases
    r"\b(fuck|shit|asshole|bitch|dick|cunt|nigger|faggot)\b",
    r"\b(kill\s+you|murder|rape|suicide)\b",
]

# Sales-adjacent vocabulary for off-topic detection
SALES_VOCABULARY = {
    "product", "service", "price", "cost", "budget", "demo", "trial",
    "feature", "benefit", "solution", "offer", "competitor", "team",
    "meeting", "call", "schedule", "roi", "value", "platform", "tool",
    "integration", "security", "compliance", "certificate", "license",
    "subscription", "contract", "discount", "workflow", "process",
    "challenge", "problem", "need", "help", "support", "customer",
    "client", "company", "business", "organization", "department",
    "manager", "director", "decision", "implementation", "onboarding",
    "hello", "hi", "hey", "thanks", "thank", "appreciate", "sorry",
    "question", "concern", "interested", "looking", "currently",
    "yes", "no", "sure", "absolutely", "right", "okay",
}


class GuardrailAgent(BaseAgent):
    """Validates trainee input. No LLM — pure regex/keyword matching."""

    @property
    def name(self) -> str:
        return "guardrail"

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        return {}  # No LLM

    def _check_prompt_injection(self, text: str) -> bool:
        lower = text.lower()
        return any(re.search(p, lower) for p in PROMPT_INJECTION_PATTERNS)

    def _check_character_breaking(self, text: str) -> bool:
        lower = text.lower()
        return any(re.search(p, lower) for p in CHARACTER_BREAKING_PATTERNS)

    def _check_inappropriate(self, text: str) -> bool:
        lower = text.lower()
        return any(re.search(p, lower) for p in INAPPROPRIATE_WORDS)

    def _check_off_topic(self, text: str) -> bool:
        """Flag messages with no sales-related words (only for longer messages)."""
        words = set(re.findall(r"[a-z]+", text.lower()))
        if len(words) < 8:
            return False  # Too short to judge
        overlap = words & SALES_VOCABULARY
        return len(overlap) == 0

    def _check_nonsense(self, text: str) -> bool:
        """Detect keyboard mashing or repeated characters."""
        # More than 5 of the same character in a row
        if re.search(r"(.)\1{5,}", text):
            return True
        # Very high ratio of non-alpha characters
        alpha = sum(1 for c in text if c.isalpha())
        if len(text) > 10 and alpha / len(text) < 0.3:
            return True
        return False

    def run(self, ctx: AgentContext) -> AgentResult:
        text = ctx.trainee_message.strip()

        # Check 1: Empty or too short
        if len(text) < 2:
            return self._make_result(data={
                "action": "block",
                "reason": "empty_message",
                "canned_response": "Sorry, I didn't catch that. Could you say that again?",
            })

        # Check 2: Too long (paste-bomb)
        if len(text) > 3000:
            return self._make_result(data={
                "action": "block",
                "reason": "message_too_long",
                "canned_response": (
                    "Whoa, that's a lot to take in at once. "
                    "Can you break that down for me? What's the key point?"
                ),
            })

        # Check 3: Prompt injection
        if self._check_prompt_injection(text):
            logger.warning(f"GuardrailAgent: prompt injection detected")
            return self._make_result(data={
                "action": "block",
                "reason": "prompt_injection",
                "canned_response": (
                    "I'm not sure I follow — can we get back to "
                    "what we were discussing?"
                ),
            })

        # Check 4: Character-breaking attempt
        if self._check_character_breaking(text):
            logger.info(f"GuardrailAgent: character-breaking attempt")
            return self._make_result(data={
                "action": "block",
                "reason": "character_breaking",
                "canned_response": (
                    "I'm not sure what you mean by that. "
                    "Anyway — where were we? You were telling me about your solution."
                ),
            })

        # Check 5: Inappropriate content
        if self._check_inappropriate(text):
            logger.warning(f"GuardrailAgent: inappropriate content detected")
            return self._make_result(data={
                "action": "block",
                "reason": "inappropriate",
                "canned_response": (
                    "Let's keep this professional. "
                    "I'm happy to continue if we can stay on topic."
                ),
            })

        # Check 6: Nonsense / keyboard mashing
        if self._check_nonsense(text):
            return self._make_result(data={
                "action": "block",
                "reason": "nonsense",
                "canned_response": (
                    "Sorry, I think we might have a bad connection. "
                    "Could you repeat that?"
                ),
            })

        # Check 7: Off-topic (soft — redirect, don't block)
        if self._check_off_topic(text):
            return self._make_result(data={
                "action": "redirect",
                "reason": "off_topic",
                "redirect_hint": (
                    "IMPORTANT: The salesperson just said something completely "
                    "off-topic and unrelated to the sales conversation. "
                    "As the customer, politely but firmly steer back to business. "
                    "For example: 'That's interesting, but can we get back to "
                    "what you were saying about the product?'"
                ),
            })

        # All checks passed
        return self._make_result(data={
            "action": "allow",
            "reason": "passed",
        })
